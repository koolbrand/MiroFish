"""
`GET /api/backup/export`: credencial propia de solo lectura, contenido coherente y nada de secretos en los logs.
"""

import hashlib
import io
import json
import logging
import os
import sqlite3
import tarfile

import pytest

from app import create_app
from app.api import backup as backup_api
from app.config import Config
from app.services import backup_export

BACKUP_TOKEN = "t" * 40
ADMIN_TOKEN = "clave-admin-de-prueba"


@pytest.fixture
def uploads(tmp_path, monkeypatch):
    root = tmp_path / "uploads"
    (root / "projects" / "proj_aaaaaaaaaaaa" / "files").mkdir(parents=True)
    (root / "projects" / "proj_aaaaaaaaaaaa" / "project.json").write_text('{"name":"Proyecto"}', encoding="utf-8")
    (root / "projects" / "proj_aaaaaaaaaaaa" / "files" / "brief.pdf").write_bytes(b"%PDF-1.4 original subido")
    (root / "reports" / "report_bbbbbbbbbbbb").mkdir(parents=True)
    (root / "reports" / "report_bbbbbbbbbbbb" / "full_report.md").write_text("# Informe\n", encoding="utf-8")
    sim = root / "simulations" / "sim_cccccccccccc"
    (sim / "ipc_commands").mkdir(parents=True)
    (sim / "ipc_commands" / "cmd.json").write_text("{}", encoding="utf-8")        # transitorio: no se copia
    (sim / "state.json").write_text('{"status":"completed"}', encoding="utf-8")
    (sim / ".state.json.abc123.tmp").write_text("a medias", encoding="utf-8")      # temporal atómico: no se copia
    monkeypatch.setattr(Config, "UPLOAD_FOLDER", str(root))
    return root


@pytest.fixture
def client(uploads, monkeypatch):
    monkeypatch.setattr(Config, "BACKUP_TOKEN", BACKUP_TOKEN)
    monkeypatch.setattr(Config, "API_AUTH_REQUIRED", True)
    monkeypatch.setattr(Config, "API_AUTH_TOKEN", ADMIN_TOKEN)
    app = create_app()
    app.config["TESTING"] = True
    app.config["RATELIMIT_ENABLED"] = False
    return app.test_client()


def good():
    return {"X-Backup-Token": BACKUP_TOKEN}


def open_tar(response):
    return tarfile.open(fileobj=io.BytesIO(response.data), mode="r:gz")


# ---------- quién puede ----------

def test_disabled_without_a_token_returns_404_and_reveals_nothing(client, monkeypatch):
    monkeypatch.setattr(Config, "BACKUP_TOKEN", "")
    r = client.get("/api/backup/export", headers=good())
    assert r.status_code == 404 and r.get_json() == {"success": False, "error": "Not found"}


def test_a_short_token_does_not_enable_it(client, monkeypatch):
    monkeypatch.setattr(Config, "BACKUP_TOKEN", "corto")
    assert client.get("/api/backup/export", headers={"X-Backup-Token": "corto"}).status_code == 404


@pytest.mark.parametrize("headers", [{}, {"X-Backup-Token": ""}, {"X-Backup-Token": "x" * 40}, {"X-Backup-Token": BACKUP_TOKEN + "x"}])
def test_missing_or_wrong_token_is_401(client, headers):
    r = client.get("/api/backup/export", headers=headers)
    assert r.status_code == 401 and r.get_json()["success"] is False


def test_the_admin_key_does_not_open_the_backup(client):
    r = client.get("/api/backup/export", headers={"Authorization": f"Bearer {ADMIN_TOKEN}"})
    assert r.status_code == 401


def test_the_backup_token_opens_nothing_else(client):
    for path in ("/api/graph/project/list", "/api/simulation/history", "/api/backup/otra"):
        r = client.get(path, headers=good())
        assert r.status_code in (401, 404), path


def test_only_get_is_allowed(client):
    assert client.post("/api/backup/export", headers=good()).status_code == 405


# ---------- contenido ----------

def test_export_contains_everything_with_a_manifest(client):
    r = client.get("/api/backup/export", headers=good())
    assert r.status_code == 200 and r.mimetype == "application/gzip"
    assert r.headers["X-Backup-Sha256"] == hashlib.sha256(r.data).hexdigest()
    assert int(r.headers["Content-Length"]) == len(r.data)
    with open_tar(r) as tar:
        names = set(tar.getnames())
        manifest = json.load(tar.extractfile("MANIFIESTO.json"))
        assert tar.extractfile("projects/proj_aaaaaaaaaaaa/files/brief.pdf").read() == b"%PDF-1.4 original subido"
    assert {"projects/proj_aaaaaaaaaaaa/project.json", "projects/proj_aaaaaaaaaaaa/files/brief.pdf",
            "reports/report_bbbbbbbbbbbb/full_report.md", "simulations/sim_cccccccccccc/state.json",
            "MANIFIESTO.json"} <= names
    assert manifest["proyectos"] == 1 and manifest["simulaciones"] == 1 and manifest["informes"] == 1
    assert manifest["ficheros"] == 4 and manifest["omitidos"] == []
    by_path = {e["path"]: e for e in manifest["archivos"]}
    assert by_path["projects/proj_aaaaaaaaaaaa/files/brief.pdf"]["sha256"] == hashlib.sha256(b"%PDF-1.4 original subido").hexdigest()


def test_temp_files_and_ipc_folders_are_left_out(client):
    with open_tar(client.get("/api/backup/export", headers=good())) as tar:
        names = tar.getnames()
    assert not any(n.endswith(".tmp") or "ipc_commands" in n for n in names)


def test_a_sqlite_database_is_copied_as_a_consistent_snapshot(client, uploads, tmp_path):
    db = uploads / "simulations" / "sim_cccccccccccc" / "twitter_simulation.db"
    conn = sqlite3.connect(db)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("CREATE TABLE post (id INTEGER PRIMARY KEY, texto TEXT)")
    conn.executemany("INSERT INTO post (texto) VALUES (?)", [(f"publicación {i}",) for i in range(200)])
    conn.commit()                                  # las filas están en el -wal; el archivo principal casi vacío
    try:
        r = client.get("/api/backup/export", headers=good())
        with open_tar(r) as tar:
            tar.extract("simulations/sim_cccccccccccc/twitter_simulation.db", tmp_path, filter="data")
            manifest = json.load(tar.extractfile("MANIFIESTO.json"))
            names = tar.getnames()
    finally:
        conn.close()
    restored = sqlite3.connect(tmp_path / "simulations" / "sim_cccccccccccc" / "twitter_simulation.db")
    try:
        assert restored.execute("SELECT COUNT(*) FROM post").fetchone()[0] == 200
        assert restored.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    finally:
        restored.close()
    assert not any(n.endswith(("-wal", "-shm")) for n in names)
    entry = next(e for e in manifest["archivos"] if e["path"].endswith("twitter_simulation.db"))
    assert entry["nota"] == "sqlite-snapshot"


def test_a_corrupt_sqlite_is_copied_as_bytes_and_flagged(client, uploads):
    (uploads / "simulations" / "sim_cccccccccccc" / "roto.db").write_bytes(b"esto no es sqlite")
    with open_tar(client.get("/api/backup/export", headers=good())) as tar:
        manifest = json.load(tar.extractfile("MANIFIESTO.json"))
        assert tar.extractfile("simulations/sim_cccccccccccc/roto.db").read() == b"esto no es sqlite"
    assert next(e for e in manifest["archivos"] if e["path"].endswith("roto.db"))["nota"].startswith("sqlite-copia-de-bytes")


def test_a_file_that_disappears_mid_copy_is_reported_not_fatal(client, monkeypatch):
    real = backup_export._sha256_and_size

    def flaky(path):
        if path.endswith("full_report.md"):
            raise FileNotFoundError(path)
        return real(path)
    monkeypatch.setattr(backup_export, "_sha256_and_size", flaky)
    r = client.get("/api/backup/export", headers=good())
    assert r.status_code == 200
    with open_tar(r) as tar:
        manifest = json.load(tar.extractfile("MANIFIESTO.json"))
    assert [o["path"] for o in manifest["omitidos"]] == ["reports/report_bbbbbbbbbbbb/full_report.md"]
    assert manifest["ficheros"] == 3


# ---------- límites y secretos ----------

def test_only_one_export_at_a_time(client):
    assert backup_api._export_lock.acquire(blocking=False)
    try:
        assert client.get("/api/backup/export", headers=good()).status_code == 429
    finally:
        backup_api._export_lock.release()
    assert client.get("/api/backup/export", headers=good()).status_code == 200      # y se libera al terminar


def test_no_temp_file_is_left_behind(client, tmp_path, monkeypatch):
    monkeypatch.setattr("tempfile.tempdir", str(tmp_path))
    client.get("/api/backup/export", headers=good())
    assert [p.name for p in tmp_path.iterdir() if p.name.startswith("simuloo-backup-")] == []


def test_the_token_never_reaches_the_logs(client):
    records = []

    class Capture(logging.Handler):
        def emit(self, record):
            records.append(record.getMessage())
    handler = Capture(level=logging.DEBUG)
    root = logging.getLogger("mirofish")
    root.addHandler(handler)
    try:
        client.get("/api/backup/export", headers=good())
        client.get("/api/backup/export", headers={"X-Backup-Token": "mal-" + "x" * 40})
    finally:
        root.removeHandler(handler)
    assert records and not any(BACKUP_TOKEN in line or "mal-" + "x" * 40 in line for line in records)
