"""La lectura del grafo no autoriza pisar archivos si otro request arrancó OASIS."""
import subprocess
import sys
from types import SimpleNamespace

import pytest

from app.api import simulation as api
from app.models.task import TaskManager
from app.services import simulation_manager as sm
from app.services.simulation_runner import SimulationRunner, SimulationRunState, RunnerStatus
from app.services.zep_entity_reader import EntityNode, FilteredEntities
from test_reprepare_failed import prepared, fake_preparation, client, storage, auth  # noqa: F401


@pytest.fixture
def harmless_process():
    process = subprocess.Popen([sys.executable, '-c', 'import sys; sys.stdin.read()'], stdin=subprocess.PIPE)
    try:
        yield process
    finally:
        process.communicate(timeout=5)


def snapshot(directory):
    return {path.name: path.read_bytes() for path in directory.iterdir() if path.is_file()}


@pytest.mark.parametrize('preview_count', [0, 1])
def test_start_during_preview_blocks_prepare_before_invalidation_or_worker(client, fake_preparation, monkeypatch, harmless_process, preview_count):
    _, state, directory = prepared()
    workers = []
    real_thread = api.threading.Thread
    class DeferredThread(real_thread):
        def __init__(self, target=None, **kwargs):
            real_thread.__init__(self, target=target, **kwargs)
            if target is not None:
                workers.append(target)
        def start(self):
            pass
    monkeypatch.setattr(api.threading, 'Thread', DeferredThread)
    def start(**kwargs):
        SimulationRunner._processes[state.simulation_id] = harmless_process
        return SimulationRunState(state.simulation_id, runner_status=RunnerStatus.RUNNING)
    monkeypatch.setattr(SimulationRunner, 'start_simulation', start)
    after_start = {}
    def preview(**kwargs):
        response = client.post('/api/simulation/start', headers=auth(), json={'simulation_id': state.simulation_id})
        assert response.status_code == 200
        assert sm.SimulationManager().get_simulation(state.simulation_id).status == sm.SimulationStatus.RUNNING
        after_start.update(snapshot(directory))
        nodes = [EntityNode('0', 'Actor 0', ['Person'], 'Sintético', {})] if preview_count else []
        return FilteredEntities(nodes, {'Person'}, preview_count, preview_count)
    monkeypatch.setattr(api, 'ZepEntityReader', lambda: SimpleNamespace(filter_defined_entities=preview))
    response = client.post('/api/simulation/prepare', headers=auth(), json={'simulation_id': state.simulation_id, 'force_regenerate': True})
    assert response.status_code == 409 and response.get_json()['success'] is False
    assert harmless_process.poll() is None and not workers
    assert snapshot(directory) == after_start
    assert TaskManager().list_tasks(task_type='simulation_prepare') == []


@pytest.mark.parametrize('status', [sm.SimulationStatus.RUNNING, sm.SimulationStatus.COMPLETED])
@pytest.mark.parametrize('direct', [False, True])
def test_live_process_including_completed_interview_environment_protects_files(client, fake_preparation, monkeypatch, harmless_process, status, direct):
    manager, state, directory = prepared()
    state.status = status
    manager._save_simulation_state(state)
    SimulationRunner._processes[state.simulation_id] = harmless_process
    before = snapshot(directory)
    if direct:
        with pytest.raises(sm.PreparationConflictError):
            manager.prepare_simulation(state.simulation_id, 'Escenario', 'Brief')
    else:
        response = client.post('/api/simulation/prepare', headers=auth(), json={'simulation_id': state.simulation_id, 'force_regenerate': True})
        assert response.status_code == 409
        assert TaskManager().list_tasks(task_type='simulation_prepare') == []
    assert harmless_process.poll() is None
    assert snapshot(directory) == before


def test_direct_stale_running_without_process_can_prepare(client, fake_preparation):
    manager, state, _ = prepared()
    state.status = sm.SimulationStatus.RUNNING
    manager._save_simulation_state(state)
    assert state.simulation_id not in SimulationRunner.live_processes()
    with pytest.raises(ValueError, match='semántica'):
        manager.prepare_simulation(state.simulation_id, 'Escenario', 'Brief')
    persisted = sm.SimulationManager().get_simulation(state.simulation_id)
    assert persisted.status == sm.SimulationStatus.FAILED
    assert persisted.profiles_count == 2 and not persisted.config_generated


def test_begin_reloads_current_state_and_only_copies_explicit_preview_fields(client):
    manager, stale, _ = prepared()
    fresh_manager = sm.SimulationManager()
    fresh = fresh_manager.get_simulation(stale.simulation_id)
    fresh.status = sm.SimulationStatus.RUNNING
    fresh.current_round = 31
    fresh.twitter_status = 'completed'
    fresh_manager._save_simulation_state(fresh)
    result = manager.begin_preparation(stale, entities_count=7, entity_types=['Public'])
    assert result is not stale
    assert result.current_round == 31 and result.twitter_status == 'completed'
    assert result.entities_count == 7 and result.entity_types == ['Public']
    assert result.status == sm.SimulationStatus.PREPARING and not result.config_generated
