"""«A todos» respeta el tope por entrevista efectiva antes de enviar órdenes/modelos."""
from pathlib import Path

import pytest

from app.config import Config
from app.services.simulation_manager import SimulationManager
from app.services.simulation_runner import SimulationRunner, interview_target_count
from app.utils.fs import atomic_write_json
from test_cost_limits import auth, client, prepared_simulation  # noqa: F401
from test_pipeline import storage  # noqa: F401


def config_for(n, both=True):
    sid = prepared_simulation()
    path = Path(SimulationManager.SIMULATION_DATA_DIR) / sid / 'simulation_config.json'
    atomic_write_json(str(path), {'agent_configs': [{'agent_id': i} for i in range(n)],
                                 'reddit_config': {'platform': 'reddit'},
                                 'twitter_config': {'platform': 'twitter'} if both else None})
    return sid, path


@pytest.mark.parametrize('n,platform', [(21, 'reddit'), (11, None)])
def test_all_cannot_bypass_limit_and_never_checks_or_sends_to_environment(client, monkeypatch, n, platform):
    sid, _ = config_for(n)
    def forbidden(*args, **kwargs):
        raise AssertionError('No consultar ni enviar al entorno antes del tope')
    monkeypatch.setattr(SimulationRunner, 'check_env_alive', forbidden)
    monkeypatch.setattr(SimulationRunner, 'interview_all_agents', forbidden)
    r = client.post('/api/simulation/interview/all', headers=auth(),
                    json={'simulation_id': sid, 'prompt': 'Pregunta sintética', 'platform': platform})
    assert r.status_code == 400
    assert str(Config.MAX_INTERVIEWS_PER_REQUEST) in r.get_json()['error']


@pytest.mark.parametrize('n,platform,both', [(20, 'reddit', True), (10, None, True), (20, None, False)])
def test_all_accepts_the_limit_and_passes_the_same_agents_to_batch(client, monkeypatch, n, platform, both):
    sid, _ = config_for(n, both=both)
    seen = []
    monkeypatch.setattr(SimulationRunner, 'check_env_alive', lambda *_: True)
    monkeypatch.setattr(SimulationRunner, 'interview_agents_batch', lambda **kwargs:
                        seen.append(kwargs) or {'success': True, 'interviews_count': len(kwargs['interviews'])})
    r = client.post('/api/simulation/interview/all', headers=auth(),
                    json={'simulation_id': sid, 'prompt': 'Pregunta sintética', 'platform': platform})
    assert r.status_code == 200 and r.get_json()['success']
    assert len(seen) == 1 and len(seen[0]['interviews']) == n
    assert seen[0]['platform'] == platform


@pytest.mark.parametrize('n,platform', [(21, 'reddit'), (11, None)])
def test_runner_also_blocks_oversized_all_before_any_batch_dispatch(storage, monkeypatch, n, platform):
    sid, _ = config_for(n)
    def forbidden(**kwargs):
        raise AssertionError('No enviar orden de entrevista')
    monkeypatch.setattr(SimulationRunner, 'interview_agents_batch', forbidden)
    with pytest.raises(ValueError, match=str(Config.MAX_INTERVIEWS_PER_REQUEST)):
        SimulationRunner.interview_all_agents(sid, 'Pregunta sintética', platform=platform)


def test_corrupt_configuration_cannot_trigger_interviews(client, monkeypatch):
    sid, path = config_for(1)
    path.write_text('{', encoding='utf-8')
    monkeypatch.setattr(SimulationRunner, 'check_env_alive', lambda *_: pytest.fail('no enviar'))
    r = client.post('/api/simulation/interview/all', headers=auth(),
                    json={'simulation_id': sid, 'prompt': 'Pregunta sintética'})
    assert r.status_code == 400 and path.read_text() == '{'


def test_effective_target_count_includes_both_platforms_and_item_overrides():
    assert interview_target_count([{'agent_id': 1}], config={}) == 2
    assert interview_target_count([{'agent_id': 1}], platform='reddit') == 1
    assert interview_target_count([{'agent_id': 1, 'platform': 'twitter'}]) == 1


def test_batch_also_counts_both_platforms_before_any_environment_call(client, monkeypatch):
    sid, _ = config_for(11)
    monkeypatch.setattr(SimulationRunner, 'check_env_alive', lambda *_: pytest.fail('no consultar entorno'))
    r = client.post('/api/simulation/interview/batch', headers=auth(), json={
        'simulation_id': sid, 'interviews': [{'agent_id': i, 'prompt': 'Pregunta'} for i in range(11)]})
    assert r.status_code == 400 and '20' in r.get_json()['error']


def test_batch_accepts_twenty_single_platform_interviews(client, monkeypatch):
    sid, _ = config_for(20)
    seen = []
    monkeypatch.setattr(SimulationRunner, 'check_env_alive', lambda *_: True)
    monkeypatch.setattr(SimulationRunner, 'interview_agents_batch', lambda **kwargs:
                        seen.append(kwargs) or {'success': True})
    r = client.post('/api/simulation/interview/batch', headers=auth(), json={
        'simulation_id': sid, 'platform': 'reddit',
        'interviews': [{'agent_id': i, 'prompt': 'Pregunta'} for i in range(20)]})
    assert r.status_code == 200 and len(seen) == 1 and len(seen[0]['interviews']) == 20


def test_direct_batch_cannot_send_twenty_two_interviews(storage, monkeypatch):
    sid, _ = config_for(11)
    from app.services import simulation_runner
    monkeypatch.setattr(simulation_runner, 'SimulationIPCClient', lambda *_: pytest.fail('no crear IPC'))
    with pytest.raises(ValueError, match='20'):
        SimulationRunner.interview_agents_batch(sid, [{'agent_id': i, 'prompt': 'Pregunta'} for i in range(11)])
