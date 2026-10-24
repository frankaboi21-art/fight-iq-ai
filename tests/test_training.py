import json
import os
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

import app.main as main
from app.core import database
from app.services import training

CODE = 'training-test-beta-invitation-code'
PASSWORD = 'a-long-test-password-123'
HEADERS = {'X-FightIQ-Client': 'web', 'Origin': 'http://testserver'}
BACKENDS = ['sqlite'] + (['postgres'] if os.getenv('TRAINING_TEST_POSTGRES_URL') else [])


@pytest.fixture(params=BACKENDS)
def client(request, tmp_path, monkeypatch):
    cfg = main.settings
    monkeypatch.setattr(cfg, 'database_url', os.environ['TRAINING_TEST_POSTGRES_URL'] if request.param == 'postgres' else '')
    monkeypatch.setattr(cfg, 'training_db_path', str(tmp_path / 'training.db'))
    monkeypatch.setattr(cfg, 'usage_db_path', str(tmp_path / 'usage.db'))
    monkeypatch.setattr(cfg, 'beta_access_code', CODE)
    monkeypatch.setattr(cfg, 'environment', 'development')
    monkeypatch.setattr(cfg, 'public_origin', '')
    monkeypatch.setattr(cfg, 'render_external_url', '')
    with database.transaction() as db:
        db.execute('DELETE FROM athletes')
        db.execute('DELETE FROM attempts')
    with TestClient(main.app) as test:
        yield test


def register(client, handle='athlete_one'):
    assert client.post('/api/v1/session', json={'code': CODE}, headers=HEADERS).status_code == 200
    response = client.post('/api/v1/training/register', json={'handle': handle, 'password': PASSWORD}, headers=HEADERS)
    assert response.status_code == 200, response.text
    return response.json()['recovery_code']


def note(title='Training today', **changes):
    return {'title': title, 'discipline': 'MMA', 'purpose': 'self', 'training_type': 'drilling',
            'performed_on': date.today().isoformat(), 'minutes': 30, 'kind': 'note', 'notes': 'Observed with my coach.', **changes}


def save(client, payload):
    result = client.post('/api/v1/training/entries', json=payload, headers=HEADERS)
    assert result.status_code == 200, result.text
    return result.json()['entry']


def confirm(client, entry, verdict='confirmed'):
    response = client.post(f'/api/v1/training/entries/{entry["id"]}/feedback', json={'verdict': verdict}, headers=HEADERS)
    assert response.status_code == 200, response.text


def footage():
    return {'visibility': 'clear', 'athlete_match': 'confirmed', 'summary': 'A visible exchange.',
            'limitations': ['Sampled frames only.'], 'moments': [], 'priority': 'Check the exit.', 'additions': [],
            'practice': [{'name': 'Exit rehearsal', 'minutes': 5, 'instructions': 'Rehearse slowly.', 'success_check': 'Recover balance.'}],
            'next_session_check': 'Check balance.', 'coverage': {'start': 0.0, 'end': 1.0, 'frames': 5, 'sample_fps': 5}}


def reviewed_payload(**changes):
    report = footage()
    return note(kind='footage', report=report, receipt=training.receipt('footage', report), **changes)


def test_account_cookie_profile_and_private_export(client):
    recovery = register(client)
    me = client.get('/api/v1/training/me').json()['athlete']
    assert me['handle'] == 'athlete_one'
    assert len(recovery) > 30
    assert client.post('/api/v1/training/profile', json={'display_name': 'A', 'goal': 'Cleaner exits', 'discipline': 'Boxing'}, headers=HEADERS).status_code == 200
    data = client.get('/api/v1/training/export').json()
    assert data['athlete']['profile']['goal'] == 'Cleaner exits'
    assert PASSWORD not in json.dumps(data) and recovery not in json.dumps(data)
    with database.transaction() as db:
        encoded = db.execute('SELECT password,recovery FROM athletes').fetchone()
        assert encoded[0] != PASSWORD and encoded[1] != recovery
    assert client.post('/api/v1/training/logout', json={}, headers=HEADERS).status_code == 200
    assert client.get('/api/v1/training/entries').status_code == 401
    result = client.post('/api/v1/training/login', json={'handle': 'ATHLETE_ONE', 'password': PASSWORD}, headers=HEADERS)
    assert result.status_code == 200
    assert 'HttpOnly' in result.headers['set-cookie'] and 'SameSite=strict' in result.headers['set-cookie']
    assert client.get('/api/v1/training/me').json()['athlete']['profile']['goal'] == 'Cleaner exits'


def test_beta_required_register_and_csrf(client):
    payload = {'handle': 'tester', 'password': PASSWORD}
    assert client.post('/api/v1/training/register', json=payload, headers=HEADERS).status_code == 401
    assert client.post('/api/v1/training/register', json=payload).status_code == 403
    register(client)
    assert client.post('/api/v1/training/profile', json={}, headers={**HEADERS, 'Origin': 'https://evil.example'}).status_code == 403
    assert client.post('/api/v1/training/profile', json={'sessions_per_week': 0}, headers=HEADERS).status_code == 422


def test_password_spaces_are_preserved_for_login_and_deletion(client):
    assert client.post('/api/v1/session', json={'code': CODE}, headers=HEADERS).status_code == 200
    exact = '  significant password spaces  '
    response = client.post('/api/v1/training/register', json={'handle': ' Spaced_User ', 'password': exact}, headers=HEADERS)
    assert response.status_code == 200
    client.post('/api/v1/training/logout', json={}, headers=HEADERS)
    assert client.post('/api/v1/training/login', json={'handle': 'spaced_user', 'password': exact.strip()}, headers=HEADERS).status_code == 401
    assert client.post('/api/v1/training/login', json={'handle': 'spaced_user', 'password': exact}, headers=HEADERS).status_code == 200
    assert client.post('/api/v1/training/delete-account', json={'password': exact.strip(), 'confirmation': 'DELETE'}, headers=HEADERS).status_code == 401
    assert client.post('/api/v1/training/delete-account', json={'password': exact, 'confirmation': 'DELETE'}, headers=HEADERS).status_code == 200


def test_private_records_not_visible_to_other_accounts(client):
    register(client)
    first = save(client, note())
    client.post('/api/v1/training/logout', json={}, headers=HEADERS)
    register(client, 'athlete_two')
    assert client.get('/api/v1/training/entries').json()['entries'] == []
    assert client.delete('/api/v1/training/entries/'+first['id'], headers=HEADERS).status_code == 404
    assert client.get('/api/v1/training/entries/'+first['id']+'/comments').status_code == 404
    assert client.post('/api/v1/training/entries/'+first['id']+'/feedback', json={'verdict': 'confirmed'}, headers=HEADERS).status_code == 404


def test_receipt_round_trip_tamper_and_duplicate(client):
    register(client)
    payload = reviewed_payload()
    payload['report']['coverage']['start'] = 0  # JavaScript JSON serialization.
    save(client, payload)
    assert client.post('/api/v1/training/entries', json=payload, headers=HEADERS).status_code == 409
    payload['report']['priority'] = 'A fabricated finding'
    assert client.post('/api/v1/training/entries', json=payload, headers=HEADERS).status_code == 422
    # A new review of an identical exchange is independently saveable.
    save(client, reviewed_payload(title='A separate review'))
    invalid = note(report={'unexpected': 'not a note'})
    assert client.post('/api/v1/training/entries', json=invalid, headers=HEADERS).status_code == 422


def test_manual_scoring_receipt_can_be_saved(client):
    register(client)
    report = client.post('/api/v1/analysis', json={'reviewed_pillars': ['composure']}).json()
    signature = report.pop('receipt')
    entry = save(client, note(kind='session', report=report, receipt=signature))
    assert entry['report']['reviewed_count'] == 1


def test_confirmation_practice_reassessment_and_correction(client):
    register(client)
    entry = save(client, reviewed_payload())
    assert client.get('/api/v1/training/development').json()['tasks'] == []
    url = f'/api/v1/training/entries/{entry["id"]}/tasks/0'
    assert client.post(url, json={'status': 'practiced'}, headers=HEADERS).status_code == 409
    confirm(client, entry)
    plan = client.get('/api/v1/training/development').json()
    assert len(plan['tasks']) == 1 and plan['tasks'][0]['entry_id'] == entry['id']
    assert client.post(url, json={'status': 'practiced'}, headers=HEADERS).status_code == 200
    assert client.post(url, json={'status': 'practiced', 'outcome': 'improving'}, headers=HEADERS).status_code == 422
    later = save(client, note('Reassessment'))
    confirm(client, later)
    payload = {'status': 'reassessed', 'outcome': 'improving', 'reassessment_entry': later['id'], 'notes': 'Coach and I checked balance.'}
    assert client.post(url, json=payload, headers=HEADERS).status_code == 200
    assert client.get('/api/v1/training/development').json()['metrics']['reported_improving'] == 1
    confirm(client, later, 'needs_correction')
    plan = client.get('/api/v1/training/development').json()
    assert plan['metrics']['reported_improving'] == 0 and plan['tasks'][0]['status'] == 'practiced'


def test_different_settings_cannot_claim_comparable_progress(client):
    register(client)
    entry = save(client, reviewed_payload())
    confirm(client, entry)
    later = save(client, note(training_type='competition'))
    confirm(client, later)
    result = client.post(f'/api/v1/training/entries/{entry["id"]}/tasks/0', json={'status': 'reassessed', 'outcome': 'improving', 'reassessment_entry': later['id']}, headers=HEADERS)
    assert result.status_code == 422


def test_reassessment_revisits_difficult_drills_without_resurrecting_old_duplicates(client):
    register(client)
    older = save(client, reviewed_payload(title='Original drill'))
    confirm(client, older)
    latest = save(client, reviewed_payload(title='Updated drill'))
    confirm(client, latest)
    later = save(client, note('Later evidence'))
    confirm(client, later)
    url = f'/api/v1/training/entries/{latest["id"]}/tasks/0'
    payload = {'status': 'reassessed', 'outcome': 'improving', 'reassessment_entry': later['id']}
    assert client.post(url, json=payload, headers=HEADERS).status_code == 200
    assert client.get('/api/v1/training/development').json()['tasks'] == []
    for outcome in ['unchanged', 'needs_work']:
        payload.update(outcome=outcome, notes='Review the setup with my coach.')
        assert client.post(url, json=payload, headers=HEADERS).status_code == 200
        tasks = client.get('/api/v1/training/development').json()['tasks']
        assert len(tasks) == 1 and tasks[0]['entry_id'] == latest['id']
        assert tasks[0]['revisit'] is True and tasks[0]['notes'] == payload['notes']


def test_backfilled_session_does_not_override_more_recent_training(client):
    register(client)
    recent = save(client, reviewed_payload(title='Today'))
    confirm(client, recent)
    historical = save(client, reviewed_payload(title='Backfilled yesterday', performed_on=(date.today()-timedelta(days=1)).isoformat()))
    confirm(client, historical)
    plan = client.get('/api/v1/training/development').json()
    assert plan['tasks'][0]['entry_id'] == recent['id']
    assert plan['coverage'][0]['title'] == 'Today'


def test_scouting_and_uncertain_footage_do_not_feed_athlete_plan(client):
    register(client)
    scout = save(client, reviewed_payload(purpose='opponent'))
    confirm(client, scout)
    assert scout['tasks'] == []
    report = footage(); report['athlete_match'] = 'uncertain'
    uncertain = save(client, note(kind='footage', report=report, receipt=training.receipt('footage', report)))
    confirm(client, uncertain)
    assert client.get('/api/v1/training/development').json()['tasks'] == []


def test_coach_grant_comments_revoke_and_no_edit(client):
    register(client, 'coach')
    client.post('/api/v1/training/logout', json={}, headers=HEADERS)
    register(client)
    owner = client.get('/api/v1/training/me').json()['athlete']['id']
    entry = save(client, note())
    scout = save(client, note('Private scouting', purpose='opponent'))
    assert client.post('/api/v1/training/coaches', json={'handle': 'coach'}, headers=HEADERS).status_code == 200
    athlete_cookie = client.cookies.get(training.COOKIE)
    client.cookies.delete(training.COOKIE)
    assert client.post('/api/v1/training/login', json={'handle': 'coach', 'password': PASSWORD}, headers=HEADERS).status_code == 200
    coach_cookie = client.cookies.get(training.COOKIE)
    shared = client.get(f'/api/v1/training/athletes/{owner}/entries').json()['entries']
    assert [e['id'] for e in shared] == [entry['id']]
    assert client.post(f'/api/v1/training/entries/{entry["id"]}/comments', json={'body': 'Check the next session.'}, headers=HEADERS).status_code == 200
    assert client.get(f'/api/v1/training/entries/{scout["id"]}/comments').status_code == 404
    assert client.delete(f'/api/v1/training/entries/{entry["id"]}', headers=HEADERS).status_code == 404
    client.cookies.clear();client.cookies.set(training.COOKIE, athlete_cookie)
    assert client.delete('/api/v1/training/coaches/coach', headers=HEADERS).status_code == 200
    assert client.get(f'/api/v1/training/entries/{entry["id"]}/comments').json()['comments'][0]['author'] == 'coach'
    client.cookies.clear();client.cookies.set(training.COOKIE, coach_cookie)
    assert client.get(f'/api/v1/training/athletes/{owner}/entries').status_code == 404
    assert client.get(f'/api/v1/training/entries/{entry["id"]}/comments').status_code == 404


def test_recovery_rotates_code_and_revokes_sessions(client):
    recovery = register(client)
    old_cookie = client.cookies.get(training.COOKIE)
    response = client.post('/api/v1/training/recover', json={'handle': 'athlete_one', 'password': 'new-long-test-password-321', 'recovery': recovery}, headers=HEADERS)
    assert response.status_code == 200 and response.json()['recovery_code'] != recovery
    client.cookies.clear();client.cookies.set(training.COOKIE, old_cookie)
    assert client.get('/api/v1/training/entries').status_code == 401
    assert client.post('/api/v1/training/recover', json={'handle': 'athlete_one', 'password': PASSWORD, 'recovery': recovery}, headers=HEADERS).status_code == 401


def test_tactical_system_validation_link_and_deletion(client):
    register(client)
    entry = save(client, note())
    system = {'title': 'Entry and exit', 'discipline': 'MMA', 'situation': 'Outside range', 'cue': 'Stable base', 'action': 'Rehearse a step', 'prerequisite': 'Coach supervision', 'practice': 'Slow rehearsal', 'success_check': 'Balanced exit', 'entry_id': entry['id'], 'branches': [{'reaction': 'Opponent holds', 'response': 'Reset', 'exit': 'Regain space'}, {'reaction': 'Opponent moves', 'response': 'Observe', 'exit': 'Regain stance'}]}
    result = client.post('/api/v1/training/systems', json=system, headers=HEADERS)
    assert result.status_code == 200
    system_id = result.json()['system']['id']
    system['branches'] = []
    assert client.post('/api/v1/training/systems', json=system, headers=HEADERS).status_code == 422
    assert client.delete('/api/v1/training/entries/'+entry['id'], headers=HEADERS).status_code == 200
    assert client.get('/api/v1/training/systems').json()['systems'][0]['entry_id'] == ''
    assert client.delete('/api/v1/training/systems/'+system_id, headers=HEADERS).status_code == 200
    assert client.get('/api/v1/training/systems').json()['systems'] == []


def test_account_deletion_removes_records_and_sessions(client):
    register(client)
    save(client, note())
    assert client.post('/api/v1/training/delete-account', json={'password': 'incorrect', 'confirmation': 'DELETE'}, headers=HEADERS).status_code == 401
    assert client.post('/api/v1/training/delete-account', json={'password': PASSWORD, 'confirmation': 'DELETE'}, headers=HEADERS).status_code == 200
    with database.transaction() as db:
        assert db.execute('SELECT COUNT(*) FROM athletes').fetchone()[0] == 0
        assert db.execute('SELECT COUNT(*) FROM training_entries').fetchone()[0] == 0
        assert db.execute('SELECT COUNT(*) FROM athlete_sessions').fetchone()[0] == 0


def test_production_does_not_save_to_ephemeral_disk(client, monkeypatch):
    monkeypatch.setattr(main.settings, 'environment', 'production')
    monkeypatch.setattr(main.settings, 'database_url', '')
    assert client.get('/api/v1/training/me').json() == {'available': False, 'athlete': None}
    assert client.get('/api/v1/training/entries').status_code == 503


def test_expired_account_session_denied(client):
    register(client)
    with database.transaction() as db:
        db.execute('UPDATE athlete_sessions SET expires=0')
    assert client.get('/api/v1/training/me').json()['athlete'] is None


def test_new_ui_assets_and_no_external_scripts(client):
    page = client.get('/').text
    assert 'id="trainingRoot"' in page and '/static/training.js?v=4' in page
    assert 'https://cdn' not in page
    assert client.get('/static/training.js').status_code == 200
