"""`/health/ready`: Neo4j y disco, con resultado en caché y sin detalles internos en la respuesta."""

import pytest

from app import create_app
from app.config import Config
from app.utils import health


@pytest.fixture
def client(monkeypatch, tmp_path):
    monkeypatch.setattr(Config, "UPLOAD_FOLDER", str(tmp_path))
    app = create_app()
    app.config["TESTING"] = True
    health.reset_cache()
    yield app.test_client()
    health.reset_cache()


def set_checks(monkeypatch, **results):
    calls = {name: 0 for name in results}

    def make(name, ok):
        def check():
            calls[name] += 1
            return ok
        return check
    monkeypatch.setattr(health, "CHECKS", {name: make(name, ok) for name, ok in results.items()})
    return calls


def test_ready_when_everything_answers(client, monkeypatch):
    set_checks(monkeypatch, neo4j=True, disk=True)
    r = client.get("/health/ready")
    assert r.status_code == 200 and r.get_json() == {"status": "ok", "checks": {"neo4j": True, "disk": True}}


def test_not_ready_when_neo4j_is_down_but_plain_health_stays_ok(client, monkeypatch):
    set_checks(monkeypatch, neo4j=False, disk=True)
    r = client.get("/health/ready")
    assert r.status_code == 503 and r.get_json() == {"status": "degraded", "checks": {"neo4j": False, "disk": True}}
    assert client.get("/health").status_code == 200           # la sonda del contenedor no depende de Neo4j


def test_the_result_is_cached_between_polls(client, monkeypatch):
    calls = set_checks(monkeypatch, neo4j=True, disk=True)
    for _ in range(5):
        assert client.get("/health/ready").status_code == 200
    assert calls == {"neo4j": 1, "disk": 1}
    health.reset_cache()
    client.get("/health/ready")
    assert calls["neo4j"] == 2


def test_needs_no_authentication(client, monkeypatch):
    monkeypatch.setattr(Config, "API_AUTH_REQUIRED", True)
    set_checks(monkeypatch, neo4j=True, disk=True)
    assert client.get("/health/ready").status_code == 200


def test_disk_check_writes_and_leaves_nothing_behind(monkeypatch, tmp_path):
    monkeypatch.setattr(Config, "UPLOAD_FOLDER", str(tmp_path))
    assert health.check_disk() is True
    assert list(tmp_path.iterdir()) == []


def test_disk_check_fails_when_space_is_low(monkeypatch, tmp_path):
    monkeypatch.setattr(Config, "UPLOAD_FOLDER", str(tmp_path))
    monkeypatch.setattr(Config, "MIN_FREE_DISK_MB", 10 ** 12)
    assert health.check_disk() is False


def test_disk_check_fails_when_it_cannot_write(monkeypatch, tmp_path):
    blocker = tmp_path / "archivo"
    blocker.write_text("x")
    monkeypatch.setattr(Config, "UPLOAD_FOLDER", str(blocker / "dentro"))     # una carpeta bajo un archivo
    assert health.check_disk() is False


def test_neo4j_check_is_false_without_leaking_the_error(monkeypatch):
    monkeypatch.setattr(Config, "NEO4J_URI", "bolt://127.0.0.1:1")           # nada escucha
    assert health.check_neo4j() is False


def test_response_never_contains_internal_details(client, monkeypatch):
    set_checks(monkeypatch, neo4j=False, disk=False)
    body = client.get("/health/ready").get_data(as_text=True)
    for secret in (Config.NEO4J_URI or "bolt://", "uploads", "Traceback"):
        assert secret not in body
