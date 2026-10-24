import json
import pytest

from app.core import database
from app.services import research, training
from tests.test_training import client, register, save, confirm, footage, note, HEADERS


def evidence(client, title='Permissioned clip', purpose='opponent', discipline='MMA'):
    report=footage()
    report['moments']=[{'title':'Guard recovery', 'kind':'improvement', 'phase':'striking',
                       'evidence':'The hand is below the chin in the cited frame.', 'confidence':'medium',
                       'why_it_matters':'Check defensive recovery.', 'adjustment':'Rehearse a controlled reset.',
                       'frame_numbers':[2], 'timestamp':0.2, 'end_timestamp':0.2}]
    entry=save(client,note(title=title,purpose=purpose,discipline=discipline,kind='footage',source='Owned test clip',
                           report=report,receipt=training.receipt('footage',report)))
    confirm(client,entry)
    return entry


def result(entry_id):
    return research.ResearchReport(summary='A limited study.', limitations=['Selected sections only.'], next_evidence='Collect another comparable view.',
        findings=[research.Finding(title='Recovery option',observation='Hand position in the cited frame.',interpretation='A reset may help.',
                                   uncertainty='No timing can be inferred.',training_option='Controlled shadow practice.',prerequisite='Coach checks the stance.',
                                   success_check='Return to a stable position.',citations=[research.Citation(entry_id=entry_id,moment_index=0)])])


@pytest.fixture(autouse=True)
def mocked_provider(monkeypatch):
    monkeypatch.setattr(research.get_settings(),'openai_api_key','synthetic-only')
    async def fake(payload,sources):
        return result(sources[0]['entry_id'])
    monkeypatch.setattr(research,'generate',fake)


def study(client,entries,**changes):
    return client.post('/api/v1/research',json={'title':'Preparation study','purpose':'opponent','question':'What should I examine?',
                        'entry_ids':[e['id'] for e in entries],'consent':True,**changes},headers=HEADERS)


def test_cited_study_uses_server_timestamps_and_stays_private(client):
    register(client);entry=evidence(client)
    response=study(client,[entry]);assert response.status_code==200,response.text
    record=response.json()['study'];citation=record['report']['findings'][0]['citations'][0]
    assert citation['timestamp']==0.2 and citation['evidence']==entry['report']['moments'][0]['evidence']
    assert client.get('/api/v1/training/export').json()['research_studies'][0]['id']==record['id']
    client.post('/api/v1/training/logout',json={},headers=HEADERS);register(client,'other_athlete')
    assert client.get('/api/v1/research').json()['studies']==[]
    assert study(client,[entry]).status_code==404
    client.delete('/api/v1/research/'+record['id'],headers=HEADERS)
    with database.transaction() as db:
        assert db.execute('SELECT COUNT(*) FROM research_reports').fetchone()[0]==1


def test_sources_must_be_confirmed_permissioned_evidence_in_one_discipline(client):
    register(client);first=evidence(client);second=evidence(client,discipline='Boxing')
    assert study(client,[first,second]).status_code==422
    assert study(client,[first,first]).status_code==422
    assert study(client,[first],purpose='style').status_code==422
    assert study(client,[first],consent=False).status_code==422
    confirm(client,first,'unreviewed')
    assert study(client,[first]).status_code==422
    with database.transaction() as db:
        assert db.execute('SELECT COUNT(*) FROM research_reports').fetchone()[0]==0


def test_fabricated_citation_is_rejected_without_saved_report(client,monkeypatch):
    register(client);entry=evidence(client)
    async def invalid(payload,sources):
        return result('invented-source')
    monkeypatch.setattr(research,'generate',invalid)
    assert study(client,[entry]).status_code==502
    assert client.get('/api/v1/research').json()['studies']==[]


def test_corrected_sources_mark_study_stale_and_deletion_removes_derived_study(client):
    register(client);entry=evidence(client)
    assert study(client,[entry]).status_code==200
    confirm(client,entry,'needs_correction')
    stale=client.get('/api/v1/research').json()['studies'][0]
    assert stale['sources_current'] is False and stale['report'] is None
    assert 'Sources changed' in stale['status']
    client.delete('/api/v1/training/entries/'+entry['id'],headers=HEADERS)
    assert client.get('/api/v1/research').json()['studies']==[]


def test_source_changes_during_generation_cannot_save_obsolete_study(client,monkeypatch):
    register(client);entry=evidence(client)
    async def modified(payload,sources):
        with database.transaction() as db:
            row=db.execute('SELECT athlete,data FROM training_entries WHERE id=?',(entry['id'],)).fetchone()
            current=json.loads(row[1]);current['feedback']['correction']='A new correction during processing.'
            training.write_entry(db,row[0],current)
        return result(entry['id'])
    monkeypatch.setattr(research,'generate',modified)
    assert study(client,[entry]).status_code==409
    assert client.get('/api/v1/research').json()['studies']==[]


def test_style_study_works_without_changing_personal_practice_plan(client):
    register(client);entry=evidence(client,purpose='style')
    assert study(client,[entry],purpose='style').status_code==200
    assert client.get('/api/v1/training/development').json()['tasks']==[]
