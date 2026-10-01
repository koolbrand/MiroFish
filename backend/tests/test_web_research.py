"""
Investigación en internet antes de la ontología (paso opcional `web_research`).

Sin red: la llamada HTTP al proveedor va contra un httpx.MockTransport que
imita las respuestas de MiniMax (formato Anthropic con Server Tools, tal como
salieron en las llamadas reales del 1-oct-2026: búsqueda forzada que acaba en
`pause_turn` y luego una redacción sin herramientas).
"""

import io
import json
import logging

import httpx
import pytest

from app.config import Config
from app.models.project import ProjectManager
from app.services import pipeline_state, web_research

# Mismo entorno que el modo automático: carpetas temporales, app, guion de etapas
from test_pipeline import (  # noqa: F401 — fixtures reutilizados
    action_posts,
    app,
    auth,
    auth_config,
    backend,
    client,
    make_project,
    ontology,
    pipeline_of,
    storage,
    upload,
    wait_finished,
    write_old_pipeline,
)

KEY = "sk-clave-secreta-de-prueba-123"
TITLE = "Contexto de internet (investigación automática)"
# Lo que entra en el material es el cuerpo del informe (graph_text): sin título, sin fuentes y sin referencias [n]
BODY_MARK = "La patronal la rechaza."
DOC = ProjectManager.RESEARCH_DOCUMENT_FILENAME

PATRONAL = {"type": "web_search_result", "title": "Las patronales rechazan la jornada de 37,5 horas",
            "url": "https://www.ejemplo.es/patronal/?utm_source=buscador", "page_age": "Jul 16, 2025",
            "content": "CEOE y Cepyme rechazan por unanimidad la propuesta del Gobierno."}
SINDICATOS = {"type": "web_search_result", "title": "Los sindicatos convocan movilizaciones",
              "url": "https://sindicato.es/movilizaciones", "page_age": "Sep 8, 2025",
              "content": "UGT y CCOO convocan concentraciones en todo el país."}
PATRONAL_DUP = {**PATRONAL, "url": "https://ejemplo.es/patronal"}  # misma página, otra forma
ENCUESTA = {"type": "web_search_result", "title": "Dos de cada tres, a favor de reducir la jornada",
            "url": "https://encuestas.es/jornada", "page_age": None,
            "content": "El 66 % respalda pasar de 40 a 37,5 horas."}
SEARCH_ERROR = {"type": "web_search_tool_result_error", "error_code": "max_uses_exceeded"}

WRITTEN = (
    "## Datos\nDos de cada tres personas apoyan la medida [3]. Una cifra sin respaldo [9].\n\n"
    "## Implicados\nLa patronal la rechaza [1]. Los sindicatos se movilizan [2, 1].\n\n"
    "## Referencias\n[1] Otra cosa — https://inventada.example/x\n"
)
NOTHING = "[[NO_RESULTS]]\nNo hay información fiable sobre el puerto de Tepor: los resultados hablan de otros puertos."


# ============== Proveedor falso ==============

def search_response(*blocks, stop_reason="pause_turn", final_text=None):
    """Fase 1: frase de entrada, una búsqueda por bloque y (opcional) el texto final."""
    content = [{"type": "text", "text": "Voy a buscar información actual sobre este tema."}]
    for i, results in enumerate(blocks):
        content.append({"type": "server_tool_use", "id": f"call_{i}", "name": "web_search",
                        "input": {"query": f"consulta {i}"}})
        content.append({"type": "web_search_tool_result", "tool_use_id": f"call_{i}", "content": results})
    if final_text:
        content.append({"type": "text", "text": final_text})
    return httpx.Response(200, json={
        "id": "m1", "type": "message", "role": "assistant", "model": "MiniMax-M3",
        "content": content, "stop_reason": stop_reason,
        "usage": {"input_tokens": 13000, "output_tokens": 400},
        "base_resp": {"status_code": 0, "status_msg": ""},
    })


def write_response(text, stop_reason="end_turn"):
    return httpx.Response(200, json={
        "id": "m2", "type": "message", "content": [{"type": "text", "text": text}],
        "stop_reason": stop_reason, "usage": {"input_tokens": 5000, "output_tokens": 700},
        "base_resp": {"status_code": 0, "status_msg": ""},
    })


class FakeProvider:
    def __init__(self):
        self.requests = []          # (url, cabeceras, cuerpo)
        self.stages = []            # etapa del pipeline al llegar cada petición
        self.search = lambda: search_response([PATRONAL, SINDICATOS], [PATRONAL_DUP, ENCUESTA])
        self.write = lambda: write_response(WRITTEN)
        self.error = None           # excepción de httpx a lanzar

    @property
    def payloads(self):
        return [payload for _url, _headers, payload in self.requests]

    def __call__(self, request):
        payload = json.loads(request.content)
        self.requests.append((str(request.url), dict(request.headers), payload))
        projects = ProjectManager.list_projects()
        state = pipeline_state.read_pipeline(projects[0].project_id) if len(projects) == 1 else None
        self.stages.append(state.get("stage") if state else None)
        if self.error:
            raise self.error("tiempo agotado", request=request)
        return self.search() if "tools" in payload else self.write()


@pytest.fixture
def provider(storage, monkeypatch):
    # `storage`: los proyectos viven en una carpeta temporal (nunca en uploads/ real)
    fake = FakeProvider()
    monkeypatch.setattr(web_research, "_transport", httpx.MockTransport(fake))
    monkeypatch.setattr(Config, "WEB_RESEARCH_ENABLED", True)
    monkeypatch.setattr(Config, "WEB_RESEARCH_API_KEY", KEY)
    monkeypatch.setattr(Config, "WEB_RESEARCH_BASE_URL", "https://api.minimax.io/v1")
    monkeypatch.setattr(Config, "WEB_RESEARCH_MODEL", "MiniMax-M3")
    monkeypatch.setattr(Config, "WEB_RESEARCH_FORCE_SEARCH", True)
    monkeypatch.setattr(Config, "WEB_RESEARCH_TIMEOUT", 240.0)
    return fake


@pytest.fixture
def log_lines():
    """Lo que escriben el servicio y la API (cada logger mirofish.* tiene sus handlers y no propaga)."""
    lines = []

    class Collect(logging.Handler):
        def emit(self, record):
            lines.append(record.getMessage())

    handler = Collect(level=logging.DEBUG)
    loggers = [logging.getLogger(name) for name in ("mirofish.web_research", "mirofish.api")]
    for logger in loggers:
        logger.addHandler(handler)
    yield lines
    for logger in loggers:
        logger.removeHandler(handler)


def research(material="Brief: jornada laboral de 37,5 horas.", locale="es"):
    return web_research.research_for_brief("¿Cómo reaccionará la gente a las 37,5 horas?", material, locale)


# ============== Servicio: parseo ==============

def test_happy_path_sources_queries_and_citations(provider):
    result = research()
    assert result["status"] == "done", result
    assert result["queries"] == ["consulta 0", "consulta 1"]
    # Primero las citadas, en orden de aparición; la URL duplicada (utm, www, barra) cuenta una vez
    assert result["sources"] == [
        {"title": ENCUESTA["title"], "url": ENCUESTA["url"], "page_age": None},
        {"title": PATRONAL["title"], "url": PATRONAL["url"], "page_age": "Jul 16, 2025"},
        {"title": SINDICATOS["title"], "url": SINDICATOS["url"], "page_age": "Sep 8, 2025"},
    ]
    md = result["markdown"]
    assert md.startswith(f"# {TITLE}")
    assert "Información de internet sin verificar: revisa las fuentes." in md
    # Renumeradas según la lista final; la cita [9] (ningún resultado) desaparece
    assert "apoyan la medida [1]" in md
    assert "La patronal la rechaza [2]" in md
    assert "se movilizan [3, 2]" in md
    assert "sin respaldo." in md and "[9]" not in md
    # La lista del modelo (con una URL inventada) no sale: sale la nuestra
    assert "## Referencias" not in md and "inventada.example" not in md
    assert "## Fuentes" in md
    assert f"1. {ENCUESTA['title']} — {ENCUESTA['url']}" in md
    assert f"2. {PATRONAL['title']} — {PATRONAL['url']} (antigüedad: Jul 16, 2025)" in md
    # La frase de entrada («voy a buscar…») no entra en el documento
    assert "Voy a buscar" not in md
    assert result["error"] is None and result["note"] is None
    assert result["usage"] == {"input_tokens": 18000, "output_tokens": 1100,
                               "web_search_requests": 2, "calls": 2}
    assert result["created_at"] and result["duration_s"] >= 0


def test_request_shape(provider):
    long_material = "a" * 6000 + "MARCA_DESPUES_DEL_LIMITE"
    research(material=long_material)
    (url1, headers1, search), (url2, _h2, write) = provider.requests
    assert url1 == url2 == "https://api.minimax.io/anthropic/v1/messages"
    assert headers1["x-api-key"] == KEY
    assert headers1["anthropic-version"] == "2023-06-01"
    assert headers1["content-type"] == "application/json"
    assert search["model"] == "MiniMax-M3" and search["max_tokens"] == 4000
    assert search["tools"] == [{"type": "web_search_20250305", "name": "web_search"}]
    assert search["tool_choice"] == {"type": "any"}
    prompt = search["messages"][0]["content"]
    assert "¿Cómo reaccionará la gente a las 37,5 horas?" in prompt
    assert "a" * 6000 in prompt and "MARCA_DESPUES_DEL_LIMITE" not in prompt  # ~6000 caracteres
    # Redacción: sin herramientas y con los resultados numerados por nosotros (sin duplicados)
    assert "tools" not in write and "tool_choice" not in write
    written_prompt = write["messages"][0]["content"]
    assert f"[1] {PATRONAL['title']} (Jul 16, 2025) — {PATRONAL['url']}" in written_prompt
    assert f"[2] {SINDICATOS['title']}" in written_prompt
    assert f"[3] {ENCUESTA['title']} — {ENCUESTA['url']}" in written_prompt
    assert "[4]" not in written_prompt


@pytest.mark.parametrize("base,endpoint", [
    ("https://api.minimax.io/v1", "https://api.minimax.io/anthropic/v1/messages"),
    ("https://api.minimax.io", "https://api.minimax.io/anthropic/v1/messages"),
    ("https://api.minimax.io/anthropic/", "https://api.minimax.io/anthropic/v1/messages"),
])
def test_endpoint_is_derived_from_base_url(monkeypatch, base, endpoint):
    monkeypatch.setattr(Config, "WEB_RESEARCH_BASE_URL", base)
    assert web_research._endpoint() == endpoint


def test_prompt_follows_project_language(provider):
    research(locale="en")
    assert provider.payloads[0]["messages"][0]["content"].startswith("Simulation question")
    result = research(locale="zh")
    assert result["markdown"].startswith("# 互联网背景（自动调研）")
    assert "## 来源" in result["markdown"]


def test_model_that_writes_after_searching_needs_one_call(provider):
    provider.search = lambda: search_response(
        [PATRONAL, SINDICATOS], stop_reason="end_turn",
        final_text=("## Implicados\nLa patronal la rechaza [1]. Algo inventado [2].\n\n## Referencias\n"
                    f"[1] Las patronales — {PATRONAL_DUP['url']}\n[2] Falsa — https://inventada.example/x\n"),
    )
    result = research()
    assert len(provider.requests) == 1
    assert result["status"] == "done"
    assert result["sources"][0]["url"] == PATRONAL["url"]           # la citada, primero
    assert [s["url"] for s in result["sources"]] == [PATRONAL["url"], SINDICATOS["url"]]
    assert "rechaza [1]" in result["markdown"] and "inventado." in result["markdown"]


def test_search_result_error_object_does_not_break_parsing(provider):
    provider.search = lambda: search_response([PATRONAL], SEARCH_ERROR, [ENCUESTA])
    provider.write = lambda: write_response("## Implicados\nLa patronal la rechaza [1] y la gente la apoya [2].")
    result = research()
    assert result["status"] == "done"
    assert [s["url"] for s in result["sources"]] == [PATRONAL["url"], ENCUESTA["url"]]
    assert result["queries"] == ["consulta 0", "consulta 1", "consulta 2"]


def test_only_search_errors_is_empty_without_writing(provider):
    provider.search = lambda: search_response(SEARCH_ERROR, {"error_code": "unavailable"})
    result = research()
    assert result["status"] == "empty"
    assert result["sources"] == [] and result["markdown"] == ""
    assert result["note"] == "Las búsquedas no devolvieron resultados utilizables."
    assert len(provider.requests) == 1  # sin resultados no se redacta


def test_answer_from_memory_is_discarded(provider):
    """Llamada real 1: sin buscar, con citas [n] que no respalda nada."""
    provider.search = lambda: httpx.Response(200, json={
        "content": [{"type": "text", "text": "## Implicados\nEl Gobierno promueve la medida [1][2].\n\n"
                                             "## Referencias\n[1] X — https://a.example\n[2] Y — https://b.example"}],
        "stop_reason": "end_turn", "usage": {"input_tokens": 1026, "output_tokens": 1268},
    })
    result = research()
    assert result["status"] == "empty"
    assert result["markdown"] == "" and result["sources"] == []
    assert "sin buscar en internet" in result["note"]
    assert "El Gobierno" not in result["note"]  # lo de memoria no se enseña
    assert len(provider.requests) == 1


def test_nothing_found_is_empty(provider):
    provider.write = lambda: write_response(NOTHING)
    result = research()
    assert result["status"] == "empty"
    assert result["markdown"] == "" and result["sources"] == []
    assert result["note"].startswith("No hay información fiable sobre el puerto de Tepor")
    assert "NO_RESULTS" not in result["note"]
    assert result["queries"] == ["consulta 0", "consulta 1"]  # se enseña qué se buscó


def test_short_uncited_answer_is_empty(provider):
    provider.write = lambda: write_response("No he encontrado nada útil sobre este tema.")
    assert research()["status"] == "empty"


def test_timeout_is_failed(provider):
    provider.error = httpx.ReadTimeout
    result = research()
    assert result["status"] == "failed"
    assert result["error"] == "Tiempo de espera agotado (240 s)"
    assert result["markdown"] == "" and result["sources"] == []


def test_http_500_is_failed_without_leaking_the_key(provider, log_lines):
    provider.search = lambda: httpx.Response(500, json={
        "type": "error", "error": {"type": "api_error", "message": f"fallo interno (clave {KEY})"}})
    result = research()
    assert result["status"] == "failed"
    assert result["error"].startswith("El proveedor de búsqueda respondió HTTP 500")
    assert KEY not in json.dumps(result)
    assert log_lines and not any(KEY in line for line in log_lines)


def test_provider_error_in_200_body_is_failed(provider):
    provider.search = lambda: httpx.Response(200, json={"base_resp": {"status_code": 1004, "status_msg": "auth"}})
    result = research()
    assert result["status"] == "failed" and "auth" in result["error"]


def test_truncated_write_without_text_is_failed(provider):
    provider.write = lambda: httpx.Response(200, json={"content": [], "stop_reason": "max_tokens"})
    result = research()
    assert result["status"] == "failed" and "WEB_RESEARCH_MAX_TOKENS" in result["error"]


def test_disabled_does_not_call(provider, monkeypatch):
    monkeypatch.setattr(Config, "WEB_RESEARCH_ENABLED", False)
    assert research()["status"] == "disabled"
    monkeypatch.setattr(Config, "WEB_RESEARCH_ENABLED", True)
    monkeypatch.setattr(Config, "WEB_RESEARCH_API_KEY", None)
    assert research()["status"] == "disabled"
    assert provider.requests == []


# ============== ontology/generate ==============

ONTOLOGY_KEYS = {"project_id", "project_name", "ontology", "analysis_summary", "files", "total_text_length"}


def test_without_the_field_nothing_changes(client, ontology, provider):
    r = upload(client, path="/api/graph/ontology/generate")
    assert r.status_code == 200
    data = r.get_json()["data"]
    assert set(data) == ONTOLOGY_KEYS  # la misma respuesta de siempre
    assert data["files"] == [{"filename": "brief.md", "size": len(b"# Brief\nUna app para familias.")}]
    r = upload(client, path="/api/graph/ontology/generate", web_research="false")
    assert set(r.get_json()["data"]) == ONTOLOGY_KEYS
    assert provider.requests == []
    project = ProjectManager.get_project(data["project_id"])
    assert project.web_research is None
    assert BODY_MARK not in ontology.calls[0][0][-1]


def test_done_adds_the_document_to_the_material(client, ontology, provider):
    r = upload(client, path="/api/graph/ontology/generate", web_research="true")
    assert r.status_code == 200, r.get_json()
    data = r.get_json()["data"]
    project_id = data["project_id"]
    size = len(ProjectManager.get_research_document(project_id).encode("utf-8"))
    assert data["files"] == [
        {"filename": "brief.md", "size": len(b"# Brief\nUna app para familias.")},
        {"filename": DOC, "size": size, "generated": "web_research"},
    ]
    research_view = data["web_research"]
    assert research_view["status"] == "done" and research_view["in_material"] is True
    assert research_view["document"] == DOC
    assert "markdown" not in research_view and len(research_view["sources"]) == 3
    # Entra en la ontología (y en el texto extraído, que es lo que lee el grafo)
    [(texts, _req, _ctx)] = ontology.calls
    assert len(texts) == 2 and texts[1].startswith("## ") and BODY_MARK in texts[1] and "Fuentes" not in texts[1]
    extracted = ProjectManager.get_extracted_text(project_id)
    assert "Una app para familias." in extracted and BODY_MARK in extracted and "Fuentes" not in extracted
    assert data["total_text_length"] == len(extracted)
    # GET /project lo devuelve (sin el Markdown)
    project = client.get(f"/api/graph/project/{project_id}", headers=auth()).get_json()["data"]
    assert project["web_research"] == research_view


def test_empty_is_saved_but_not_added(client, ontology, provider):
    provider.write = lambda: write_response(NOTHING)
    r = upload(client, path="/api/graph/ontology/generate", web_research="1")
    assert r.status_code == 200
    data = r.get_json()["data"]
    assert data["files"] == [{"filename": "brief.md", "size": len(b"# Brief\nUna app para familias.")}]
    assert data["web_research"]["status"] == "empty"
    assert data["web_research"]["in_material"] is False and data["web_research"]["document"] is None
    assert "Tepor" in data["web_research"]["note"]
    [(texts, _req, _ctx)] = ontology.calls
    assert len(texts) == 1
    assert BODY_MARK not in ProjectManager.get_extracted_text(data["project_id"])
    assert ProjectManager.get_project(data["project_id"]).web_research["status"] == "empty"
    r = client.get(f"/api/graph/project/{data['project_id']}/research", headers=auth())
    assert r.status_code == 404


@pytest.mark.parametrize("failure", ["timeout", "http500"])
def test_failure_never_breaks_the_project(client, ontology, provider, failure):
    if failure == "timeout":
        provider.error = httpx.ConnectTimeout
    else:
        provider.search = lambda: httpx.Response(500, text="Internal Server Error")
    r = upload(client, path="/api/graph/ontology/generate", web_research="true")
    assert r.status_code == 200
    data = r.get_json()["data"]
    assert data["web_research"]["status"] == "failed" and data["web_research"]["error"]
    assert data["ontology"]["entity_types"]  # la ontología se generó igual
    assert len(ontology.calls) == 1 and len(ontology.calls[0][0]) == 1
    assert KEY not in json.dumps(r.get_json())


def test_research_download_route(client, ontology, provider):
    project_id = upload(client, path="/api/graph/ontology/generate", web_research="true").get_json()["data"]["project_id"]
    r = client.get(f"/api/graph/project/{project_id}/research", headers=auth())
    assert r.status_code == 200
    assert r.mimetype == "text/markdown"
    assert r.headers["Content-Disposition"] == f"attachment; filename={DOC}"
    body = r.get_data(as_text=True)
    assert body.startswith(f"# {TITLE}") and "## Fuentes" in body
    assert body == ProjectManager.get_research_document(project_id)


def test_research_download_errors(client, ontology, provider):
    assert client.get("/api/graph/project/proj_noexiste0000/research", headers=auth()).status_code == 404
    manual = make_project()
    r = client.get(f"/api/graph/project/{manual}/research", headers=auth())
    assert r.status_code == 404 and r.get_json()["success"] is False
    assert client.get("/api/graph/project/proj_x.y/research", headers=auth()).status_code == 400
    assert client.get(f"/api/graph/project/{manual}/research").status_code == 401


# ============== Modo automático ==============

def test_auto_goes_through_research_before_ontology(client, backend, ontology, provider):
    r = upload(client, web_research="true")
    assert r.status_code == 200
    state = r.get_json()["data"]["pipeline"]
    project_id = r.get_json()["data"]["project_id"]
    backend.project_id = project_id
    assert state["stage"] == "research" and state["stage_index"] == 1 and state["web_research"] is True

    final = wait_finished(client, project_id)
    assert final["status"] == "completed", final
    assert final["web_research"] is True
    assert provider.stages == ["research", "research"]  # búsqueda y redacción, en la etapa research
    [(texts, _req, _ctx)] = ontology.calls
    assert texts[-1].startswith("## ") and BODY_MARK in texts[-1]
    assert BODY_MARK in ProjectManager.get_extracted_text(project_id)
    assert action_posts(backend)[0] == ("/api/graph/build", {"project_id": project_id})
    project = ProjectManager.get_project(project_id)
    assert project.web_research["status"] == "done"
    assert project.files[-1]["generated"] == "web_research"


def test_auto_without_the_field_skips_research(client, backend, ontology, provider):
    r = upload(client)
    state = r.get_json()["data"]["pipeline"]
    assert state["stage"] == "ontology" and state["web_research"] is False
    assert wait_finished(client, state["project_id"])["status"] == "completed"
    assert provider.requests == []


def test_auto_research_failure_does_not_fail_the_pipeline(client, backend, ontology, provider):
    provider.error = httpx.ReadTimeout
    project_id = upload(client, web_research="true").get_json()["data"]["project_id"]
    backend.project_id = project_id
    assert wait_finished(client, project_id)["status"] == "completed"
    assert ProjectManager.get_project(project_id).web_research["status"] == "failed"
    assert len(ontology.calls[0][0]) == 1


def test_resume_does_not_repeat_research(client, backend, ontology, provider):
    ontology.fail = "El LLM no respondió"
    project_id = upload(client, web_research="true").get_json()["data"]["project_id"]
    backend.project_id = project_id
    final = wait_finished(client, project_id)
    assert final["status"] == "failed" and final["stage"] == "ontology"
    assert len(provider.requests) == 2

    ontology.fail = None
    r = client.post(f"/api/pipeline/{project_id}/resume", headers=auth())
    assert r.status_code == 200
    state = r.get_json()["data"]
    assert state["stage"] == "ontology" and state["web_research"] is True
    assert wait_finished(client, project_id)["status"] == "completed"
    assert len(provider.requests) == 2  # no se volvió a investigar
    # La ontología lee el texto de disco, ya con la investigación
    assert BODY_MARK in ontology.calls[-1][0][0]


def test_resume_interrupted_in_research_runs_it(client, backend, ontology, provider):
    project_id = make_project(graph_done=False, with_ontology=False)
    backend.project_id = project_id
    write_old_pipeline(project_id, "interrupted", "research", web_research=True)
    assert pipeline_of(client, project_id)["web_research"] is True

    r = client.post(f"/api/pipeline/{project_id}/resume", headers=auth())
    assert r.status_code == 200 and r.get_json()["data"]["stage"] == "research"
    assert wait_finished(client, project_id)["status"] == "completed"
    assert len(provider.requests) == 2
    texts = ontology.calls[-1][0]
    assert len(texts) == 1 and "Una app para familias." in texts[0] and BODY_MARK in texts[0]
    # Una sola vez en el material aunque se hubiera empezado antes
    assert ProjectManager.get_extracted_text(project_id).count(BODY_MARK) == 1


def test_old_pipelines_report_web_research_false(client):
    project_id = make_project()
    write_old_pipeline(project_id, "completed", "done")
    assert pipeline_of(client, project_id)["web_research"] is False


def test_repeated_research_replaces_the_previous_one(storage, provider):
    """Si se repite (corte a medias), la anterior sale del material y de la lista de archivos."""
    from app.api.graph import run_project_web_research

    project_id = make_project(graph_done=False, with_ontology=False)
    project = ProjectManager.get_project(project_id)
    project.files = [{"filename": "brief.md", "size": 10}]
    ProjectManager.save_project(project)
    run_project_web_research(project, None, "es")
    run_project_web_research(ProjectManager.get_project(project_id), None, "es")
    project = ProjectManager.get_project(project_id)
    assert [f["filename"] for f in project.files] == ["brief.md", DOC]
    assert ProjectManager.get_extracted_text(project_id).count(BODY_MARK) == 1

    provider.write = lambda: write_response(NOTHING)
    run_project_web_research(project, None, "es")
    project = ProjectManager.get_project(project_id)
    assert [f["filename"] for f in project.files] == ["brief.md"]
    assert BODY_MARK not in ProjectManager.get_extracted_text(project_id)
    assert ProjectManager.get_research_document(project_id) is None


def test_drop_uncited_bullets_keeps_unconfirmed_section():
    from app.services.web_research import _drop_uncited
    body = (
        "## Implicados\n"
        "- Aena y el Gobierno lo defienden [1, 2].\n"
        "- Una plataforma vecinal prepara movilizaciones.\n"
        "## Datos sin respaldo\n"
        "- Cifra que nadie cita.\n"
        "## Lo que no se puede confirmar\n"
        "- No hay encuestas publicadas.\n"
    )
    out, dropped = _drop_uncited(body)
    assert dropped == 2
    assert "Aena y el Gobierno" in out
    assert "plataforma vecinal" not in out
    assert "Cifra que nadie cita" not in out
    assert "## Datos sin respaldo" not in out          # se quedó sin contenido
    assert "No hay encuestas publicadas" in out        # la sección de lo no confirmado no lleva citas


def test_graph_text_keeps_body_only():
    from app.services.web_research import graph_text
    md = (
        "# Contexto de internet (investigación automática)\n\n"
        "*Búsqueda del 2026-10-01*\n\n"
        "> Información de internet sin verificar: revisa las fuentes.\n\n"
        "## Implicados\n"
        "- Aena y el Gobierno lo defienden [1, 2].\n\n"
        "## Lo que no se puede confirmar\n"
        "- No hay encuestas publicadas.\n\n"
        "## Fuentes\n\n"
        "1. El País — https://elpais.com/x\n"
        "2. Instagram — https://instagram.com/y\n"
    )
    out = graph_text(md)
    assert "Aena y el Gobierno lo defienden." in out      # el cuerpo, sin la referencia
    assert "[1" not in out
    for ausente in ("Contexto de internet", "Búsqueda del", "sin verificar", "encuestas", "elpais.com", "Instagram", "Fuentes"):
        assert ausente not in out
