"""Adaptadores de OASIS: usa su plantilla extensible, sin editar la dependencia."""
import csv
import json

from .profile_memory import is_canonical, render_memory, decode_twitter_profile

TEMPLATE = '''# OBJECTIVE
You are a {platform} user in a simulation. Observe the platform posts and choose actions using the available functions.

# SELF-DESCRIPTION
{reference_memory}

# RESPONSE METHOD
Please perform actions by tool calling.
'''


def load_profiles(path, platform):
    with open(path, encoding='utf-8', newline='') as source:
        rows = json.load(source) if platform == 'reddit' else list(csv.DictReader(source))
    if not isinstance(rows, list):
        raise ValueError('Lista de perfiles inválida')
    profiles = []
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError('Perfil inválido')
        if platform == 'twitter':
            row = decode_twitter_profile(row)
        elif row.get('profile_schema_version') is not None and not is_canonical(row):
            raise ValueError('Versión de perfil no compatible')
        profiles.append(row)
    return profiles


async def _generate(profile_path, platform, model=None, available_actions=None):
    # Carga diferida: importar este adaptador no inicializa OASIS ni modelos.
    from camel.prompts import TextPrompt
    from oasis.social_agent import AgentGraph, SocialAgent
    from oasis.social_platform.config import UserInfo
    from oasis.social_agent.agents_generator import generate_reddit_agent_graph as legacy_reddit
    from oasis.social_agent.agents_generator import generate_twitter_agent_graph as legacy_twitter
    profiles = load_profiles(profile_path, platform)
    if not any(is_canonical(profile) for profile in profiles):
        legacy = legacy_reddit if platform == 'reddit' else legacy_twitter
        return await legacy(profile_path, model=model, available_actions=available_actions)
    graph = AgentGraph()
    for index, profile in enumerate(profiles):
        canonical = is_canonical(profile)
        if canonical:
            user_info = UserInfo(user_name=profile.get('user_name', profile.get('username', '')),
                                 name=profile.get('name', ''),
                                 description=profile.get('name', ''), recsys_type=platform,
                                 profile={'platform': platform, 'reference_memory': render_memory(profile)})
            template = TextPrompt(TEMPLATE)
        else:
            other_info = {'user_profile': profile.get('persona', profile.get('user_char'))}
            if platform == 'reddit':
                other_info.update({key: profile[key] for key in ('age', 'gender', 'mbti', 'country')})
            user_info = UserInfo(user_name=profile.get('username'), name=profile.get('name', profile.get('username')),
                                 description=profile.get('bio', profile.get('description')),
                                 recsys_type=platform, profile={'nodes': [], 'edges': [], 'other_info': other_info})
            template = None
        agent = SocialAgent(agent_id=int(profile['user_id']) if canonical else index,
                            user_info=user_info, user_info_template=template,
                            agent_graph=graph, model=model, available_actions=available_actions)
        graph.add_agent(agent)
    return graph


async def generate_reddit_agent_graph(profile_path, model=None, available_actions=None):
    return await _generate(profile_path, 'reddit', model, available_actions)


async def generate_twitter_agent_graph(profile_path, model=None, available_actions=None):
    return await _generate(profile_path, 'twitter', model, available_actions)


def profile_memory_policy(directory, platform, enable_twitter=True, enable_reddit=True, requested=False):
    """Protege fuente ante perfiles nuevos, mixtos o contrato ilegible; legacy sigue igual."""
    from pathlib import Path
    files = []
    if platform == 'twitter' or (platform == 'parallel' and enable_twitter):
        files.append(('twitter', 'twitter_profiles.csv'))
    if platform == 'reddit' or (platform == 'parallel' and enable_reddit):
        files.append(('reddit', 'reddit_profiles.json'))
    reason, canonical = '', False
    for kind, filename in files:
        try:
            rows = load_profiles(str(Path(directory) / filename), kind)
            if not rows:
                raise ValueError('Sin perfiles')
            canonical |= any(is_canonical(row) for row in rows)
            if canonical:
                reason = 'blocked_for_canonical_profiles'
        except (OSError, ValueError, TypeError, KeyError):
            reason = 'blocked_for_unreadable_profile_contract'
            canonical = True
            break
    return {'source_graph': 'immutable' if canonical else 'legacy_shared',
            'social_activity': 'simulated_local_evidence' if canonical else 'legacy_graph_and_local_evidence',
            'graph_update': reason if canonical else ('enabled' if requested else 'disabled'),
            'requested': bool(requested)}
