"""
Endurecimiento HTTP: topes de cuerpo por ruta, registro sin contenido, cabeceras y errores sin detalles internos.
"""

import io
import logging

import pytest

from app import create_app
from app.config import Config, env_flag_on_by_default
from app.models.project import ProjectManager

from test_pipeline import ontology, storage  # noqa: F401

TOKEN = "token-endurecimiento"


class Captured(logging.Handler):
    """Los loggers de la app no propagan: caplog no los ve, se engancha un manejador a ellos."""

    def __init__(self):
        super().__init__(logging.DEBUG)
        self.lines = []

    def emit(self, record):
        self.lines.append(record.getMessage())

    @property
    def text(self):
        return "\n".join(self.lines)


@pytest.fixture
def server_log():
    handler = Captured()
    loggers = [logging.getLogger(n) for n in ("mirofish.request", "mirofish.security")]
    for lg in loggers:
        lg.addHandler(handler)
    yield handler
    for lg in loggers:
        lg.removeHandler(handler)


@pytest.fixture
def client(storage, monkeypatch):
    monkeypatch.setattr(Config, "API_AUTH_REQUIRED", True)
    monkeypatch.setattr(Config, "API_AUTH_TOKEN", TOKEN)
    monkeypatch.setattr(Config, "DEBUG", False)
    app = create_app()
    app.config["TESTING"] = True
    app.config["RATELIMIT_ENABLED"] = False
    return app.test_client()


def auth():
    return {"Authorization": f"Bearer {TOKEN}"}


# ---------- tope de cuerpo ----------

def test_json_routes_reject_bodies_over_the_default_limit(client):
    big = {"project_id": "proj_000000000000", "relleno": "x" * (2 * 1024 * 1024)}
    r = client.post("/api/simulation/create", headers=auth(), json=big)
    assert r.status_code == 413
    assert r.get_json()["success"] is False


def test_anonymous_big_bodies_are_not_parsed_and_get_401(client, server_log):
    r = client.post("/api/simulation/create", json={"secreto": "texto-privado-xyz", "relleno": "x" * 200_000})
    assert r.status_code == 401
    assert "texto-privado-xyz" not in server_log.text and "Cuerpo de la petición" not in server_log.text
    assert "401" in server_log.text                                  # sí queda constancia del intento


def test_upload_routes_keep_the_large_limit(client, ontology, monkeypatch):
    monkeypatch.setattr(Config, "MAX_TOTAL_TEXT_CHARS", 50_000_000)       # aquí solo se prueba el tope de CUERPO
    two_mb = b"# Brief\n" + b"palabra " * 300_000
    data = {"simulation_requirement": "¿Funcionará?", "files": (io.BytesIO(two_mb), "brief.md")}
    r = client.post("/api/graph/ontology/generate", headers=auth(), data=data, content_type="multipart/form-data")
    assert r.status_code != 413


def test_get_requests_are_not_limited(client):
    assert client.get("/api/graph/project/list", headers=auth()).status_code == 200


# ---------- registro ----------

def test_the_request_log_has_the_shape_of_the_body_not_its_content(client, server_log):
    client.post("/api/report/chat", headers=auth(),
                json={"simulation_id": "sim_aaaaaaaaaaaa", "message": "mensaje-privado-abc123", "api_key": "sk-secreto"})
    assert "mensaje-privado-abc123" not in server_log.text and "sk-secreto" not in server_log.text
    assert "message" in server_log.text and "str[" in server_log.text   # sí se ve que había un mensaje y su tamaño
    assert "sim_aaaaaaaaaaaa" in server_log.text                              # y los ids, útiles para depurar


# ---------- cabeceras ----------

def test_security_headers_and_no_store_on_the_api(client):
    r = client.get("/api/graph/project/list", headers=auth())
    assert r.headers["X-Content-Type-Options"] == "nosniff"
    assert r.headers["X-Frame-Options"] == "DENY"
    assert r.headers["Referrer-Policy"] == "same-origin"
    assert r.headers["Cache-Control"] == "no-store"
    health = client.get("/health")
    assert health.headers["X-Content-Type-Options"] == "nosniff" and "no-store" not in health.headers.get("Cache-Control", "")


# ---------- errores ----------

def test_a_500_does_not_leak_internal_details(client, monkeypatch, server_log):
    from app.api import graph as graph_api

    class Broken:
        def get_graph_data(self, graph_id):
            raise RuntimeError("Cannot resolve address neo4j:7687 en /app/backend/app/x.py")

    monkeypatch.setattr(graph_api, "GraphBuilderService", Broken)
    r = client.get("/api/graph/data/mirofish_aaaaaaaaaaaa", headers=auth())
    assert r.status_code == 500
    body = r.get_json()
    text = r.get_data(as_text=True)
    assert "neo4j" not in text and "/app/backend" not in text
    assert "ref " in body["error"] and "traceback" not in body
    assert "Cannot resolve address" in server_log.text                       # el detalle sí queda en el log del servidor


def test_client_errors_keep_their_useful_message(client):
    r = client.post("/api/graph/build", headers=auth(), json={"project_id": "proj_000000000000", "chunk_size": 10})
    assert r.status_code == 400 and "chunk_size" in r.get_json()["error"]


# ---------- configuración ----------

@pytest.mark.parametrize("raw,expected", [("true", True), ("TRUE", True), ("1", True), ("yes", True), ("on", True), (" true ", True),
                                          ("", True), ("false", False), ("False", False), (" false ", False), ("0", False),
                                          ("no", False), ("off", False)])
def test_auth_is_on_unless_explicitly_turned_off(monkeypatch, raw, expected):
    monkeypatch.setenv("TEST_FLAG_AUTH", raw)
    assert env_flag_on_by_default("TEST_FLAG_AUTH") is expected


def test_auth_is_on_when_the_variable_is_missing(monkeypatch):
    monkeypatch.delenv("TEST_FLAG_AUTH", raising=False)
    assert env_flag_on_by_default("TEST_FLAG_AUTH") is True



@pytest.mark.parametrize("message,kept", [
    ("El LLM no respondió", True),
    ("El modelo no está disponible ahora mismo", True),
    ("Cannot resolve address neo4j:7687", False),
    ("[Errno 2] No such file or directory: '/app/backend/uploads/projects/x.json'", False),
    ("Connection error to https://api.minimax.io/v1/chat", False),
    ("Traceback (most recent call last): boom", False),
    ('File "app.py", line 12, in run', False),
])
def test_user_facing_500_messages_are_kept_and_internal_ones_replaced(client, monkeypatch, message, kept):
    from app.api import graph as graph_api

    class Broken:
        def get_graph_data(self, graph_id):
            raise RuntimeError(message)

    monkeypatch.setattr(graph_api, "GraphBuilderService", Broken)
    r = client.get("/api/graph/data/mirofish_aaaaaaaaaaaa", headers=auth())
    assert r.status_code == 500
    assert (r.get_json()["error"] == message) is kept
    if not kept:
        assert "ref " in r.get_json()["error"]
