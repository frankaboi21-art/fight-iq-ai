"""Attributed human judgments, scoped to evidence and gym-checked qualifications.

No role, AI response, or athlete confirmation is treated as a coaching credential.
"""
from datetime import date
import json
import secrets
import time
from typing import Literal

from fastapi import APIRouter, HTTPException, Request
from pydantic import Field, model_validator

from app.core import database
from app.core.security import require_same_origin
from app.services.training import Strict, DISCIPLINES, account, comment_access, canonical, digest
from app.services.gyms import membership, lock_gym, owner_only, staff, audit

router=APIRouter(prefix="/api/v1/validation")


class Credential(Strict):
    coach_id: str = Field(min_length=1,max_length=40)
    discipline: DISCIPLINES
    qualification: str = Field(min_length=3,max_length=300)
    verification_reference: str = Field(min_length=3,max_length=400)
    expires_on: date
    checked_evidence: Literal[True]


class Decision(Strict):
    source_fingerprint: str = Field(min_length=64,max_length=64)
    gym_id: str = Field(min_length=1,max_length=40)
    item_kind: Literal["moment","drill"]
    item_index: int = Field(ge=0,le=30)
    verdict: Literal["supported","corrected","rejected","uncertain"]
    evidence: str = Field(min_length=3,max_length=1000)
    explanation: str = Field(min_length=3,max_length=1000)
    correction: str = Field(default="",max_length=1000)
    success_check: str = Field(default="",max_length=500)
    source_reviewed: Literal[True]

    @model_validator(mode="after")
    def correction_required(self):
        if self.verdict=="corrected" and (len(self.correction)<3 or len(self.success_check)<3):
            raise ValueError("A correction needs controlled practice instructions and a visible success check")
        return self


def fingerprint(entry):
    return digest(json.dumps(canonical({k:entry[k] for k in ["report","discipline","purpose","feedback"]}),sort_keys=True,separators=(",",":")))


def qualification(db,gym,coach,discipline):
    row=db.execute("SELECT data,active FROM coach_credentials WHERE gym=? AND coach=? AND discipline=?",(gym,coach,discipline)).fetchone()
    if not row or not row[1]: return None
    value=json.loads(row[0])
    if value['expires_on']<date.today().isoformat(): return None
    member=db.execute("SELECT role,status FROM gym_members WHERE gym=? AND athlete=?",(gym,coach)).fetchone()
    return value if member and member[0] in {'owner','coach'} and member[1]=='active' else None


@router.get("/gyms/{gym}/credentials")
def credentials(gym:str,request:Request):
    with database.transaction() as db:
        actor=account(request,db)['id'];membership(db,gym,actor)
        rows=db.execute("SELECT c.coach,c.discipline,c.data,c.active,a.handle FROM coach_credentials c JOIN athletes a ON a.id=c.coach WHERE c.gym=?",(gym,)).fetchall()
        return {"credentials":[{**json.loads(r[2]),'coach_id':r[0],'discipline':r[1],'active':bool(r[3]),'current':bool(qualification(db,gym,r[0],r[1])),'handle':r[4]} for r in rows]}


@router.post("/gyms/{gym}/credentials")
def verify(gym:str,payload:Credential,request:Request):
    require_same_origin(request)
    with database.transaction() as db:
        actor=account(request,db);lock_gym(db,gym);owner_only(membership(db,gym,actor['id']),actor['id'])
        if payload.coach_id==actor['id']:
            raise HTTPException(422,"A gym owner cannot verify their own qualifications.")
        staff(membership(db,gym,payload.coach_id))
        if payload.expires_on<date.today(): raise HTTPException(422,"Choose a current qualification expiry or review date.")
        record={**payload.model_dump(mode='json'),'id':secrets.token_hex(16),'verified_by':actor['handle'],'verified_on':time.time(),
                'scope':'Qualification evidence checked by this gym owner; not independently certified by Fight IQ.'}
        db.execute("INSERT INTO coach_credentials VALUES (?,?,?,?,1) ON CONFLICT(gym,coach,discipline) DO UPDATE SET data=excluded.data,active=1",(gym,payload.coach_id,payload.discipline,json.dumps(record)))
        audit(db,gym,actor['id'],'qualification_verified',payload.coach_id)
    return {'credential':record}


@router.delete("/gyms/{gym}/credentials/{coach}/{discipline}")
def revoke(gym:str,coach:str,discipline:str,request:Request):
    require_same_origin(request)
    with database.transaction() as db:
        actor=account(request,db)['id'];lock_gym(db,gym);owner_only(membership(db,gym,actor),actor)
        db.execute("UPDATE coach_credentials SET active=0 WHERE gym=? AND coach=? AND discipline=?",(gym,coach,discipline))
        audit(db,gym,actor,'qualification_revoked',coach if db.execute('SELECT id FROM athletes WHERE id=?',(coach,)).fetchone() else None)
    return {'revoked':True}


def records(db,entry,rows=None,credential_cache=None):
    if rows is None: rows=db.execute("SELECT data,reviewer FROM coach_validations WHERE entry=? ORDER BY created DESC,id DESC",(entry['id'],)).fetchall()
    if credential_cache is None: credential_cache={}
    result=[];seen=set()
    for row in rows:
        value=json.loads(row[0]);key=(row[1],value['item_kind'],value['item_index'])
        latest=key not in seen;seen.add(key)
        credential_key=(value['gym_id'],row[1],entry['discipline'])
        if credential_key not in credential_cache: credential_cache[credential_key]=qualification(db,*credential_key)
        credential=credential_cache[credential_key]
        source_current=latest and value['fingerprint']==fingerprint(entry)
        current=source_current and bool(credential) and credential['id']==value['credential']['id']
        value.update(current=current,source_current=source_current,status='Current coach review' if current else 'Historical / source or qualification changed')
        result.append(value)
    return result


def archive(db,owner,entries):
    grouped={};cache={}
    for row in db.execute("SELECT v.entry,v.data,v.reviewer FROM coach_validations v JOIN training_entries e ON e.id=v.entry WHERE e.athlete=? ORDER BY v.created DESC,v.id DESC",(owner,)).fetchall():
        grouped.setdefault(row[0],[]).append((row[1],row[2]))
    return {entry['id']:records(db,entry,grouped.get(entry['id'],[]),cache) for entry in entries}


def task_decision(reviews,index):
    objections=[v for v in reviews if v['source_current'] and v['item_kind']=='drill' and v['item_index']==index and v['verdict']!='supported']
    if objections: return {'status':'needs_coach_resolution','reviews':objections}
    current=[v for v in reviews if v['current'] and v['item_kind']=='drill' and v['item_index']==index]
    if not current: return {'status':'unreviewed'}
    if any(v['verdict']!='supported' for v in current):
        return {'status':'needs_coach_resolution','reviews':current}
    return {'status':'coach_supported','reviews':current}


@router.get("/entries/{entry_id}")
def detail(entry_id:str,request:Request):
    with database.transaction() as db:
        actor=comment_access(request,db,entry_id)
        row=db.execute('SELECT athlete,data FROM training_entries WHERE id=?',(entry_id,)).fetchone();entry=json.loads(row[1])
        choices=[]
        if row[0]!=actor['id'] and entry['purpose']=='self':
            for r in db.execute("SELECT c.gym,g.name FROM coach_credentials c JOIN gyms g ON g.id=c.gym JOIN gym_members a ON a.gym=c.gym WHERE c.coach=? AND c.discipline=? AND a.athlete=? AND a.status='active' AND a.sharing=1",(actor['id'],entry['discipline'],row[0])).fetchall():
                if qualification(db,r[0],actor['id'],entry['discipline']): choices.append({'id':r[0],'name':r[1]})
        return {'reviews':records(db,entry),'review_gyms':choices,'source_fingerprint':fingerprint(entry)}


@router.post("/entries/{entry_id}")
def review(entry_id:str,payload:Decision,request:Request):
    require_same_origin(request)
    with database.transaction() as db:
        actor=comment_access(request,db,entry_id)
        row=db.execute('SELECT athlete,data FROM training_entries WHERE id=?',(entry_id,)).fetchone();entry=json.loads(row[1])
        if actor['id']==row[0]: raise HTTPException(403,"Self-review cannot be labelled coach validation.")
        lock_gym(db,payload.gym_id);staff(membership(db,payload.gym_id,actor['id']))
        target=membership(db,payload.gym_id,row[0])
        credential=qualification(db,payload.gym_id,actor['id'],entry['discipline'])
        if not target['sharing'] or not credential or entry['purpose']!='self':
            raise HTTPException(403,"A current discipline qualification and shared gym review are required.")
        if entry['feedback']['verdict']!='confirmed': raise HTTPException(409,"Ask the athlete to check and confirm this source first.")
        if payload.source_fingerprint!=fingerprint(entry): raise HTTPException(409,"This source changed. Reopen it before reviewing.")
        items=entry['report'].get('moments',[]) if payload.item_kind=='moment' else entry['tasks']
        if payload.item_index>=len(items): raise HTTPException(422,"Choose an existing finding or drill.")
        if db.execute('SELECT COUNT(*) FROM coach_validations WHERE entry=?',(entry_id,)).fetchone()[0]>=100:
            raise HTTPException(409,"This source has reached 100 human review records.")
        value={**payload.model_dump(),'id':secrets.token_hex(16),'reviewer':actor['handle'],'created':time.time(),
               'fingerprint':fingerprint(entry),'credential':credential,'source_item':items[payload.item_index],
               'scope':'Human judgment on this item only; not a validated athlete score or platform accuracy claim.'}
        db.execute('INSERT INTO coach_validations VALUES (?,?,?,?,?)',(value['id'],entry_id,actor['id'],json.dumps(value),value['created']))
        audit(db,payload.gym_id,actor['id'],'evidence_'+payload.verdict,row[0])
    return {'review':value}
