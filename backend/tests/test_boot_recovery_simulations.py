"""
Al arrancar, una simulación que estaba «en marcha» no puede seguirlo estando: su proceso murió con el servidor.
"""

import json
import os

import pytest

from app.services.boot_recovery import recover_orphaned_simulations
from app.services.simulation_manager import SimulationManager
from app.services.simulation_runner import SimulationRunner

REASON = "El servidor se reinició."


@pytest.fixture
def sims(tmp_path, monkeypatch):
    monkeypatch.setattr(SimulationManager, "SIMULATION_DATA_DIR", str(tmp_path))
    monkeypatch.setattr(SimulationRunner, "RUN_STATE_DIR", str(tmp_path))
    return tmp_path


def make(root, sim_id, run=None, state=None, env=None, extra=None):
    folder = root / sim_id
    folder.mkdir()
    if run is not None:
        (folder / "run_state.json").write_text(json.dumps(run), encoding="utf-8")
    if state is not None:
        (folder / "state.json").write_text(json.dumps(state), encoding="utf-8")
    if env is not None:
        (folder / "env_status.json").write_text(json.dumps(env), encoding="utf-8")
    for name, text in (extra or {}).items():
        (folder / name).write_text(text, encoding="utf-8")
    return folder


def load(root, sim_id, name):
    return json.loads((root / sim_id / name).read_text(encoding="utf-8"))


def test_running_simulations_become_failed_keeping_their_data(sims):
    make(sims, "sim_aaaaaaaaaaa1",
         run={"runner_status": "running", "current_round": 38, "total_rounds": 40, "twitter_running": True,
              "reddit_running": True, "twitter_actions_count": 120, "reddit_actions_count": 90},
         state={"status": "running", "twitter_status": "running", "reddit_status": "completed"},
         env={"status": "alive", "twitter_available": True},
         extra={"actions.jsonl": '{"a":1}\n'})
    assert recover_orphaned_simulations(REASON) == 1
    run = load(sims, "sim_aaaaaaaaaaa1", "run_state.json")
    assert run["runner_status"] == "failed" and run["error"] == REASON
    assert run["twitter_running"] is False and run["reddit_running"] is False
    assert (run["current_round"], run["twitter_actions_count"], run["reddit_actions_count"]) == (38, 120, 90)
    state = load(sims, "sim_aaaaaaaaaaa1", "state.json")
    assert (state["status"], state["twitter_status"], state["reddit_status"]) == ("failed", "failed", "completed")
    assert load(sims, "sim_aaaaaaaaaaa1", "env_status.json")["status"] == "stopped"
    assert (sims / "sim_aaaaaaaaaaa1" / "actions.jsonl").read_text(encoding="utf-8") == '{"a":1}\n'


@pytest.mark.parametrize("live", ["starting", "running", "paused", "stopping"])
def test_every_live_runner_state_is_recovered(sims, live):
    make(sims, "sim_bbbbbbbbbbb1", run={"runner_status": live})
    assert recover_orphaned_simulations(REASON) == 1
    assert load(sims, "sim_bbbbbbbbbbb1", "run_state.json")["runner_status"] == "failed"


def test_finished_idle_and_prepared_simulations_are_left_alone(sims):
    make(sims, "sim_ccccccccccc1", run={"runner_status": "completed"}, state={"status": "completed"}, env={"status": "stopped"})
    make(sims, "sim_ccccccccccc2", run={"runner_status": "stopped"}, state={"status": "stopped"})
    make(sims, "sim_ccccccccccc3", state={"status": "ready"})
    make(sims, "sim_ccccccccccc4", state={"status": "preparing"})            # la preparación la retoma la pantalla
    before = {sid: {n: (sims / sid / n).read_text(encoding="utf-8") for n in os.listdir(sims / sid)} for sid in os.listdir(sims)}
    assert recover_orphaned_simulations(REASON) == 0
    after = {sid: {n: (sims / sid / n).read_text(encoding="utf-8") for n in os.listdir(sims / sid)} for sid in os.listdir(sims)}
    assert before == after


def test_broken_files_and_foreign_entries_do_not_stop_the_sweep(sims):
    make(sims, "sim_ddddddddddd1", run=None, extra={"run_state.json": '{"runner_st'})
    make(sims, "sim_ddddddddddd2", run={"runner_status": "running"})
    (sims / "notas.txt").write_text("hola", encoding="utf-8")
    (sims / "no_es_una_simulacion").mkdir()
    assert recover_orphaned_simulations(REASON) == 1
    assert load(sims, "sim_ddddddddddd2", "run_state.json")["runner_status"] == "failed"


def test_it_is_idempotent_and_ok_without_a_folder(sims, tmp_path, monkeypatch):
    make(sims, "sim_eeeeeeeeeee1", run={"runner_status": "running"})
    assert recover_orphaned_simulations(REASON) == 1
    assert recover_orphaned_simulations(REASON) == 0
    monkeypatch.setattr(SimulationRunner, "RUN_STATE_DIR", str(tmp_path / "no_existe"))
    assert recover_orphaned_simulations(REASON) == 0
