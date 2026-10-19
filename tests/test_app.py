import hashlib
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

import app.main as main
from app.core import security
from app.services.scoring_engine import PILLAR_WEIGHTS

CODE = 'test-access-code-for-this-test-only'
HEADERS = {'X-FightIQ-Client': 'web', 'Origin': 'http://testserver'}
PLAN = {'observations': ['A chin exposure was logged.'],
        'priority': {'title': 'Recover your guard', 'explanation': 'One risky exchange was logged.', 'action': 'Reset before returning.'},
        'tactics': ['Reset.', 'Observe.', 'Angle out.'],
        'drills': [{'name': 'Mirror work', 'instructions': 'Use a slow pace.', 'duration': '2 minutes'},
                   {'name': 'Footwork', 'instructions': 'Practice with a coach.', 'duration': '2 minutes'}],
        'cue': 'Reset, then move.'}
PAYLOAD = {'mistakes': [{'mistake_id': 'RISK_001', 'severity': 'critical', 'round': 1}]}


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(main.settings, 'usage_db_path', str(tmp_path / 'usage.sqlite3'))
    monkeypatch.setattr(main.settings, 'beta_access_code', CODE)
    monkeypatch.setattr(main.settings, 'openai_api_key', 'test-key-not-used')
    monkeypatch.setattr(main.settings, 'environment', 'development')
    monkeypatch.setattr(main.settings, 'coach_hourly_limit', 10)
    monkeypatch.setattr(main.settings, 'coach_daily_limit', 30)
    monkeypatch.setattr(main, 'generate_corner_advice', AsyncMock(return_value=PLAN))
    with TestClient(main.app) as result:
        yield result


def login(client):
    result = client.post('/api/v1/session', json={'code': CODE}, headers=HEADERS)
    assert result.status_code == 200
    return result


def test_health_and_safe_headers(client):
    result = client.get('/api/v1/health')
    assert result.json()['status'] == 'ok'
    assert result.json()['version'] == '0.4.0'
    assert result.headers['cache-control'] == 'no-store'
    assert result.headers['x-content-type-options'] == 'nosniff'
    assert 'test-key-not-used' not in result.text


def test_empty_log_is_not_perfect(client):
    data = client.post('/api/v1/analysis', json={}).json()
    assert data['overall_score'] is None
    assert data['grade'] is None
    assert data['assessment_status'] == 'not_assessed'
    assert all(p['score'] is None for p in data['pillar_scores'].values())


def test_only_observed_pillar_is_scored(client):
    data = client.post('/api/v1/analysis', json=PAYLOAD).json()
    assert data['overall_score'] is None
    assert data['reviewed_count'] == 1
    assert data['pillar_scores']['risk_management']['score'] < 100
    assert data['pillar_scores']['composure']['score'] is None


def test_explicit_complete_review_allows_overall(client):
    data = client.post('/api/v1/analysis', json={**PAYLOAD, 'reviewed_pillars': list(PILLAR_WEIGHTS)}).json()
    assert data['overall_score'] < 100
    assert data['assessment_status'] == 'complete'


def test_repeated_observations_and_floor(client):
    data = client.post('/api/v1/analysis', json={'mistakes': [{'mistake_id':'RISK_001','count':20,'severity':'critical'}]}).json()
    assert data['pillar_scores']['risk_management']['score'] == 0
    assert data['observation_count'] == 20


@pytest.mark.parametrize('payload', [
    {'mistakes':[{'mistake_id':'UNKNOWN'}]},
    {'mistakes':[{'mistake_id':'RISK_001','count':0}]},
    {'mistakes':[{'mistake_id':'RISK_001','round':13}]},
    {'mistakes':[{'mistake_id':'RISK_001'}]*101},
    {'reviewed_pillars':['invented']},
])
def test_invalid_assessment_rejected(client,payload):
    assert client.post('/api/v1/analysis',json=payload).status_code == 422


def test_demo_label_and_coverage(client):
    data = client.get('/api/v1/analysis/demo').json()
    assert data['is_demo'] is True
    assert data['reviewed_count'] == 6
    assert len(data['mistakes']) == 3


def test_anonymous_cannot_spend(client):
    assert client.post('/api/v1/ai/coach',json=PAYLOAD,headers=HEADERS).status_code == 401
    main.generate_corner_advice.assert_not_called()


def test_missing_code_fails_closed(client,monkeypatch):
    monkeypatch.setattr(main.settings,'beta_access_code','')
    assert client.get('/api/v1/session').json()['access_available'] is False
    assert client.post('/api/v1/session',json={'code':CODE},headers=HEADERS).status_code == 503
    assert client.post('/api/v1/ai/coach',json=PAYLOAD,headers=HEADERS).status_code == 401


def test_wrong_code_and_login_limit(client):
    for _ in range(8):
        assert client.post('/api/v1/session',json={'code':'wrong'},headers=HEADERS).status_code == 401
    result=client.post('/api/v1/session',json={'code':CODE},headers=HEADERS)
    assert result.status_code == 429
    assert int(result.headers['retry-after']) > 0


def test_cookie_flags_and_logout(client,monkeypatch):
    result=login(client)
    assert 'HttpOnly' in result.headers['set-cookie']
    assert 'SameSite=strict' in result.headers['set-cookie']
    assert client.get('/api/v1/session').json()['authenticated']
    assert client.delete('/api/v1/session',headers=HEADERS).status_code == 200
    assert not client.get('/api/v1/session').json()['authenticated']
    monkeypatch.setattr(main.settings,'environment','production')
    assert 'Secure' in login(client).headers['set-cookie']


def test_expired_and_tampered_sessions(client):
    expired='0.'+'a'*32
    for value in [expired+'.'+security.signature(expired), security.make_session()+'tampered']:
        client.cookies.set(security.COOKIE_NAME,value)
        assert client.post('/api/v1/ai/coach',json=PAYLOAD,headers=HEADERS).status_code == 401
    main.generate_corner_advice.assert_not_called()


def test_code_rotation_invalidates_sessions(client,monkeypatch):
    login(client)
    monkeypatch.setattr(main.settings,'beta_access_code','rotated-test-code-long-enough')
    assert not client.get('/api/v1/session').json()['authenticated']


def test_cross_site_requests_rejected(client):
    login(client)
    assert client.post('/api/v1/ai/coach',json=PAYLOAD).status_code == 403
    assert client.post('/api/v1/ai/coach',json=PAYLOAD,headers={**HEADERS,'Origin':'https://another-site.example'}).status_code == 403
    main.generate_corner_advice.assert_not_called()


def test_provider_receives_recomputed_assessment(client):
    login(client)
    result=client.post('/api/v1/ai/coach',json={**PAYLOAD,'context':'Orthodox boxer'},headers=HEADERS)
    assert result.status_code == 200
    assert result.json()['plan']['cue'] == PLAN['cue']
    report,context=main.generate_corner_advice.call_args.args
    assert report['overall_score'] is None
    assert report['priority_fix']['mistake_id']=='RISK_001'
    assert context=='Orthodox boxer'
    assert client.post('/api/v1/ai/coach',json={'analysis':{'overall_score':100}},headers=HEADERS).status_code == 422


def test_empty_session_does_not_consume_provider_call(client):
    login(client)
    assert client.post('/api/v1/ai/coach',json={},headers=HEADERS).status_code == 422
    main.generate_corner_advice.assert_not_called()


def test_coach_allowance_and_failed_attempts(client):
    login(client)
    main.generate_corner_advice.side_effect=RuntimeError('A complete plan was not returned.')
    for _ in range(3):
        assert client.post('/api/v1/ai/coach',json=PAYLOAD,headers=HEADERS).status_code == 502
    result=client.post('/api/v1/ai/coach',json=PAYLOAD,headers=HEADERS)
    assert result.status_code == 429
    assert main.generate_corner_advice.call_count==3


def test_global_allowance_cannot_be_bypassed_by_new_login(client,monkeypatch):
    monkeypatch.setattr(main.settings,'coach_hourly_limit',2)
    for _ in range(2):
        login(client)
        assert client.post('/api/v1/ai/coach',json=PAYLOAD,headers=HEADERS).status_code==200
    login(client)
    assert client.post('/api/v1/ai/coach',json=PAYLOAD,headers=HEADERS).status_code==429


def test_atomic_allowance_under_concurrent_requests(client,monkeypatch):
    monkeypatch.setattr(main.settings,'coach_hourly_limit',2)
    def attempt(i):
        try:
            security.consume_allowance('coach',str(i))
            return 200
        except HTTPException as error:
            return error.status_code
    with ThreadPoolExecutor(max_workers=6) as pool:
        results=list(pool.map(attempt,range(6)))
    assert results.count(200)==2
    assert results.count(429)==4


def test_usage_storage_failure_denies_provider_call(client,monkeypatch,tmp_path):
    login(client)
    bad=tmp_path/'file';bad.write_text('not a directory')
    monkeypatch.setattr(main.settings,'usage_db_path',str(bad/'usage.sqlite3'))
    result=client.post('/api/v1/ai/coach',json=PAYLOAD,headers=HEADERS)
    assert result.status_code==503
    main.generate_corner_advice.assert_not_called()


def test_oversized_body_and_no_secret_echo(client):
    assert client.post('/api/v1/session',content='x'*32769,headers={'Content-Type':'application/json'}).status_code==413
    result=client.post('/api/v1/session',json={'code':'sensitive'*300},headers=HEADERS)
    assert result.status_code==422
    assert 'sensitive' not in result.text


def test_websocket_rejects_bad_input_and_keeps_working(client):
    with client.websocket_connect('/ws/live/test') as socket:
        assert socket.receive_json()['type']=='connected'
        socket.send_json({'type':'mistake','mistake_id':'RISK_001','round':'bad'})
        assert socket.receive_json()['type']=='error'
        socket.send_json({'type':'mistake','mistake_id':'RISK_001'})
        assert socket.receive_json()['data']['reviewed_count']==1
        socket.send_json({'type':'reset'})
        assert socket.receive_json()['data']['overall_score'] is None


def test_render_canonical_origin_is_used_behind_proxy(client, monkeypatch):
    monkeypatch.setattr(main.settings, 'render_external_url', 'https://fight-iq-ai.onrender.com')
    headers = {**HEADERS, 'Origin': 'https://fight-iq-ai.onrender.com'}
    assert client.post('/api/v1/session', json={'code': CODE}, headers=headers).status_code == 200
    assert client.post('/api/v1/ai/coach', json=PAYLOAD, headers=headers).status_code == 200
    assert client.post('/api/v1/ai/coach', json=PAYLOAD, headers=HEADERS).status_code == 403


def test_existing_usage_ledger_is_respected_by_new_session(client):
    login(client)
    for _ in range(3):
        assert client.post('/api/v1/ai/coach', json=PAYLOAD, headers=HEADERS).status_code == 200
    import sqlite3
    with sqlite3.connect(main.settings.usage_db_path) as connection:
        assert connection.execute("SELECT COUNT(*) FROM attempts WHERE kind='coach'").fetchone()[0] == 3
    assert client.post('/api/v1/ai/coach', json=PAYLOAD, headers=HEADERS).status_code == 429


def test_html_loads_external_assets_and_has_no_inline_scripts(client):
    result = client.get('/')
    assert result.status_code == 200
    assert '/static/app.js?v=4' in result.text
    assert '<script>' not in result.text
    assert "script-src 'self'" in result.headers['content-security-policy']
    assert client.get('/static/styles.css').status_code == 200
    assert client.get('/static/app.js').status_code == 200

# Footage-review checks use generated blank JPEGs and mocked AI; no real footage.
import base64
import io
from types import SimpleNamespace
from PIL import Image
from app.services import video_coach


def footage_payload(**overrides):
    buffer = io.BytesIO()
    Image.new('RGB', (64, 64), 'gray').save(buffer, 'JPEG')
    image = 'data:image/jpeg;base64,' + base64.b64encode(buffer.getvalue()).decode()
    payload = {'discipline': 'Boxing', 'experience': 'Beginner',
               'athlete': 'Solo athlete in blue shorts', 'goal': 'Guard recovery',
               'start': 10, 'end': 11, 'consent': True,
               'frames': [{'timestamp': 10 + i / 5, 'image': image} for i in range(5)]}
    return {**payload, **overrides}


def footage_review(**overrides):
    return video_coach.FootageReview(**{
        'visibility': 'limited', 'athlete_match': 'confirmed',
        'summary': 'A controlled stance is visible.', 'limitations': ['Only sampled frames were reviewed.'],
        'moments': [{'frame_numbers': [2, 4], 'kind': 'strength', 'phase': 'movement',
                     'title': 'Balanced stance', 'evidence': 'Base is visible in the cited frames.',
                     'confidence': 'medium', 'why_it_matters': 'A base supports movement.',
                     'adjustment': 'Practice slowly with a coach.'}],
        'priority': 'Review stance with a coach.', 'additions': [], 'practice': [],
        'next_session_check': 'Check whether the base remains stable.', **overrides})


def test_video_anonymous_rejected_before_parsing_or_images(client, monkeypatch):
    generate = AsyncMock()
    monkeypatch.setattr(main, 'generate_footage_review', generate)
    result = client.post('/api/v1/video/review', content='invalid', headers=HEADERS)
    assert result.status_code == 401
    generate.assert_not_called()


def test_video_success_and_quota(client, monkeypatch):
    login(client)
    payload = footage_payload()
    review = video_coach.attach_evidence(footage_review(), video_coach.VideoRequest(**payload))
    generate = AsyncMock(return_value=review)
    monkeypatch.setattr(main, 'generate_footage_review', generate)
    for _ in range(2):
        response = client.post('/api/v1/video/review', json=payload, headers=HEADERS)
        assert response.status_code == 200
        assert response.json()['review']['moments'][0]['timestamp'] == 10.2
        assert response.json()['review']['coverage']['sample_fps'] == 5
    assert client.post('/api/v1/video/review', json=payload, headers=HEADERS).status_code == 429
    assert generate.call_count == 2


@pytest.mark.parametrize('changes', [
    {'consent': False}, {'athlete': ''}, {'discipline': 'unknown'},
    {'experience': 'professional'}, {'end': 25}, {'start': -1},
    {'start': float('inf')}, {'goal': 'x' * 601}, {'frames': []},
])
def test_video_rejects_bad_context_and_bounds(client, monkeypatch, changes):
    login(client)
    generate = AsyncMock()
    monkeypatch.setattr(main, 'generate_footage_review', generate)
    if changes.get('start') == float('inf'):
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            video_coach.VideoRequest(**footage_payload(**changes))
    else:
        assert client.post('/api/v1/video/review', json=footage_payload(**changes), headers=HEADERS).status_code == 422
    generate.assert_not_called()


def test_video_requires_ordered_timestamps_and_all_samples(client, monkeypatch):
    login(client)
    generate = AsyncMock()
    monkeypatch.setattr(main, 'generate_footage_review', generate)
    payload = footage_payload()
    payload['frames'][1]['timestamp'] = 10.9
    assert client.post('/api/v1/video/review', json=payload, headers=HEADERS).status_code == 422
    payload = footage_payload(end=20)  # Ten seconds requires fifty frames.
    assert client.post('/api/v1/video/review', json=payload, headers=HEADERS).status_code == 422
    generate.assert_not_called()


@pytest.mark.parametrize('image', ['https://example.com/private.jpg', 'data:image/jpeg;base64,' + 'a' * 60])
def test_video_rejects_remote_or_corrupt_frames(client, monkeypatch, image):
    login(client)
    generate = AsyncMock()
    monkeypatch.setattr(main, 'generate_footage_review', generate)
    payload = footage_payload()
    payload['frames'][0]['image'] = image
    assert client.post('/api/v1/video/review', json=payload, headers=HEADERS).status_code == 422
    generate.assert_not_called()


def test_video_rejects_oversized_images_before_decode(client):
    payload = footage_payload()
    data = io.BytesIO()
    Image.new('RGB', (1000, 64)).save(data, 'JPEG')
    payload['frames'][0]['image'] = 'data:image/jpeg;base64,' + base64.b64encode(data.getvalue()).decode()
    with pytest.raises(ValueError):
        video_coach.validate_images(video_coach.VideoRequest(**payload))


def test_video_body_limit_and_cross_origin(client):
    login(client)
    assert client.post('/api/v1/video/review', content='x' * 6100001, headers=HEADERS).status_code == 413
    assert client.post('/api/v1/video/review', json=footage_payload(), headers={**HEADERS, 'Origin': 'https://other.example'}).status_code == 403
    assert client.post('/api/v1/session', content='x' * 33000, headers=HEADERS).status_code == 413


def test_video_citations_resolve_only_to_supplied_frames():
    payload = video_coach.VideoRequest(**footage_payload())
    result = video_coach.attach_evidence(footage_review(), payload)
    assert result['moments'][0]['timestamp'] == 10.2
    assert result['moments'][0]['end_timestamp'] == 10.6
    bad = footage_review()
    bad.moments[0].frame_numbers = [99]
    with pytest.raises(RuntimeError):
        video_coach.attach_evidence(bad, payload)


@pytest.mark.parametrize('changes', [{'visibility':'unusable'}, {'athlete_match':'uncertain'}])
def test_uncertain_video_removes_personalized_findings(changes):
    result = video_coach.attach_evidence(footage_review(**changes), video_coach.VideoRequest(**footage_payload()))
    assert result['moments'] == result['additions'] == result['practice'] == []


def test_video_provider_failure_is_safe_and_consumes_allowance(client, monkeypatch):
    login(client)
    generate = AsyncMock(side_effect=RuntimeError('internal data must not be returned'))
    monkeypatch.setattr(main, 'generate_footage_review', generate)
    for _ in range(2):
        response = client.post('/api/v1/video/review', json=footage_payload(), headers=HEADERS)
        assert response.status_code == 502
        assert 'internal data' not in response.text
    assert client.post('/api/v1/video/review', json=footage_payload(), headers=HEADERS).status_code == 429


def test_video_global_allowance_survives_new_sessions(client):
    for i in range(3):
        security.consume_allowance('video', f'session-{i}')
    with pytest.raises(HTTPException) as caught:
        security.consume_allowance('video', 'new-session')
    assert caught.value.status_code == 429


def test_video_provider_receives_images_context_and_no_storage(client, monkeypatch):
    import asyncio
    provider = AsyncMock()
    provider.responses.parse.return_value = SimpleNamespace(output_parsed=footage_review())
    factory = AsyncMock()
    factory.__aenter__.return_value = provider
    monkeypatch.setattr(video_coach, 'AsyncOpenAI', lambda **kwargs: factory)
    result = asyncio.run(video_coach.generate_footage_review(video_coach.VideoRequest(**footage_payload())))
    args = provider.responses.parse.call_args.kwargs
    assert args['store'] is False
    assert args['text_format'] is video_coach.FootageReview
    parts = args['input'][0]['content']
    assert len([part for part in parts if part['type'] == 'input_image']) == 5
    assert '10.200' in parts[3]['text']
    assert result['coverage']['frames'] == 5


def test_footage_assets_and_video_policy(client):
    response = client.get('/')
    assert 'id="fightVideo"' in response.text
    assert 'id="videoConsent"' in response.text
    assert '/static/video.js?v=4' in response.text
    assert "media-src 'self' blob:" in response.headers['content-security-policy']
    assert 'microphone=()' in response.headers['permissions-policy']
    assert client.get('/static/video.js').status_code == 200
