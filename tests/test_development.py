from datetime import date, timedelta

from app.services import training
from tests.test_training import client, register, save, note, confirm, footage, HEADERS


def drill(client, name, minutes=5, **changes):
    report = footage()
    report['practice'][0].update(name=name, minutes=minutes)
    entry = save(client, note(kind='footage', report=report, receipt=training.receipt('footage', report), **changes))
    confirm(client, entry)
    return entry


def update(client, entry, **values):
    return client.post(f'/api/v1/training/entries/{entry["id"]}/tasks/0', json=values, headers=HEADERS)


def plan(client):
    return client.get('/api/v1/training/development').json()


def test_unresolved_outcomes_outrank_newer_drills_and_keep_evidence(client):
    register(client)
    difficult = drill(client, 'Older difficult drill', performed_on=(date.today()-timedelta(days=2)).isoformat())
    unchanged = drill(client, 'Unchanged drill')
    practiced = drill(client, 'Practiced drill')
    new = drill(client, 'Newest drill')
    later = save(client, note('Comparable evidence')); confirm(client, later)
    for entry, outcome in [(difficult, 'needs_work'), (unchanged, 'unchanged')]:
        assert update(client, entry, status='reassessed', outcome=outcome, reassessment_entry=later['id'], notes='Check the setup together.').status_code == 200
    assert update(client, practiced, status='practiced').status_code == 200
    result = plan(client)
    assert [t['entry_id'] for t in result['tasks']] == [difficult['id'], unchanged['id'], practiced['id']]
    assert result['tasks'][0]['reassessment_entry'] == later['id']
    assert result['tasks'][0]['notes'] == 'Check the setup together.'
    assert result['deferred_tasks'][0]['entry_id'] == new['id']


def test_weekly_budget_never_silently_truncates_a_drill(client):
    register(client)
    short = drill(client, 'Short drill', minutes=3)
    long = drill(client, 'Full eight minute drill', minutes=8)
    assert client.post('/api/v1/training/profile', json={'practice_minutes': 10, 'sessions_per_week': 4}, headers=HEADERS).status_code == 200
    result = plan(client)
    assert [(t['entry_id'], t['allocated_minutes']) for t in result['tasks']] == [(long['id'], 8)]
    assert result['deferred_tasks'][0]['entry_id'] == short['id']
    assert 'No instructions or duration were shortened' in result['deferred_tasks'][0]['deferred_reason']
    week = result['weekly_plan']
    assert len(week['sessions']) == 4 and week['total_minutes'] == 32
    assert all(s['minutes'] == 8 and s['task_refs'] == [{'entry_id': long['id'], 'task_id': '0'}] for s in week['sessions'])
    assert week['suggested_review_on'] == (date.today()+timedelta(days=7)).isoformat()
    # Reading or scheduling a plan cannot mark practice complete.
    assert client.get('/api/v1/training/entries').json()['entries'][0]['tasks'][0]['status'] == 'planned'


def test_unknown_duration_requires_explicit_time_and_preserves_original(client):
    register(client)
    report = {'plan': {'drills': [{'name': 'Round-based drill', 'duration': '3 rounds of 2 minutes with rests', 'instructions': 'Keep the original controlled instructions.'}]}}
    entry = save(client, note(kind='corner', report=report, receipt=training.receipt('corner', report))); confirm(client, entry)
    assert plan(client)['tasks'] == []
    assert plan(client)['deferred_tasks'][0]['allocated_minutes'] is None
    assert update(client, entry, status='planned', planned_minutes=9).status_code == 200
    result = plan(client)
    assert result['tasks'][0]['allocated_minutes'] == 9
    assert result['tasks'][0]['time_basis'] == 'Time chosen by you'
    assert result['tasks'][0]['instructions'] == report['plan']['drills'][0]['instructions']
    saved = client.get('/api/v1/training/export').json()['entries'][0]
    assert saved['report'] == report and saved['tasks'][0]['planned_minutes'] == 9
    for invalid in [0, 61, -1, 2.5]:
        assert update(client, entry, status='planned', planned_minutes=invalid).status_code == 422
    assert update(client, entry, status='planned', planned_minutes=None).status_code == 200
    assert plan(client)['tasks'] == []


def test_exact_written_duration_and_oversized_drills(client):
    register(client)
    report = {'plan': {'drills': [{'name': 'Exact written time', 'duration': '7 minutes', 'instructions': 'Retain instructions.'},
                                  {'name': 'Ambiguous time', 'duration': '5–10 minutes', 'instructions': 'Ask about timing.'}]}}
    entry = save(client, note(kind='corner', report=report, receipt=training.receipt('corner', report))); confirm(client, entry)
    assert plan(client)['tasks'][0]['allocated_minutes'] == 7
    assert client.post('/api/v1/training/profile', json={'practice_minutes': 5}, headers=HEADERS).status_code == 200
    result = plan(client)
    assert result['tasks'] == [] and result['weekly_plan']['sessions'] == []
    assert 'exceeds your session budget' in result['deferred_tasks'][0]['deferred_reason']


def test_improvement_and_source_correction_rebuild_week_without_old_duplicates(client):
    register(client)
    drill(client, 'Same drill', performed_on=(date.today()-timedelta(days=1)).isoformat())
    latest = drill(client, 'Same drill')
    later = save(client, note('Evidence of the outcome')); confirm(client, later)
    assert update(client, latest, status='reassessed', outcome='improving', reassessment_entry=later['id']).status_code == 200
    result = plan(client)
    assert result['weekly_plan']['sessions'] == []
    assert [t['entry_id'] for t in result['improving_tasks']] == [latest['id']]
    confirm(client, later, 'needs_correction')
    result = plan(client)
    assert result['improving_tasks'] == [] and result['tasks'][0]['status'] == 'practiced'
    assert result['tasks'][0]['entry_id'] == latest['id']
    assert len(result['weekly_plan']['sessions']) == 3


def test_other_disciplines_research_and_unconfirmed_records_never_fill_week(client):
    register(client)
    drill(client, 'Another discipline', discipline='Boxing')
    drill(client, 'Opponent drill', purpose='opponent')
    unconfirmed = drill(client, 'Unconfirmed drill'); confirm(client, unconfirmed, 'unreviewed')
    result = plan(client)
    assert result['tasks'] == result['deferred_tasks'] == result['weekly_plan']['sessions'] == []
