import json
import time
from unittest.mock import AsyncMock

import pytest
from app.core import database
from app.services import live_review as live, video_coach
from tests.test_training import client, register, HEADERS, note, save
from tests.test_app import footage_payload, footage_review

CONTEXT=dict(discipline='MMA',experience='Beginner',athlete='Blue shirt on left',goal='Balance',consent=True)


@pytest.fixture(autouse=True)
def provider(monkeypatch):
    monkeypatch.setattr(live.get_settings(),'openai_api_key','synthetic-test-only')


def begin(client):
    result=client.post('/api/v1/live/start',json=CONTEXT,headers=HEADERS)
    assert result.status_code==200,result.text
    return result.json()['id']


def window(start=0):
    image=footage_payload()['frames'][0]['image']
    return {**CONTEXT,'start':start,'end':start+4,'frames':[{'timestamp':round(start+i*.21,3),'image':image} for i in range(19)]}


def send(client,sid,payload=None):
    payload=payload or window()
    with database.transaction() as db:
        db.execute('UPDATE live_sessions SET created=? WHERE id=?',(time.time()-payload['end']-1,sid))
    return client.post(f'/api/v1/live/{sid}/window',json=payload,headers=HEADERS)


async def synthetic(payload):
    return video_coach.attach_evidence(footage_review(),payload)


def test_live_actual_timestamps_signed_save_and_no_frame_persistence(client,monkeypatch):
    monkeypatch.setattr(live,'generate_footage_review',synthetic)
    register(client);sid=begin(client);result=send(client,sid)
    assert result.status_code==200,result.text
    data=result.json();r=data['review']
    assert r['moments'][0]['timestamp']==.21 and r['coverage']['mode']=='near-live'
    assert r['coverage']['sample_fps']==4.75 and data['processing_seconds']>=0
    save(client,note(kind='footage',report=r,receipt=data['receipt']))
    with database.transaction() as db:
        stored=db.execute('SELECT data,busy_until,lease FROM live_sessions WHERE id=?',(sid,)).fetchone()
        assert 'image' not in stored[0] and 'summary' not in stored[0] and stored[1]==0 and stored[2]==''
    assert client.post(f'/api/v1/live/{sid}/stop',json={},headers=HEADERS).status_code==200
    with database.transaction() as db:
        assert db.execute('SELECT data FROM live_sessions WHERE id=?',(sid,)).fetchone()[0]=='{}'


def test_live_auth_context_bad_frames_and_duplicate_rejection(client,monkeypatch):
    generate=AsyncMock(side_effect=synthetic);monkeypatch.setattr(live,'generate_footage_review',generate)
    assert client.post('/api/v1/live/start',json=CONTEXT,headers=HEADERS).status_code==401
    register(client);sid=begin(client)
    assert client.post('/api/v1/live/start',json=CONTEXT,headers=HEADERS).status_code==409
    payload=window();payload['goal']='Changed';assert send(client,sid,payload).status_code==422
    payload=window();payload['frames'][2]['timestamp']=.1;assert send(client,sid,payload).status_code==422
    payload=window();payload['frames'][1]['image']='https://example.com/'+'x'*40;assert send(client,sid,payload).status_code==422
    generate.assert_not_called()
    assert send(client,sid).status_code==200
    assert send(client,sid).status_code==409
    assert generate.call_count==1
    client.post('/api/v1/training/logout',json={},headers=HEADERS);register(client,'another_athlete')
    assert send(client,sid,window(5)).status_code==404


def test_stop_during_processing_discards_late_feedback(client,monkeypatch):
    register(client);sid=begin(client)
    async def stopped(payload):
        with database.transaction() as db: db.execute("UPDATE live_sessions SET active=0,data='{}' WHERE id=?",(sid,))
        return await synthetic(payload)
    monkeypatch.setattr(live,'generate_footage_review',stopped)
    assert send(client,sid).status_code==409
    with database.transaction() as db: assert db.execute('SELECT busy_until FROM live_sessions WHERE id=?',(sid,)).fetchone()[0]==0


def test_live_allowance_failure_no_replay_and_expiry(client,monkeypatch):
    generate=AsyncMock(side_effect=RuntimeError('provider private detail'))
    monkeypatch.setattr(live,'generate_footage_review',generate)
    register(client);sid=begin(client)
    for i in range(6):
        result=send(client,sid,window(i*5));assert result.status_code==502,result.text
        assert 'provider private detail' not in result.text
    assert send(client,sid,window(30)).status_code==429
    assert generate.call_count==6
    with database.transaction() as db: db.execute('UPDATE live_sessions SET created=? WHERE id=?',(time.time()-181,sid))
    assert client.post(f'/api/v1/live/{sid}/window',json=window(),headers=HEADERS).status_code==409
    with database.transaction() as db:
        db.execute('UPDATE live_sessions SET created=? WHERE id=?',(time.time()-601,sid));live.cleanup(db)
        assert not db.execute('SELECT id FROM live_sessions WHERE id=?',(sid,)).fetchone()


def test_live_global_busy_and_stale_window_rejected(client,monkeypatch):
    generate=AsyncMock();monkeypatch.setattr(live,'generate_footage_review',generate)
    register(client);sid=begin(client)
    with database.transaction() as db: db.execute('UPDATE live_sessions SET busy_until=? WHERE id=?',(time.time()+100,sid))
    assert send(client,sid).status_code==429
    with database.transaction() as db: db.execute('UPDATE live_sessions SET busy_until=0,created=? WHERE id=?',(time.time()-40,sid))
    assert client.post(f'/api/v1/live/{sid}/window',json=window(),headers=HEADERS).status_code==422
    generate.assert_not_called()


def test_live_session_starts_bounded_without_provider_calls(client):
    register(client)
    for _ in range(20):
        sid=begin(client)
        assert client.post(f'/api/v1/live/{sid}/stop',json={},headers=HEADERS).status_code==200
    assert client.post('/api/v1/live/start',json=CONTEXT,headers=HEADERS).status_code==429
    with database.transaction() as db:
        db.execute('UPDATE live_sessions SET created=?',(time.time()-601,))
    begin(client)
