"""
Etiquetas legibles de los tipos de la ontología (solo para mostrar).

Los nombres internos siguen en inglés (Graphiti los exige y el generador de perfiles decide por ellos);
el modelo añade una etiqueta en el idioma de la interfaz y el proyecto la guarda con ese idioma.
"""

import io

import pytest

from app import create_app
from app.api import graph as graph_api
from app.config import Config
from app.models.project import ProjectManager
from app.services.ontology_generator import OntologyGenerator
from app.utils.locale import set_locale

from test_pipeline import storage  # noqa: F401 — disco temporal

TOKEN = "t-etiquetas"


class FakeLLM:
    def __init__(self, result):
        self.result = result

    def chat_json(self, messages, temperature=0.3, max_tokens=4096):
        self.messages = messages
        return self.result


def raw_ontology():
    return {
        "entity_types": [
            {"name": "app_developer", "label": "  Desarrollador \n de apps ", "description": "Dev", "attributes": [], "examples": []},
            {"name": "TechPlatform", "label": 42, "description": "Plataforma", "attributes": [], "examples": []},
            {"name": "ParentUser", "label": "x" * 200, "description": "Madre", "attributes": [], "examples": []},
            {"name": "Sin", "description": "sin etiqueta", "attributes": [], "examples": []},
        ],
        "edge_types": [
            {"name": "competes_with", "label": "compite con", "description": "c", "source_targets": [], "attributes": []},
            {"name": "WORKS_FOR", "label": "   ", "description": "t", "source_targets": [], "attributes": []},
        ],
        "analysis_summary": "ok",
    }


def test_labels_are_cleaned_and_names_stay_in_english():
    gen = OntologyGenerator(llm_client=FakeLLM(raw_ontology()))
    out = gen.generate(["texto"], "¿Qué pasará?")
    ents = {e["name"]: e for e in out["entity_types"]}
    assert ents["AppDeveloper"]["label"] == "Desarrollador de apps"        # espacios y saltos colapsados
    assert "label" not in ents["TechPlatform"]                              # no es texto: se quita
    assert len(ents["ParentUser"]["label"]) == 60                           # tope
    assert "label" not in ents["Sin"]
    edges = {e["name"]: e for e in out["edge_types"]}
    assert edges["COMPETES_WITH"]["label"] == "compite con"
    assert "label" not in edges["WORKS_FOR"]                                # vacía: se quita


def test_the_model_is_asked_for_labels_in_the_user_language():
    llm = FakeLLM(raw_ontology())
    OntologyGenerator(llm_client=llm).generate(["texto"], "¿Qué pasará?")
    system = llm.messages[0]["content"]
    assert "`label`" in system and "only shown to people" in system
    assert '"label"' in system                                              # el esquema de salida lo pide


@pytest.mark.parametrize("locale", ["es", "en", "zh"])
def test_the_language_of_the_labels_is_recorded(locale):
    set_locale(locale)
    try:
        out = OntologyGenerator(llm_client=FakeLLM(raw_ontology())).generate(["texto"], "x")
    finally:
        set_locale("es")
    assert out["label_locale"] == locale


def test_the_project_keeps_labels_and_their_language(storage, monkeypatch):
    class Fake:
        def generate(self, document_texts, simulation_requirement, additional_context=None):
            return {"entity_types": [{"name": "Persona", "label": "Persona", "attributes": []}],
                    "edge_types": [{"name": "HABLA_CON", "label": "habla con"}],
                    "analysis_summary": "r", "label_locale": "es"}
    monkeypatch.setattr(graph_api, "OntologyGenerator", Fake)
    monkeypatch.setattr(Config, "API_AUTH_REQUIRED", True)
    monkeypatch.setattr(Config, "API_AUTH_TOKEN", TOKEN)
    monkeypatch.setattr(Config, "POCKETBASE_URL", "")
    app = create_app()
    app.config["TESTING"] = True
    app.config["RATELIMIT_ENABLED"] = False
    r = app.test_client().post(
        "/api/graph/ontology/generate", headers={"Authorization": f"Bearer {TOKEN}"},
        data={"simulation_requirement": "¿Comprarán?", "project_name": "Demo",
              "files": (io.BytesIO(b"# Brief\nUna app."), "brief.md")},
        content_type="multipart/form-data")
    assert r.status_code == 200, r.get_json()
    project = ProjectManager.get_project(r.get_json()["data"]["project_id"])
    assert project.ontology["label_locale"] == "es"
    assert project.ontology["entity_types"][0]["label"] == "Persona"
    assert project.ontology["edge_types"][0]["label"] == "habla con"
