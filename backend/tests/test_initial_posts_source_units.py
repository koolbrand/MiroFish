"""Factual seeds publish literal complete units, never uncited candidate prose."""
import hashlib
import json

import pytest

from app.services.simulation_config_generator import EventConfig, SimulationConfigGenerator, _SeedValidationError
from app.utils.locale import get_locale, set_locale, t
from test_initial_posts_fidelity import generator, post, review


def claim(text, quote):
    return {'claim': text, 'source_quote': quote}


def assert_published_units(posted, source):
    evidence = posted['source_provenance']
    assert evidence['status'] == 'source_backed' and evidence['version'] == 2
    assert evidence['verification'] == 'literal_material_only'
    expected = [t('api.seedSourceMaterial')]
    for unit in evidence['claims']:
        text = source[unit['source_start']:unit['source_end']]
        assert text == unit['claim'] == unit['source_quote']
        assert posted['content'][unit['content_start']:unit['content_end']] == text
        assert unit['source_sha256'] == hashlib.sha256(source.encode('utf-8')).hexdigest()
        expected.append(text)
    assert posted['content'] == '\n\n'.join(expected)
    assert len(posted['content']) <= 2000


def test_review_that_misses_a_second_factual_assertion_cannot_publish_it(monkeypatch):
    source = '1. El 4 de abril, Alfa adoptó una marca nueva; no tiene candidato. [Medio Norte]'
    candidate = 'Alfa adoptó una marca nueva. Ayer firmamos un acuerdo con Beta y una donación de 50 millones.'
    gen, calls = generator(monkeypatch, {'reviews': [review(0, 'supported', [
        claim('Alfa adoptó una marca nueva', 'Alfa adoptó una marca nueva'),
    ])]})
    config = gen._validate_initial_posts(EventConfig(initial_posts=[post(candidate, 5)]), source)
    result = config.initial_posts[0]
    assert result['poster_agent_id'] == 5 and result['poster_name'] == 'Actor 5'
    assert result['poster_type'] == 'Person'
    assert 'firmamos' not in result['content'] and '50 millones' not in json.dumps(config.initial_posts)
    assert 'no tiene candidato' in result['content'] and '[Medio Norte]' in result['content']
    assert len(calls) == 1 and config.initial_posts_validation['version'] == 2
    assert config.initial_posts_validation['method'] == 'literal_source_units_after_review'
    assert_published_units(result, source)


@pytest.mark.parametrize('newline', ['\n', '\r\n'])
def test_list_item_keeps_wrapped_condition_negation_date_and_source(newline, monkeypatch):
    unit = newline.join(['1. El 7 de mayo, Sol sería candidata según Medio Sur,',
                         '   si se convocan elecciones. No existe designación oficial. [Medio Sur]'])
    other = '2. El pleno estudia una ponencia, no una sentencia firme. [Institución]'
    source = unit + newline + other
    gen, _ = generator(monkeypatch, {'reviews': [review(0, 'supported', [
        claim('Sol será candidata', 'Sol sería candidata según Medio Sur'),
    ])]})
    cfg = gen._validate_initial_posts(EventConfig(initial_posts=[post('Sol será candidata.')]), source)
    assert cfg.initial_posts[0]['source_provenance']['claims'][0]['source_quote'] == unit
    assert 'No existe designación oficial' in cfg.initial_posts[0]['content']
    assert other not in cfg.initial_posts[0]['content']
    assert_published_units(cfg.initial_posts[0], source)


def test_prose_with_visual_line_wraps_remains_a_whole_paragraph(monkeypatch):
    source = 'Vega comparece en Delta.\nNo es investigada en Eco; la instrucción de Eco corresponde a Soto.'
    gen, _ = generator(monkeypatch, {'reviews': [review(0, 'supported', [claim('Vega comparece', 'Vega comparece')])]})
    cfg = gen._validate_initial_posts(EventConfig(initial_posts=[post('Vega comparece; ayer fue condenada en Eco.')]), source)
    assert cfg.initial_posts[0]['source_provenance']['claims'][0]['source_quote'] == source
    assert 'condenada' not in cfg.initial_posts[0]['content']
    assert_published_units(cfg.initial_posts[0], source)


def test_introductory_qualifier_before_list_cannot_be_separated(monkeypatch):
    source = 'No se han aprobado estas propuestas:\n- Suspender la tarifa.\n- Ampliar el horario.'
    gen, _ = generator(monkeypatch, {'reviews': [review(0, 'supported', [claim('Suspender la tarifa', 'Suspender la tarifa')])]})
    cfg = gen._validate_initial_posts(EventConfig(initial_posts=[post('Suspender la tarifa.')]), source)
    assert 'No se han aprobado estas propuestas:' in cfg.initial_posts[0]['content']
    assert '- Suspender la tarifa.' in cfg.initial_posts[0]['content']
    assert_published_units(cfg.initial_posts[0], source)


def test_introductory_negation_across_blank_lines_and_section_heading_stay_with_list(monkeypatch):
    source = '## Hechos no confirmados\n\nNo ocurrió lo siguiente:\n\n- El Ejecutivo convocó elecciones.\n- Se aprobó la medida.'
    gen, _ = generator(monkeypatch, {'reviews': [review(0, 'supported', [
        claim('El Ejecutivo convocó elecciones', 'El Ejecutivo convocó elecciones'),
    ])]})
    cfg = gen._validate_initial_posts(EventConfig(initial_posts=[post('El Ejecutivo convocó elecciones.')]), source)
    assert [unit['source_quote'] for unit in cfg.initial_posts[0]['source_provenance']['claims']] == [
        '## Hechos no confirmados', 'No ocurrió lo siguiente:', '- El Ejecutivo convocó elecciones.']
    assert_published_units(cfg.initial_posts[0], source)


def test_nested_list_keeps_conditional_parent_and_all_its_children(monkeypatch):
    source = ('- Solo si la cámara lo aprueba:\n'
              '  - La medida entrará en vigor.\n'
              '  - Se publicará entonces la fecha.\n'
              '- No existe aprobación todavía.')
    gen, _ = generator(monkeypatch, {'reviews': [review(0, 'supported', [
        claim('La medida entrará en vigor', 'La medida entrará en vigor'),
    ])]})
    cfg = gen._validate_initial_posts(EventConfig(initial_posts=[post('La medida entrará en vigor.')]), source)
    assert cfg.initial_posts[0]['source_provenance']['claims'][0]['source_quote'] == source.split('\n- No existe')[0]
    assert_published_units(cfg.initial_posts[0], source)


@pytest.mark.parametrize('newline', ['\n', '\r\n'])
def test_nested_item_after_blank_lines_keeps_parent_condition_and_indentation(monkeypatch, newline):
    parent = '- Solo si la cámara lo aprueba:'
    child = '  - La medida entrará en vigor.'
    source = newline.join([parent, '', child, '', '- No existe aprobación todavía.'])
    gen, _ = generator(monkeypatch, {'reviews': [review(0, 'supported', [
        claim('La medida entrará en vigor', 'La medida entrará en vigor'),
    ])]})
    cfg = gen._validate_initial_posts(EventConfig(initial_posts=[post('La medida entrará en vigor.')]), source)
    assert [unit['source_quote'] for unit in cfg.initial_posts[0]['source_provenance']['claims']] == [parent, child]
    assert_published_units(cfg.initial_posts[0], source)


def test_list_continuing_after_blank_line_keeps_same_introductory_negation(monkeypatch):
    source = 'No se ha confirmado:\n\n1. La convocatoria oficial.\n\n2. Una aprobación definitiva.'
    gen, _ = generator(monkeypatch, {'reviews': [review(0, 'supported', [claim('aprobación', 'aprobación')])]})
    cfg = gen._validate_initial_posts(EventConfig(initial_posts=[post('Una aprobación.')]), source)
    assert [unit['source_quote'] for unit in cfg.initial_posts[0]['source_provenance']['claims']] == [
        'No se ha confirmado:', '2. Una aprobación definitiva.']
    assert_published_units(cfg.initial_posts[0], source)


def test_long_introductory_context_is_never_dropped_to_fit_a_short_list_item(monkeypatch):
    source = 'No ha ocurrido ' + 'contexto ' * 250 + ':\n\n- La convocatoria oficial.'
    gen, _ = generator(monkeypatch, {'reviews': [review(0, 'supported', [claim('convocatoria', 'convocatoria')])]})
    cfg = EventConfig(initial_posts=[post('La convocatoria.')])
    with pytest.raises(ValueError):
        gen._validate_initial_posts(cfg, source)
    assert cfg.initial_posts == []
    assert cfg.initial_posts_validation['rejections'][0]['reason_code'] == 'source_units_over_limit'


def test_cross_unit_quote_keeps_both_items_and_overlapping_claims_do_not_duplicate_units(monkeypatch):
    first = '1. El índice sube 3,2%; dato provisional. [Instituto]'
    second = '2. El alquiler sube 7,1%; fuente privada. [Agencia]'
    source = first + '\n' + second
    quote = 'dato provisional. [Instituto]\n2. El alquiler'
    gen, _ = generator(monkeypatch, {'reviews': [review(0, 'supported', [
        claim('El índice sube', 'El índice sube'), claim('El alquiler', quote),
    ])]})
    cfg = gen._validate_initial_posts(EventConfig(initial_posts=[post('El índice sube. El alquiler también.')]), source)
    assert [unit['source_quote'] for unit in cfg.initial_posts[0]['source_provenance']['claims']] == [first, second]
    assert_published_units(cfg.initial_posts[0], source)


def test_selection_order_is_source_order_not_review_order_and_shared_units_do_not_drop_other_posts(monkeypatch):
    first, second, third = ['1. Uno sería provisional.', '2. Dos no es oficial.', '3. Tres es una propuesta.']
    source = '\n'.join([first, second, third])
    gen, _ = generator(monkeypatch, {'reviews': [
        review(0, 'supported', [claim('Tres', 'Tres'), claim('Uno', 'Uno')]),
        review(1, 'supported', [claim('Dos', 'Dos'), claim('Uno', 'Uno')]),
    ]})
    cfg = gen._validate_initial_posts(EventConfig(initial_posts=[post('Uno. Tres.'), post('Uno. Dos.', 1)]), source)
    assert len(cfg.initial_posts) == 2
    assert [p['source_quote'] for p in cfg.initial_posts[0]['source_provenance']['claims']] == [first, third]
    assert [p['source_quote'] for p in cfg.initial_posts[1]['source_provenance']['claims']] == [first, second]
    for result in cfg.initial_posts:
        assert_published_units(result, source)


def test_exact_duplicate_materialized_content_is_removed_across_batches(monkeypatch):
    source = 'La propuesta no es una decisión definitiva.'
    def answer(prompt):
        data = json.loads(prompt.split('\n')[-1])
        return {'reviews': [review(p['post_index'], 'supported', [claim('propuesta', 'propuesta')]) for p in data['posts']]}
    gen, calls = generator(monkeypatch, answer)
    cfg = gen._validate_initial_posts(EventConfig(initial_posts=[post('Una propuesta.', n) for n in range(9)]), source)
    assert len(calls) == 2 and len(cfg.initial_posts) == 1
    assert cfg.initial_posts[0]['poster_agent_id'] == 0
    assert len(cfg.initial_posts_validation['rejections']) == 8
    assert all(r['reason'] == 'duplicate_source_content' for r in cfg.initial_posts_validation['rejections'])


def test_oversized_whole_unit_is_rejected_without_cutting_qualifier(monkeypatch):
    source = 'Una propuesta ' + 'contexto ' * 250 + 'NO aprobada.'
    gen, _ = generator(monkeypatch, {'reviews': [
        review(0, 'supported', [claim('Una propuesta', 'Una propuesta')]), review(1),
    ]})
    cfg = gen._validate_initial_posts(EventConfig(initial_posts=[post('Una propuesta.'), post('Me gustaría debatir.', 1)]), source)
    assert [p['poster_agent_id'] for p in cfg.initial_posts] == [1]
    assert cfg.initial_posts_validation['rejections'] == [
        {'post_index': 0, 'reason': 'source_materialization_failed', 'reason_code': 'source_units_over_limit'}]


def test_combined_whole_units_over_limit_reject_the_post_not_one_required_piece(monkeypatch):
    first, second = '1. Alfa ' + 'contexto ' * 125, '2. Beta ' + 'contexto ' * 125 + 'no aprobado.'
    source = first + '\n' + second
    gen, _ = generator(monkeypatch, {'reviews': [review(0, 'supported', [
        claim('Alfa', 'Alfa'), claim('Beta', 'Beta')])]})
    cfg = EventConfig(initial_posts=[post('Alfa y Beta.')])
    with pytest.raises(ValueError):
        gen._validate_initial_posts(cfg, source)
    assert cfg.initial_posts == [] and cfg.initial_posts_validation['status'] == 'failed'
    assert cfg.initial_posts_validation['rejections'][0]['reason_code'] == 'source_units_over_limit'


@pytest.mark.parametrize('change', ['hash', 'start', 'end', 'quote', 'bool'])
def test_materializer_rechecks_literal_offsets_and_source_hash(change):
    source = 'Vega no es investigada.'
    digest = hashlib.sha256(source.encode('utf-8')).hexdigest()
    item = {'source_start': 0, 'source_end': 4, 'source_quote': 'Vega'}
    if change == 'hash':
        digest = 'x' * 64
    elif change == 'bool':
        item['source_start'] = False
    else:
        item['source_' + change] = 1 if change in ('start', 'end') else 'Otra'
    with pytest.raises(_SeedValidationError, match='inválid'):
        SimulationConfigGenerator._materialize_seed_source(source, [item], digest, 2000)


@pytest.mark.parametrize('locale', ['es', 'en', 'zh'])
def test_header_is_translated_fixed_text_and_opinions_never_claim_factual_verification(monkeypatch, locale):
    previous = get_locale()
    set_locale(locale)
    try:
        source = 'No hay decisión definitiva.'
        gen, _ = generator(monkeypatch, {'reviews': [review(0, 'supported', [claim('decisión', 'decisión')]), review(1)]})
        cfg = gen._validate_initial_posts(EventConfig(initial_posts=[post('Una decisión.'), post('Preferiría debatir.', 1)]), source)
        assert cfg.initial_posts[0]['content'].startswith(t('api.seedSourceMaterial') + '\n\n')
        assert 'api.seedSourceMaterial' not in cfg.initial_posts[0]['content']
        assert_published_units(cfg.initial_posts[0], source)
        opinion = cfg.initial_posts[1]['source_provenance']
        assert opinion['status'] == 'simulated_opinion' and opinion['verification'] == 'not_verified_as_fact'
        assert opinion['claims'] == []
    finally:
        set_locale(previous)
