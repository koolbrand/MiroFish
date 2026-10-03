"""
Modo automático (pipeline en el servidor), sin LLM, Neo4j ni OASIS.

Las rutas de etapa (build, create, prepare, start, report...) las responde un
guion (`backend`); el resto de llamadas internas va a la app real, que lee el
estado de disco en carpetas temporales.
"""

import io
import json
import os
import threading
import time
from datetime import datetime, timedelta

import pytest

from app import create_app
from app.api import graph as graph_api
from app.config import Config
from app.models.project import ProjectManager, ProjectStatus
from app.services import auto_pipeline, pipeline_state
from app.services.report_agent import Report, ReportManager, ReportStatus
from app.services.simulation_manager import SimulationManager, SimulationStatus
from app.services.simulation_runner import RunnerStatus, SimulationRunner, SimulationRunState
from app.utils.security import INTERNAL_AUTH_HEADER

TOKEN = "test-token-pipeline"
GRAPH_ID = "mirofish_test"
REPORT_ID = "report_auto00000001"


def auth():
    return {"Authorization": f"Bearer {TOKEN}"}


# ============== Entorno ==============

@pytest.fixture
def storage(tmp_path, monkeypatch):
    sims = tmp_path / "simulations"
    for d in ("projects", "simulations", "reports"):
        (tmp_path / d).mkdir()
    monkeypatch.setattr(ProjectManager, "PROJECTS_DIR", str(tmp_path / "projects"))
    monkeypatch.setattr(SimulationManager, "SIMULATION_DATA_DIR", str(sims))
    monkeypatch.setattr(SimulationRunner, "RUN_STATE_DIR", str(sims))
    monkeypatch.setattr(Config, "OASIS_SIMULATION_DATA_DIR", str(sims))
    monkeypatch.setattr(ReportManager, "REPORTS_DIR", str(tmp_path / "reports"))
    monkeypatch.setattr(SimulationRunner, "_run_states", {})
    monkeypatch.setattr(SimulationRunner, "_processes", {})
    return tmp_path


@pytest.fixture
def auth_config(monkeypatch):
    monkeypatch.setattr(Config, "API_AUTH_REQUIRED", True)
    monkeypatch.setattr(Config, "API_AUTH_TOKEN", TOKEN)
    monkeypatch.setattr(Config, "POCKETBASE_URL", "")


@pytest.fixture
def app(storage, auth_config, monkeypatch):
    monkeypatch.setattr(auto_pipeline, "POLL_SECONDS", 0.01)
    monkeypatch.setattr(auto_pipeline, "STARTING_GRACE_SECONDS", 0.05)
    application = create_app()
    application.config["TESTING"] = True
    application.config["RATELIMIT_ENABLED"] = False
    yield application
    # Ningún hilo del modo automático sobrevive al test
    for runner in list(auto_pipeline._ACTIVE_RUNS.values()):
        runner.cancel_event.set()
        runner.thread.join(timeout=5)


@pytest.fixture
def client(app):
    return app.test_client()


class FakeOntologyGenerator:
    calls = []
    fail = None

    def generate(self, document_texts, simulation_requirement, additional_context=None):
        FakeOntologyGenerator.calls.append((list(document_texts), simulation_requirement, additional_context))
        if FakeOntologyGenerator.fail:
            raise RuntimeError(FakeOntologyGenerator.fail)
        return {
            "entity_types": [{"name": "Persona", "attributes": []}],
            "edge_types": [{"name": "HABLA_CON"}],
            "analysis_summary": "Resumen",
        }


@pytest.fixture
def ontology(monkeypatch):
    FakeOntologyGenerator.calls = []
    FakeOntologyGenerator.fail = None
    monkeypatch.setattr(graph_api, "OntologyGenerator", FakeOntologyGenerator)
    # La traducción de los tipos en segundo plano llamaría a un modelo de verdad
    FakeOntologyGenerator.warmed = []
    monkeypatch.setattr(graph_api.type_labels_service, "warm_async",
                        lambda ontology, locale: FakeOntologyGenerator.warmed.append((ontology, locale)))
    return FakeOntologyGenerator


def ok(data=None, **extra):
    return 200, {"success": True, "data": data or {}, **extra}


def err(status, message, **extra):
    return status, {"success": False, "error": message, **extra}


def run_status(sim_id, status, **extra):
    return {
        "simulation_id": sim_id,
        "runner_status": status,
        "twitter_running": status == "running",
        "reddit_running": status == "running",
        "twitter_completed": status == "completed",
        "reddit_completed": status == "completed",
        "twitter_actions_count": 5,
        "reddit_actions_count": 5,
        **extra,
    }


class FakeBackend:
    """Guion de las rutas de etapa. Devuelve None para delegar en la app real."""

    def __init__(self):
        self.project_id = None
        self.sim_id = None
        self.stage_at = {}
        self.graph_task = ["processing", "completed"]
        self.graph_error = None
        self.prepare_response = None
        self.prepare_polls = ["processing", "completed"]
        self.start_response = None
        self.started = False
        self.stopped = False
        self.run_after_start = ["running", "completed"]
        self.report_response = None
        self.block = {}          # path -> threading.Event que la llamada espera
        self.entered = {}        # path -> threading.Event (la llamada ha llegado)

    def _stage(self):
        state = pipeline_state.read_pipeline(self.project_id) if self.project_id else None
        return state.get("stage") if state else None

    @staticmethod
    def _next(seq):
        return seq.pop(0) if len(seq) > 1 else seq[0]

    def __call__(self, method, path, payload):
        # El hilo puede adelantarse al test: el proyecto sale del propio cuerpo
        if isinstance(payload, dict) and payload.get("project_id"):
            self.project_id = payload["project_id"]
        if path in self.entered:
            self.entered[path].set()
        if path in self.block:
            assert self.block[path].wait(5)

        if method == "POST" and not path.endswith("/status"):
            self.stage_at.setdefault(path, self._stage())

        if (method, path) == ("POST", "/api/graph/build"):
            project = ProjectManager.get_project(payload["project_id"])
            if self.graph_error:
                project.status, project.error = ProjectStatus.FAILED, self.graph_error
            else:
                project.status, project.graph_id = ProjectStatus.GRAPH_COMPLETED, GRAPH_ID
            ProjectManager.save_project(project)
            return ok({"project_id": payload["project_id"], "task_id": "task-graph"})
        if (method, path) == ("GET", "/api/graph/task/task-graph"):
            status = self._next(self.graph_task)
            return ok({"task_id": "task-graph", "status": status, "message": f"[{status}]",
                       "error": "Traceback (most recent call last): ..." if status == "failed" else None})
        if (method, path) == ("POST", "/api/simulation/create"):
            state = SimulationManager().create_simulation(
                project_id=payload["project_id"], graph_id=payload["graph_id"],
                enable_twitter=payload["enable_twitter"], enable_reddit=payload["enable_reddit"],
            )
            self.sim_id = state.simulation_id
            return ok(state.to_dict())
        if (method, path) == ("POST", "/api/simulation/prepare"):
            self.sim_id = payload["simulation_id"]
            return self.prepare_response or ok({
                "simulation_id": payload["simulation_id"], "task_id": "task-prep",
                "status": "preparing", "already_prepared": False,
            })
        if (method, path) == ("POST", "/api/simulation/prepare/status"):
            return ok({"task_id": "task-prep", "status": self._next(self.prepare_polls)})
        if method == "POST" and path == "/api/simulation/start":
            self.started = True
            return self.start_response or ok(run_status(payload["simulation_id"], "running"))
        if method == "POST" and path == "/api/simulation/stop":
            self.stopped = True
            return ok(run_status(payload["simulation_id"], "stopped"))
        if method == "GET" and path.endswith("/run-status"):
            if self.stopped:
                return ok(run_status(self.sim_id, "stopped"))
            if not self.started:
                return None  # la ruta real lee run_state.json de disco
            return ok(run_status(self.sim_id, self._next(self.run_after_start)))
        if (method, path) == ("POST", "/api/report/generate"):
            return self.report_response or ok({
                "simulation_id": payload["simulation_id"], "report_id": REPORT_ID,
                "task_id": "task-rep", "status": "generating", "already_generated": False,
            })
        if (method, path) == ("POST", "/api/report/generate/status"):
            return ok({"task_id": "task-rep", "status": "completed"})
        return None


@pytest.fixture
def backend(monkeypatch):
    """Sustituye al cliente interno: guion para las etapas, app real para el resto."""
    script = FakeBackend()
    script.calls = []
    real_client = auto_pipeline.InternalApiClient

    class ScriptedClient:
        def __init__(self, app, locale):
            self._real = real_client(app, locale)

        def get(self, path):
            return self._call("GET", path, None)

        def post(self, path, payload):
            return self._call("POST", path, payload)

        def _call(self, method, path, payload):
            script.calls.append((method, path, payload))
            result = script(method, path, payload)
            if result is not None:
                return result
            return self._real.get(path) if method == "GET" else self._real.post(path, payload)

    monkeypatch.setattr(auto_pipeline, "InternalApiClient", ScriptedClient)
    return script


def action_posts(script):
    """POST que lanzan algo (sin los sondeos de estado)."""
    return [(path, payload) for method, path, payload in script.calls
            if method == "POST" and not path.endswith("/status")]


def wait_for(predicate, timeout=10):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        value = predicate()
        if value:
            return value
        time.sleep(0.01)
    raise AssertionError("tiempo de espera agotado en el test")


def pipeline_of(client, project_id):
    r = client.get(f"/api/pipeline/{project_id}", headers=auth())
    assert r.status_code == 200
    return r.get_json()["data"]


def wait_finished(client, project_id):
    return wait_for(lambda: (lambda s: s if s.get("status") != "running" else None)(pipeline_of(client, project_id)))


def upload(client, path="/api/pipeline/auto", **fields):
    data = {
        "simulation_requirement": "¿Comprarán la app?",
        "project_name": "Demo",
        "files": (io.BytesIO(b"# Brief\nUna app para familias."), "brief.md"),
    }
    data.update(fields)
    return client.post(path, headers=auth(), data=data, content_type="multipart/form-data")


# ============== Estado en disco para reanudar ==============

def make_project(graph_done=True, with_ontology=True):
    project = ProjectManager.create_project(name="Manual")
    project.simulation_requirement = "¿Comprarán la app?"
    if with_ontology:
        project.ontology = {"entity_types": [{"name": "Persona"}], "edge_types": []}
        project.status = ProjectStatus.ONTOLOGY_GENERATED
    if graph_done:
        project.status = ProjectStatus.GRAPH_COMPLETED
        project.graph_id = "mirofish_existing"
    ProjectManager.save_project(project)
    ProjectManager.save_extracted_text(project.project_id, "\n\n=== brief.md ===\nUna app para familias.")
    return project.project_id


def make_prepared_simulation(project_id, created_at):
    manager = SimulationManager()
    state = manager.create_simulation(project_id=project_id, graph_id="mirofish_existing")
    state.status = SimulationStatus.READY
    state.config_generated = True
    state.created_at = created_at
    manager._save_simulation_state(state)
    sim_dir = os.path.join(SimulationManager.SIMULATION_DATA_DIR, state.simulation_id)
    for name, content in (("simulation_config.json", '{"agent_configs": [{"agent_id": 0, "entity_name": "Actor"}]}'),
                          ("reddit_profiles.json", '[{"user_id": 0, "name": "Actor"}]'),
                          ("twitter_profiles.csv", "user_id,name\n0,Actor\n")):
        with open(os.path.join(sim_dir, name), "w", encoding="utf-8") as f:
            f.write(content)
    return state.simulation_id


def set_run_state(sim_id, status, **fields):
    SimulationRunner._save_run_state(SimulationRunState(
        simulation_id=sim_id, runner_status=RunnerStatus(status), **fields))


def write_old_pipeline(project_id, status, stage, **fields):
    pipeline_state.write_pipeline(project_id, {
        "mode": "auto", "status": status, "stage": stage, "project_id": project_id,
        "simulation_id": None, "report_id": None, "error": None,
        "started_at": "2026-09-30T10:00:00", "finished_at": None, "run_id": "old-run",
        **fields,
    })


def iso(minutes_ago):
    return (datetime.now() - timedelta(minutes=minutes_ago)).isoformat()


# ============== Camino feliz ==============

def test_auto_runs_every_stage_in_order_with_the_screen_params(client, backend, ontology):
    r = upload(client)
    assert r.status_code == 200
    body = r.get_json()["data"]
    project_id = body["project_id"]
    backend.project_id = project_id
    assert project_id.startswith("proj_")
    assert set(body["pipeline"]) == set(pipeline_state.PUBLIC_KEYS)
    assert body["pipeline"]["mode"] == "auto"
    assert body["pipeline"]["status"] == "running"
    assert body["pipeline"]["stage"] == "ontology" and body["pipeline"]["stage_index"] == 1
    assert body["pipeline"]["max_rounds"] == 40

    final = wait_finished(client, project_id)
    assert final["status"] == "completed", final
    assert final["stage"] == "done" and final["stage_index"] == 5
    assert final["simulation_id"] == backend.sim_id
    assert final["report_id"] == REPORT_ID
    assert final["error"] is None and final["finished_at"]

    # Ontología con el texto del brief, en el hilo
    [(texts, requirement, _ctx)] = ontology.calls
    assert "Una app para familias." in texts[0] and requirement == "¿Comprarán la app?"

    sim_id = backend.sim_id
    assert action_posts(backend) == [
        ("/api/graph/build", {"project_id": project_id}),
        ("/api/simulation/create", {"project_id": project_id, "graph_id": GRAPH_ID,
                                    "enable_twitter": True, "enable_reddit": True}),
        ("/api/simulation/prepare", {"simulation_id": sim_id, "use_llm_for_profiles": True,
                                     "parallel_profile_count": 5}),
        ("/api/simulation/start", {"simulation_id": sim_id, "platform": "parallel", "force": False,
                                   "enable_graph_memory_update": True, "max_rounds": 40}),
        ("/api/report/generate", {"simulation_id": sim_id, "force_regenerate": True}),
    ]
    assert auto_pipeline.AUTO_MAX_ROUNDS == 40
    # Sondeos: los mismos cuerpos que la pantalla (el del informe, solo task_id)
    polls = {(path, json.dumps(payload, sort_keys=True)) for method, path, payload in backend.calls
             if method == "POST" and path.endswith("/status")}
    assert polls == {
        ("/api/simulation/prepare/status", json.dumps({"task_id": "task-prep", "simulation_id": sim_id}, sort_keys=True)),
        ("/api/report/generate/status", json.dumps({"task_id": "task-rep"}, sort_keys=True)),
    }
    assert ("GET", "/api/graph/task/task-graph", None) in backend.calls
    # El stage se escribe ANTES de lanzar cada etapa
    assert backend.stage_at == {
        "/api/graph/build": "graph",
        "/api/simulation/create": "prepare",
        "/api/simulation/prepare": "prepare",
        "/api/simulation/start": "simulate",
        "/api/report/generate": "report",
    }
    assert ProjectManager.get_project(project_id).status == ProjectStatus.GRAPH_COMPLETED


def test_auto_validates_like_ontology_generate(client, backend, ontology, storage):
    r = client.post("/api/pipeline/auto", headers=auth(), data={}, content_type="multipart/form-data")
    assert r.status_code == 400
    r = upload(client, files=(io.BytesIO(b"no soy un pdf"), "brief.pdf"))
    assert r.status_code == 400
    r = upload(client, simulation_requirement="x" * 10_001)
    assert r.status_code == 400
    assert os.listdir(storage / "projects") == []
    assert ontology.calls == []


# ============== Rondas elegidas ==============

def start_payload(backend):
    [payload] = [p for path, p in action_posts(backend) if path == "/api/simulation/start"]
    return payload


@pytest.mark.parametrize("rounds", [20, 40, 72])
def test_auto_uses_the_rounds_chosen_on_launch(client, backend, ontology, rounds):
    r = upload(client, max_rounds=str(rounds))
    assert r.status_code == 200
    body = r.get_json()["data"]
    backend.project_id = body["project_id"]
    assert body["pipeline"]["max_rounds"] == rounds

    final = wait_finished(client, body["project_id"])
    assert final["status"] == "completed", final
    assert final["max_rounds"] == rounds
    assert start_payload(backend)["max_rounds"] == rounds


@pytest.mark.parametrize("value", ["abc", "1.5", "9", "0", "-5", "101", "5000"])
def test_auto_rejects_rounds_out_of_range(client, backend, ontology, storage, value):
    r = upload(client, max_rounds=value)
    assert r.status_code == 400
    assert "max_rounds" in r.get_json()["error"]
    # Nada a medias: ni proyecto ni hilo
    assert os.listdir(storage / "projects") == []
    assert ontology.calls == []


def test_auto_rounds_limits_are_inclusive(client, backend, ontology):
    for value in (Config.SIMULATION_MIN_ROUNDS, Config.SIMULATION_MAX_ROUNDS):
        r = upload(client, max_rounds=str(value))
        assert r.status_code == 200, value
        wait_finished(client, r.get_json()["data"]["project_id"])


def test_resume_keeps_the_rounds_chosen_at_launch(client, backend):
    project_id = make_project()
    backend.project_id = project_id
    sim_id = make_prepared_simulation(project_id, created_at=iso(5))
    backend.sim_id = sim_id
    set_run_state(sim_id, "stopped", twitter_actions_count=3, reddit_actions_count=3)
    write_old_pipeline(project_id, "cancelled", "simulate", simulation_id=sim_id, max_rounds=72)

    r = client.post(f"/api/pipeline/{project_id}/resume", headers=auth())
    assert r.status_code == 200
    assert r.get_json()["data"]["max_rounds"] == 72
    final = wait_finished(client, project_id)
    assert final["status"] == "completed", final
    assert start_payload(backend)["max_rounds"] == 72


def test_old_pipeline_without_rounds_reads_as_the_default(client, backend):
    project_id = make_project()
    write_old_pipeline(project_id, "failed", "graph")
    assert pipeline_of(client, project_id)["max_rounds"] == 40


def test_simulation_start_caps_the_rounds(client, backend):
    """Validación antes de mirar la simulación: con una inexistente, lo válido llega al 404."""
    def start(**extra):
        return client.post("/api/simulation/start", headers=auth(),
                           json={"simulation_id": "sim_notexist0001", **extra})

    too_many = start(max_rounds=Config.SIMULATION_MAX_ROUNDS + 1)
    assert too_many.status_code == 400
    assert str(Config.SIMULATION_MAX_ROUNDS) in too_many.get_json()["error"]
    assert start(max_rounds=0).status_code == 400
    assert start(max_rounds="muchas").status_code == 400
    assert start(max_rounds=Config.SIMULATION_MAX_ROUNDS).status_code == 404
    assert start().status_code == 404


# ============== Fallos ==============

def test_graph_failure_marks_failed_with_stage_and_reason(client, backend, ontology):
    backend.graph_error = "El grafo se construyó sin entidades"
    backend.graph_task = ["processing", "failed"]
    project_id = upload(client).get_json()["data"]["project_id"]
    backend.project_id = project_id

    final = wait_finished(client, project_id)
    assert final["status"] == "failed"
    assert final["stage"] == "graph" and final["stage_index"] == 1
    # El motivo limpio del proyecto, no el traceback de la tarea
    assert final["error"] == "El grafo se construyó sin entidades"
    assert final["finished_at"]
    assert "/api/simulation/create" not in [p for p, _ in action_posts(backend)]


def test_ontology_failure_keeps_project_and_can_resume(client, backend, ontology):
    ontology.fail = "El LLM no respondió"
    project_id = upload(client).get_json()["data"]["project_id"]
    backend.project_id = project_id
    final = wait_finished(client, project_id)
    assert final["status"] == "failed" and final["stage"] == "ontology"
    assert "El LLM no respondió" in final["error"]
    assert ProjectManager.get_project(project_id) is not None  # no se borra como en la ruta manual

    ontology.fail = None
    r = client.post(f"/api/pipeline/{project_id}/resume", headers=auth())
    assert r.status_code == 200 and r.get_json()["data"]["stage"] == "ontology"
    assert wait_finished(client, project_id)["status"] == "completed"
    # Al reanudar usa el texto ya extraído en disco
    assert "Una app para familias." in ontology.calls[-1][0][0]


def test_prepare_rejection_fails_with_error_and_hint(client, backend, ontology):
    backend.prepare_response = err(400, "El grafo no tiene entidades utilizables",
                                   data={"hint": "Revisa el documento"})
    project_id = upload(client).get_json()["data"]["project_id"]
    backend.project_id = project_id
    final = wait_finished(client, project_id)
    assert final["status"] == "failed" and final["stage"] == "prepare" and final["stage_index"] == 2
    assert final["error"] == "El grafo no tiene entidades utilizables Revisa el documento"
    assert final["simulation_id"] == backend.sim_id


def test_report_recoverable_409_fails_without_forcing(client, backend, ontology):
    backend.report_response = err(409, "No se puede generar el informe: la simulación debe estar completada.",
                                  recoverable=True, partial_data={"total_actions": 40})
    project_id = upload(client).get_json()["data"]["project_id"]
    backend.project_id = project_id
    final = wait_finished(client, project_id)
    assert final["status"] == "failed" and final["stage"] == "report" and final["stage_index"] == 4
    assert final["error"].startswith("No se puede generar el informe")
    reports = [payload for path, payload in action_posts(backend) if path == "/api/report/generate"]
    assert reports == [{"simulation_id": backend.sim_id, "force_regenerate": True}]  # nunca force


def test_stage_timeout_marks_failed(client, backend, ontology, monkeypatch):
    monkeypatch.setattr(auto_pipeline, "GRAPH_TIMEOUT_SECONDS", 0.05)
    backend.graph_task = ["processing"]
    project_id = upload(client).get_json()["data"]["project_id"]
    backend.project_id = project_id
    final = wait_finished(client, project_id)
    assert final["status"] == "failed" and final["stage"] == "graph"
    assert "Tiempo de espera agotado" in final["error"]


# ============== Carreras con la pantalla ==============

def test_start_already_running_counts_as_started(client, backend, ontology):
    """La pantalla lanzó /start antes: 400 «ya en ejecución» → se espera, sin force."""
    backend.start_response = err(400, "La simulación está en ejecución. Detenla primero en /stop, "
                                      "o usa force=true para reiniciar.")
    project_id = upload(client).get_json()["data"]["project_id"]
    backend.project_id = project_id
    final = wait_finished(client, project_id)
    assert final["status"] == "completed", final
    starts = [payload for path, payload in action_posts(backend) if path == "/api/simulation/start"]
    assert len(starts) == 1 and starts[0]["force"] is False


def test_simulation_already_running_is_not_started_again(client, backend, ontology, monkeypatch):
    """run-status ya dice running (la pantalla la arrancó): no se llama a /start."""
    backend.started = True
    backend.run_after_start = ["running", "running", "completed"]
    monkeypatch.setattr(SimulationRunner, "get_running_simulations",
                        classmethod(lambda cls: [backend.sim_id] if backend.sim_id else []))
    project_id = upload(client).get_json()["data"]["project_id"]
    backend.project_id = project_id
    final = wait_finished(client, project_id)
    assert final["status"] == "completed", final
    assert "/api/simulation/start" not in [p for p, _ in action_posts(backend)]


# ============== Cancelar ==============

def test_cancel_stops_loop_and_simulation(client, backend, ontology):
    backend.run_after_start = ["running"]  # nunca termina
    project_id = upload(client).get_json()["data"]["project_id"]
    backend.project_id = project_id
    wait_for(lambda: backend.started and pipeline_of(client, project_id)["stage"] == "simulate")

    r = client.post(f"/api/pipeline/{project_id}/cancel", headers=auth())
    assert r.status_code == 200
    state = r.get_json()["data"]
    assert state["status"] == "cancelled" and state["stage"] == "simulate" and state["finished_at"]

    wait_for(lambda: auto_pipeline.active_runner(project_id) is None)
    assert backend.stopped
    assert ("/api/simulation/stop", {"simulation_id": backend.sim_id}) in action_posts(backend)
    assert "/api/report/generate" not in [p for p, _ in action_posts(backend)]
    assert pipeline_of(client, project_id)["status"] == "cancelled"

    # Idempotente
    again = client.post(f"/api/pipeline/{project_id}/cancel", headers=auth()).get_json()["data"]
    assert again["status"] == "cancelled"


# ============== Reanudar ==============

def test_resume_skips_done_stages_and_reuses_latest_simulation(client, backend):
    project_id = make_project()
    backend.project_id = project_id
    older = make_prepared_simulation(project_id, created_at=iso(60))
    newest = make_prepared_simulation(project_id, created_at=iso(5))
    backend.sim_id = newest
    # Cancelada en plena simulación: el `stopped` es del pipeline, no terminó
    set_run_state(newest, "stopped", twitter_actions_count=3, reddit_actions_count=3)
    write_old_pipeline(project_id, "cancelled", "simulate", simulation_id=newest)

    r = client.post(f"/api/pipeline/{project_id}/resume", headers=auth())
    assert r.status_code == 200
    state = r.get_json()["data"]
    assert state["status"] == "running" and state["stage"] == "simulate" and state["stage_index"] == 3
    assert state["simulation_id"] == newest and state["error"] is None and state["finished_at"] is None

    final = wait_finished(client, project_id)
    assert final["status"] == "completed", final
    assert final["simulation_id"] == newest
    posts = [p for p, _ in action_posts(backend)]
    assert "/api/graph/build" not in posts
    assert "/api/simulation/create" not in posts
    assert "/api/simulation/prepare" not in posts
    starts = [payload for path, payload in action_posts(backend) if path == "/api/simulation/start"]
    assert starts == [{"simulation_id": newest, "platform": "parallel", "force": True,
                       "enable_graph_memory_update": True, "max_rounds": 40}]
    assert len(SimulationManager().list_simulations(project_id=project_id)) == 2
    assert older != newest


def test_resume_reuses_finished_run_and_existing_report(client, backend):
    project_id = make_project()
    backend.project_id = project_id
    sim_id = make_prepared_simulation(project_id, created_at=iso(5))
    set_run_state(sim_id, "completed", twitter_completed=True, reddit_completed=True,
                  twitter_actions_count=10, reddit_actions_count=10)
    ReportManager.save_report(Report(
        report_id="report_existing0001", simulation_id=sim_id, graph_id="mirofish_existing",
        simulation_requirement="¿Comprarán la app?", status=ReportStatus.COMPLETED, created_at=iso(1)))
    write_old_pipeline(project_id, "interrupted", "report", simulation_id=sim_id)

    r = client.post(f"/api/pipeline/{project_id}/resume", headers=auth())
    assert r.status_code == 200 and r.get_json()["data"]["stage"] == "report"
    final = wait_finished(client, project_id)
    assert final["status"] == "completed" and final["report_id"] == "report_existing0001"
    assert action_posts(backend) == []  # nada relanzado, nada creado


def test_resume_manual_project_switches_to_auto(client, backend):
    project_id = make_project()
    backend.project_id = project_id
    sim_id = make_prepared_simulation(project_id, created_at=iso(5))  # preparada, nunca ejecutada
    backend.sim_id = sim_id
    assert pipeline_of(client, project_id) == {"mode": "manual"}

    r = client.post(f"/api/pipeline/{project_id}/resume", headers=auth())
    assert r.status_code == 200
    assert r.get_json()["data"]["mode"] == "auto" and r.get_json()["data"]["stage"] == "simulate"
    final = wait_finished(client, project_id)
    assert final["status"] == "completed" and final["mode"] == "auto"
    assert [p for p, _ in action_posts(backend)] == ["/api/simulation/start", "/api/report/generate"]
    # Primera ejecución de esa simulación: sin force
    assert action_posts(backend)[0][1]["force"] is False


def test_duplicate_run_is_409(client, backend):
    project_id = make_project()
    backend.project_id = project_id
    gate = threading.Event()
    backend.block["/api/simulation/create"] = gate
    backend.entered["/api/simulation/create"] = threading.Event()

    assert client.post(f"/api/pipeline/{project_id}/resume", headers=auth()).status_code == 200
    assert backend.entered["/api/simulation/create"].wait(5)
    r = client.post(f"/api/pipeline/{project_id}/resume", headers=auth())
    assert r.status_code == 409
    assert r.get_json()["success"] is False and r.get_json()["data"]["status"] == "running"

    gate.set()
    assert wait_finished(client, project_id)["status"] == "completed"
    creates = [p for p, _ in action_posts(backend) if p == "/api/simulation/create"]
    assert len(creates) == 1


# ============== Arranque, auth, lecturas ==============

def test_boot_marks_running_pipelines_as_interrupted(storage, auth_config):
    running = make_project()
    done = make_project()
    write_old_pipeline(running, "running", "simulate")
    write_old_pipeline(done, "completed", "done", finished_at="2026-09-30T11:00:00")

    create_app()

    state = pipeline_state.read_pipeline(running)
    assert state["status"] == "interrupted" and state["stage"] == "simulate"
    assert state["finished_at"] and state["error"]
    assert pipeline_state.read_pipeline(done)["status"] == "completed"
    assert auto_pipeline.active_runner(running) is None  # no se reanuda solo


@pytest.mark.parametrize("method,path", [
    ("post", "/api/pipeline/auto"),
    ("get", "/api/pipeline/proj_abc123def456"),
    ("post", "/api/pipeline/proj_abc123def456/cancel"),
    ("post", "/api/pipeline/proj_abc123def456/resume"),
])
def test_pipeline_requires_token(client, method, path):
    r = getattr(client, method)(path)
    assert r.status_code == 401
    r = getattr(client, method)(path, headers={INTERNAL_AUTH_HEADER: "adivinado"})
    assert r.status_code == 401


def test_get_pipeline_unknown_and_manual(client):
    assert client.get("/api/pipeline/proj_noexiste0000", headers=auth()).status_code == 404
    assert client.post("/api/pipeline/proj_noexiste0000/resume", headers=auth()).status_code == 404
    project_id = make_project()
    assert pipeline_of(client, project_id) == {"mode": "manual"}
    assert client.post(f"/api/pipeline/{project_id}/cancel", headers=auth()).get_json()["data"] == {"mode": "manual"}


def test_internal_client_skips_auth_and_rate_limit(storage, auth_config, monkeypatch):
    monkeypatch.setattr(Config, "API_WRITE_RATE_LIMIT", "2 per minute")
    application = create_app()
    api = auto_pipeline.InternalApiClient(application, "es")
    codes = [api.post("/api/graph/build", {})[0] for _ in range(5)]
    assert codes == [400] * 5  # sin project_id: ni 401 ni 429
    outsider = application.test_client()
    assert outsider.get("/api/graph/project/list").status_code == 401


def test_history_includes_pipeline_mode(client):
    auto_project = make_project()
    manual_project = make_project()
    make_prepared_simulation(auto_project, created_at=iso(3))
    make_prepared_simulation(manual_project, created_at=iso(2))
    write_old_pipeline(auto_project, "failed", "report", error="x")

    r = client.get("/api/simulation/history", headers=auth())
    assert r.status_code == 200
    items = {item["project_id"]: item for item in r.get_json()["data"]}
    assert items[auto_project]["pipeline_mode"] == "auto"
    assert items[auto_project]["pipeline_status"] == "failed"
    assert items[manual_project]["pipeline_mode"] == "manual"
    assert items[manual_project]["pipeline_status"] is None
    for item in items.values():  # lo de antes sigue ahí
        for key in ("simulation_id", "project_name", "files", "report_id", "runner_status", "total_rounds"):
            assert key in item


# ============== La ruta manual no cambia ==============

def test_ontology_generate_still_responds_the_same(client, ontology):
    r = upload(client, path="/api/graph/ontology/generate")
    assert r.status_code == 200
    data = r.get_json()["data"]
    assert set(data) == {"project_id", "project_name", "ontology", "analysis_summary", "files", "total_text_length"}
    assert data["project_name"] == "Demo"
    assert data["ontology"] == {"entity_types": [{"name": "Persona", "attributes": []}],
                                "edge_types": [{"name": "HABLA_CON"}]}
    assert data["analysis_summary"] == "Resumen"
    assert data["files"] == [{"filename": "brief.md", "size": len(b"# Brief\nUna app para familias.")}]
    assert data["total_text_length"] > 0
    project = ProjectManager.get_project(data["project_id"])
    assert project.status == ProjectStatus.ONTOLOGY_GENERATED
    assert project.simulation_requirement == "¿Comprarán la app?"
    assert pipeline_state.read_pipeline(data["project_id"]) is None  # sigue siendo manual


def test_ontology_generate_errors_unchanged(client, ontology, storage):
    path = "/api/graph/ontology/generate"
    r = client.post(path, headers=auth(), data={"simulation_requirement": "x"}, content_type="multipart/form-data")
    assert r.status_code == 400
    r = upload(client, path=path, files=(io.BytesIO(b"no soy un pdf"), "brief.pdf"))
    assert r.status_code == 400
    # Texto demasiado largo: 500 como antes de separar los helpers (el except genérico lo recoge)
    r = upload(client, path=path, simulation_requirement="x" * 10_001)
    assert r.status_code == 500
    ontology.fail = "El LLM no respondió"
    r = upload(client, path=path)
    assert r.status_code == 500 and r.get_json()["error"] == "El LLM no respondió"
    assert os.listdir(storage / "projects") == []  # sin proyectos huérfanos
