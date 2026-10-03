"""Un intento nuevo fallido no acredita archivos conservados de un intento anterior."""
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.api import simulation as api
from app.config import Config
from app.models.project import ProjectManager
from app.models.task import TaskManager
from app.services import simulation_manager as sm
from app.services.oasis_profile_generator import OasisAgentProfile, OasisProfileGenerator
from app.services.simulation_runner import SimulationRunner, RunnerStatus, SimulationRunState
from app.services.zep_entity_reader import EntityNode, FilteredEntities
from test_cost_limits import auth, client  # noqa: F401
from test_pipeline import storage  # noqa: F401


def profile(i):
    return OasisAgentProfile(i, f'user_{i}', f'Actor {i}', 'Bio sintética', 'Opinión simulada')


def prepared():
    project = ProjectManager.create_project('P', owner_id=None)
    project.simulation_requirement = 'Ensayar reacciones'
    ProjectManager.save_project(project)
    ProjectManager.save_extracted_text(project.project_id, 'Brief sintético.')
    manager = sm.SimulationManager()
    state = manager.create_simulation(project.project_id, 'mirofish_synthetic')
    state.status = sm.SimulationStatus.READY
    state.config_generated = True
    state.config_reasoning = 'Razón antigua'
    state.profiles_count = 1
    state.error = 'Error anterior'
    manager._save_simulation_state(state)
    directory = Path(manager._get_simulation_dir(state.simulation_id))
    (directory / 'simulation_config.json').write_text(json.dumps({'agent_configs': [{'agent_id': 0, 'entity_name': 'Actor 0'}]}))
    writer = OasisProfileGenerator.__new__(OasisProfileGenerator)
    for platform, filename in [('reddit', 'reddit_profiles.json'), ('twitter', 'twitter_profiles.csv')]:
        writer.save_profiles([profile(0)], str(directory / filename), platform)
    (directory / 'actions.jsonl').write_text('historia anterior\n')
    return manager, state, directory


@pytest.fixture
def fake_preparation(monkeypatch):
    monkeypatch.setattr(Config, 'JEV_ENTITY_FILTER', False)
    nodes = [EntityNode(str(i), f'Actor {i}', ['Entity', 'Person'], 'Resumen', {}) for i in range(2)]
    reader = lambda: SimpleNamespace(filter_defined_entities=lambda **kwargs: FilteredEntities(nodes, {'Person'}, 2, 2))
    monkeypatch.setattr(sm, 'ZepEntityReader', reader)
    monkeypatch.setattr(api, 'ZepEntityReader', reader)
    class Profiles(OasisProfileGenerator):
        def __init__(self, **kwargs):
            pass
        def generate_profiles_from_entities(self, **kwargs):
            return [profile(0), profile(1)]
    monkeypatch.setattr(sm, 'OasisProfileGenerator', Profiles)
    class ConfigGenerator:
        def generate_config(self, **kwargs):
            raise ValueError('La validación semántica de semillas rechazó el contenido')
    monkeypatch.setattr(sm, 'SimulationConfigGenerator', ConfigGenerator)
    monkeypatch.setattr(TaskManager(), '_tasks', {})


def assert_not_startable(client, sid):
    for force in (False, True):
        response = client.post('/api/simulation/start', headers=auth(), json={'simulation_id': sid, 'force': force})
        assert response.status_code == 400 and response.get_json()['success'] is False


def test_direct_ready_to_new_profiles_to_validation_failure_is_not_prepared(client, fake_preparation, monkeypatch):
    manager, state, directory = prepared()
    config_before = (directory / 'simulation_config.json').read_bytes()
    observed = []
    def progress(stage, progress, message, **kwargs):
        observed.append(sm.SimulationManager().get_simulation(state.simulation_id).config_generated)
    with pytest.raises(ValueError, match='semántica'):
        manager.prepare_simulation(state.simulation_id, 'Escenario', 'Brief', progress_callback=progress)
    persisted = sm.SimulationManager().get_simulation(state.simulation_id)
    assert persisted.status == sm.SimulationStatus.FAILED
    assert persisted.config_generated is False and persisted.config_reasoning == ''
    assert persisted.profiles_count == 2 and not any(observed)
    assert len(json.loads((directory / 'reddit_profiles.json').read_text())) == 2
    assert (directory / 'simulation_config.json').read_bytes() == config_before
    assert (directory / 'actions.jsonl').read_text() == 'historia anterior\n'
    monkeypatch.setattr(SimulationRunner, 'start_simulation', lambda **kwargs: pytest.fail('no OASIS'))
    assert api._check_simulation_prepared(state.simulation_id)[0] is False
    response = client.post('/api/simulation/prepare/status', headers=auth(), json={'simulation_id': state.simulation_id})
    assert response.get_json()['data']['already_prepared'] is False
    assert_not_startable(client, state.simulation_id)


def test_api_invalidates_before_worker_and_failed_task_stays_unprepared(client, fake_preparation, monkeypatch):
    _, state, directory = prepared()
    targets = []
    real_thread = api.threading.Thread
    class DeferredThread(real_thread):
        def __init__(self, target=None, **kwargs):
            # threading.Timer invoca Thread.__init__ sin target: sigue siendo
            # un hilo real del limitador, solo diferimos el worker de prepare.
            real_thread.__init__(self, target=target, **kwargs)
            if target is not None:
                targets.append(target)
        def start(self):
            pass
    monkeypatch.setattr(api.threading, 'Thread', DeferredThread)
    monkeypatch.setattr(SimulationRunner, 'start_simulation', lambda **kwargs: pytest.fail('no OASIS'))
    response = client.post('/api/simulation/prepare', headers=auth(), json={'simulation_id': state.simulation_id, 'force_regenerate': True})
    monkeypatch.setattr(api.threading, 'Thread', real_thread)
    assert response.status_code == 200
    repeated = client.post('/api/simulation/prepare', headers=auth(), json={'simulation_id': state.simulation_id, 'force_regenerate': True})
    assert repeated.status_code == 200
    assert repeated.get_json()['data']['task_id'] == response.get_json()['data']['task_id']
    assert len(targets) == 1
    persisted = sm.SimulationManager().get_simulation(state.simulation_id)
    assert persisted.status == sm.SimulationStatus.PREPARING
    assert not persisted.config_generated and persisted.profiles_count == 0 and persisted.error is None
    assert api._check_simulation_prepared(state.simulation_id)[0] is False
    assert_not_startable(client, state.simulation_id)
    targets[0]()
    persisted = sm.SimulationManager().get_simulation(state.simulation_id)
    assert persisted.status == sm.SimulationStatus.FAILED and not persisted.config_generated
    task_id = response.get_json()['data']['task_id']
    response = client.post('/api/simulation/prepare/status', headers=auth(), json={'simulation_id': state.simulation_id, 'task_id': task_id})
    assert response.get_json()['data']['status'] == 'failed'
    assert_not_startable(client, state.simulation_id)


@pytest.mark.parametrize('status', [sm.SimulationStatus.PREPARING, sm.SimulationStatus.FAILED])
@pytest.mark.parametrize('platform', ['reddit', 'twitter'])
def test_legacy_mixed_files_are_rejected_without_mutating_history(client, monkeypatch, status, platform):
    manager, state, directory = prepared()
    state.status = status
    manager._save_simulation_state(state)
    writer = OasisProfileGenerator.__new__(OasisProfileGenerator)
    filename = 'reddit_profiles.json' if platform == 'reddit' else 'twitter_profiles.csv'
    writer.save_profiles([profile(0), profile(1)], str(directory / filename), platform)
    snapshot = {path.name: path.read_bytes() for path in directory.iterdir()}
    monkeypatch.setattr(SimulationRunner, 'start_simulation', lambda **kwargs: pytest.fail('no OASIS'))
    assert api._check_simulation_prepared(state.simulation_id)[0] is False
    assert_not_startable(client, state.simulation_id)
    assert {path.name: path.read_bytes() for path in directory.iterdir()} == snapshot


@pytest.mark.parametrize('status', [sm.SimulationStatus.FAILED, sm.SimulationStatus.COMPLETED, sm.SimulationStatus.STOPPED])
def test_historical_valid_preparation_remains_restartable(client, monkeypatch, status):
    manager, state, directory = prepared()
    state.status = status
    manager._save_simulation_state(state)
    before = (directory / 'state.json').read_bytes()
    assert api._check_simulation_prepared(state.simulation_id)[0] is True
    assert (directory / 'state.json').read_bytes() == before
    calls = []
    def start(**kwargs):
        calls.append(kwargs)
        return SimulationRunState(state.simulation_id, runner_status=RunnerStatus.RUNNING)
    monkeypatch.setattr(SimulationRunner, 'start_simulation', start)
    response = client.post('/api/simulation/start', headers=auth(), json={'simulation_id': state.simulation_id})
    assert response.status_code == 200 and len(calls) == 1
    assert (directory / 'actions.jsonl').read_text() == 'historia anterior\n'


@pytest.mark.parametrize('status', [sm.SimulationStatus.PREPARING, sm.SimulationStatus.FAILED])
def test_historical_runner_does_not_resurrect_new_preparation(client, monkeypatch, status):
    manager, state, directory = prepared()
    state = manager.begin_preparation(state)
    state.status = status
    manager._save_simulation_state(state)
    monkeypatch.setattr(SimulationRunner, 'get_run_state', lambda sid: SimulationRunState(sid, runner_status=RunnerStatus.COMPLETED))
    before = (directory / 'state.json').read_bytes()
    response = client.get(f'/api/simulation/{state.simulation_id}', headers=auth())
    assert response.status_code == 200 and response.get_json()['data']['status'] == status.value
    assert (directory / 'state.json').read_bytes() == before


def test_ready_flag_false_cannot_bypass_start(client, monkeypatch):
    manager, state, _ = prepared()
    state.config_generated = False
    manager._save_simulation_state(state)
    monkeypatch.setattr(SimulationRunner, 'start_simulation', lambda **kwargs: pytest.fail('no OASIS'))
    assert_not_startable(client, state.simulation_id)


@pytest.mark.parametrize('config', [{}, {'agent_configs': []}, {'agent_configs': None}, {'agent_configs': {}}, {'agent_configs': [1]}, {'agent_configs': [{'agent_id': 0}]}])
def test_missing_or_malformed_agent_config_is_not_prepared(client, monkeypatch, config):
    _, state, directory = prepared()
    (directory / 'simulation_config.json').write_text(json.dumps(config))
    monkeypatch.setattr(SimulationRunner, 'start_simulation', lambda **kwargs: pytest.fail('no OASIS'))
    assert api._check_simulation_prepared(state.simulation_id)[0] is False
    assert_not_startable(client, state.simulation_id)


@pytest.mark.parametrize('platform', ['reddit', 'twitter'])
def test_same_ids_assigned_to_different_actor_cannot_reuse_old_config(client, monkeypatch, platform):
    manager, state, directory = prepared()
    state.status = sm.SimulationStatus.FAILED
    manager._save_simulation_state(state)
    replacement = profile(0)
    replacement.name = 'Otro actor'
    writer = OasisProfileGenerator.__new__(OasisProfileGenerator)
    writer.save_profiles([replacement], str(directory / ('reddit_profiles.json' if platform == 'reddit' else 'twitter_profiles.csv')), platform)
    monkeypatch.setattr(SimulationRunner, 'start_simulation', lambda **kwargs: pytest.fail('no OASIS'))
    assert api._check_simulation_prepared(state.simulation_id)[0] is False
    assert_not_startable(client, state.simulation_id)


def test_preparing_with_old_true_flag_is_never_promoted_by_reading(client, monkeypatch):
    manager, state, directory = prepared()
    state.status = sm.SimulationStatus.PREPARING
    manager._save_simulation_state(state)
    before = (directory / 'state.json').read_bytes()
    monkeypatch.setattr(SimulationRunner, 'start_simulation', lambda **kwargs: pytest.fail('no OASIS'))
    assert api._check_simulation_prepared(state.simulation_id)[0] is False
    assert_not_startable(client, state.simulation_id)
    assert (directory / 'state.json').read_bytes() == before


def test_zero_entity_preview_invalidates_previous_preparation_without_worker(client, monkeypatch):
    _, state, _ = prepared()
    monkeypatch.setattr(api, 'ZepEntityReader', lambda: SimpleNamespace(
        filter_defined_entities=lambda **kwargs: FilteredEntities([], set(), 0, 0)))
    monkeypatch.setattr(SimulationRunner, 'start_simulation', lambda **kwargs: pytest.fail('no OASIS'))
    response = client.post('/api/simulation/prepare', headers=auth(), json={'simulation_id': state.simulation_id, 'force_regenerate': True})
    assert response.status_code == 400
    persisted = sm.SimulationManager().get_simulation(state.simulation_id)
    assert persisted.status == sm.SimulationStatus.FAILED and not persisted.config_generated
    assert_not_startable(client, state.simulation_id)


def test_existing_failed_76_config_84_profiles_remains_failed_on_read(client, monkeypatch):
    manager, state, directory = prepared()
    state.status = sm.SimulationStatus.FAILED
    state.profiles_count = 84
    manager._save_simulation_state(state)
    (directory / 'simulation_config.json').write_text(json.dumps({'agent_configs': [
        {'agent_id': i, 'entity_name': f'Actor {i}'} for i in range(76)]}))
    writer = OasisProfileGenerator.__new__(OasisProfileGenerator)
    for platform, filename in [('reddit', 'reddit_profiles.json'), ('twitter', 'twitter_profiles.csv')]:
        writer.save_profiles([profile(i) for i in range(84)], str(directory / filename), platform)
    monkeypatch.setattr(SimulationRunner, 'get_run_state', lambda sid: SimulationRunState(sid, runner_status=RunnerStatus.COMPLETED))
    monkeypatch.setattr(SimulationRunner, 'start_simulation', lambda **kwargs: pytest.fail('no OASIS'))
    before = {path.name: path.read_bytes() for path in directory.iterdir()}
    response = client.get(f'/api/simulation/{state.simulation_id}', headers=auth())
    assert response.status_code == 200 and response.get_json()['data']['status'] == 'failed'
    assert api._check_simulation_prepared(state.simulation_id)[0] is False
    assert_not_startable(client, state.simulation_id)
    assert {path.name: path.read_bytes() for path in directory.iterdir()} == before
