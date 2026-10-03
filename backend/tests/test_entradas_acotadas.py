"""Entradas de usuario acotadas y comprobadas: texto libre que llega al modelo y ficheros que se leen.
Auditoría del 3-oct-2026 sobre los endpoints (la rama de seguridad de mayo ya estaba casi toda en main; esto cierra lo que faltaba)."""

import io
import os

import pytest

from app.config import Config
from app.utils.security import clamp_limit
from test_pipeline import storage  # noqa: F401


@pytest.fixture()
def cliente(storage, monkeypatch):   # noqa: F811
    from app import create_app
    monkeypatch.setattr(Config, "API_AUTH_REQUIRED", True)
    monkeypatch.setattr(Config, "API_AUTH_TOKEN", "tok")
    app = create_app()
    app.config["TESTING"] = True
    app.config["RATELIMIT_ENABLED"] = False
    return app.test_client()


H = {"Authorization": "Bearer tok"}
TOPE = Config.MAX_INTERVIEW_PROMPT_CHARS


# ---------------------------------------------------------------- clamp_limit
def test_clamp_limit_acota_y_tolera_basura():
    assert [clamp_limit(x, default=10, high=50) for x in (5, 50, 51, 10**9, 0, -3)] == [5, 50, 50, 50, 1, 1]
    assert [clamp_limit(x, default=10, high=50) for x in (None, "abc", [], "7", 7.9)] == [10, 10, 10, 7, 7]


# ---------------------------------------------------------------- entrevistas: el prompt tiene tope (el lote ya lo tenía)
@pytest.mark.parametrize("ruta,cuerpo", [
    ("/api/simulation/interview", {"simulation_id": "sim_x", "agent_id": 0}),
    ("/api/simulation/interview/all", {"simulation_id": "sim_x"}),
])
def test_el_prompt_de_la_entrevista_tiene_tope_en_individual_y_en_todos(cliente, ruta, cuerpo):
    largo = cliente.post(ruta, json={**cuerpo, "prompt": "x" * (TOPE + 1)}, headers=H)
    assert largo.status_code == 400 and str(TOPE) in largo.get_json()["error"]
    justo = cliente.post(ruta, json={**cuerpo, "prompt": "x" * TOPE}, headers=H)          # en el tope: pasa este control y falla por otra cosa
    assert str(TOPE) not in (justo.get_json() or {}).get("error", "")
    raro = cliente.post(ruta, json={**cuerpo, "prompt": ["no", "es", "texto"]}, headers=H)
    assert raro.status_code == 400 and str(TOPE) in raro.get_json()["error"]


# ---------------------------------------------------------------- búsqueda del informe: consulta acotada
def test_la_consulta_de_busqueda_del_informe_tiene_tope(cliente):
    largo = cliente.post("/api/report/tools/search", json={"graph_id": "g", "query": "q" * (Config.MAX_SEARCH_QUERY_CHARS + 1)}, headers=H)
    assert largo.status_code == 400 and str(Config.MAX_SEARCH_QUERY_CHARS) in largo.get_json()["error"]
    raro = cliente.post("/api/report/tools/search", json={"graph_id": "g", "query": {"a": 1}}, headers=H)
    assert raro.status_code == 400


# ---------------------------------------------------------------- brief: el contenido del fichero tiene que ser lo que dice su extensión
@pytest.mark.parametrize("nombre,contenido", [
    ("brief.pdf", b"MZ\x90\x00 esto es un ejecutable renombrado"),
    ("brief.docx", b"no soy un zip"),
    ("brief.txt", b"texto\x00con un byte nulo: es binario"),
])
def test_el_brief_rechaza_ficheros_cuyo_contenido_no_es_su_extension(cliente, nombre, contenido):
    r = cliente.post("/api/brief/check", data={"files": (io.BytesIO(contenido), nombre)}, headers=H, content_type="multipart/form-data")
    assert r.status_code == 400 and nombre in r.get_json()["error"]


# ---------------------------------------------------------------- nombre del proyecto: sin caracteres de control y con tope
def test_renombrar_un_proyecto_quita_los_caracteres_de_control_y_acota(cliente):
    from app.models.project import ProjectManager
    p = ProjectManager.create_project(name="P", owner_id=None)
    r = cliente.patch(f"/api/graph/project/{p.project_id}", json={"name": "a\x00b\x07c\td"}, headers=H)
    assert r.status_code == 200 and ProjectManager.get_project(p.project_id).name == "abc\td"
    cliente.patch(f"/api/graph/project/{p.project_id}", json={"name": "n" * 300}, headers=H)
    assert len(ProjectManager.get_project(p.project_id).name) == 120
