"""Effective API fallback consumes canonical metadata rather than free biographies."""
import csv
import json
from pathlib import Path

import pytest

from app.api import simulation as api
from app.services.profile_memory import canonical_metadata
from app.services.simulation_manager import SimulationManager
from test_pipeline import storage  # noqa: F401
from test_cost_limits import client, auth  # noqa: F401


SIM = 'sim_aaaaaaaaaaaa'


def profile():
    return dict(canonical_metadata('Actora A estudia una propuesta; no la ha aprobado.', 'Actora A', 'named_actor'),
                user_id=0, name='Actora A', username='actora_a', bio='FREE BIO MUST NOT ENTER MEMORY',
                persona='FREE PERSONA MUST NOT ENTER MEMORY')


def write_csv(value, marker='1'):
    folder = Path(SimulationManager.SIMULATION_DATA_DIR, SIM)
    folder.mkdir()
    row = {'name': 'Actora A', 'username': 'actora_a', 'user_id': '0', 'description': 'legacy bio',
           'user_char': 'legacy persona', 'profile_schema_version': marker,
           'profile_metadata': json.dumps(value)}
    with (folder / 'twitter_profiles.csv').open('w', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=list(row))
        writer.writeheader()
        writer.writerow(row)
    return folder


def test_csv_preserves_full_canonical_memory_for_fallback(storage):
    expected = profile()
    write_csv(expected)
    assert api._load_simulation_profiles(SIM) == [expected]


@pytest.mark.parametrize('marker', ['', '2'])
def test_csv_metadata_never_degrades_silently_to_legacy_free_biography(storage, marker):
    write_csv(profile(), marker)
    with pytest.raises(ValueError):
        api._load_simulation_profiles(SIM)


def test_legacy_csv_remains_readable(storage):
    folder = Path(SimulationManager.SIMULATION_DATA_DIR, SIM)
    folder.mkdir()
    (folder / 'twitter_profiles.csv').write_text('name,username,description,user_char\nLegacy,legacy,Bio,Persona\n')
    assert api._load_simulation_profiles(SIM)[0]['bio'] == 'Bio'


def test_effective_fallback_excludes_generated_summary_and_free_bio_for_canonical_actor(monkeypatch):
    monkeypatch.setattr(api, '_load_simulation_profiles', lambda sid: [profile()])
    monkeypatch.setattr(api, '_load_simulation_context', lambda sid: {
        'project_name': 'Synthetic scenario', 'simulation_requirement': '¿Cómo respondería?',
        'analysis_summary': 'GENERATED SUMMARY CLAIMS ACTOR ALREADY APPROVED',
    })
    captured = []
    class FakeLLM:
        def chat(self, **kwargs):
            captured.append(kwargs['messages'])
            return 'Una opinión simulada.'
    monkeypatch.setattr(api, 'LLMClient', FakeLLM)
    result = api._build_interview_llm_fallback_payload(SIM, [{'agent_id': 0, 'prompt': '¿Qué opina?'}])
    assert result['success'] is True and len(captured) == 1
    system = captured[0][0]['content']
    assert 'no la ha aprobado' in system
    assert 'INITIAL REFERENCE MEMORY' in system
    assert 'FREE BIO' not in system and 'FREE PERSONA' not in system
    assert 'GENERATED SUMMARY' not in system


def test_start_api_reports_effective_immutable_policy_even_if_graph_update_was_requested(client, monkeypatch):
    from types import SimpleNamespace
    from test_reprepare_failed import prepared
    from app.services.simulation_runner import SimulationRunner
    _, state, _ = prepared()
    policy = {'source_graph': 'immutable', 'graph_update': 'blocked_for_canonical_profiles', 'requested': True}
    seen = []
    def start(**kwargs):
        seen.append(kwargs)
        return SimpleNamespace(memory_policy=policy, to_dict=lambda: {'memory_policy': policy})
    monkeypatch.setattr(SimulationRunner, 'start_simulation', start)
    response = client.post('/api/simulation/start', headers=auth(), json={
        'simulation_id': state.simulation_id, 'enable_graph_memory_update': True,
    })
    assert response.status_code == 200
    assert seen[0]['enable_graph_memory_update'] is True
    assert response.get_json()['data']['graph_memory_update_enabled'] is False
    assert response.get_json()['data']['memory_policy'] == policy


@pytest.mark.parametrize('version', [True, False, '1', '2', 1.0, 2, 0])
def test_reddit_incompatible_contract_fails_before_fallback_llm_even_with_free_bio(storage, monkeypatch, version):
    folder = Path(SimulationManager.SIMULATION_DATA_DIR, SIM)
    folder.mkdir()
    raw = dict(profile(), profile_schema_version=version)
    (folder / 'reddit_profiles.json').write_text(json.dumps([raw]))
    monkeypatch.setattr(api, 'LLMClient', lambda: pytest.fail('incompatible version must not instantiate LLM'))
    result = api._build_interview_llm_fallback_payload(SIM, [{'agent_id': 0, 'prompt': 'Pregunta'}])
    assert result['success'] is False and 'no compatible' in result['error']
    assert 'FREE BIO' not in result['error'] and 'FREE PERSONA' not in result['error']


@pytest.mark.parametrize('version', [None, 'absent'])
def test_reddit_legacy_null_or_absent_version_remains_readable(storage, version):
    folder = Path(SimulationManager.SIMULATION_DATA_DIR, SIM)
    folder.mkdir()
    legacy = {'name': 'Legacy', 'bio': 'Legacy biography'}
    if version is None:
        legacy['profile_schema_version'] = None
    (folder / 'reddit_profiles.json').write_text(json.dumps([legacy]))
    assert api._load_simulation_profiles(SIM) == [legacy]


@pytest.mark.parametrize('marker', ['', '2', 'True', '1.0'])
def test_csv_incompatible_metadata_cannot_call_fallback_llm(storage, monkeypatch, marker):
    write_csv(profile(), marker)
    monkeypatch.setattr(api, 'LLMClient', lambda: pytest.fail('CSV contract failure must not instantiate LLM'))
    result = api._build_interview_llm_fallback_payload(SIM, [{'agent_id': 0, 'prompt': 'Pregunta'}])
    assert result['success'] is False
    assert 'FREE BIO' not in result['error'] and 'FREE PERSONA' not in result['error']
