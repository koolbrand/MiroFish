"""El punto de partida de un proyecto (objetivo + archivos + texto del brief) para el paso 1."""

import pytest

from app.api.graph import BRIEF_PREVIEW_CHARS, _RESEARCH_TEXT_HEADER
from app.config import Config
from app.models.project import ProjectManager
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


def _proyecto(texto, objetivo="¿Quién ganaría las elecciones generales hoy?"):
    p = ProjectManager.create_project(name="P", owner_id=None)
    p.simulation_requirement = objetivo
    p.files = [{"filename": "brief.md", "size": 1234, "path": "x"},
               {"filename": "noticias.pdf", "size": 2_450_000, "path": "y"},
               {"filename": "investigacion-internet.md", "size": 99, "generated": "web_research"}]
    ProjectManager.save_project(p)
    ProjectManager.save_extracted_text(p.project_id, texto)
    return p


def test_el_brief_trae_objetivo_archivos_y_el_texto_sin_la_investigacion(cliente):
    p = _proyecto("Texto del brief que subió la persona." + _RESEARCH_TEXT_HEADER + "INVESTIGACION DE INTERNET")
    r = cliente.get(f"/api/graph/project/{p.project_id}/brief", headers=H).get_json()["data"]
    assert r["simulation_requirement"] == "¿Quién ganaría las elecciones generales hoy?"
    assert [f["filename"] for f in r["files"]] == ["brief.md", "noticias.pdf"]            # lo generado por el servidor no es «un archivo subido»
    assert r["text"] == "Texto del brief que subió la persona." and "INVESTIGACION" not in r["text"]
    assert r["text_length"] == len(r["text"]) and r["truncated"] is False


def test_un_brief_largo_se_recorta_y_se_dice(cliente):
    p = _proyecto("x" * (BRIEF_PREVIEW_CHARS + 5000))
    r = cliente.get(f"/api/graph/project/{p.project_id}/brief", headers=H).get_json()["data"]
    assert len(r["text"]) == BRIEF_PREVIEW_CHARS and r["text_length"] == BRIEF_PREVIEW_CHARS + 5000 and r["truncated"] is True


def test_un_proyecto_sin_texto_ni_objetivo_no_rompe(cliente):
    p = ProjectManager.create_project(name="Vacío", owner_id=None)
    r = cliente.get(f"/api/graph/project/{p.project_id}/brief", headers=H).get_json()["data"]
    assert r == {"simulation_requirement": "", "files": [], "text": "", "text_length": 0, "truncated": False}


def test_un_proyecto_que_no_existe_da_404(cliente):
    assert cliente.get("/api/graph/project/proj_000000000000/brief", headers=H).status_code == 404
