"""
/run-status/detail: mismas respuestas que antes, leyendo el archivo de acciones una sola vez.
"""

import json

import pytest

from app import create_app
from app.config import Config
from app.models.project import ProjectManager
from app.services.simulation_manager import SimulationManager
from app.services.simulation_runner import RunnerStatus, SimulationRunner, SimulationRunState

from test_pipeline import storage  # noqa: F401

TOKEN = "token-detalle"


@pytest.fixture
def client(storage, monkeypatch):
    monkeypatch.setattr(Config, "API_AUTH_REQUIRED", True)
    monkeypatch.setattr(Config, "API_AUTH_TOKEN", TOKEN)
    monkeypatch.setattr(SimulationRunner, "_run_states", {})
    app = create_app()
    app.config["TESTING"] = True
    app.config["RATELIMIT_ENABLED"] = False
    return app.test_client()


def action(round_num, agent, kind="CREATE_POST", ts="2026-10-01T10:00:00"):
    return {"round": round_num, "timestamp": ts, "agent_id": agent, "agent_name": f"A{agent}", "action_type": kind,
            "action_args": {"content": f"r{round_num}-a{agent}"}, "result": None, "success": True}


def write_actions(folder, platform, rows):
    (folder / platform).mkdir(parents=True, exist_ok=True)
    (folder / platform / "actions.jsonl").write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")


def setup_sim():
    project = ProjectManager.create_project(name="P", owner_id=None)
    sim = SimulationManager().create_simulation(project_id=project.project_id, graph_id="mirofish_g00000000001")
    folder = __import__("pathlib").Path(SimulationManager.SIMULATION_DATA_DIR) / sim.simulation_id
    write_actions(folder, "twitter", [action(1, 1, ts="2026-10-01T10:00:01"), action(2, 1, ts="2026-10-01T10:00:05"), action(2, 2, ts="2026-10-01T10:00:06")])
    write_actions(folder, "reddit", [action(1, 3, ts="2026-10-01T10:00:02"), action(2, 4, ts="2026-10-01T10:00:07")])
    state = SimulationRunState(simulation_id=sim.simulation_id, runner_status=RunnerStatus.RUNNING, current_round=2, total_rounds=10)
    SimulationRunner._run_states[sim.simulation_id] = state
    return sim.simulation_id


def get(client, sid, query=""):
    r = client.get(f"/api/simulation/{sid}/run-status/detail{query}", headers={"Authorization": f"Bearer {TOKEN}"})
    assert r.status_code == 200, r.get_json()
    return r.get_json()["data"]


def test_detail_has_every_list_and_reads_the_actions_once(client, monkeypatch):
    sid = setup_sim()
    calls = []
    real = SimulationRunner.get_all_actions.__func__

    def counting(cls, *args, **kwargs):
        calls.append(kwargs)
        return real(cls, *args, **kwargs)

    monkeypatch.setattr(SimulationRunner, "get_all_actions", classmethod(counting))
    data = get(client, sid)
    assert len(calls) == 1                                                  # antes: 4 lecturas completas por consulta
    assert len(data["all_actions"]) == 5
    assert {a["platform"] for a in data["twitter_actions"]} == {"twitter"} and len(data["twitter_actions"]) == 3
    assert {a["platform"] for a in data["reddit_actions"]} == {"reddit"} and len(data["reddit_actions"]) == 2
    assert sorted(a["agent_id"] for a in data["recent_actions"]) == [1, 2, 4]            # solo la ronda actual (2)
    assert all(a["round_num"] == 2 for a in data["recent_actions"])


def test_the_platform_filter_still_applies(client):
    sid = setup_sim()
    data = get(client, sid, "?platform=twitter")
    assert len(data["all_actions"]) == 3 and len(data["twitter_actions"]) == 3 and data["reddit_actions"] == []
    assert sorted(a["agent_id"] for a in data["recent_actions"]) == [1, 2]
