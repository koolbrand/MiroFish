"""Fuente literal y proyección efectiva a OASIS: sin modelos ni APIs reales."""
import asyncio
import csv
import json
from dataclasses import replace

import pytest

from app.services import profile_memory as memory
from app.services import oasis_profile_adapter as adapter
from app.services.interview_guard import build_interview_system_prompt, INTERVIEW_PROMPT_PREFIX, REPORT_INTERVIEW_PROMPT_PREFIX
from app.services.poblacion.banco import Encuestado
from app.services.poblacion.fuentes import FUENTES
from app.services.zep_entity_reader import EntityNode
from test_profile_source_fidelity import generator

SOURCE = ('Vega es perjudicada en Delta. Soto la cita para el 8 de octubre; Eco corresponde a Rivas. '
          'Vega NO es investigada en Eco.\n\nSol sería candidata según el medio Norte; no existe designación oficial. '
          'Norte vota en contra; el Gobierno no retira la medida. El indicador publicado es 3,2 %.')


def entity(name='Vega', kind='Person', audience=False):
    return EntityNode('a', name, ['Entity', kind], 'Tiene 42 años, máster inventado y participó ayer en una manifestación.',
                      {'age': 42, 'profession': 'Máster inventado', **({'__simuloo_individual': True} if audience else {})})


def named(gen=None):
    return (gen or generator()).generate_profile_from_entity(entity(), 0, original_source=SOURCE)


def respondent():
    return Encuestado(1, 'estudio_sintetico_2024', None, None, None, 'Galicia', None, None, None, None, None, 1,
                      respuestas=[{'pregunta': 'Recuerdo del voto emitido en 2023', 'respuesta': 'Partido Alfa', 'politica': True},
                                  {'pregunta': 'Intención de voto si mañana hubiera elecciones', 'respuesta': 'No sabe', 'politica': True}])


def survey(gen):
    return gen.generate_profile_from_entity(entity('Público · 1', audience=True), 0, encuestado=respondent(),
                                           fuente=FUENTES['cis'], relevantes=['Recuerdo del voto emitido en 2023',
                                           'Intención de voto si mañana hubiera elecciones'], original_source=SOURCE)


@pytest.mark.parametrize('kind', ['Person', 'PoliticalOrganization', 'Company', 'LegalActor', 'Entity'])
def test_concrete_and_unconfirmed_actors_ignore_model_and_graph_biography(kind):
    gen = generator()
    profile = gen.generate_profile_from_entity(entity(kind=kind), 0, original_source=SOURCE)
    assert gen.client.calls == [] and profile.bio == 'Vega'
    assert profile.age is None and profile.gender is None and profile.mbti is None and profile.profession is None
    assert 'máster inventado' not in profile.persona and 'manifestación' not in profile.persona
    assert memory.validate_passages(SOURCE, profile.source_passages)
    assert 'Vega NO es investigada en Eco' in profile.persona
    assert profile.source_coverage['identity_match'] is True


def test_alias_without_literal_match_uses_shared_context_without_attribution():
    profile = generator().generate_profile_from_entity(entity('Partido Alfa (PA)'), 0, original_source=SOURCE)
    assert profile.source_coverage['identity_match'] is False
    assert profile.source_coverage['selection'] == 'shared_context' and len(profile.source_passages) == 2
    assert 'shared scenario context ONLY' in profile.persona and 'No role, action or position is attributed' in profile.persona
    assert memory.validate_passages(SOURCE, profile.source_passages)


def test_whole_paragraph_is_omitted_instead_of_cutting_negation_or_distinct_case():
    source = 'Vega ' + 'antecedentes ' * 30 + 'NO es investigada en Eco; la perjudicada es Otra.'
    passages, coverage = memory.select_passages(source, 'Vega', max_chars=50)
    assert passages == [] and coverage['omitted'] == 1 and not coverage['complete']


@pytest.mark.parametrize('change', ['text', 'start', 'end', 'source_sha256', 'source'])
def test_changed_source_fabricated_quote_or_offsets_fail_validation(change):
    passages = json.loads(json.dumps(named().source_passages))
    source = SOURCE
    if change == 'source':
        source += ' Cambiado.'
    elif change == 'text':
        passages[0]['text'] = 'Vega fue condenada en Eco.'
    elif change == 'source_sha256':
        passages[0][change] = 'x' * 64
    else:
        passages[0][change] += 1
    with pytest.raises(ValueError):
        memory.validate_passages(source, passages)


@pytest.mark.parametrize('bad', [None, [None], [1], ['inventado'], [{'start': True, 'end': 2, 'text': 'x'}]])
def test_malformed_passages_raise_controlled_error(bad):
    with pytest.raises(ValueError):
        memory.validate_passages(SOURCE, bad)


@pytest.mark.parametrize('bad', [None, {'bio': 'Doctorado inventado'}, {**memory.DEFAULT_STYLE, 'persona': 'Candidata oficial'},
                                 {**memory.DEFAULT_STYLE, 'formality': 'Vega fue condenada'}])
def test_free_biography_cannot_be_smuggled_through_style(bad):
    with pytest.raises(ValueError):
        memory.validate_style(bad)


def test_survey_keeps_measured_answers_and_does_not_turn_recall_into_current_intention():
    gen = generator()
    profile = survey(gen)
    assert gen.client.calls == [] and profile.identity_kind == 'survey_respondent'
    assert profile.age is None and profile.gender is None and profile.mbti is None
    assert profile.country == 'España' and profile.data_ref == 'estudio_sintetico_2024'
    for row in respondent().respuestas:
        assert row['pregunta'] in profile.persona and row['respuesta'] in profile.persona
    assert 'Past vote recall is NOT current voting intention' in profile.persona
    assert profile.memory_facts == [fact for fact in profile.survey_facts if 'respondió' in fact]


def test_serializers_and_fallback_rebuild_memory_even_if_free_bio_is_polluted(tmp_path):
    gen = generator()
    profile = named(gen)
    profile.bio = profile.persona = 'Inventado: Vega fue condenada y tiene un máster.'
    gen.save_profiles([profile], str(tmp_path / 'reddit_profiles.json'), 'reddit')
    gen.save_profiles([profile], str(tmp_path / 'twitter_profiles.csv'), 'twitter')
    reddit = json.loads((tmp_path / 'reddit_profiles.json').read_text())[0]
    with (tmp_path / 'twitter_profiles.csv').open() as source:
        twitter = next(csv.DictReader(source))
    for projected in (reddit, memory.decode_twitter_profile(twitter)):
        assert projected['bio'] == 'Vega' and 'Inventado:' not in projected['persona']
        assert 'Vega NO es investigada en Eco' in projected['persona']
        assert projected['age'] is None and projected['mbti'] is None
        prompt = build_interview_system_prompt('Vega', 'Máster falso', 'Bio falsa', profile=projected)
        assert 'Bio falsa' not in prompt and 'Máster falso' not in prompt
        assert 'Vega NO es investigada en Eco' in prompt
    assert 'Inventado:' not in twitter['user_char'] and twitter['description'] == 'Vega'
    assert 'posiciones simuladas' in INTERVIEW_PROMPT_PREFIX and 'posiciones simuladas' in REPORT_INTERVIEW_PROMPT_PREFIX


@pytest.mark.parametrize('platform', ['reddit', 'twitter'])
def test_effective_oasis_custom_template_retains_tools_and_omits_unknown_identity(tmp_path, monkeypatch, platform):
    (tmp_path / 'log').mkdir()
    monkeypatch.chdir(tmp_path)
    import socket
    from camel.models import StubModel
    from camel.types import ModelType
    monkeypatch.setattr(socket.socket, 'connect', lambda *args: pytest.fail('No se permite red'))
    gen = generator()
    path = tmp_path / ('reddit_profiles.json' if platform == 'reddit' else 'twitter_profiles.csv')
    gen.save_profiles([survey(gen)], str(path), platform)
    actions = ['create_post', 'create_comment']
    graph = asyncio.run(adapter._generate(str(path), platform, model=StubModel(ModelType.STUB), available_actions=actions))
    agents = list(graph.get_agents())
    assert len(agents) == 1
    agent = agents[0][1]
    assert {tool.func.__name__ for tool in agent.action_tools} == set(actions)
    prompt = agent.system_message.content
    assert '# OBJECTIVE' in prompt and '# RESPONSE METHOD' in prompt and 'tool calling' in prompt
    assert 'years old' not in prompt and 'ISTJ' not in prompt and 'MBTI personality type' not in prompt
    assert 'Vega NO es investigada en Eco' in prompt and 'no existe designación oficial' in prompt
    assert 'estudio_sintetico_2024' in prompt and 'simulated positions' in prompt


@pytest.mark.parametrize('platform', ['reddit', 'twitter', 'parallel'])
def test_graph_policy_blocks_canonical_profiles_for_each_platform(tmp_path, platform):
    gen = generator()
    for kind, filename in [('reddit', 'reddit_profiles.json'), ('twitter', 'twitter_profiles.csv')]:
        if platform == 'parallel' or kind == platform:
            gen.save_profiles([named(gen)], str(tmp_path / filename), kind)
    policy = adapter.profile_memory_policy(tmp_path, platform, requested=True)
    assert policy['source_graph'] == 'immutable' and policy['graph_update'] == 'blocked_for_canonical_profiles'
    assert policy['social_activity'] == 'simulated_local_evidence'


@pytest.mark.parametrize('mode', ['legacy_only', 'mixed', 'unknown_version', 'malformed'])
def test_graph_policy_preserves_legacy_and_blocks_mixed_unknown_or_malformed(tmp_path, mode):
    gen = generator()
    profile = named(gen)
    legacy = replace(profile, profile_schema_version=None)
    gen.save_profiles([legacy], str(tmp_path / 'twitter_profiles.csv'), 'twitter')
    if mode == 'legacy_only':
        policy = adapter.profile_memory_policy(tmp_path, 'twitter', requested=True)
        assert policy['source_graph'] == 'legacy_shared' and policy['graph_update'] == 'enabled'
        return
    gen.save_profiles([profile, legacy], str(tmp_path / 'reddit_profiles.json'), 'reddit')
    if mode == 'unknown_version':
        profiles = json.loads((tmp_path / 'reddit_profiles.json').read_text())
        profiles[0]['profile_schema_version'] = 999
        (tmp_path / 'reddit_profiles.json').write_text(json.dumps(profiles))
    if mode == 'malformed':
        (tmp_path / 'reddit_profiles.json').write_text('{')
    policy = adapter.profile_memory_policy(tmp_path, 'parallel', requested=True)
    assert policy['source_graph'] == 'immutable' and policy['graph_update'].startswith('blocked_')


def test_synthetic_model_output_cannot_write_factual_passages_or_style(monkeypatch):
    gen = generator()
    monkeypatch.setattr(gen, '_generate_profile_with_llm', lambda **kwargs: {
        'bio': 'Biografía ficticia', 'persona': 'Experiencia inventada de la persona sintética',
        'source_passages': [{'text': 'Vega fue condenada'}],
        'communication_style': {'bio': 'Titulación inventada'}, 'age': 38,
        'data_source': 'CIS', 'data_ref': 'INVENTADO', 'memory_facts': ['Votó Alfa']})
    profile = gen.generate_profile_from_entity(entity('Público', audience=True), 0, original_source=SOURCE)
    assert profile.identity_kind == 'synthetic_audience'
    assert profile.data_source is None and profile.data_ref is None and profile.memory_facts == []
    assert memory.validate_passages(SOURCE, profile.source_passages)
    assert profile.communication_style == memory.DEFAULT_STYLE
    assert 'FICTIONAL BIOGRAPHY' in profile.persona
    assert 'Biografía ficticia' in profile.fictional_biography
    assert all('Vega fue condenada' not in p['text'] for p in profile.source_passages)


@pytest.mark.parametrize('kind', ['reddit', 'twitter'])
def test_disabled_platform_is_not_required_by_memory_policy(tmp_path, kind):
    gen = generator()
    path = tmp_path / ('reddit_profiles.json' if kind == 'reddit' else 'twitter_profiles.csv')
    gen.save_profiles([replace(named(gen), profile_schema_version=None)], str(path), kind)
    policy = adapter.profile_memory_policy(tmp_path, 'parallel', enable_twitter=kind == 'twitter',
                                           enable_reddit=kind == 'reddit', requested=True)
    assert policy['graph_update'] == 'enabled' and policy['source_graph'] == 'legacy_shared'


@pytest.mark.parametrize('version', [True, False, '1', '2', 2, '', 1.0])
def test_incompatible_profile_version_never_becomes_legacy_bio(version):
    profile = {'profile_schema_version': version, 'identity_kind': 'named_actor', 'bio': 'BIO_LIBRE_INVENTADA'}
    assert memory.is_canonical(profile) is False
    with pytest.raises(ValueError, match='incompatible'):
        build_interview_system_prompt('Actor', 'Cargo inventado', 'BIO_LIBRE_INVENTADA', profile=profile)


@pytest.mark.parametrize('platform', ['reddit', 'twitter'])
@pytest.mark.parametrize('kind', ['named', 'survey', 'mixed'])
def test_real_environment_reset_signup_and_manual_post_keep_identity(tmp_path, monkeypatch, platform, kind):
    import socket
    (tmp_path / 'log').mkdir()
    monkeypatch.chdir(tmp_path)
    from camel.models import StubModel
    from camel.types import ModelType
    from oasis.environment.env import OasisEnv
    from oasis.social_platform.typing import DefaultPlatformType, ActionType
    monkeypatch.setattr(socket.socket, 'connect', lambda *args: pytest.fail('No se permite red'))
    gen = generator()
    profile = survey(gen) if kind == 'survey' else named(gen)
    profiles = [profile]
    if kind == 'mixed':
        profiles.append(replace(profile, profile_schema_version=None, user_id=1, user_name='legacy_user', name='Legacy'))
    path = tmp_path / ('reddit_profiles.json' if platform == 'reddit' else 'twitter_profiles.csv')
    gen.save_profiles(profiles, str(path), platform)
    async def smoke():
        graph = await adapter._generate(str(path), platform, model=StubModel(ModelType.STUB),
                                        available_actions=['create_post', 'create_comment'])
        env = OasisEnv(graph, DefaultPlatformType.REDDIT if platform == 'reddit' else DefaultPlatformType.TWITTER,
                       database_path=str(tmp_path / 'observed.db'))
        try:
            await env.reset()
            agent = list(graph.get_agents())[0][1]
            await agent.perform_action_by_data(ActionType.CREATE_POST, content='Opinión simulada de prueba')
            stored = env.platform.db.execute('SELECT user_name,name FROM user ORDER BY user_id').fetchall()
            assert stored == [(p.user_name, p.name) for p in profiles]
            assert env.platform.db.execute('SELECT count(*) FROM post').fetchone()[0] == 1
            assert memory.validate_passages(SOURCE, profile.source_passages)
        finally:
            await env.close()
    asyncio.run(smoke())
