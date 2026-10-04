"""The action log and persisted runner share the simulation clock, without OASIS."""
import ast
import json
from pathlib import Path

import pytest

from scripts.action_logger import ActionLogger, PlatformActionLogger
from app.services.simulation_runner import SimulationRunner, SimulationRunState


def records(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines()]


@pytest.mark.parametrize('platform', ['twitter', 'reddit'])
@pytest.mark.parametrize('minutes, limit, configured, planned, elapsed', [
    (60, 15, 72, 15, 15), (30, 15, 144, 15, 7.5), (45, None, 96, 96, 11.25),
    (60, 100, 72, 72, 15), (60, 0, 72, 72, 15),
])
def test_start_clock_and_round_end_drive_persisted_monitor_metadata(tmp_path, monkeypatch, platform,
                                                                   minutes, limit, configured, planned, elapsed):
    monkeypatch.setattr(SimulationRunner, '_graph_memory_enabled', {})
    monkeypatch.setattr(SimulationRunner, 'RUN_STATE_DIR', str(tmp_path))
    monkeypatch.setattr(SimulationRunner, '_run_states', {})
    logger = PlatformActionLogger(platform, str(tmp_path))
    logger.log_simulation_start({'time_config': {'total_simulation_hours': 72, 'minutes_per_round': minutes},
                                 'agent_configs': [{}, {}]}, max_rounds=limit)
    logger.log_round_end(0, 2)
    logger.log_round_start(15, simulated_hour=14)
    logger.log_round_end(15, 0)
    start, zero, _, end = records(logger.log_path)
    assert start['total_rounds'] == planned and start['configured_total_rounds'] == configured
    assert start['minutes_per_round'] == minutes and start['agents_count'] == 2
    assert zero['simulated_hours'] == 0 and end['simulated_hours'] == elapsed
    state = SimulationRunState('sim_aaaaaaaaaaaa', total_rounds=planned)
    SimulationRunner._read_action_log(logger.log_path, 0, state, platform)
    assert state.current_round == 15 and state.simulated_hours == elapsed
    assert getattr(state, platform + '_simulated_hours') == elapsed
    (tmp_path / state.simulation_id).mkdir()
    (tmp_path / state.simulation_id / 'state.json').write_text('{}')
    SimulationRunner._save_run_state(state)
    assert json.loads((tmp_path / state.simulation_id / 'run_state.json').read_text())['simulated_hours'] == elapsed


def test_legacy_logger_keeps_independent_platform_clocks(tmp_path):
    logger = ActionLogger(str(tmp_path / 'actions.jsonl'))
    for platform, minutes in [('twitter', 60), ('reddit', 30)]:
        logger.log_simulation_start(platform, {'time_config': {'total_simulation_hours': 72, 'minutes_per_round': minutes}},
                                    max_rounds=15)
        logger.log_round_end(15, 0, platform)
    data = records(logger.log_path)
    assert data[0]['total_rounds'] == data[2]['total_rounds'] == 15
    assert data[0]['configured_total_rounds'] == 72 and data[2]['configured_total_rounds'] == 144
    assert data[1]['simulated_hours'] == 15 and data[3]['simulated_hours'] == 7.5


def test_default_clock_and_old_round_logging_without_start_remain_compatible(tmp_path):
    logger = PlatformActionLogger('twitter', str(tmp_path))
    logger.log_round_end(1, 0)
    logger.log_simulation_start({})
    logger.log_round_end(1, 0)
    old, start, new = records(logger.log_path)
    assert 'simulated_hours' not in old
    assert start['total_rounds'] == start['configured_total_rounds'] == 144
    assert new['simulated_hours'] == 0.5


def test_both_parallel_platform_functions_forward_requested_limit_to_start_metadata():
    # Parse source only: importing this script creates OASIS/model machinery.
    script = Path(__file__).parents[1] / 'scripts' / 'run_parallel_simulation.py'
    tree = ast.parse(script.read_text())
    for name in ('run_twitter_simulation', 'run_reddit_simulation'):
        function = next(node for node in tree.body if isinstance(node, ast.AsyncFunctionDef) and node.name == name)
        starts = [node for node in ast.walk(function) if isinstance(node, ast.Call)
                  and isinstance(node.func, ast.Attribute) and node.func.attr == 'log_simulation_start']
        assert len(starts) == 1
        assert any(keyword.arg == 'max_rounds' and isinstance(keyword.value, ast.Name)
                   and keyword.value.id == 'max_rounds' for keyword in starts[0].keywords)
