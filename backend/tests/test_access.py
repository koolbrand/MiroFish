"""
Aislamiento por usuario: cada usuario ve solo sus proyectos (y lo que cuelga de ellos).

Dos usuarios de PocketBase falsos (userA, userB), la clave estática como admin y el secreto interno
del modo automático. Los datos van a disco temporal; no hay red ni modelo.
"""

import io

import httpx
import pytest

from app import create_app
from app.config import Config
from app.models.project import ProjectManager
from app.models.task import TaskManager
from app.services.report_agent import Report, ReportManager, ReportStatus
from app.services.simulation_manager import SimulationManager
from app.utils import security
from app.utils.access import user_identity
from app.utils.security import INTERNAL_AUTH_HEADER, internal_request_headers

# Mismo entorno de disco temporal y generador de ontología simulado que el resto
from test_pipeline import ontology, storage  # noqa: F401 — fixtures reutilizados

ADMIN_TOKEN = "token-admin-estatico"
USERS = {"tokA": "userA", "tokB": "userB"}


def hdr(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def app(storage, monkeypatch):
    monkeypatch.setattr(Config, "API_AUTH_REQUIRED", True)
    monkeypatch.setattr(Config, "API_AUTH_TOKEN", ADMIN_TOKEN)
    monkeypatch.setattr(Config, "POCKETBASE_URL", "http://pb.test")
    monkeypatch.setattr(Config, "LEGACY_OWNER_ID", None)
    monkeypatch.setattr(security, "_pocketbase_user_id", lambda token: USERS.get(token))
    application = create_app()
    application.config["TESTING"] = True
    application.config["RATELIMIT_ENABLED"] = False
    return application


@pytest.fixture
def client(app):
    return app.test_client()


def make_world(owner, tag, graph=True):
    """Un proyecto con su simulación y su informe, a nombre de `owner`."""
    project = ProjectManager.create_project(name=f"Proyecto {tag}", owner_id=owner)
    if graph:
        project.graph_id = f"mirofish_{tag}0000000000"
        ProjectManager.save_project(project)
    manager = SimulationManager()
    sim = manager.create_simulation(project_id=project.project_id, graph_id=project.graph_id or "mirofish_x")
    ReportManager.save_report(Report(
        report_id=f"report_{tag}000000001", simulation_id=sim.simulation_id, graph_id=project.graph_id or "mirofish_x",
        simulation_requirement="¿Qué pasará?", status=ReportStatus.COMPLETED, created_at="2026-10-01T10:00:00"))
    return {"project": project.project_id, "sim": sim.simulation_id, "report": f"report_{tag}000000001",
            "graph": project.graph_id}


@pytest.fixture
def world(app):
    return {"A": make_world("userA", "a"), "B": make_world("userB", "b")}


def ids(response, key):
    return {row[key] for row in response.get_json()["data"]}


# ============== Listados ==============

def test_project_list_shows_only_my_projects(client, world):
    a = client.get("/api/graph/project/list", headers=hdr("tokA"))
    assert ids(a, "project_id") == {world["A"]["project"]}
    b = client.get("/api/graph/project/list", headers=hdr("tokB"))
    assert ids(b, "project_id") == {world["B"]["project"]}


def test_simulation_lists_and_history_show_only_mine(client, world):
    for path in ("/api/simulation/list", "/api/simulation/history"):
        a = client.get(path, headers=hdr("tokA"))
        assert a.status_code == 200 and ids(a, "simulation_id") == {world["A"]["sim"]}, path
        b = client.get(path, headers=hdr("tokB"))
        assert ids(b, "simulation_id") == {world["B"]["sim"]}, path


def test_report_list_shows_only_mine(client, world):
    a = client.get("/api/report/list", headers=hdr("tokA"))
    assert ids(a, "report_id") == {world["A"]["report"]}
    b = client.get("/api/report/list", headers=hdr("tokB"))
    assert ids(b, "report_id") == {world["B"]["report"]}


def test_filter_comes_before_the_limit(client, app):
    # B tiene 3 proyectos más recientes que el de A: con limit=1, A sigue viendo el suyo
    a = make_world("userA", "a")
    for tag in ("b1", "b2", "b3"):
        make_world("userB", tag)
    r = client.get("/api/graph/project/list?limit=1", headers=hdr("tokA"))
    assert ids(r, "project_id") == {a["project"]}
    r = client.get("/api/simulation/history?limit=1", headers=hdr("tokA"))
    assert ids(r, "simulation_id") == {a["sim"]}


def test_admin_sees_everything(client, world):
    r = client.get("/api/graph/project/list", headers=hdr(ADMIN_TOKEN))
    assert ids(r, "project_id") == {world["A"]["project"], world["B"]["project"]}
    r = client.get("/api/report/list", headers=hdr(ADMIN_TOKEN))
    assert ids(r, "report_id") == {world["A"]["report"], world["B"]["report"]}


# ============== Acceso por id ==============

def test_someone_elses_things_are_not_found(client, world):
    a = world["A"]
    for path in (
        f"/api/graph/project/{a['project']}",
        f"/api/simulation/{a['sim']}",
        f"/api/simulation/{a['sim']}/run-status",
        f"/api/simulation/{a['sim']}/profiles",
        f"/api/report/{a['report']}",
        f"/api/report/{a['report']}/download",
        f"/api/report/check/{a['sim']}",
        f"/api/pipeline/{a['project']}",
        f"/api/graph/data/{a['graph']}",
    ):
        r = client.get(path, headers=hdr("tokB"))
        assert r.status_code == 404, path
        assert r.get_json() == {"success": False, "error": "No encontrado"}, path


def test_my_own_things_are_reachable(client, world):
    a = world["A"]
    assert client.get(f"/api/graph/project/{a['project']}", headers=hdr("tokA")).status_code == 200
    assert client.get(f"/api/simulation/{a['sim']}", headers=hdr("tokA")).status_code == 200
    assert client.get(f"/api/report/{a['report']}", headers=hdr("tokA")).status_code == 200


def test_ids_in_the_body_and_query_are_checked_too(client, world):
    a = world["A"]
    # crear una simulación colgando del proyecto ajeno
    r = client.post("/api/simulation/create", headers=hdr("tokB"), json={"project_id": a["project"]})
    assert r.status_code == 404
    # listar las simulaciones de un proyecto ajeno
    r = client.get(f"/api/simulation/list?project_id={a['project']}", headers=hdr("tokB"))
    assert r.status_code == 404
    # chatear con el informe de otro
    r = client.post("/api/report/chat", headers=hdr("tokB"), json={"simulation_id": a["sim"], "message": "hola"})
    assert r.status_code == 404
    # generar un informe de la simulación de otro
    r = client.post("/api/report/generate", headers=hdr("tokB"), json={"simulation_id": a["sim"]})
    assert r.status_code == 404
    # y con un formulario
    r = client.post("/api/graph/build", headers=hdr("tokB"), data={"project_id": a["project"]})
    assert r.status_code == 404


def test_unknown_ids_are_plain_404_and_malformed_are_400(client, world):
    assert client.get("/api/graph/project/proj_000000000000", headers=hdr("tokA")).status_code == 404
    assert client.get("/api/simulation/sim_000000000000", headers=hdr("tokA")).status_code == 404
    assert client.get("/api/graph/project/no_es_un_id", headers=hdr("tokA")).status_code == 400


def test_an_orphan_graph_is_admin_only(client, world):
    assert client.get("/api/graph/data/mirofish_huerfano00000", headers=hdr("tokA")).status_code == 404


def test_a_simulation_whose_project_vanished_is_admin_only(client, world):
    ProjectManager.delete_project(world["A"]["project"])
    assert client.get(f"/api/simulation/{world['A']['sim']}", headers=hdr("tokA")).status_code == 404
    assert client.get(f"/api/report/{world['A']['report']}", headers=hdr("tokA")).status_code == 404
    assert client.get(f"/api/simulation/{world['A']['sim']}", headers=hdr(ADMIN_TOKEN)).status_code == 200


# ============== Quién crea, de quién es ==============

def upload(client, token):
    data = {"simulation_requirement": "¿Comprarán la app?", "project_name": "Demo",
            "files": (io.BytesIO(b"# Brief\nUna app para familias."), "brief.md")}
    return client.post("/api/graph/ontology/generate", headers=hdr(token), data=data, content_type="multipart/form-data")


def test_a_new_project_belongs_to_whoever_creates_it(client, ontology):
    r = upload(client, "tokA")
    assert r.status_code == 200, r.get_json()
    project_id = r.get_json()["data"]["project_id"]
    assert ProjectManager.get_project(project_id).owner_id == "userA"
    assert client.get(f"/api/graph/project/{project_id}", headers=hdr("tokA")).status_code == 200
    assert client.get(f"/api/graph/project/{project_id}", headers=hdr("tokB")).status_code == 404
    assert project_id not in ids(client.get("/api/graph/project/list", headers=hdr("tokB")), "project_id")


def test_a_project_made_with_the_admin_key_has_no_owner(client, ontology):
    project_id = upload(client, ADMIN_TOKEN).get_json()["data"]["project_id"]
    assert ProjectManager.get_project(project_id).owner_id is None
    assert client.get(f"/api/graph/project/{project_id}", headers=hdr("tokA")).status_code == 404


def test_the_owner_survives_later_saves(client, world):
    project = ProjectManager.get_project(world["A"]["project"])
    project.name = "Renombrado"
    ProjectManager.save_project(project)
    assert ProjectManager.get_project(world["A"]["project"]).owner_id == "userA"
    r = client.patch(f"/api/graph/project/{world['A']['project']}", headers=hdr("tokA"), json={"name": "Otro nombre"})
    assert r.status_code == 200
    assert ProjectManager.get_project(world["A"]["project"]).owner_id == "userA"


# ============== Proyectos sin dueño (anteriores al cambio) ==============

def test_ownerless_projects_are_admin_only_until_assigned(client, monkeypatch):
    legacy = make_world(None, "l")
    assert ids(client.get("/api/graph/project/list", headers=hdr("tokA")), "project_id") == set()
    assert client.get(f"/api/simulation/{legacy['sim']}", headers=hdr("tokA")).status_code == 404
    assert legacy["project"] in ids(client.get("/api/graph/project/list", headers=hdr(ADMIN_TOKEN)), "project_id")

    monkeypatch.setattr(Config, "LEGACY_OWNER_ID", "userA")
    assert ids(client.get("/api/graph/project/list", headers=hdr("tokA")), "project_id") == {legacy["project"]}
    assert client.get(f"/api/report/{legacy['report']}", headers=hdr("tokA")).status_code == 200
    assert client.get(f"/api/report/{legacy['report']}", headers=hdr("tokB")).status_code == 404


# ============== Tareas ==============

def test_tasks_are_listed_and_readable_only_by_their_owner(app, client):
    manager = TaskManager()
    with app.test_request_context("/"):
        from flask import g
        g.identity = user_identity("userA")
        mine = manager.create_task("Construir grafo")
    internal = manager.create_task("Tarea del servidor")          # fuera de una petición: sin dueño

    assert manager.get_task(mine).metadata["owner_id"] == "userA"
    assert "owner_id" not in manager.get_task(internal).metadata

    a = client.get("/api/graph/tasks", headers=hdr("tokA"))
    assert {t["task_id"] for t in a.get_json()["data"]} == {mine}
    assert client.get("/api/graph/tasks", headers=hdr("tokB")).get_json()["data"] == []
    assert client.get(f"/api/graph/task/{mine}", headers=hdr("tokA")).status_code == 200
    assert client.get(f"/api/graph/task/{mine}", headers=hdr("tokB")).status_code == 404
    # sin dueño: por id pasa (no se adivina), pero no sale en el listado
    assert client.get(f"/api/graph/task/{internal}", headers=hdr("tokB")).status_code == 200
    assert {t["task_id"] for t in client.get("/api/graph/tasks", headers=hdr(ADMIN_TOKEN)).get_json()["data"]} == {mine, internal}


# ============== Identidades ==============

def test_the_internal_secret_sees_everything(client, world):
    headers = internal_request_headers()
    r = client.get("/api/graph/project/list", headers=headers)
    assert ids(r, "project_id") == {world["A"]["project"], world["B"]["project"]}
    assert client.get(f"/api/simulation/{world['A']['sim']}", headers=headers).status_code == 200


def test_invalid_tokens_are_401_and_open_dev_mode_is_admin(client, world, monkeypatch):
    assert client.get("/api/graph/project/list", headers=hdr("tokX")).status_code == 401
    assert client.get("/api/graph/project/list").status_code == 401
    monkeypatch.setattr(Config, "API_AUTH_REQUIRED", False)
    r = client.get("/api/graph/project/list")
    assert ids(r, "project_id") == {world["A"]["project"], world["B"]["project"]}


def test_health_stays_public(client):
    assert client.get("/api/health").status_code != 401 or client.get("/health").status_code == 200


# ============== PocketBase: de dónde sale el id ==============

def _fake_refresh(monkeypatch, body, status=200):
    class FakeClient:
        def __init__(self, *a, **k): pass
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def post(self, url, headers=None):
            return httpx.Response(status, json=body, request=httpx.Request("POST", url))
    monkeypatch.setattr(security.httpx, "Client", FakeClient)
    security._PB_TOKEN_CACHE.clear()


def test_the_user_id_comes_from_the_refresh_record(monkeypatch):
    monkeypatch.setattr(Config, "POCKETBASE_URL", "http://pb.test")
    monkeypatch.undo() if False else None
    _fake_refresh(monkeypatch, {"token": "x", "record": {"id": "abc123", "email": "a@b.c"}})
    assert security.__dict__["_pocketbase_user_id"].__name__ == "_pocketbase_user_id"
    assert security.identify_bearer("Bearer algo") == ("user", "abc123")


def test_falls_back_to_the_jwt_id_claim(monkeypatch):
    import base64, json
    monkeypatch.setattr(Config, "POCKETBASE_URL", "http://pb.test")
    payload = base64.urlsafe_b64encode(json.dumps({"id": "fromjwt1", "type": "authRecord"}).encode()).decode().rstrip("=")
    token = f"h.{payload}.s"
    _fake_refresh(monkeypatch, {"token": "x"})
    assert security.identify_bearer(f"Bearer {token}") == ("user", "fromjwt1")


def test_a_rejected_token_has_no_identity(monkeypatch):
    monkeypatch.setattr(Config, "POCKETBASE_URL", "http://pb.test")
    _fake_refresh(monkeypatch, {"message": "no"}, status=401)
    assert security.identify_bearer("Bearer malo") is None


def test_the_static_key_is_admin(monkeypatch):
    monkeypatch.setattr(Config, "API_AUTH_TOKEN", ADMIN_TOKEN)
    assert security.identify_bearer(f"Bearer {ADMIN_TOKEN}") == ("admin", None)
    assert security.validate_bearer_token(f"Bearer {ADMIN_TOKEN}") is True
