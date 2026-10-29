from datetime import date,timedelta

from app.core import database
from app.services import training
from tests.test_training import client, save, reviewed_payload, confirm, HEADERS
from tests.test_gyms import active_team,switch,share


def prepare(client):
    users,gym=active_team(client)
    entry=save(client,reviewed_payload());confirm(client,entry);share(client,gym)
    return users,gym,entry


def verify(client,users,gym,discipline='MMA'):
    switch(client,users,'gym_owner')
    payload={'coach_id':users['gym_coach']['id'],'discipline':discipline,'qualification':'Synthetic test qualification',
             'verification_reference':'Fixture only; no actual credential','expires_on':(date.today()+timedelta(days=30)).isoformat(),'checked_evidence':True}
    result=client.post(f'/api/v1/validation/gyms/{gym}/credentials',json=payload,headers=HEADERS)
    assert result.status_code==200,result.text
    return payload


def decision(client,gym,entry,**changes):
    result=client.get('/api/v1/validation/entries/'+entry['id'])
    assert result.status_code==200,result.text
    return {'gym_id':gym,'item_kind':'drill','item_index':0,'verdict':'supported','evidence':'Synthetic evidence check.',
            'explanation':'Controlled fixture only.','source_reviewed':True,'source_fingerprint':result.json()['source_fingerprint'],**changes}


def submit(client,entry,payload):
    return client.post('/api/v1/validation/entries/'+entry['id'],json=payload,headers=HEADERS)


def test_only_owner_can_check_another_active_coachs_qualification(client):
    users,gym,entry=prepare(client)
    payload=verify(client,users,gym)
    payload['coach_id']=users['gym_owner']['id']
    assert client.post(f'/api/v1/validation/gyms/{gym}/credentials',json=payload,headers=HEADERS).status_code==422
    switch(client,users,'gym_coach');payload['coach_id']=users['gym_coach']['id']
    assert client.post(f'/api/v1/validation/gyms/{gym}/credentials',json=payload,headers=HEADERS).status_code==403
    switch(client,users,'gym_owner');payload['checked_evidence']=False
    assert client.post(f'/api/v1/validation/gyms/{gym}/credentials',json=payload,headers=HEADERS).status_code==422


def test_qualification_discipline_and_source_attestation_are_required(client):
    users,gym,entry=prepare(client);switch(client,users,'gym_coach')
    payload=decision(client,gym,entry)
    assert submit(client,entry,payload).status_code==403
    verify(client,users,gym,'Boxing');switch(client,users,'gym_coach')
    assert submit(client,entry,payload).status_code==403
    verify(client,users,gym);switch(client,users,'gym_coach')
    assert submit(client,entry,{**payload,'source_reviewed':False}).status_code==422
    assert submit(client,entry,{**payload,'item_index':20}).status_code==422
    assert submit(client,entry,payload).status_code==200
    switch(client,users,'gym_athlete')
    assert submit(client,entry,payload).status_code==403


def test_current_supported_drills_can_gate_weekly_plan_and_export(client):
    users,gym,entry=prepare(client)
    assert client.post('/api/v1/training/profile',json={'coaching_policy':'coach_supported_only'},headers=HEADERS).status_code==200
    assert client.get('/api/v1/training/development').json()['tasks']==[]
    verify(client,users,gym);switch(client,users,'gym_coach')
    assert submit(client,entry,decision(client,gym,entry)).status_code==200
    switch(client,users,'gym_athlete')
    plan=client.get('/api/v1/training/development').json()
    assert plan['tasks'][0]['coach_review']['status']=='coach_supported'
    exported=client.get('/api/v1/training/export').json()
    assert exported['human_reviews'][entry['id']][0]['reviewer']=='gym_coach'
    assert exported['human_reviews'][entry['id']][0]['credential']['verified_by']=='gym_owner'


def test_correction_holds_original_advice_and_retains_version_history(client):
    users,gym,entry=prepare(client);verify(client,users,gym);switch(client,users,'gym_coach')
    assert submit(client,entry,decision(client,gym,entry)).status_code==200
    payload=decision(client,gym,entry,verdict='corrected')
    assert submit(client,entry,payload).status_code==422
    payload.update(correction='Use the coach-adjusted controlled setup.',success_check='Visible balance before movement.')
    assert submit(client,entry,payload).status_code==200
    switch(client,users,'gym_athlete');result=client.get('/api/v1/training/development').json()
    assert result['tasks']==[] and result['deferred_tasks'][0]['coach_review']['status']=='needs_coach_resolution'
    original=client.get('/api/v1/training/entries').json()['entries'][0]
    assert original['report']==entry['report']
    reviews=client.get('/api/v1/validation/entries/'+entry['id']).json()['reviews']
    assert len(reviews)==2 and sum(r['current'] for r in reviews)==1
    # Removing qualification cannot silently reactivate advice that was rejected/corrected.
    switch(client,users,'gym_owner')
    client.delete(f"/api/v1/validation/gyms/{gym}/credentials/{users['gym_coach']['id']}/MMA",headers=HEADERS)
    switch(client,users,'gym_athlete');assert client.get('/api/v1/training/development').json()['tasks']==[]


def test_feedback_changes_expire_reviews_and_stale_forms_cannot_validate(client):
    users,gym,entry=prepare(client);verify(client,users,gym);switch(client,users,'gym_coach')
    old=decision(client,gym,entry);assert submit(client,entry,old).status_code==200
    switch(client,users,'gym_athlete')
    client.post(f"/api/v1/training/entries/{entry['id']}/feedback",json={'verdict':'confirmed','correction':'Changed the source context.'},headers=HEADERS)
    assert not client.get('/api/v1/validation/entries/'+entry['id']).json()['reviews'][0]['current']
    switch(client,users,'gym_coach');assert submit(client,entry,old).status_code==409


def test_sharing_revocation_and_membership_removal_revoke_validation_access(client):
    users,gym,entry=prepare(client);verify(client,users,gym);switch(client,users,'gym_coach')
    payload=decision(client,gym,entry);assert submit(client,entry,payload).status_code==200
    switch(client,users,'gym_athlete');share(client,gym,False)
    switch(client,users,'gym_coach')
    assert submit(client,entry,payload).status_code==404
    assert client.get('/api/v1/validation/entries/'+entry['id']).status_code==404
    switch(client,users,'gym_owner')
    client.delete(f"/api/v1/gyms/{gym}/members/{users['gym_coach']['id']}",headers=HEADERS)
    switch(client,users,'gym_athlete')
    assert not client.get('/api/v1/validation/entries/'+entry['id']).json()['reviews'][0]['current']
    client.delete('/api/v1/training/entries/'+entry['id'],headers=HEADERS)
    with database.transaction() as db:
        assert db.execute('SELECT COUNT(*) FROM coach_validations').fetchone()[0]==0
