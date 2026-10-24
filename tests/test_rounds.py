import base64
import io
import json
import time
import pytest

from PIL import Image

from app.core import database
from app.services import round_review as rounds
from tests.test_training import client, register, HEADERS, PASSWORD, note


@pytest.fixture(autouse=True)
def synthetic_provider(monkeypatch):
    monkeypatch.setattr(rounds.get_settings(), 'openai_api_key', 'synthetic-test-only')


def create(client, **changes):
    payload = dict(discipline="MMA", experience="Beginner", athlete="Blue shirt on left", goal="Balance",
                   start=0, end=11, source_name="synthetic.mp4", source_digest="a"*64, consent=True)
    response = client.post('/api/v1/rounds', json={**payload, **changes}, headers=HEADERS)
    assert response.status_code == 200, response.text
    return response.json()


def section(job, index=0, **changes):
    frame = io.BytesIO()
    Image.new('RGB', (64, 64), 'gray').save(frame, format='JPEG')
    image = 'data:image/jpeg;base64,'+base64.b64encode(frame.getvalue()).decode()
    span = job['windows'][index]
    frames = [{'timestamp': round(span['start']+i/5, 3), 'image': image} for i in range(min(50, int((span['end']-span['start'])*5+.001)))]
    return {**{k:job['context'][k] for k in ('discipline','experience','athlete','goal')}, **span, 'consent':True, 'frames':frames, **changes}


def send(client, job, index=0, **changes):
    return client.post(f"/api/v1/rounds/{job['id']}/sections/{index}", json=section(job,index,**changes), headers=HEADERS)


async def abstain(payload):
    return {'visibility':'unusable', 'athlete_match':'uncertain', 'summary':'Synthetic pattern', 'limitations':['No athlete visible.'],
            'moments':[], 'priority':'Use clearer footage.', 'additions':[], 'practice':[], 'next_session_check':'Use permissioned footage.',
            'coverage':{'start':payload.start,'end':payload.end,'frames':len(payload.frames),'sample_fps':5}}


def test_round_pipeline_persists_text_without_frames_and_saves_signed_index(client, monkeypatch):
    monkeypatch.setattr(rounds, 'generate_footage_review', abstain)
    register(client)
    job = create(client)
    assert len(job['windows']) == 2
    for i in range(2):
        assert send(client,job,i).status_code == 202
    result = client.get('/api/v1/rounds/'+job['id']).json()
    assert result['status'] == 'complete' and result['completed_sections'] == 2
    assert result['report']['coverage']['frames'] == 54
    assert result['report']['moments'] == result['report']['practice'] == []
    assert 'lease' not in result
    with database.transaction() as db:
        stored = db.execute('SELECT data FROM round_jobs WHERE id=?',(job['id'],)).fetchone()[0]
        assert 'data:image' not in stored and 'base64' not in stored
    payload = note(kind='footage', report=result['report'], receipt=result['receipt'])
    assert client.post('/api/v1/training/entries', json=payload, headers=HEADERS).status_code == 200
    archive = client.get('/api/v1/training/export').json()
    assert archive['temporary_round_reviews'][0]['id'] == job['id']
    assert 'lease' not in archive['temporary_round_reviews'][0]


def test_round_access_context_and_order_are_enforced(client, monkeypatch):
    monkeypatch.setattr(rounds,'generate_footage_review',abstain)
    register(client)
    job = create(client)
    assert send(client,job,1).status_code == 409
    assert send(client,job,athlete='Someone else').status_code == 422
    assert client.post('/api/v1/rounds',json=job['context'],headers=HEADERS).status_code == 422
    assert client.post('/api/v1/rounds/'+job['id']+'/cancel',json={}).status_code == 403
    client.post('/api/v1/training/logout',json={},headers=HEADERS)
    register(client,'another_athlete')
    assert client.get('/api/v1/rounds/'+job['id']).status_code == 404
    assert send(client,job).status_code == 404
    assert client.get('/api/v1/rounds').json()['jobs'] == []
    assert client.post('/api/v1/rounds/'+job['id']+'/cancel',json={},headers=HEADERS).status_code == 404


def test_failed_round_requires_explicit_retry_and_preserves_completed_sections(client, monkeypatch):
    monkeypatch.setattr(rounds,'generate_footage_review',abstain)
    register(client);job=create(client)
    assert send(client,job).status_code == 202
    async def failure(payload):
        raise RuntimeError('secret provider detail must not leak')
    monkeypatch.setattr(rounds,'generate_footage_review',failure)
    assert send(client,job,1).status_code == 202
    failed=client.get('/api/v1/rounds/'+job['id']).json()
    assert failed['status']=='failed' and failed['completed_sections']==1
    assert 'secret provider' not in json.dumps(failed)
    assert send(client,job,1).status_code==409
    monkeypatch.setattr(rounds,'generate_footage_review',abstain)
    assert send(client,job,1,retry=True).status_code==202
    assert client.get('/api/v1/rounds/'+job['id']).json()['attempts']==3
    assert send(client,job,1,retry=True).status_code==409


def test_interrupted_lease_is_not_retried_automatically_and_cancel_is_final(client, monkeypatch):
    monkeypatch.setattr(rounds,'generate_footage_review',abstain)
    register(client);job=create(client)
    job.update(status='running',updated=time.time()-110,lease='stale',attempts=1)
    with database.transaction() as db:
        db.execute('UPDATE round_jobs SET data=?,status=?,updated=? WHERE id=?',(json.dumps(job),'running',job['updated'],job['id']))
    interrupted=client.get('/api/v1/rounds/'+job['id']).json()
    assert interrupted['status']=='interrupted'
    assert send(client,job).status_code==409
    cancelled=client.post('/api/v1/rounds/'+job['id']+'/cancel',json={},headers=HEADERS).json()
    assert cancelled['status']=='cancelled'
    assert send(client,job,retry=True).status_code==409


def test_cancellation_during_provider_call_does_not_resurrect_job(client, monkeypatch):
    register(client);job=create(client)
    async def cancel_during_review(payload):
        with database.transaction() as db:
            current=json.loads(db.execute('SELECT data FROM round_jobs WHERE id=?',(job['id'],)).fetchone()[0])
            current['status']='cancelled';rounds.write(db,current)
        return await abstain(payload)
    monkeypatch.setattr(rounds,'generate_footage_review',cancel_during_review)
    assert send(client,job).status_code==202
    cancelled=client.get('/api/v1/rounds/'+job['id']).json()
    assert cancelled['status']=='cancelled' and cancelled['completed_sections']==0


def test_round_retention_limits_and_account_deletion(client):
    register(client);job=create(client)
    duplicate=client.post('/api/v1/rounds',json={**job['context'],'consent':True},headers=HEADERS)
    assert duplicate.status_code==409
    with database.transaction() as db:
        db.execute('UPDATE round_jobs SET created=? WHERE id=?',(time.time()-rounds.RETENTION-1,job['id']))
    assert client.get('/api/v1/rounds').json()['jobs']==[]
    create(client,end=300)
    response=client.post('/api/v1/training/delete-account',json={'password':PASSWORD,'confirmation':'DELETE'},headers=HEADERS)
    assert response.status_code==200
    with database.transaction() as db:
        assert db.execute('SELECT COUNT(*) FROM round_jobs').fetchone()[0]==0


def test_round_sampling_covers_fractional_tail_and_rejects_unbounded_work(client):
    register(client)
    job=create(client,end=10.1)
    assert job['windows']==[{'start':0,'end':5.05},{'start':5.05,'end':10.1}]
    assert all(1<=w['end']-w['start']<=10.01 for w in rounds.windows(0,300))
    assert client.post('/api/v1/rounds',json={**job['context'],'end':301,'consent':True},headers=HEADERS).status_code==422


def test_provider_budget_blocks_additional_sections_without_calling_provider(client, monkeypatch):
    calls=[]
    async def counted(payload):
        calls.append(payload.start)
        return await abstain(payload)
    monkeypatch.setattr(rounds,'generate_footage_review',counted)
    monkeypatch.setattr(rounds.get_settings(),'round_hourly_limit',1)
    register(client);job=create(client)
    assert send(client,job).status_code==202
    assert send(client,job,1).status_code==429
    assert calls==[0]
    current=client.get('/api/v1/rounds/'+job['id']).json()
    assert current['completed_sections']==1 and current['status']=='ready'


def test_job_retry_budget_is_bounded_even_when_all_attempts_fail(client,monkeypatch):
    calls=[]
    async def failure(payload):
        calls.append(1)
        raise RuntimeError('test failure')
    monkeypatch.setattr(rounds,'generate_footage_review',failure)
    register(client);job=create(client,end=5)
    for attempt in range(4):
        assert send(client,job,retry=attempt>0).status_code==202
    assert send(client,job,retry=True).status_code==429
    assert len(calls)==4
