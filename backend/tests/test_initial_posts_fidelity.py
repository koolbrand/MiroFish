"""Source fidelity at the seed boundary, with fake providers and synthetic data."""
import json
from types import SimpleNamespace

import pytest

from app.services import simulation_config_generator as scg
from app.services.simulation_config_generator import EventConfig, SimulationConfigGenerator


def post(content='Preferiría un servicio más barato.', agent=0):
    return {'content': content, 'poster_name': f'Actor {agent}',
            'poster_type': 'Person', 'poster_agent_id': agent}


def review(index, verdict='opinion_only', claims=None):
    return {'post_index': index, 'verdict': verdict, 'claims': claims or []}


def generator(monkeypatch, response):
    gen = object.__new__(SimulationConfigGenerator)
    calls = []
    def answer(prompt):
        calls.append(prompt)
        if isinstance(response, Exception):
            raise response
        return response(prompt) if callable(response) else response
    monkeypatch.setattr(gen, '_call_seed_validation', answer)
    return gen, calls


def test_preserves_opinions_and_supported_facts_with_literal_provenance(monkeypatch):
    source = 'El catálogo de la tienda del barrio fija un precio de 5 euros el 7 de junio.'
    fact = 'El catálogo fija un precio de 5 euros el 7 de junio.'
    gen, calls = generator(monkeypatch, {'reviews': [
        review(1, 'supported', [{'claim': fact, 'source_quote': source}]), review(0),
    ]})
    cfg = gen._validate_initial_posts(EventConfig(initial_posts=[post(), post(fact, 1)]), source)
    assert len(calls) == 1 and [p['poster_agent_id'] for p in cfg.initial_posts] == [0, 1]
    assert cfg.initial_posts[0]['source_provenance']['status'] == 'simulated_opinion'
    evidence = cfg.initial_posts[1]['source_provenance']['claims'][0]
    assert source[evidence['source_start']:evidence['source_end']] == evidence['source_quote']
    assert cfg.initial_posts_validation['status'] == 'validated'
    assert cfg.initial_posts_validation['accepted'] == 2


def test_unsupported_agreement_is_dropped_without_rewriting_or_changing_author(monkeypatch):
    source = 'Se propuso un acuerdo entre dos asociaciones. La segunda no ha respondido.'
    gen, _ = generator(monkeypatch, {'reviews': [review(0, 'unsupported'), review(1)]})
    cfg = gen._validate_initial_posts(EventConfig(initial_posts=[
        post('Ambas asociaciones ya estudian juntas el acuerdo.'), post('Me gustaría que dialogaran.', 1),
    ]), source)
    assert [p['content'] for p in cfg.initial_posts] == ['Me gustaría que dialogaran.']
    assert cfg.initial_posts[0]['poster_agent_id'] == 1
    assert cfg.initial_posts_validation['status'] == 'partial'
    assert cfg.initial_posts_validation['rejections'] == [{'post_index': 0, 'reason': 'unsupported'}]


@pytest.mark.parametrize('reply', [
    {}, [], {'reviews': []}, {'reviews': [review(0), review(0)]},
    {'reviews': [review(True)]}, {'reviews': [review(-1)]}, {'reviews': [review(10)]},
    {'reviews': [dict(review(0), extra='untrusted')]},
    {'reviews': [review(0, 'unknown')]}, {'reviews': [review(0, 'supported')]},
    {'reviews': [review(0)], 'extra': 'untrusted'}, RuntimeError('fake provider unavailable'),
])
def test_malformed_or_unavailable_review_cannot_complete_preparation(monkeypatch, reply):
    gen, calls = generator(monkeypatch, reply)
    cfg = EventConfig(initial_posts=[post()])
    with pytest.raises(ValueError, match='No se pudieron validar|api.seedValidationFailed'):
        gen._validate_initial_posts(cfg, 'Material sintético.')
    assert len(calls) == 1 and cfg.initial_posts == []
    assert cfg.initial_posts_validation['status'] == 'failed'
    assert cfg.initial_posts_validation['rejections'][0]['reason'] in ('validation_unavailable', 'invalid_review')


@pytest.mark.parametrize('claim, quote', [
    ('El precio fue 8 euros.', 'El precio fue 5 euros.'),
    ('El precio fue 5 euros.', 'Una cita inventada.'),
    ('Esto no aparece en el post.', 'El precio fue 5 euros.'),
    ('El precio fue 5 euros.', ''),
])
def test_literal_claim_source_and_numbers_are_checked_independently(monkeypatch, claim, quote):
    gen, _ = generator(monkeypatch, {'reviews': [review(0, 'supported', [
        {'claim': claim, 'source_quote': quote},
    ])]})
    cfg = EventConfig(initial_posts=[post('El precio fue 8 euros. El precio fue 5 euros.')])
    with pytest.raises(ValueError):
        gen._validate_initial_posts(cfg, 'El precio fue 5 euros.')
    assert cfg.initial_posts == []


def test_all_semantically_rejected_posts_are_a_visible_failure(monkeypatch):
    gen, _ = generator(monkeypatch, {'reviews': [review(0, 'unsupported')]})
    cfg = EventConfig(initial_posts=[post('Se ha aprobado el acuerdo.')])
    with pytest.raises(ValueError):
        gen._validate_initial_posts(cfg, 'El acuerdo es una propuesta pendiente.')
    assert cfg.initial_posts_validation['rejections'] == [{'post_index': 0, 'reason': 'unsupported'}]


def test_missing_review_for_one_post_invalidates_the_whole_batch(monkeypatch):
    gen, _ = generator(monkeypatch, {'reviews': [review(0)]})
    cfg = EventConfig(initial_posts=[post(), post(agent=1)])
    with pytest.raises(ValueError):
        gen._validate_initial_posts(cfg, 'Original.')
    assert cfg.initial_posts == [] and cfg.initial_posts_validation['dropped'] == 2


def test_no_posts_needs_no_provider_call_and_empty_source_only_allows_reviewed_opinions(monkeypatch):
    gen, calls = generator(monkeypatch, {'reviews': [review(0)]})
    assert gen._validate_initial_posts(EventConfig(), '').initial_posts == []
    assert calls == []
    cfg = gen._validate_initial_posts(EventConfig(initial_posts=[post()]), '')
    assert cfg.initial_posts_validation['source_available'] is False
    assert cfg.initial_posts[0]['source_provenance']['status'] == 'simulated_opinion'
    bad, _ = generator(monkeypatch, {'reviews': [review(0, 'supported', [
        {'claim': 'Aprobado.', 'source_quote': 'Aprobado.'}]) ]})
    with pytest.raises(ValueError):
        bad._validate_initial_posts(EventConfig(initial_posts=[post('Aprobado.')]), '')


def test_input_and_batch_budget_source_bound_and_audit_metadata(monkeypatch):
    def echo(prompt):
        data = json.loads(prompt.split('\n')[-1])
        assert len(data['posts']) <= 8
        assert len(data['original_material']) <= 32000
        return {'reviews': [review(p['post_index']) for p in data['posts']]}
    gen, calls = generator(monkeypatch, echo)
    source = 'Inicio importante. ' + 'relleno ' * 10000 + ' Final importante.'
    cfg = gen._validate_initial_posts(EventConfig(initial_posts=[post(agent=i) for i in range(35)]), source)
    assert len(calls) == 4 and len(cfg.initial_posts) == 32
    assert cfg.initial_posts_validation['source_truncated'] is True
    assert cfg.initial_posts_validation['dropped'] == 3
    data = json.loads(calls[0].split('\n')[-1])
    assert data['original_material'].startswith('Inicio importante.')
    assert data['original_material'].endswith('Final importante.')
    # Machine-readable audit persists, without private rejected text or source body.
    params = scg.SimulationParameters('sim_test', 'proj_test', 'graph_test', 'scenario', event_config=cfg)
    persisted = params.to_dict()['event_config']['initial_posts_validation']
    assert persisted == cfg.initial_posts_validation and source not in json.dumps(persisted)


def test_oversize_seed_is_not_sent_to_model(monkeypatch):
    gen, calls = generator(monkeypatch, {'reviews': [review(0)]})
    cfg = gen._validate_initial_posts(EventConfig(initial_posts=[post('x' * 2001), post(agent=1)]), 'Original.')
    assert len(calls) == 1 and [p['poster_agent_id'] for p in cfg.initial_posts] == [1]
    assert 'x' * 2001 not in calls[0]


@pytest.mark.parametrize('finish, content', [('length', '{"reviews":[]}'), ('length', ''), ('stop', '{broken')])
def test_provider_json_boundary_is_strict_and_has_no_hidden_retry(monkeypatch, finish, content):
    gen = object.__new__(SimulationConfigGenerator)
    gen.model_name = 'fake'
    seen = {}
    class FakeClient:
        def with_options(self, **kwargs):
            seen.update(kwargs)
            return self
        @property
        def chat(self):
            return SimpleNamespace(completions=SimpleNamespace(create=self.create))
        def create(self, **kwargs):
            seen['request'] = kwargs
            return SimpleNamespace(choices=[SimpleNamespace(finish_reason=finish, message=SimpleNamespace(content=content))])
    gen.client = FakeClient()
    with pytest.raises(ValueError) as error:
        gen._call_seed_validation('Synthetic prompt')
    assert seen['max_retries'] == 0 and seen['timeout'] <= 240
    from app.config import Config
    assert seen['request']['max_tokens'] == min(Config.LLM_MAX_TOKENS_CAP, 32768)
    assert seen['request']['temperature'] == 0
    assert gen._seed_validation_error_code(error.value) == (
        'provider_token_limit' if finish == 'length' else 'provider_json_invalid')


def test_generate_config_validates_after_resolving_authors_before_returning(monkeypatch):
    gen, calls = generator(monkeypatch, {'reviews': [review(0)]})
    gen.model_name = 'fake'
    gen.base_url = 'http://127.0.0.1:9'
    entities = [scg.EntityNode('u0', 'Actor 0', ['Entity', 'Person'], '', {})]
    monkeypatch.setattr(gen, '_generate_time_config', lambda *args: {})
    monkeypatch.setattr(gen, '_generate_event_config', lambda *args: {'initial_posts': [post()]})
    monkeypatch.setattr(gen, '_generate_agent_configs_batch', lambda **kwargs: [
        scg.AgentActivityConfig(0, 'u0', 'Actor 0', 'Person')])
    cfg = gen.generate_config('sim_test', 'proj_test', 'graph_test', 'Scenario', 'Original.', entities)
    assert len(calls) == 1
    assert cfg.event_config.initial_posts[0]['poster_name'] == 'Actor 0'
    assert cfg.event_config.initial_posts_validation['accepted'] == 1


def test_truncated_flag_does_not_depend_on_accidentally_equal_excerpt_length(monkeypatch):
    gen, _ = generator(monkeypatch, {'reviews': [review(0)]})
    original = 'x' * (32000 + len('\n[... material omitido ...]\n'))
    cfg = gen._validate_initial_posts(EventConfig(initial_posts=[post()]), original)
    assert cfg.initial_posts_validation['source_truncated'] is True


@pytest.mark.parametrize('response', [
    RuntimeError('synthetic provider failure'),
    {'reviews': [review(0, 'supported', [{'claim': 'Preferiría un servicio más barato.',
                                        'source_quote': 'cita inventada'}])]},
])
def test_validation_failure_marks_real_preparation_failed_not_ready(tmp_path, monkeypatch, response):
    from app.config import Config
    from app.services import simulation_manager as sm
    from app.services.zep_entity_reader import FilteredEntities

    gen, calls = generator(monkeypatch, response)
    gen.model_name = 'fake'
    gen.base_url = 'http://127.0.0.1:9'
    entities = [scg.EntityNode('u0', 'Actor 0', ['Entity', 'Person'], '', {})]
    monkeypatch.setattr(gen, '_generate_time_config', lambda *args: {})
    monkeypatch.setattr(gen, '_generate_event_config', lambda *args: {'initial_posts': [post()]})
    monkeypatch.setattr(gen, '_generate_agent_configs_batch', lambda **kwargs: [
        scg.AgentActivityConfig(0, 'u0', 'Actor 0', 'Person')])
    monkeypatch.setattr(Config, 'JEV_ENTITY_FILTER', False)
    monkeypatch.setattr(sm.SimulationManager, 'SIMULATION_DATA_DIR', str(tmp_path))
    monkeypatch.setattr(sm, 'ZepEntityReader', lambda: SimpleNamespace(
        filter_defined_entities=lambda **kwargs: FilteredEntities(entities, {'Person'}, 1, 1)))
    monkeypatch.setattr(sm, 'SimulationConfigGenerator', lambda: gen)
    class Profiles:
        def __init__(self, **kwargs):
            pass
        def generate_profiles_from_entities(self, **kwargs):
            return [SimpleNamespace(user_id=0)]
        def save_profiles(self, **kwargs):
            pass
    monkeypatch.setattr(sm, 'OasisProfileGenerator', Profiles)
    manager = sm.SimulationManager()
    sid = manager.create_simulation('proj_synthetic', 'mirofish_synthetic').simulation_id
    with pytest.raises(ValueError):
        manager.prepare_simulation(sid, 'Scenario', 'Original.')
    state = manager.get_simulation(sid)
    assert len(calls) == 1 and state.status == sm.SimulationStatus.FAILED
    assert state.error == scg.t('api.seedValidationFailed')
    assert not state.config_generated


@pytest.mark.parametrize('cap', [256, 2048, 32768, 65536])
def test_reasoning_token_budget_respects_global_cap_and_one_request(monkeypatch, cap):
    from app.config import Config
    gen = object.__new__(SimulationConfigGenerator)
    gen.model_name = 'fake'
    monkeypatch.setattr(Config, 'LLM_MAX_TOKENS_CAP', cap)
    requests = []
    options = []
    class Client:
        def with_options(self, **kwargs):
            options.append(kwargs)
            return self
        @property
        def chat(self):
            return SimpleNamespace(completions=SimpleNamespace(create=self.create))
        def create(self, **kwargs):
            requests.append(kwargs)
            return SimpleNamespace(choices=[SimpleNamespace(finish_reason='stop',
                                    message=SimpleNamespace(content='{"reviews":[]}'))])
    gen.client = Client()
    assert gen._call_seed_validation('Synthetic prompt') == {'reviews': []}
    assert len(requests) == 1 and requests[0]['max_tokens'] == min(cap, 32768)
    assert options[0]['max_retries'] == 0 and options[0]['timeout'] <= 240
    assert 'reasoning' not in requests[0] and 'extra_body' not in requests[0]


@pytest.mark.parametrize('error, code', [
    (scg._SeedValidationError('respuesta de validación incompleta', 'provider_token_limit'), 'provider_token_limit'),
    (ValueError('índice de validación inválido'), 'row_index_invalid'),
    (ValueError('cita o afirmación no literal'), 'claim_or_quote_not_literal'),
    (ValueError('cifras sin respaldo literal'), 'numeric_token_not_in_quote'),
    (json.JSONDecodeError('invalid', '{', 0), 'provider_json_invalid'),
    (TimeoutError('private timeout message'), 'provider_timeout'),
    (RuntimeError('private token or provider response body'), 'provider_or_validation_error'),
])
def test_safe_failure_codes_in_metadata_and_logs_do_not_include_provider_text(monkeypatch, error, code):
    gen, calls = generator(monkeypatch, error)
    warnings = []
    monkeypatch.setattr(scg, 'logger', SimpleNamespace(warning=lambda message, *args: warnings.append(message % args)))
    cfg = EventConfig(initial_posts=[post()])
    with pytest.raises(ValueError):
        gen._validate_initial_posts(cfg, 'Original.')
    assert len(calls) == 1 and cfg.initial_posts_validation['rejections'][0]['reason_code'] == code
    assert code in warnings[0]
    assert 'private' not in json.dumps(cfg.initial_posts_validation) and 'private' not in warnings[0]


@pytest.mark.parametrize('bad_review, code', [
    (dict(review(0), extra='not allowed'), 'row_fields_invalid'),
    (review(0, 'unknown'), 'row_verdict_invalid'),
    (review(0, 'supported'), 'row_claims_invalid'),
    (review(0, 'supported', [{'claim': 'El precio es 8 euros.', 'source_quote': 'El precio es 5 euros.'}]),
     'numeric_token_not_in_quote'),
    (review(0, 'supported', [{'claim': 'El precio es 8 euros.', 'source_quote': 'cita inventada'}]),
     'claim_or_quote_not_literal'),
])
def test_defective_row_drops_only_its_post_after_complete_unique_index_contract(monkeypatch, bad_review, code):
    gen, _ = generator(monkeypatch, {'reviews': [bad_review, review(1), review(2, 'unsupported')]})
    cfg = gen._validate_initial_posts(EventConfig(initial_posts=[
        post('El precio es 8 euros.'), post('Me gustaría un precio menor.', 1), post('Ya se aprobó.', 2),
    ]), 'El precio es 5 euros.')
    assert [p['poster_agent_id'] for p in cfg.initial_posts] == [1]
    assert cfg.initial_posts_validation['rejections'] == [
        {'post_index': 0, 'reason': 'invalid_review', 'reason_code': code},
        {'post_index': 2, 'reason': 'unsupported'},
    ]


@pytest.mark.parametrize('rows', [
    [review(0), review(0)], [review(0)], [review(0), review(True)],
    [review(0), {'verdict': 'opinion_only', 'claims': []}],
])
def test_ambiguous_or_incomplete_batch_never_preserves_even_an_individually_valid_post(monkeypatch, rows):
    gen, _ = generator(monkeypatch, {'reviews': rows})
    cfg = EventConfig(initial_posts=[post(), post(agent=1)])
    with pytest.raises(ValueError):
        gen._validate_initial_posts(cfg, 'Original.')
    assert cfg.initial_posts == []
    assert all(r['reason'] == 'validation_unavailable' for r in cfg.initial_posts_validation['rejections'])


def test_every_row_with_invalid_provenance_still_fails_preparation_boundary(monkeypatch):
    rows = [review(i, 'supported', [{'claim': 'El precio es 8 euros.', 'source_quote': 'El precio es 5 euros.'}])
            for i in range(2)]
    gen, _ = generator(monkeypatch, {'reviews': rows})
    cfg = EventConfig(initial_posts=[post('El precio es 8 euros.', i) for i in range(2)])
    with pytest.raises(ValueError):
        gen._validate_initial_posts(cfg, 'El precio es 5 euros.')
    assert cfg.initial_posts == [] and cfg.initial_posts_validation['status'] == 'failed'
    assert all(r['reason_code'] == 'numeric_token_not_in_quote' for r in cfg.initial_posts_validation['rejections'])
