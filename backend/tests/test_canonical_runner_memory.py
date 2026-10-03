"""El runner real no crea updater fuente con contrato nuevo (Popen/modelos simulados)."""
import json
from dataclasses import replace

import pytest

from app.services import simulation_runner as runner
from app.services.simulation_runner import SimulationRunner
from test_runner_lifecycle import isolated, FakeProc, SIM  # noqa: F401
from test_canonical_profile_memory import generator, named


@pytest.mark.parametrize('platform', ['reddit', 'twitter', 'parallel'])
@pytest.mark.parametrize('canonical', [True, False])
def test_runner_persists_policy_and_creates_graph_updater_only_for_legacy(isolated, monkeypatch, platform, canonical):
    directory = isolated / SIM
    directory.mkdir()
    (directory / 'simulation_config.json').write_text(json.dumps({
        'time_config': {'total_simulation_hours': 1, 'minutes_per_round': 60},
        'twitter_config': {} if platform in ('twitter', 'parallel') else None,
        'reddit_config': {} if platform in ('reddit', 'parallel') else None,
    }))
    gen = generator()
    profile = named(gen)
    if not canonical:
        profile = replace(profile, profile_schema_version=None)
    for kind, filename in [('reddit', 'reddit_profiles.json'), ('twitter', 'twitter_profiles.csv')]:
        if platform in (kind, 'parallel'):
            gen.save_profiles([profile], str(directory / filename), kind)
    calls = []
    monkeypatch.setattr(runner.ZepGraphMemoryManager, 'create_updater', lambda *args: calls.append(args))
    monkeypatch.setattr(runner.subprocess, 'Popen', lambda *args, **kwargs: FakeProc())
    monkeypatch.setattr(runner.threading.Thread, 'start', lambda self: None)
    try:
        state = SimulationRunner.start_simulation(SIM, platform=platform, enable_graph_memory_update=True, graph_id='mirofish_source')
        assert bool(calls) is not canonical
        assert SimulationRunner._graph_memory_enabled[SIM] is not canonical
        assert state.memory_policy['source_graph'] == ('immutable' if canonical else 'legacy_shared')
        persisted = json.loads((directory / 'run_state.json').read_text())
        assert persisted['memory_policy'] == state.memory_policy
        restored = SimulationRunner._load_run_state(SIM)
        assert restored.memory_policy == state.memory_policy
    finally:
        for file in SimulationRunner._stdout_files.values():
            if file:
                file.close()
