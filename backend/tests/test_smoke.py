"""
Smoke tests del backend: arranque, health, puerta de auth y validaciones.
No necesitan LLM, Neo4j ni red. Ejecutar: `cd backend && uv run pytest -q`
"""

import pytest

from app import create_app
from app.config import Config

TOKEN = "test-token-smoke"


@pytest.fixture()
def client(monkeypatch):
    monkeypatch.setattr(Config, "API_AUTH_REQUIRED", True)
    monkeypatch.setattr(Config, "API_AUTH_TOKEN", TOKEN)
    # Sin PocketBase: cualquier token distinto del estático debe fallar sin red
    monkeypatch.setattr(Config, "POCKETBASE_URL", "")
    app = create_app()
    app.config["TESTING"] = True
    app.config["RATELIMIT_ENABLED"] = False
    return app.test_client()


def auth():
    return {"Authorization": f"Bearer {TOKEN}"}


@pytest.mark.parametrize("path", ["/health", "/api/health"])
def test_health_is_public(client, path):
    r = client.get(path)
    assert r.status_code == 200
    assert r.get_json()["status"] == "ok"


@pytest.mark.parametrize("headers", [{}, {"Authorization": "Bearer wrong"}, {"Authorization": TOKEN}])
def test_api_requires_valid_token(client, headers):
    r = client.get("/api/graph/project/list", headers=headers)
    assert r.status_code == 401
    assert r.get_json()["success"] is False


def test_api_accepts_static_token(client):
    r = client.get("/api/graph/project/list", headers=auth())
    assert r.status_code == 200
    assert r.get_json()["success"] is True


def test_cors_preflight_not_blocked_by_auth(client):
    r = client.options(
        "/api/graph/project/list",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "Authorization",
        },
    )
    assert r.status_code == 200
    assert r.headers.get("Access-Control-Allow-Origin") == "http://localhost:5173"


def test_cors_rejects_unknown_origin(client):
    r = client.get("/api/health", headers={"Origin": "https://evil.example"})
    assert "Access-Control-Allow-Origin" not in r.headers


def test_unknown_api_route_is_json_404(client):
    r = client.get("/api/no-existe", headers=auth())
    assert r.status_code == 404
    assert r.is_json and r.get_json()["success"] is False


def test_unknown_api_route_is_json_404_even_without_the_built_frontend(client, monkeypatch, tmp_path):
    """Sin `frontend/dist` (desarrollo solo con la API, CI) no existe la ruta comodín del SPA: el 404 sigue siendo JSON."""
    import os as _os
    real_exists = _os.path.exists
    monkeypatch.setattr(_os.path, "exists", lambda p: False if str(p).endswith("frontend/dist") else real_exists(p))
    from app import create_app
    app = create_app()
    app.config["TESTING"] = True
    r = app.test_client().get("/api/no-existe", headers=auth())
    assert r.status_code == 404 and r.is_json
    assert r.get_json() == {"success": False, "error": "Not found"}
    page = app.test_client().get("/no-es-api")
    assert page.status_code == 404 and not page.is_json            # lo que no es API conserva su 404 normal


def test_project_id_traversal_rejected(client):
    r = client.get("/api/graph/project/..%2F..%2Fetc", headers=auth())
    assert r.status_code in (400, 404)


def test_simulation_id_traversal_rejected(client):
    r = client.get("/api/simulation/..%2Fsecret", headers=auth())
    assert r.status_code in (400, 404)


def test_ontology_requires_requirement(client):
    r = client.post("/api/graph/ontology/generate", headers=auth(), data={})
    assert r.status_code == 400
    assert r.get_json()["success"] is False


def test_frontend_static_cannot_escape_dist(client):
    r = client.get("/..%2F..%2F.env")
    assert b"LLM_API_KEY" not in r.data


@pytest.fixture()
def limited_client(monkeypatch):
    monkeypatch.setattr(Config, "API_AUTH_TOKEN", TOKEN)
    monkeypatch.setattr(Config, "POCKETBASE_URL", "")
    monkeypatch.setattr(Config, "API_READ_RATE_LIMIT", "100 per minute")
    monkeypatch.setattr(Config, "API_WRITE_RATE_LIMIT", "3 per minute")
    return create_app().test_client()


def test_polling_reads_are_not_throttled_like_writes(limited_client):
    # Ritmo real de la UI: >30 lecturas/min en la misma ruta
    codes = [limited_client.get("/api/simulation/list", headers=auth()).status_code for _ in range(40)]
    assert codes.count(429) == 0
    # Los POST de estado cuentan como lectura
    codes = [limited_client.post("/api/simulation/env-status", headers=auth(), json={}).status_code for _ in range(10)]
    assert 429 not in codes


def test_writes_are_throttled_with_json(limited_client):
    codes = []
    for _ in range(5):
        r = limited_client.post("/api/graph/ontology/generate", headers=auth(), data={})
        codes.append(r.status_code)
    assert codes[-1] == 429
    assert r.is_json and r.get_json()["success"] is False


def test_proxy_fix_uses_forwarded_ip(limited_client):
    # Dos clientes distintos detrás del mismo proxy no comparten cupo
    for _ in range(3):
        limited_client.post("/api/graph/ontology/generate", headers={**auth(), "X-Forwarded-For": "10.0.0.1"}, data={})
    r = limited_client.post("/api/graph/ontology/generate", headers={**auth(), "X-Forwarded-For": "10.0.0.2"}, data={})
    assert r.status_code != 429


@pytest.mark.parametrize("path", [
    "/api/simulation/bad.id",
    "/api/simulation/bad.id/run-status",
    "/api/report/bad.id",
    "/api/report/bad.id/agent-log",
    "/api/graph/project/proj_x.y",
])
def test_invalid_ids_are_400(client, path):
    r = client.get(path, headers=auth())
    assert r.status_code == 400
    assert r.get_json()["success"] is False


def test_listings_skip_junk_entries(client, tmp_path, monkeypatch):
    # .DS_Store y duplicados de iCloud ('proj_x 2') no deben tumbar los listados
    from app.models.project import ProjectManager
    from app.services.report_agent import ReportManager
    from app.services.simulation_manager import SimulationManager

    for d, junk in [("projects", "proj_abc 2"), ("reports", "report_abc 2"), ("simulations", "sim_abc 2")]:
        (tmp_path / d / junk).mkdir(parents=True)
        (tmp_path / d / ".DS_Store").write_text("x")
    monkeypatch.setattr(ProjectManager, "PROJECTS_DIR", str(tmp_path / "projects"))
    monkeypatch.setattr(ReportManager, "REPORTS_DIR", str(tmp_path / "reports"))
    monkeypatch.setattr(SimulationManager, "SIMULATION_DATA_DIR", str(tmp_path / "simulations"))

    assert ProjectManager.list_projects() == []
    assert ReportManager.list_reports() == []
    assert SimulationManager().list_simulations() == []


def test_get_unknown_simulation_does_not_create_dir(client, tmp_path, monkeypatch):
    from app.services.simulation_manager import SimulationManager
    monkeypatch.setattr(SimulationManager, "SIMULATION_DATA_DIR", str(tmp_path))
    assert SimulationManager().get_simulation("sim_doesnotexist") is None
    assert not (tmp_path / "sim_doesnotexist").exists()


def test_prepare_reuses_running_task(client, monkeypatch):
    """Recargar la página en el paso 2 no debe lanzar una segunda preparación."""
    from app.api import simulation as sim_api
    from app.models.task import TaskManager, TaskStatus

    tm = TaskManager()
    task_id = tm.create_task(task_type="simulation_prepare", metadata={"simulation_id": "sim_reload123"})
    tm.update_task(task_id, status=TaskStatus.PROCESSING)
    assert sim_api._find_active_prepare_task("sim_reload123")["task_id"] == task_id
    assert sim_api._find_active_prepare_task("sim_otra") is None

    tm.update_task(task_id, status=TaskStatus.COMPLETED)
    assert sim_api._find_active_prepare_task("sim_reload123") is None


def test_report_generate_reuses_running_task(client):
    from app.api import report as report_api
    from app.models.task import TaskManager, TaskStatus

    tm = TaskManager()
    task_id = tm.create_task(task_type="report_generate",
                             metadata={"simulation_id": "sim_dbl123", "report_id": "report_abc123def456"})
    tm.update_task(task_id, status=TaskStatus.PROCESSING)
    active = report_api._find_active_report_task("sim_dbl123")
    assert active["metadata"]["report_id"] == "report_abc123def456"
    tm.update_task(task_id, status=TaskStatus.FAILED)
    assert report_api._find_active_report_task("sim_dbl123") is None


def test_graph_tasks_list_returns_json(client):
    # Regresión: la ruta llamaba a .to_dict() sobre diccionarios y daba 500
    from app.models.task import TaskManager
    TaskManager().create_task("tarea de prueba")
    r = client.get("/api/graph/tasks", headers=auth())
    assert r.status_code == 200
    body = r.get_json()
    assert body["success"] is True
    assert body["count"] == len(body["data"]) >= 1
    assert all(isinstance(t, dict) for t in body["data"])
