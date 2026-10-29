import httpx
from app.core import database
from tests.test_training import client, register, save, note, HEADERS, PASSWORD


def setup_team(client):
    users={}
    for name in ['gym_owner','gym_coach','gym_athlete']:
        register(client,name)
        users[name]={'id':client.get('/api/v1/training/me').json()['athlete']['id'],'cookies':httpx.Cookies(client.cookies)}
    switch(client,users,'gym_owner')
    response=client.post('/api/v1/gyms',json={'name':'Synthetic training gym'},headers=HEADERS)
    assert response.status_code==200,response.text
    return users,response.json()['gym']['id']


def switch(client,users,name):
    client.cookies.clear();client.cookies.update(users[name]['cookies'])


def invite(client,gym,handle,role='athlete'):
    response=client.post(f'/api/v1/gyms/{gym}/members',json={'handle':handle,'role':role},headers=HEADERS)
    assert response.status_code==200,response.text


def accept(client,gym):
    assert client.post(f'/api/v1/gyms/{gym}/accept',json={},headers=HEADERS).status_code==200


def share(client,gym,value=True):
    assert client.post(f'/api/v1/gyms/{gym}/sharing',json={'sharing':value},headers=HEADERS).status_code==200


def active_team(client):
    users,gym=setup_team(client)
    invite(client,gym,'gym_coach','coach');invite(client,gym,'gym_athlete')
    switch(client,users,'gym_coach');accept(client,gym)
    switch(client,users,'gym_athlete');accept(client,gym)
    return users,gym


def test_invitation_requires_acceptance_and_journal_sharing_is_opt_in(client):
    users,gym=setup_team(client)
    invite(client,gym,'gym_athlete')
    switch(client,users,'gym_athlete')
    assert client.get('/api/v1/gyms').json()['gyms'][0]['status']=='invited'
    assert client.get('/api/v1/gyms/'+gym).status_code==404
    accept(client,gym)
    own=save(client,note(title='Private training note'))
    save(client,note(title='Private opponent research',purpose='opponent'))
    target=users['gym_athlete']['id']
    switch(client,users,'gym_owner')
    assert client.get(f'/api/v1/gyms/{gym}/athletes/{target}/entries').status_code==403
    switch(client,users,'gym_athlete');share(client,gym)
    switch(client,users,'gym_owner')
    shared=client.get(f'/api/v1/gyms/{gym}/athletes/{target}/entries').json()['entries']
    assert [e['id'] for e in shared]==[own['id']]
    assert client.get('/api/v1/gyms/'+gym).json()['audit'][0]['action']=='review_access'
    switch(client,users,'gym_athlete')
    assert any(e['action']=='review_access' for e in client.get('/api/v1/gyms/'+gym).json()['audit'])


def test_gym_coach_comments_are_revoked_with_sharing_and_membership(client):
    users,gym=active_team(client);entry=save(client,note());share(client,gym)
    path=f"/api/v1/training/entries/{entry['id']}/comments"
    switch(client,users,'gym_coach')
    assert client.post(path,json={'body':'Controlled test comment'},headers=HEADERS).status_code==200
    switch(client,users,'gym_athlete');share(client,gym,False)
    switch(client,users,'gym_coach')
    assert client.get(path).status_code==404
    assert client.post(path,json={'body':'Must be denied'},headers=HEADERS).status_code==404
    switch(client,users,'gym_athlete');share(client,gym)
    switch(client,users,'gym_owner')
    client.delete(f"/api/v1/gyms/{gym}/members/{users['gym_coach']['id']}",headers=HEADERS)
    switch(client,users,'gym_coach')
    assert client.get(path).status_code==404


def test_only_owner_can_invite_and_only_recipient_can_record_plan_outcome(client):
    users,gym=active_team(client)
    switch(client,users,'gym_athlete')
    assert client.post(f'/api/v1/gyms/{gym}/members',json={'handle':'gym_owner','role':'coach'},headers=HEADERS).status_code==403
    payload={'recipient':users['gym_athlete']['id'],'title':'Controlled practice','discipline':'MMA','goal':'Stable reset',
             'practice':'Rehearse slowly with your coach.','success_check':'Return to stance.','review_date':'2026-10-25'}
    assert client.post(f'/api/v1/gyms/{gym}/plans',json=payload,headers=HEADERS).status_code==403
    switch(client,users,'gym_coach')
    response=client.post(f'/api/v1/gyms/{gym}/plans',json=payload,headers=HEADERS)
    assert response.status_code==200,response.text
    plan=response.json()['plan'];path=f"/api/v1/gyms/{gym}/plans/{plan['id']}/feedback"
    assert client.post(path,json={'status':'completed'},headers=HEADERS).status_code==404
    switch(client,users,'gym_athlete')
    assert client.post(path,json={'status':'completed','notes':'Synthetic completion'},headers=HEADERS).status_code==200
    assert client.get('/api/v1/training/export').json()['gym_collaboration']['plans'][0]['status']=='completed'
    assert client.get('/api/v1/gyms/'+gym).json()['plans'][0]['notes']=='Synthetic completion'
    delete_path=f"/api/v1/gyms/{gym}/plans/{plan['id']}"
    assert client.delete(delete_path,headers=HEADERS).status_code==403
    switch(client,users,'gym_coach')
    assert client.delete(delete_path,headers=HEADERS).status_code==200
    assert client.get('/api/v1/gyms/'+gym).json()['plans']==[]


def test_plan_cannot_link_private_research_and_deleted_source_link_is_removed(client):
    users,gym=active_team(client);entry=save(client,note());private=save(client,note(purpose='opponent'));share(client,gym)
    switch(client,users,'gym_coach')
    payload={'recipient':users['gym_athlete']['id'],'title':'Evidence plan','discipline':'MMA','goal':'Stable reset','practice':'Slow rehearsal.',
             'success_check':'A controlled exit.','review_date':'2026-10-25','entry_id':private['id']}
    assert client.post(f'/api/v1/gyms/{gym}/plans',json=payload,headers=HEADERS).status_code==403
    payload['entry_id']=entry['id']
    assert client.post(f'/api/v1/gyms/{gym}/plans',json=payload,headers=HEADERS).status_code==200
    switch(client,users,'gym_athlete');client.delete('/api/v1/training/entries/'+entry['id'],headers=HEADERS)
    assert client.get('/api/v1/gyms/'+gym).json()['plans'][0]['entry_id']==''


def test_leaving_revokes_exported_plan_access_and_owner_deletion_cascades(client):
    users,gym=active_team(client)
    switch(client,users,'gym_coach')
    payload={'recipient':users['gym_athlete']['id'],'title':'Private plan','discipline':'MMA','goal':'Reset','practice':'Slow rehearsal.',
             'success_check':'Balance.','review_date':'2026-10-25'}
    assert client.post(f'/api/v1/gyms/{gym}/plans',json=payload,headers=HEADERS).status_code==200
    assert len(client.get('/api/v1/training/export').json()['gym_collaboration']['plans'])==1
    assert client.delete(f"/api/v1/gyms/{gym}/members/{users['gym_coach']['id']}",headers=HEADERS).status_code==200
    assert client.get('/api/v1/training/export').json()['gym_collaboration']['plans']==[]
    switch(client,users,'gym_owner')
    assert client.delete(f"/api/v1/gyms/{gym}/members/{users['gym_owner']['id']}",headers=HEADERS).status_code==409
    assert client.post('/api/v1/training/delete-account',json={'password':PASSWORD,'confirmation':'DELETE'},headers=HEADERS).status_code==200
    with database.transaction() as db:
        for table in ['gyms','gym_members','gym_plans','gym_audit']:
            assert db.execute('SELECT COUNT(*) FROM '+table).fetchone()[0]==0


def test_owner_deletion_preserves_other_gym_audit_with_anonymous_actor(client):
    users,gym=active_team(client)
    switch(client,users,'gym_coach')
    other=client.post('/api/v1/gyms',json={'name':'Surviving gym'},headers=HEADERS).json()['gym']['id']
    invite(client,other,'gym_owner','coach')
    switch(client,users,'gym_owner');accept(client,other)
    assert client.post('/api/v1/training/delete-account',json={'password':PASSWORD,'confirmation':'DELETE'},headers=HEADERS).status_code==200
    switch(client,users,'gym_coach')
    assert client.get('/api/v1/gyms/'+gym).status_code==404
    assert client.get('/api/v1/gyms/'+other).status_code==200
    with database.transaction() as db:
        assert not db.execute('SELECT id FROM gym_audit WHERE gym=?',(gym,)).fetchone()
        assert db.execute('SELECT id FROM gym_audit WHERE gym=? AND actor IS NULL',(other,)).fetchone()
