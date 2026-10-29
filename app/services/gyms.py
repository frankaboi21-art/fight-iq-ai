"""Gym memberships, athlete-controlled review access, shared plans and access audit."""
from datetime import date
import json
import secrets
import time
from typing import Literal

from fastapi import APIRouter, HTTPException, Request
from pydantic import Field

from app.core import database
from app.core.security import require_same_origin
from app.services.training import Strict, account, owned_entry, load_entries

router = APIRouter(prefix="/api/v1/gyms")


class GymInput(Strict):
    name: str = Field(min_length=2, max_length=80)


class Invite(Strict):
    handle: str = Field(min_length=3, max_length=32, pattern=r"^[A-Za-z0-9_]+$")
    role: Literal["coach", "athlete"]


class Share(Strict):
    sharing: bool


class SharedPlan(Strict):
    recipient: str = Field(min_length=1, max_length=40)
    title: str = Field(min_length=1, max_length=100)
    discipline: str = Field(min_length=1, max_length=40)
    goal: str = Field(min_length=1, max_length=600)
    practice: str = Field(min_length=1, max_length=2000)
    success_check: str = Field(min_length=1, max_length=500)
    review_date: date
    entry_id: str = Field(default="", max_length=40)


class PlanFeedback(Strict):
    status: Literal["accepted", "completed", "needs_revision"]
    notes: str = Field(default="", max_length=1000)


def audit(db, gym, actor, action, subject=None):
    if action == 'review_access' and db.execute("SELECT id FROM gym_audit WHERE gym=? AND actor=? AND subject=? AND action=? AND created>?", (gym,actor,subject,action,time.time()-60)).fetchone():
        return
    db.execute("INSERT INTO gym_audit VALUES (?,?,?,?,?,?)", (secrets.token_hex(16), gym, actor, subject, action, time.time()))


def membership(db, gym, actor, active=True):
    row = db.execute("SELECT g.name,g.owner,m.role,m.status,m.sharing FROM gyms g JOIN gym_members m ON m.gym=g.id WHERE g.id=? AND m.athlete=?", (gym, actor)).fetchone()
    if not row or (active and row[3] != "active"):
        raise HTTPException(404, "Gym not found or membership is not active.")
    return {"id": gym, "name": row[0], "owner": row[1], "role": row[2], "status": row[3], "sharing": bool(row[4])}


def lock_gym(db, gym):
    suffix = " FOR UPDATE" if db.postgres else ""
    if not db.execute("SELECT id FROM gyms WHERE id=?"+suffix, (gym,)).fetchone():
        raise HTTPException(404, "Gym not found.")


def staff(member):
    if member["role"] not in {"owner", "coach"}:
        raise HTTPException(403, "Only this gym's active coaching staff can do that.")


def owner_only(member, actor):
    if member["owner"] != actor:
        raise HTTPException(403, "Only the gym owner can manage memberships.")


def gym_access(db, coach, athlete):
    # Serialize this permission check with sharing changes and membership removal.
    candidates = db.execute("SELECT c.gym FROM gym_members c JOIN gym_members a ON a.gym=c.gym WHERE c.athlete=? AND a.athlete=? ORDER BY c.gym", (coach, athlete)).fetchall()
    for row in candidates:
        lock_gym(db, row[0])
    return bool(db.execute("SELECT c.gym FROM gym_members c JOIN gym_members a ON a.gym=c.gym WHERE c.athlete=? AND c.status='active' AND c.role IN ('owner','coach') AND a.athlete=? AND a.status='active' AND a.sharing=1", (coach, athlete)).fetchone())


def access_audit(db, coach, athlete):
    for row in db.execute("SELECT c.gym FROM gym_members c JOIN gym_members a ON a.gym=c.gym WHERE c.athlete=? AND c.status='active' AND c.role IN ('owner','coach') AND a.athlete=? AND a.status='active' AND a.sharing=1", (coach, athlete)).fetchall():
        audit(db, row[0], coach, "review_access", athlete)


def archive(db, actor):
    memberships = [{"gym_id":r[0], "name":r[1], "role":r[2], "status":r[3], "sharing":bool(r[4])} for r in db.execute("SELECT g.id,g.name,m.role,m.status,m.sharing FROM gyms g JOIN gym_members m ON m.gym=g.id WHERE m.athlete=?", (actor,)).fetchall()]
    plans = [json.loads(r[0]) for r in db.execute("SELECT p.data FROM gym_plans p WHERE p.recipient=? OR (p.author=? AND EXISTS (SELECT 1 FROM gym_members m WHERE m.gym=p.gym AND m.athlete=? AND m.status='active' AND m.role IN ('owner','coach')))", (actor, actor, actor)).fetchall()]
    return {"memberships":memberships,"plans":plans}


@router.get("")
def listing(request: Request):
    with database.transaction() as db:
        actor = account(request, db)["id"]
        rows = db.execute("SELECT gym FROM gym_members WHERE athlete=?", (actor,)).fetchall()
        return {"gyms":[membership(db,r[0],actor,False) for r in rows]}


@router.post("")
def create(payload: GymInput, request: Request):
    require_same_origin(request)
    with database.transaction() as db:
        actor = account(request, db)["id"]
        db.lock_owner(actor)
        if db.execute("SELECT COUNT(*) FROM gyms WHERE owner=?", (actor,)).fetchone()[0] >= 5:
            raise HTTPException(409, "You can own up to five gyms.")
        gym = secrets.token_hex(16)
        db.execute("INSERT INTO gyms VALUES (?,?,?,?)", (gym,actor,payload.name,time.time()))
        db.execute("INSERT INTO gym_members VALUES (?,?,?,?,?)", (gym,actor,"owner","active",0))
        audit(db,gym,actor,"gym_created")
        return {"gym":membership(db,gym,actor)}


@router.get("/{gym}")
def detail(gym: str, request: Request):
    with database.transaction() as db:
        actor=account(request,db)["id"]
        member=membership(db,gym,actor)
        members=[{"id":r[0],"handle":r[1],"role":r[2],"status":r[3],"sharing":bool(r[4])} for r in db.execute("SELECT a.id,a.handle,m.role,m.status,m.sharing FROM gym_members m JOIN athletes a ON a.id=m.athlete WHERE m.gym=? ORDER BY a.handle", (gym,)).fetchall()]
        query="SELECT p.data,a.handle,p.author FROM gym_plans p LEFT JOIN athletes a ON a.id=p.author WHERE p.gym=?"
        args=[gym]
        if member["role"]=="athlete":
            query+=" AND p.recipient=?";args.append(actor)
        plans=[{**json.loads(r[0]),"author_handle":r[1] or "Deleted account","author_id":r[2]} for r in db.execute(query+" ORDER BY p.created DESC",args).fetchall()]
        events=[]
        audit_query="SELECT a.handle,s.handle,e.action,e.created FROM gym_audit e LEFT JOIN athletes a ON a.id=e.actor LEFT JOIN athletes s ON s.id=e.subject WHERE e.gym=?"
        audit_args=[gym]
        if member["role"]!="owner":
            audit_query+=" AND (e.actor=? OR e.subject=?)";audit_args.extend([actor,actor])
        events=[{"actor":r[0] or "Deleted account","subject":r[1],"action":r[2],"created":r[3]} for r in db.execute(audit_query+" ORDER BY e.created DESC LIMIT 100",audit_args).fetchall()]
        return {"gym":member,"members":members,"plans":plans,"audit":events}


@router.post("/{gym}/members")
def invite(gym: str, payload: Invite, request: Request):
    require_same_origin(request)
    with database.transaction() as db:
        actor=account(request,db)["id"];lock_gym(db,gym)
        owner_only(membership(db,gym,actor),actor)
        target=db.execute("SELECT id FROM athletes WHERE handle=?",(payload.handle.lower(),)).fetchone()
        if not target or target[0]==actor:
            raise HTTPException(422,"Choose another existing username.")
        if db.execute("SELECT athlete FROM gym_members WHERE gym=? AND athlete=?",(gym,target[0])).fetchone():
            raise HTTPException(409,"This account already has a membership or invitation. Remove it before inviting it with a different role.")
        if db.execute("SELECT COUNT(*) FROM gym_members WHERE gym=?",(gym,)).fetchone()[0]>=100:
            raise HTTPException(409,"This gym has reached 100 members and invitations.")
        db.execute("INSERT INTO gym_members VALUES (?,?,?,?,?)",(gym,target[0],payload.role,'invited',0))
        audit(db,gym,actor,'invited_'+payload.role,target[0])
    return {"invited":True}


@router.post("/{gym}/accept")
def accept(gym: str,request: Request):
    require_same_origin(request)
    with database.transaction() as db:
        actor=account(request,db)["id"];lock_gym(db,gym)
        member=membership(db,gym,actor,False)
        if member["status"]!='invited':
            raise HTTPException(409,"This membership is already active.")
        db.execute("UPDATE gym_members SET status='active',sharing=0 WHERE gym=? AND athlete=?",(gym,actor))
        audit(db,gym,actor,'invitation_accepted')
    return {"accepted":True}


@router.post("/{gym}/sharing")
def share(gym: str,payload: Share,request: Request):
    require_same_origin(request)
    with database.transaction() as db:
        actor=account(request,db)["id"];lock_gym(db,gym);membership(db,gym,actor)
        db.execute("UPDATE gym_members SET sharing=? WHERE gym=? AND athlete=?",(int(payload.sharing),gym,actor))
        audit(db,gym,actor,'sharing_enabled' if payload.sharing else 'sharing_revoked')
    return {"sharing":payload.sharing}


@router.delete("/{gym}/members/{target}")
def leave(gym: str,target: str,request: Request):
    require_same_origin(request)
    with database.transaction() as db:
        actor=account(request,db)["id"];lock_gym(db,gym);member=membership(db,gym,actor,False)
        if actor!=target:
            owner_only(member,actor)
        if target==member['owner']:
            raise HTTPException(409,"The owner must delete the gym to leave it.")
        db.execute("DELETE FROM gym_members WHERE gym=? AND athlete=?",(gym,target))
        db.execute("DELETE FROM gym_plans WHERE gym=? AND recipient=?",(gym,target))
        audit(db,gym,actor,'membership_removed',target if db.execute('SELECT id FROM athletes WHERE id=?',(target,)).fetchone() else None)
    return {"removed":True}


@router.delete("/{gym}")
def delete(gym: str,request: Request):
    require_same_origin(request)
    with database.transaction() as db:
        actor=account(request,db)["id"];lock_gym(db,gym);owner_only(membership(db,gym,actor),actor)
        db.execute("DELETE FROM gyms WHERE id=?",(gym,))
    return {"deleted":True}


@router.get("/{gym}/athletes/{target}/entries")
def reviews(gym: str,target: str,request: Request):
    with database.transaction() as db:
        actor=account(request,db)["id"];lock_gym(db,gym);staff(membership(db,gym,actor))
        target_member=membership(db,gym,target)
        if not target_member['sharing']:
            raise HTTPException(403,"This athlete has not shared their training with this gym.")
        audit(db,gym,actor,'review_access',target)
        return {"entries":[e for e in load_entries(db,target) if e['purpose']=='self']}


@router.post("/{gym}/plans")
def plan(gym: str,payload: SharedPlan,request: Request):
    require_same_origin(request)
    with database.transaction() as db:
        actor=account(request,db)["id"];lock_gym(db,gym);staff(membership(db,gym,actor))
        recipient=membership(db,gym,payload.recipient)
        if payload.entry_id:
            if not recipient['sharing']:
                raise HTTPException(403,"The recipient must share training before linking review evidence.")
            entry=owned_entry(db,payload.recipient,payload.entry_id)
            if entry['purpose']!='self':
                raise HTTPException(403,"Research records cannot be linked to gym plans.")
        if db.execute("SELECT COUNT(*) FROM gym_plans WHERE gym=?",(gym,)).fetchone()[0]>=500:
            raise HTTPException(409,"This gym has reached 500 saved plans.")
        record={**payload.model_dump(mode='json'),"id":secrets.token_hex(16),"gym":gym,"status":"assigned","notes":"","created":time.time()}
        db.execute("INSERT INTO gym_plans VALUES (?,?,?,?,?,?)",(record['id'],gym,payload.recipient,actor,json.dumps(record),record['created']))
        audit(db,gym,actor,'plan_assigned',payload.recipient)
    return {"plan":record}


@router.post("/{gym}/plans/{plan_id}/feedback")
def outcome(gym: str,plan_id: str,payload: PlanFeedback,request: Request):
    require_same_origin(request)
    with database.transaction() as db:
        actor=account(request,db)["id"];lock_gym(db,gym);membership(db,gym,actor)
        row=db.execute("SELECT data FROM gym_plans WHERE id=? AND gym=? AND recipient=?",(plan_id,gym,actor)).fetchone()
        if not row:
            raise HTTPException(404,"Assigned plan not found.")
        record=json.loads(row[0]);record.update(payload.model_dump())
        db.execute("UPDATE gym_plans SET data=? WHERE id=?",(json.dumps(record),plan_id))
        audit(db,gym,actor,'plan_'+payload.status)
    return {"plan":record}


@router.delete("/{gym}/plans/{plan_id}")
def delete_plan(gym: str,plan_id: str,request: Request):
    require_same_origin(request)
    with database.transaction() as db:
        actor=account(request,db)["id"];lock_gym(db,gym);member=membership(db,gym,actor);staff(member)
        row=db.execute("SELECT author,recipient FROM gym_plans WHERE id=? AND gym=?",(plan_id,gym)).fetchone()
        if not row or (member['role']!='owner' and row[0]!=actor):
            raise HTTPException(404,"Plan not found or not managed by you.")
        db.execute("DELETE FROM gym_plans WHERE id=? AND gym=?",(plan_id,gym))
        audit(db,gym,actor,'plan_deleted',row[1])
    return {"deleted":True}
