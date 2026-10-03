"""Generic graph labels must not hide the public before role classification."""
import pytest

from app.config import Config
from app.services import entity_role_filter as roles
from app.services.zep_entity_reader import ZepEntityReader
from test_pipeline import storage  # noqa: F401 — storage sintético compartido


def reader(monkeypatch):
    nodes = [
        dict(uuid='party', name='Partido sintético', labels=['Entity', 'Party'],
             summary='Una organización política que opina.', attributes={}),
        dict(uuid='voters', name='Electorado español', labels=['Entity'],
             summary='Personas adultas con derecho a voto, el único público.', attributes={}),
        dict(uuid='judge', name='Juez sintético', labels=['Entity'],
             summary='Un magistrado identificado, citado en un proceso judicial.', attributes={}),
        dict(uuid='law', name='Ley sintética', labels=['Entity'],
             summary='Texto legal pendiente de aprobación, no tiene voz propia.', attributes={}),
    ]
    edges = [dict(uuid='edge', name='DISCUSSES', fact='Contexto original',
                  source_node_uuid='party', target_node_uuid='voters', attributes={})]
    instance = object.__new__(ZepEntityReader)
    monkeypatch.setattr(instance, 'get_all_nodes', lambda graph_id: nodes)
    monkeypatch.setattr(instance, 'get_all_edges', lambda graph_id: edges)
    return instance


def configure_classifier(monkeypatch):
    monkeypatch.setattr(Config, 'JEV_ENTITY_FILTER', True)
    monkeypatch.setattr(Config, 'TYPESAFE_API_KEY', 'offline-synthetic')
    answers = {
        'party': dict(role='implicado', confidence=.99, organization=.99),
        'voters': dict(role='audiencia', confidence=.99, population_group=.99, named_person=.01),
        'judge': dict(role='audiencia', confidence=.99, population_group=.01, named_person=.99),
        'law': dict(role='infraestructura', confidence=.99, thing=.99),
    }
    monkeypatch.setattr(roles, '_ask_jev', lambda client, entity, topic: answers[entity.uuid])


def test_mixed_graph_delivers_untyped_public_with_context_to_classifier(monkeypatch):
    instance = reader(monkeypatch)
    candidates = instance.filter_defined_entities('mirofish_synthetic', include_untyped=True)
    assert candidates.total_count == candidates.filtered_count == 4
    assert candidates.entity_types == {'Party', 'Entity'}
    voters = next(e for e in candidates.entities if e.uuid == 'voters')
    assert voters.labels == ['Entity'] and voters.attributes == {}
    assert voters.related_edges[0]['source_node_uuid'] == 'party'
    assert voters.related_nodes[0]['uuid'] == 'party'
    configure_classifier(monkeypatch)
    result = roles.filter_entities(candidates.entities, 'Elecciones sintéticas')
    expanded = roles.expand_audience(result.kept, result, target_size=70)
    public = [e for e in expanded if e.attributes.get(roles.INDIVIDUAL_FLAG)]
    assert len(public) == 70
    assert {e.attributes[roles.GROUP_KEY] for e in public} == {'voters'}
    assert len(expanded) == 72  # one party and one identified judge remain actors
    judge = next(e for e in expanded if e.uuid == 'judge')
    assert judge.name == 'Juez sintético' and not judge.attributes.get(roles.INDIVIDUAL_FLAG)
    assert not any(e.uuid == 'law' for e in expanded)
    assert not next(e for e in expanded if e.uuid == 'party').attributes.get(roles.INDIVIDUAL_FLAG)


@pytest.mark.parametrize('allowed', [['Party'], ['Person'], ['Entity']])
def test_explicit_type_filter_is_not_bypassed_by_candidate_mode(monkeypatch, allowed):
    instance = reader(monkeypatch)
    result = instance.filter_defined_entities('mirofish_synthetic', defined_entity_types=allowed,
                                             include_untyped=True)
    assert [e.uuid for e in result.entities] == (['party'] if allowed == ['Party'] else [])


def test_default_reader_keeps_existing_type_lookup_contract(monkeypatch):
    instance = reader(monkeypatch)
    assert [e.uuid for e in instance.filter_defined_entities('mirofish_synthetic').entities] == ['party']
    assert [e.uuid for e in instance.get_entities_by_type('mirofish_synthetic', 'Party')] == ['party']


def test_missing_classifier_does_not_turn_generic_candidates_into_population(monkeypatch):
    candidates = reader(monkeypatch).filter_defined_entities('mirofish_synthetic', include_untyped=True)
    monkeypatch.setattr(Config, 'JEV_ENTITY_FILTER', True)
    monkeypatch.setattr(Config, 'TYPESAFE_API_KEY', '')
    result = roles.filter_entities(candidates.entities, 'Elecciones sintéticas')
    expanded = roles.expand_audience(result.kept, result, target_size=70)
    assert len(expanded) == 4 and not result.applied
    assert not any(e.attributes.get(roles.INDIVIDUAL_FLAG) for e in expanded)


def test_real_preparation_includes_generic_candidates_before_profile_generation(tmp_path, monkeypatch):
    from app.services import simulation_manager as manager_module
    instance = reader(monkeypatch)
    configure_classifier(monkeypatch)
    monkeypatch.setattr(manager_module, 'ZepEntityReader', lambda: instance)
    monkeypatch.setattr(manager_module.SimulationManager, 'SIMULATION_DATA_DIR', str(tmp_path))
    monkeypatch.setattr(manager_module.poblacion, 'modo_activo', lambda pedido: True)
    observed = []

    class Profiles:
        def __init__(self, **kwargs):
            pass

        def generate_profiles_from_entities(self, **kwargs):
            observed.extend(kwargs['entities'])
            raise RuntimeError('offline-stop-before-model')

    monkeypatch.setattr(manager_module, 'OasisProfileGenerator', Profiles)
    manager = manager_module.SimulationManager()
    sid = manager.create_simulation('proj_synthetic', 'mirofish_synthetic').simulation_id
    with pytest.raises(RuntimeError, match='offline-stop-before-model'):
        manager.prepare_simulation(sid, 'Elecciones sintéticas', 'Brief sintético',
                                   audience_size=70, poblacion_datos=True)
    assert len(observed) == 72
    assert sum(bool(e.attributes.get(roles.INDIVIDUAL_FLAG)) for e in observed) == 70
    state = manager.get_simulation(sid)
    assert state.entity_filter['population_groups'] == 1


@pytest.mark.parametrize('types, expected', [(None, 4), (['Party'], 1)])
def test_prepare_endpoint_preview_counts_the_same_candidates_as_preparation(storage, monkeypatch, types, expected):
    from app import create_app
    from app.api import simulation as api
    from app.models.project import ProjectManager
    from app.models.task import TaskManager
    from app.services.simulation_manager import SimulationManager
    import threading

    monkeypatch.setattr(Config, 'API_AUTH_REQUIRED', False)
    app = create_app()
    app.config['TESTING'] = True
    app.config['RATELIMIT_ENABLED'] = False
    project = ProjectManager.create_project(name='Escenario sintético')
    project.graph_id = 'mirofish_synthetic'
    project.simulation_requirement = 'Elecciones sintéticas'
    ProjectManager.save_project(project)
    sid = SimulationManager().create_simulation(project.project_id, project.graph_id).simulation_id
    monkeypatch.setattr(api, 'ZepEntityReader', lambda: reader(monkeypatch))
    monkeypatch.setattr(TaskManager(), '_tasks', {})

    class DeferredThread(threading.Thread):
        def start(self):
            pass  # no modelo: esta prueba solo observa el preview síncrono real

    monkeypatch.setattr(threading, 'Thread', DeferredThread)
    response = app.test_client().post('/api/simulation/prepare', json={
        'simulation_id': sid, 'entity_types': types,
    })
    assert response.status_code == 200, response.get_json()
    assert response.get_json()['data']['expected_entities_count'] == expected
