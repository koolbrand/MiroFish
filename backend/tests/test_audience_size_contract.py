"""Requested public size is strict, persistent and separate from named actors."""
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.api import simulation as api
from app.config import Config
from app.models.project import ProjectManager
from app.models.task import TaskManager
from app.services import entity_role_filter as roles
from app.services import simulation_manager as sm
from app.services.zep_entity_reader import EntityNode, FilteredEntities
from test_cost_limits import auth, client  # noqa: F401
from test_pipeline import storage  # noqa: F401


def create():
    project = ProjectManager.create_project('Escenario sintético')
    project.simulation_requirement = 'Reacciones a una propuesta'
    ProjectManager.save_project(project)
    manager = sm.SimulationManager()
    return manager, manager.create_simulation(project.project_id, 'mirofish_synthetic')


def candidates(group_count=1, actor_count=79):
    groups = [EntityNode(f'g{i}', f'Colectivo {i}', ['Entity'], 'Público anónimo', {})
              for i in range(group_count)]
    actors = [EntityNode(f'a{i}', f'Actor {i}', ['Person'], 'Actor identificado', {'original': i})
              for i in range(actor_count)]
    return groups + actors


def classify(nodes, group_count):
    return roles.EntityRoleResult(
        kept=nodes, applied=True, classified=len(nodes),
        roles={'audiencia': group_count, 'implicado': len(nodes) - group_count},
        roles_by_uuid={e.uuid: 'audiencia' if i < group_count else 'implicado'
                       for i, e in enumerate(nodes)},
        population_group_ids=[e.uuid for e in nodes[:group_count]],
    )


@pytest.fixture
def queued(monkeypatch):
    monkeypatch.setattr(TaskManager(), '_tasks', {})
    nodes = candidates(actor_count=1)
    monkeypatch.setattr(api, 'ZepEntityReader', lambda: SimpleNamespace(
        filter_defined_entities=lambda **kwargs: FilteredEntities(nodes, {'Person'}, 2, 2)))
    targets = []
    real_thread = api.threading.Thread
    class DeferredThread(real_thread):
        def __init__(self, target=None, **kwargs):
            real_thread.__init__(self, target=target, **kwargs)
            if target is not None:
                targets.append(target)
        def start(self):
            pass
    monkeypatch.setattr(api.threading, 'Thread', DeferredThread)
    observed = []
    def prepare(manager, **kwargs):
        observed.append(kwargs)
        state = manager.get_simulation(kwargs['simulation_id'])
        state.status = sm.SimulationStatus.FAILED  # no provider, config or OASIS
        manager._save_simulation_state(state)
        return state
    monkeypatch.setattr(sm.SimulationManager, 'prepare_simulation', prepare)
    return targets, observed


@pytest.mark.parametrize('value', [4, 151, -1, True, False, 70.0, '70', [], {}])
def test_invalid_api_size_fails_before_preview_task_or_state_change(client, monkeypatch, value):
    _, state = create()
    before = Path(sm.SimulationManager.SIMULATION_DATA_DIR, state.simulation_id, 'state.json').read_bytes()
    monkeypatch.setattr(api, 'ZepEntityReader', lambda: pytest.fail('invalid input must not read graph'))
    monkeypatch.setattr(TaskManager(), '_tasks', {})
    response = client.post('/api/simulation/prepare', headers=auth(),
                           json={'simulation_id': state.simulation_id, 'audience_size': value})
    assert response.status_code == 400
    assert not TaskManager().list_tasks(task_type='simulation_prepare')
    assert Path(sm.SimulationManager.SIMULATION_DATA_DIR, state.simulation_id, 'state.json').read_bytes() == before


@pytest.mark.parametrize('value', [5, 70, 150, None])
def test_api_persists_before_worker_and_get_round_trips_explicit_or_auto(client, queued, value):
    _, state = create()
    targets, observed = queued
    response = client.post('/api/simulation/prepare', headers=auth(),
                           json={'simulation_id': state.simulation_id, 'audience_size': value})
    assert response.status_code == 200
    assert response.get_json()['data']['audience_size'] == value
    assert not observed and sm.SimulationManager().get_simulation(state.simulation_id).audience_size == value
    read = client.get('/api/simulation/' + state.simulation_id, headers=auth())
    assert read.status_code == 200 and read.get_json()['data']['audience_size'] == value
    targets[0]()
    assert observed[0]['audience_size'] == value


def test_omitted_value_preserves_selection_null_clears_and_active_retry_does_not_edit(client, queued):
    manager, state = create()
    state.audience_size = 70
    manager._save_simulation_state(state)
    targets, observed = queued
    first = client.post('/api/simulation/prepare', headers=auth(), json={'simulation_id': state.simulation_id})
    assert first.get_json()['data']['audience_size'] == 70
    retry = client.post('/api/simulation/prepare', headers=auth(),
                        json={'simulation_id': state.simulation_id, 'audience_size': None})
    assert retry.get_json()['data']['audience_size'] == 70 and len(targets) == 1
    targets[0]()
    assert observed[0]['audience_size'] == 70
    reset = client.post('/api/simulation/prepare', headers=auth(),
                        json={'simulation_id': state.simulation_id, 'audience_size': None})
    assert reset.get_json()['data']['audience_size'] is None
    assert sm.SimulationManager().get_simulation(state.simulation_id).audience_size is None


def test_legacy_state_missing_field_is_auto_without_rewriting(client):
    manager, state = create()
    path = Path(manager.SIMULATION_DATA_DIR, state.simulation_id, 'state.json')
    raw = json.loads(path.read_text())
    raw.pop('audience_size')
    path.write_text(json.dumps(raw))
    before = path.read_bytes()
    loaded = sm.SimulationManager().get_simulation(state.simulation_id)
    assert loaded.audience_size is None and loaded.to_simple_dict()['audience_size'] is None
    assert path.read_bytes() == before


def test_automatic_five_of_eighty_four_is_explained_by_variant_cap(monkeypatch):
    monkeypatch.setattr(Config, 'AUDIENCE_EXPANSION', True)
    monkeypatch.setattr(Config, 'JEV_MIN_AUDIENCE_RATIO', .4)
    monkeypatch.setattr(Config, 'AUDIENCE_MAX_EXTRA', 20)
    monkeypatch.setattr(Config, 'AUDIENCE_MAX_VARIANTS', 4)
    nodes = candidates()
    result = classify(nodes, 1)
    expanded = roles.expand_audience(nodes, result)
    assert len(expanded) == 84 and result.summary()['audience_count'] == 5
    assert result.summary()['audience_requested'] is None
    # Explicit choice preserves all 79 actors and expands only the public.
    nodes = candidates()
    actors_before = [(e.uuid, e.name, e.summary, dict(e.attributes)) for e in nodes[1:]]
    result = classify(nodes, 1)
    expanded = roles.expand_audience(nodes, result, target_size=70)
    assert len(expanded) == 149 and result.summary()['audience_count'] == 70
    assert result.summary()['audience_requested'] == 70
    assert [(e.uuid, e.name, e.summary, e.attributes) for e in expanded[1:80]] == actors_before


@pytest.mark.parametrize('group_count, requested', [(0, 70), (6, 5)])
def test_impossible_explicit_target_fails_before_any_profile_generation(client, monkeypatch, group_count, requested):
    manager, state = create()
    nodes = candidates(group_count, 2)
    monkeypatch.setattr(sm, 'ZepEntityReader', lambda: SimpleNamespace(
        filter_defined_entities=lambda **kwargs: FilteredEntities(nodes, {'Entity'}, len(nodes), len(nodes))))
    monkeypatch.setattr(sm, 'filter_entities', lambda *args: classify(nodes, group_count))
    monkeypatch.setattr(sm, 'OasisProfileGenerator', lambda **kwargs: pytest.fail('no profiles for impossible target'))
    with pytest.raises(ValueError):
        manager.prepare_simulation(state.simulation_id, 'Escenario', 'Fuente sintética', audience_size=requested)
    persisted = sm.SimulationManager().get_simulation(state.simulation_id)
    assert persisted.status == sm.SimulationStatus.FAILED and not persisted.config_generated
    assert persisted.audience_size == requested and persisted.entity_filter['audience_count'] == group_count


@pytest.mark.parametrize('anchored, tag_actors, succeeds', [(69, True, False), (70, False, True), (70, True, False)])
def test_real_data_requires_exact_public_anchors_and_excludes_institution_tags(client, monkeypatch, anchored, tag_actors, succeeds):
    manager, state = create()
    nodes = candidates(actor_count=2)
    monkeypatch.setattr(sm, 'ZepEntityReader', lambda: SimpleNamespace(
        filter_defined_entities=lambda **kwargs: FilteredEntities(nodes, {'Entity'}, 3, 3)))
    monkeypatch.setattr(sm, 'filter_entities', lambda *args: classify(nodes, 1))
    monkeypatch.setattr(sm.poblacion, 'modo_activo', lambda pedido: True)
    seen = []
    class Profiles:
        def __init__(self, **kwargs):
            pass
        def generate_profiles_from_entities(self, **kwargs):
            assert kwargs['required_audience_size'] == 70
            seen.extend(kwargs['entities'])
            public = [i for i, e in enumerate(kwargs['entities']) if e.attributes.get(roles.INDIVIDUAL_FLAG)]
            tagged = set(public[:anchored]) | ({1, 2} if tag_actors else set())
            return [SimpleNamespace(user_id=i, data_source='Synthetic survey' if i in tagged else None,
                                    data_ref='study-test' if i in tagged else None)
                    for i in range(len(kwargs['entities']))]
        def save_profiles(self, **kwargs):
            pass
    monkeypatch.setattr(sm, 'OasisProfileGenerator', Profiles)
    config_calls = []
    def config(**kwargs):
        config_calls.append(kwargs)
        return SimpleNamespace(generation_reasoning='Synthetic test', to_json=lambda: '{}')
    monkeypatch.setattr(sm, 'SimulationConfigGenerator', lambda: SimpleNamespace(generate_config=config))
    if succeeds:
        manager.prepare_simulation(state.simulation_id, 'Escenario', 'Fuente sintética', audience_size=70, poblacion_datos=True)
    else:
        with pytest.raises(ValueError):
            manager.prepare_simulation(state.simulation_id, 'Escenario', 'Fuente sintética', audience_size=70, poblacion_datos=True)
    persisted = sm.SimulationManager().get_simulation(state.simulation_id)
    assert len(seen) == 72 and persisted.entity_filter['audience_survey_count'] == anchored
    assert bool(config_calls) is succeeds
    assert persisted.status == (sm.SimulationStatus.READY if succeeds else sm.SimulationStatus.FAILED)
    assert persisted.config_generated is succeeds


@pytest.mark.parametrize('value', [True, '70', 70.0, 151])
def test_direct_manager_rejects_invalid_before_invalidation(client, value):
    manager, state = create()
    with pytest.raises(ValueError):
        manager.prepare_simulation(state.simulation_id, 'Escenario', 'Fuente', audience_size=value)
    assert sm.SimulationManager().get_simulation(state.simulation_id).status == sm.SimulationStatus.CREATED


def test_explicit_real_data_without_bank_does_not_silently_generate_synthetic_public(client, monkeypatch):
    manager, state = create()
    nodes = candidates(actor_count=1)
    monkeypatch.setattr(sm, 'ZepEntityReader', lambda: SimpleNamespace(
        filter_defined_entities=lambda **kwargs: FilteredEntities(nodes, {'Entity'}, 2, 2)))
    monkeypatch.setattr(sm, 'filter_entities', lambda *args: classify(nodes, 1))
    monkeypatch.setattr(sm.poblacion, 'disponibles', lambda: [])
    monkeypatch.setattr(sm, 'OasisProfileGenerator', lambda **kwargs: pytest.fail('no synthetic fallback for required data'))
    with pytest.raises(ValueError):
        manager.prepare_simulation(state.simulation_id, 'Escenario', 'Fuente', audience_size=70, poblacion_datos=True)
    loaded = sm.SimulationManager().get_simulation(state.simulation_id)
    assert loaded.status == sm.SimulationStatus.FAILED and loaded.profiles_count == 0
    assert loaded.entity_filter['audience_count'] == 70
