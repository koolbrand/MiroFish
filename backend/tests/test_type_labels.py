"""
Etiquetas legibles de los tipos de la ontología: un diccionario compartido, traducido una vez por idioma.
El modelo se simula; no hay red.
"""

import json
import os

import pytest

from app import create_app
from app.config import Config
from app.services import type_labels

TOKEN = "token-tipos"


class FakeLLM:
    """Responde como un modelo correcto (o estropeado, según `reply`) y cuenta las llamadas."""

    def __init__(self, reply=None):
        self.calls = []
        self.reply = reply

    def chat_json(self, messages, temperature=0.3, max_tokens=4096):
        self.calls.append(json.loads(messages[1]["content"]))
        if isinstance(self.reply, Exception):
            raise self.reply
        if self.reply is not None:
            return self.reply
        wanted = self.calls[-1]
        table = {"SmallBusinessOwner": "dueño de pequeño negocio", "CoffeeShopEmployee": "Empleado de cafetería",
                 "WORKS_FOR": "Trabaja para", "COMPETES_WITH": "compite con", "industry": "Sector"}
        return {k: {n: table[n] for n in names if n in table} for k, names in wanted.items()}


@pytest.fixture(autouse=True)
def isolated_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(Config, "UPLOAD_FOLDER", str(tmp_path))
    type_labels.reset_memory_cache()
    yield
    type_labels.reset_memory_cache()


def names(**kw):
    return {"entity": [], "relation": [], "attribute": [], **kw}


def test_translates_once_and_remembers_across_calls_and_restarts(tmp_path):
    llm = FakeLLM()
    first = type_labels.get_labels("es", names(entity=["SmallBusinessOwner"], relation=["WORKS_FOR"]), llm)
    assert first["entity"] == {"SmallBusinessOwner": "Dueño de pequeño negocio"}      # mayúscula inicial en tipos
    assert first["relation"] == {"WORKS_FOR": "trabaja para"}                         # minúscula en relaciones
    assert len(llm.calls) == 1

    again = type_labels.get_labels("es", names(entity=["SmallBusinessOwner"], relation=["WORKS_FOR"]), llm)
    assert again == first and len(llm.calls) == 1                                     # de la caché, sin modelo

    type_labels.reset_memory_cache()                                                  # «reinicio»: se lee el archivo
    assert type_labels.get_labels("es", names(entity=["SmallBusinessOwner"]), llm)["entity"] == first["entity"]
    assert len(llm.calls) == 1
    assert os.path.exists(tmp_path / "type_labels.json")


def test_only_the_missing_names_go_to_the_model():
    llm = FakeLLM()
    type_labels.get_labels("es", names(entity=["SmallBusinessOwner"]), llm)
    type_labels.get_labels("es", names(entity=["SmallBusinessOwner", "CoffeeShopEmployee"], attribute=["industry"]), llm)
    assert llm.calls[-1] == {"entity": ["CoffeeShopEmployee"], "attribute": ["industry"]}


def test_universal_types_need_no_model_and_english_is_never_translated():
    llm = FakeLLM()
    assert type_labels.get_labels("es", names(entity=["Person", "Organization", "Entity"]), llm)["entity"] == {
        "Person": "Persona", "Organization": "Organización", "Entity": "Entidad"}
    assert type_labels.get_labels("en", names(entity=["SmallBusinessOwner"]), llm) == {"entity": {}, "relation": {}, "attribute": {}}
    assert type_labels.get_labels("fr", names(entity=["SmallBusinessOwner"]), llm)["entity"] == {}
    assert llm.calls == []


def test_languages_do_not_mix():
    llm = FakeLLM()
    type_labels.get_labels("es", names(entity=["SmallBusinessOwner"]), llm)
    type_labels.get_labels("zh", names(entity=["SmallBusinessOwner"]), llm)
    assert len(llm.calls) == 2                       # el chino se pide aparte


def test_a_failing_model_gives_nothing_and_retries_next_time():
    llm = FakeLLM(reply=RuntimeError("503"))
    assert type_labels.get_labels("es", names(entity=["SmallBusinessOwner"]), llm)["entity"] == {}
    llm.reply = None                                  # se recupera
    assert type_labels.get_labels("es", names(entity=["SmallBusinessOwner"]), llm)["entity"] == {"SmallBusinessOwner": "Dueño de pequeño negocio"}
    assert len(llm.calls) == 2


def test_junk_from_the_model_is_dropped():
    reply = {"entity": {"SmallBusinessOwner": "<script>x</script>", "CoffeeShopEmployee": "x" * 200, "Invented": "Inventado"},
             "relation": {"WORKS_FOR": ""}, "attribute": "no soy un objeto"}
    llm = FakeLLM(reply=reply)
    out = type_labels.get_labels("es", names(entity=["SmallBusinessOwner", "CoffeeShopEmployee"], relation=["WORKS_FOR"], attribute=["industry"]), llm)
    assert out == {"entity": {}, "relation": {}, "attribute": {}}                     # ni lo pedido mal formado ni lo no pedido


def test_invalid_identifiers_are_ignored_and_the_request_is_capped():
    llm = FakeLLM()
    assert type_labels.clean_names(["OK_name", "con espacios raros!", "", 5, None, "OK_name", "9empieza", "a" * 70, " Valido ", "busca atraer", "fundó"]) == ["OK_name", "Valido"]
    many = [f"Tipo{i}" for i in range(200)]
    type_labels.get_labels("es", names(entity=many), llm)
    assert len(llm.calls[0]["entity"]) == type_labels.MAX_NAMES_PER_REQUEST


# ============== La ruta ==============

@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(Config, "API_AUTH_REQUIRED", True)
    monkeypatch.setattr(Config, "API_AUTH_TOKEN", TOKEN)
    app = create_app()
    app.config["TESTING"] = True
    app.config["RATELIMIT_ENABLED"] = False
    return app.test_client()


def post(client, body, token=TOKEN):
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    return client.post("/api/graph/type-labels", headers=headers, json=body)


def test_route_returns_labels_and_requires_a_session(client, monkeypatch):
    llm = FakeLLM()
    monkeypatch.setattr(type_labels, "LLMClient", lambda: llm)
    r = post(client, {"locale": "es", "entity": ["SmallBusinessOwner", "Person"], "relation": ["COMPETES_WITH"]})
    assert r.status_code == 200
    data = r.get_json()["data"]
    assert data["locale"] == "es"
    assert data["labels"]["entity"] == {"SmallBusinessOwner": "Dueño de pequeño negocio", "Person": "Persona"}
    assert data["labels"]["relation"] == {"COMPETES_WITH": "compite con"}
    assert post(client, {"locale": "es", "entity": ["X1"]}, token=None).status_code == 401


def test_route_validates_the_body_and_english_costs_nothing(client, monkeypatch):
    llm = FakeLLM()
    monkeypatch.setattr(type_labels, "LLMClient", lambda: llm)
    assert client.post("/api/graph/type-labels", headers={"Authorization": f"Bearer {TOKEN}"}, data="no json").status_code == 400
    assert post(client, {"locale": "es", "entity": "SmallBusinessOwner"}).status_code == 400
    r = post(client, {"locale": "en", "entity": ["SmallBusinessOwner"]})
    assert r.status_code == 200 and r.get_json()["data"]["labels"]["entity"] == {}
    assert post(client, {"locale": "es"}).get_json()["data"]["labels"] == {"entity": {}, "relation": {}, "attribute": {}}
    assert llm.calls == []


# ============== Calentar al generar la ontología ==============

def test_ontology_names_collects_types_relations_and_attributes():
    ontology = {
        "entity_types": [{"name": "SmallBusinessOwner", "attributes": [{"name": "industry"}, {"name": "years_in_business"}]},
                         {"name": "Person", "attributes": []}, {"nombre": "sin nombre"}],
        "edge_types": [{"name": "WORKS_FOR", "attributes": [{"name": "since_year"}]}, {"name": "mal nombre!"}],
    }
    assert type_labels.ontology_names(ontology) == {
        "entity": ["SmallBusinessOwner", "Person"], "relation": ["WORKS_FOR"],
        "attribute": ["industry", "years_in_business", "since_year"]}
    assert type_labels.ontology_names(None) == {"entity": [], "relation": [], "attribute": []}


def test_warm_async_translates_in_the_background_and_skips_english():
    import threading
    llm, done = FakeLLM(), threading.Event()
    real = type_labels.get_labels
    type_labels.get_labels = lambda locale, names, client=None: (real(locale, names, llm), done.set())[0]
    try:
        type_labels.warm_async({"entity_types": [{"name": "SmallBusinessOwner"}], "edge_types": [{"name": "WORKS_FOR"}]}, "es")
        assert done.wait(5)
        assert type_labels.get_labels("es", names(entity=["SmallBusinessOwner"]))["entity"] == {"SmallBusinessOwner": "Dueño de pequeño negocio"}
        done.clear()
        type_labels.warm_async({"entity_types": [{"name": "SmallBusinessOwner"}]}, "en")
        assert not done.wait(0.3)                     # en inglés no hay nada que traducir
    finally:
        type_labels.get_labels = real
