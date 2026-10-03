"""Colectivos muestreables y actores identificados: regresión del caso electoral."""
import pytest

from app.config import Config
from app.services import entity_role_filter as erf
from app.services.zep_entity_reader import EntityNode


def entity(uuid, name, summary):
    return EntityNode(uuid=uuid, name=name, labels=['Entity', 'Person'],
                      summary=summary, attributes={}, related_edges=[{'fact': 'contexto original'}],
                      related_nodes=[{'name': 'actor relacionado'}])


def setup(monkeypatch, answers):
    monkeypatch.setattr(Config, 'JEV_ENTITY_FILTER', True)
    monkeypatch.setattr(Config, 'TYPESAFE_API_KEY', 'synthetic-test')
    monkeypatch.setattr(erf, '_ask_jev', lambda c, e, t: answers[e.uuid])


def test_judge_remains_one_actor_and_only_electorate_becomes_seventy_people(monkeypatch):
    judge = entity('judge', 'Biedma', 'Juez citado como perjudicado en una causa; declaración pendiente.')
    audience = entity('voters', 'Electorado español', 'Personas adultas con derecho a voto.')
    setup(monkeypatch, {
        'judge': {'role': 'audiencia', 'confidence': .99, 'named_person': .99, 'population_group': .01},
        'voters': {'role': 'audiencia', 'confidence': .99, 'named_person': .01, 'population_group': .99},
    })
    result = erf.filter_entities([judge, audience], 'elecciones')
    out = erf.expand_audience(result.kept, result, 'elecciones', target_size=70)
    sampled = [e for e in out if e.attributes.get(erf.INDIVIDUAL_FLAG)]
    assert len(out) == 71 and len(sampled) == 70
    assert {e.attributes[erf.GROUP_KEY] for e in sampled} == {'voters'}
    assert [e for e in out if e.uuid == 'judge'] == [judge]
    assert judge.name == 'Biedma' and judge.summary.startswith('Juez citado')
    assert judge.related_edges == [{'fact': 'contexto original'}]
    assert judge.related_nodes == [{'name': 'actor relacionado'}]
    assert result.roles_by_uuid['judge'] == 'audiencia'
    assert result.summary()['population_groups'] == 1
    assert result.summary()['population_unconfirmed'] == ['Biedma']
    assert not judge.attributes.get(erf.INDIVIDUAL_FLAG)


def test_uncertain_or_missing_nature_never_substitutes_a_named_person(monkeypatch):
    for classification in ({'role': 'audiencia', 'confidence': .99},
                           {'role': 'audiencia', 'confidence': .99, 'population_group': .55},
                           {'role': 'audiencia', 'confidence': .5, 'population_group': .95}):
        person = entity('person', 'Consumidora identificada', 'Autora de una reseña del producto.')
        # Marcas residuales no convierten la duda nueva en permiso para anclar.
        person.attributes = {erf.INDIVIDUAL_FLAG: True, erf.GROUP_KEY: 'old', 'original': 'value'}
        setup(monkeypatch, {'person': classification})
        result = erf.filter_entities([person], 'producto')
        out = erf.expand_audience(result.kept, result, target_size=50)
        assert out == [person] and person.attributes == {'original': 'value'}
        assert result.roles_by_uuid['person'] == 'audiencia'
        assert result.summary()['population_groups'] == 0


def test_conflicting_natures_do_not_allow_population_anchoring(monkeypatch):
    person = entity('person', 'Persona identificada', 'Un actor concreto.')
    setup(monkeypatch, {'person': {'role': 'audiencia', 'confidence': .99,
                                  'named_person': .8, 'population_group': .7}})
    result = erf.filter_entities([person], 'tema')
    assert erf.expand_audience(result.kept, result, target_size=10) == [person]
    assert not person.attributes.get(erf.INDIVIDUAL_FLAG)


def test_jev_nature_contract_reads_the_two_distinct_person_classes():
    import httpx
    class Client:
        def post(self, url, json=None):
            assert {'colectivo_personas', 'persona_identificada'} <= set(json['questions']['naturaleza']['criteria'])
            assert 'personas' not in json['questions']['naturaleza']['criteria']
            return httpx.Response(200, request=httpx.Request('POST', url), json={'answers': {
                'rol': {'choice': 'audiencia', 'confidence': .99},
                'naturaleza': {'choice': 'persona_identificada', 'probabilities': {
                    'persona_identificada': .99, 'colectivo_personas': .01}}}})
    answer = erf._ask_jev(Client(), entity('judge', 'Biedma', 'Juez de una causa'), 'tema')
    assert answer['named_person'] == .99 and answer['population_group'] == .01


def test_unavailable_classifier_removes_stale_permission_in_the_real_preparation_flow(tmp_path, monkeypatch):
    """El manager no puede saltarse la limpieza cuando el filtro no se aplica."""
    from types import SimpleNamespace
    from app.services import simulation_manager as sm
    from app.services.zep_entity_reader import FilteredEntities

    monkeypatch.setattr(sm.SimulationManager, 'SIMULATION_DATA_DIR', str(tmp_path))
    for mode in ('disabled', 'missing-key', 'unavailable'):
        judge = entity('judge', 'Biedma', 'Juez identificado; conserva sus relaciones.')
        judge.attributes = {'original': 'value', erf.INDIVIDUAL_FLAG: True,
                            erf.GROUP_KEY: 'old-group', erf.VARIANT_HINT: 2, erf.TOPIC_HINT: 'old-topic'}
        monkeypatch.setattr(Config, 'JEV_ENTITY_FILTER', mode != 'disabled')
        monkeypatch.setattr(Config, 'TYPESAFE_API_KEY', '' if mode == 'missing-key' else 'synthetic-test')
        monkeypatch.setattr(erf, '_ask_jev', lambda *args: None)
        monkeypatch.setattr(sm, 'ZepEntityReader', lambda: SimpleNamespace(
            filter_defined_entities=lambda **kwargs: FilteredEntities([judge], {'Person'}, 1, 1)))
        received = []
        class Profiles:
            def __init__(self, **kwargs):
                pass
            def generate_profiles_from_entities(self, **kwargs):
                received.extend(kwargs['entities'])
                raise RuntimeError('test-stop: no modelo tras observar entidades')
        monkeypatch.setattr(sm, 'OasisProfileGenerator', Profiles)
        manager = sm.SimulationManager()
        sid = manager.create_simulation('proj_synthetic', 'mirofish_synthetic').simulation_id
        with pytest.raises(RuntimeError, match='test-stop'):
            manager.prepare_simulation(sid, 'Elecciones', 'Brief sintético', audience_size=70, poblacion_datos=True)
        assert received == [judge]
        assert judge.attributes == {'original': 'value'}
        assert judge.name == 'Biedma' and judge.related_edges == [{'fact': 'contexto original'}]
