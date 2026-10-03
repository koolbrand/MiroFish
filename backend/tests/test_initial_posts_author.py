"""
Mensajes iniciales de la simulación: cada uno lo publica el agente que de verdad lo escribe.

Fallo medido el 3-oct-2026 en una simulación real (zona de bajas emisiones): el autor se elegía por el TIPO
de entidad y se repartía por turnos entre los del mismo tipo, así que «El gremio del taxi aclara…» salía
publicado por la plataforma ciclista y «Soy vecina del casco histórico, 72 años» por «familias con niños».
Sin LLM ni red: el modelo se sustituye por respuestas fijas.
"""

import pytest

from app.services import simulation_config_generator as scg
from app.services.simulation_config_generator import (
    AgentActivityConfig,
    EventConfig,
    SimulationConfigGenerator,
)
from app.services.zep_entity_reader import EntityNode

# (id, nombre, tipo) como en la ejecución real: varios agentes por tipo
ROSTER = [
    (0, "Ayuntamiento", "GovernmentAgency"),          # único de su tipo
    (2, "Centro de salud", "Organization"),
    (3, "Plataforma ciclista", "TransportAssociation"),
    (4, "Gremio del taxi", "TransportAssociation"),
    (5, "Ecologistas en Acción", "EnvironmentalGroup"),
    (6, "Vecinos del casco histórico", "EnvironmentalGroup"),
    (9, "Autónomos con furgoneta", "BusinessAssociation"),
    (10, "Comerciantes del centro", "BusinessAssociation"),
    (13, "Familias con niños", "Person"),
    (16, "Personas mayores", "Person"),
]

TAXI = "El gremio del taxi aclara: NO estamos en contra de la ZBE, pero pedimos un plazo."
MAYORES = "Soy vecina del casco histórico, tengo 72 años y no puedo subir la cuesta andando."
FAMILIAS = "Padre de dos niños pequeños: el aire del colegio nos preocupa cada mañana."
FURGONETA = "Soy autónomo con furgoneta y la ZBE me deja sin poder trabajar en el centro."
CICLISTAS = "Desde la plataforma ciclista pedimos carriles seguros antes de cerrar el centro."


@pytest.fixture()
def agents():
    return [
        AgentActivityConfig(agent_id=i, entity_uuid=f"u{i}", entity_name=name, entity_type=etype)
        for i, name, etype in ROSTER
    ]


@pytest.fixture()
def gen(monkeypatch):
    g = SimulationConfigGenerator(api_key="test", base_url="http://localhost:1")

    def no_llm(*_args, **_kwargs):
        raise AssertionError("no se debía preguntar al modelo")

    monkeypatch.setattr(g, "_call_llm_with_retry", no_llm)
    return g


def assign(gen, agents, posts):
    cfg = EventConfig(initial_posts=posts)
    return gen._assign_initial_post_agents(cfg, agents).initial_posts


def by_content(posts):
    return {p["content"]: p for p in posts}


# ---------- el caso real: varios agentes del mismo tipo ----------

def test_posts_go_to_the_named_agent_not_to_the_next_of_the_type(gen, agents):
    # Con el reparto por turnos, el primer mensaje de TransportAssociation iba al agente 3 y el segundo al 4
    # (y los de Person al 13 y al 16) sin mirar quién hablaba: aquí cada uno lleva su autor.
    posts = [
        {"content": TAXI, "poster_name": "Gremio del taxi", "poster_agent_id": 4, "poster_type": "TransportAssociation"},
        {"content": CICLISTAS, "poster_name": "Plataforma ciclista", "poster_agent_id": 3, "poster_type": "TransportAssociation"},
        {"content": MAYORES, "poster_name": "Personas mayores", "poster_agent_id": 16, "poster_type": "Person"},
        {"content": FAMILIAS, "poster_name": "Familias con niños", "poster_agent_id": 13, "poster_type": "Person"},
        {"content": FURGONETA, "poster_name": "Autónomos con furgoneta", "poster_agent_id": 9, "poster_type": "BusinessAssociation"},
    ]
    out = by_content(assign(gen, agents, posts))
    assert out[TAXI]["poster_agent_id"] == 4
    assert out[CICLISTAS]["poster_agent_id"] == 3
    assert out[MAYORES]["poster_agent_id"] == 16
    assert out[FAMILIAS]["poster_agent_id"] == 13
    assert out[FURGONETA]["poster_agent_id"] == 9


def test_name_wins_when_the_id_points_to_another_agent(gen, agents):
    # El modelo se equivoca de id (típico desfase en una lista larga) pero escribe bien el nombre
    posts = [{"content": TAXI, "poster_name": "Gremio del taxi", "poster_agent_id": 3, "poster_type": "TransportAssociation"}]
    assert assign(gen, agents, posts)[0]["poster_agent_id"] == 4


@pytest.mark.parametrize("written", [
    "gremio del TAXI",                                   # mayúsculas
    "Gremio del taxi.",                                  # signos
    "  Gremio   del  taxi ",                             # espacios
    "Gremio del taxi (TransportAssociation)",            # le añade el tipo
])
def test_name_is_matched_loosely_but_only_to_one_agent(gen, agents, written):
    posts = [{"content": TAXI, "poster_name": written, "poster_type": "TransportAssociation"}]
    assert assign(gen, agents, posts)[0]["poster_agent_id"] == 4


def test_accents_do_not_matter(gen):
    agents = [AgentActivityConfig(0, "u0", "Peña Ecologista", "EnvironmentalGroup"),
              AgentActivityConfig(1, "u1", "Peña Vecinal", "EnvironmentalGroup")]
    posts = [{"content": "x", "poster_name": "pena ecologista"}]
    assert assign(gen, agents, posts)[0]["poster_agent_id"] == 0


def test_string_and_float_ids_are_accepted(gen, agents):
    posts = [{"content": MAYORES, "poster_agent_id": "16", "poster_type": "Person"},
             {"content": FAMILIAS, "poster_agent_id": 13.0, "poster_type": "Person"}]
    out = assign(gen, agents, posts)
    assert [p["poster_agent_id"] for p in out] == [16, 13]


def test_contradictory_type_requires_a_new_author_decision(gen, agents, monkeypatch):
    monkeypatch.setattr(gen, "_call_llm_with_retry", lambda *_: {"assignments": [
        {"post_index": 0, "poster_name": "Gremio del taxi", "poster_agent_id": 4}]})
    posts = [{"content": TAXI, "poster_name": "gremio del taxi", "poster_type": "Official"}]
    post = assign(gen, agents, posts)[0]
    assert post == {"content": TAXI, "poster_type": "TransportAssociation",
                    "poster_name": "Gremio del taxi", "poster_agent_id": 4}


# ---------- el id y el tipo solo valen si no se contradicen ----------

def test_id_alone_is_used_when_the_type_agrees(gen, agents):
    posts = [{"content": MAYORES, "poster_agent_id": 16, "poster_type": "Person"}]
    assert assign(gen, agents, posts)[0]["poster_agent_id"] == 16


def test_id_that_contradicts_the_type_is_not_trusted(gen, agents, monkeypatch):
    # id 3 es una TransportAssociation y el mensaje dice ser una Person: no se adivina, se pregunta
    asked = []

    def answer(prompt, system_prompt):
        asked.append(prompt)
        return {"assignments": [{"post_index": 0, "poster_name": "Personas mayores", "poster_agent_id": 16}]}

    monkeypatch.setattr(gen, "_call_llm_with_retry", answer)
    posts = [{"content": MAYORES, "poster_agent_id": 3, "poster_type": "Person"}]
    assert assign(gen, agents, posts)[0]["poster_agent_id"] == 16
    assert len(asked) == 1


def test_type_alone_is_used_only_when_there_is_one_agent_of_that_type(gen, agents):
    posts = [{"content": "Comunicado oficial.", "poster_type": "GovernmentAgency"}]
    assert assign(gen, agents, posts)[0]["poster_agent_id"] == 0     # sin preguntar al modelo (el fixture lo prohíbe)


# ---------- tipo ambiguo y sin autor: se pregunta, y si no se sabe se descarta ----------

def test_ambiguous_type_without_author_asks_who_wrote_it(gen, agents, monkeypatch):
    seen = {}

    def answer(prompt, system_prompt):
        seen["prompt"] = prompt
        return {"assignments": [
            {"post_index": 0, "poster_name": "Gremio del taxi", "poster_agent_id": 4},
            {"post_index": 1, "poster_name": "Personas mayores", "poster_agent_id": None},
        ]}

    monkeypatch.setattr(gen, "_call_llm_with_retry", answer)
    posts = [{"content": TAXI, "poster_type": "TransportAssociation"},          # dos del tipo, sin nombre
             {"content": MAYORES, "poster_type": "Person"}]                     # dos del tipo, sin nombre
    out = assign(gen, agents, posts)
    assert [p["poster_agent_id"] for p in out] == [4, 16]
    # Se le enseña lo que dice cada mensaje y la lista completa de agentes con su id
    assert TAXI in seen["prompt"] and MAYORES in seen["prompt"]
    assert "Plataforma ciclista" in seen["prompt"] and '"id": 13' in seen["prompt"]


def test_only_the_posts_without_author_are_asked_about(gen, agents, monkeypatch):
    seen = {}

    def answer(prompt, system_prompt):
        seen["prompt"] = prompt
        return {"assignments": [{"post_index": 0, "poster_name": "Gremio del taxi"}]}

    monkeypatch.setattr(gen, "_call_llm_with_retry", answer)
    posts = [{"content": CICLISTAS, "poster_name": "Plataforma ciclista"},       # ya tiene autor
             {"content": TAXI, "poster_type": "TransportAssociation"}]          # este no
    out = assign(gen, agents, posts)
    assert [p["poster_agent_id"] for p in out] == [3, 4]
    assert TAXI in seen["prompt"] and CICLISTAS not in seen["prompt"]


@pytest.mark.parametrize("reply", [
    {"assignments": [{"post_index": 0, "poster_name": None, "poster_agent_id": None}]},   # «ninguno»
    {"assignments": [{"post_index": 0, "poster_name": "Asociación inventada"}]},            # no existe
    {"assignments": [{"post_index": 0, "poster_agent_id": 99}]},                            # id inexistente
    {"assignments": [{"post_index": 7, "poster_name": "Gremio del taxi"}]},                 # índice fuera de rango
    {"assignments": "mal"}, ["mal"], {},                                                    # forma rara
])
def test_unknown_author_drops_the_post_instead_of_guessing(gen, agents, monkeypatch, reply):
    monkeypatch.setattr(gen, "_call_llm_with_retry", lambda prompt, system_prompt: reply)
    posts = [{"content": TAXI, "poster_type": "TransportAssociation"}]
    assert assign(gen, agents, posts) == []


def test_model_failure_drops_the_ambiguous_posts_but_keeps_the_rest(gen, agents, monkeypatch):
    def boom(prompt, system_prompt):
        raise RuntimeError("proveedor caído")

    monkeypatch.setattr(gen, "_call_llm_with_retry", boom)
    posts = [{"content": CICLISTAS, "poster_name": "Plataforma ciclista"},
             {"content": TAXI, "poster_type": "TransportAssociation"}]
    out = assign(gen, agents, posts)
    assert [p["poster_agent_id"] for p in out] == [3]


def test_made_up_name_with_a_valid_id_and_matching_type_is_not_trusted(gen, agents, monkeypatch):
    monkeypatch.setattr(gen, "_call_llm_with_retry", lambda *_: {"assignments": []})
    posts = [{"content": TAXI, "poster_name": "Sindicato de taxistas del mundo", "poster_agent_id": 4,
              "poster_type": "TransportAssociation"}]
    assert assign(gen, agents, posts) == []


# ---------- datos raros ----------

def test_malformed_posts_are_dropped_and_the_rest_survive(gen, agents):
    posts = ["texto suelto", None, {"content": ""}, {"content": "   ", "poster_name": "Gremio del taxi"},
             {"content": 5, "poster_name": "Gremio del taxi"},
             {"content": TAXI, "poster_name": "Gremio del taxi", "poster_type": None}]
    out = assign(gen, agents, posts)
    assert [p["poster_agent_id"] for p in out] == [4]


def test_no_posts_or_no_agents(gen, agents):
    assert assign(gen, agents, []) == []
    assert assign(gen, [], [{"content": TAXI, "poster_name": "Gremio del taxi"}]) == []


def test_same_name_twice_needs_an_id_to_disambiguate(gen, monkeypatch):
    monkeypatch.setattr(gen, "_call_llm_with_retry", lambda *_: {"assignments": []})
    agents = [AgentActivityConfig(0, "u0", "María", "Person"), AgentActivityConfig(1, "u1", "María", "Person")]
    posts = [{"content": "a", "poster_name": "María", "poster_agent_id": 1},
             {"content": "b", "poster_name": "María"}]
    assert [p["poster_agent_id"] for p in assign(gen, agents, posts)] == [1]


# ---------- lo que ve el modelo al escribir los mensajes ----------

def entity(name, etype, summary=""):
    return EntityNode(uuid=name, name=name, labels=["Entity", etype], summary=summary, attributes={})


def test_prompt_lists_every_agent_with_the_id_the_config_will_use(gen, monkeypatch):
    # Antes solo enseñaba 3 nombres por tipo y ningún id: el modelo no podía elegir autor
    seen = {}

    def capture(prompt, system_prompt):
        seen["prompt"], seen["system"] = prompt, system_prompt
        return {"initial_posts": []}

    monkeypatch.setattr(gen, "_call_llm_with_retry", capture)
    entities = [entity(f"Vecino {i}", "Person", f"Resumen {i}") for i in range(8)] + [entity("Gremio del taxi", "TransportAssociation")]
    gen._generate_event_config("ctx", "Una ZBE en el centro", entities)

    for i in range(8):                                   # los 8 de un mismo tipo, no solo 3
        assert f'"id": {i}, "name": "Vecino {i}", "type": "Person"' in seen["prompt"]
    assert '"id": 8, "name": "Gremio del taxi", "type": "TransportAssociation"' in seen["prompt"]
    assert "poster_name" in seen["prompt"] and "poster_agent_id" in seen["prompt"]
    assert "poster_name" in seen["system"]


def test_roster_is_capped_and_says_so(gen):
    rows = [(i, f"Agente {i}", "Person", "") for i in range(SimulationConfigGenerator.ROSTER_MAX_ENTRIES + 5)]
    text = gen._roster_text(rows)
    assert text.count("\n") == SimulationConfigGenerator.ROSTER_MAX_ENTRIES      # 200 líneas + la nota
    assert "y 5 agentes más" in text and "Agente 204" not in text


def test_roster_keeps_names_with_quotes_and_accents_intact(gen):
    text = gen._roster_text([(1, 'Colectivo «Bici» y "Aire"', "Organization", "Ñandú — ciclistas")])
    assert 'Colectivo «Bici» y \\"Aire\\"' in text and "Ñandú" in text


def test_norm_helpers():
    assert scg._norm("  Ñandú — «Bici»! ") == "nandu bici"
    assert scg._norm_type("Transport_Association") == "transportassociation"
    assert scg._as_agent_id(True) is None and scg._as_agent_id("x") is None and scg._as_agent_id("07") == 7


@pytest.mark.parametrize('post', [
    {'content': TAXI, 'poster_agent_id': 4, 'poster_type': 'ImaginaryType'},
    {'content': TAXI, 'poster_agent_id': 99, 'poster_type': 'GovernmentAgency'},
    {'content': TAXI, 'poster_name': 'Gremio', 'poster_agent_id': 4, 'poster_type': 'TransportAssociation'},
])
def test_invalid_explicit_hints_do_not_fall_back_to_another_identity(gen, agents, monkeypatch, post):
    monkeypatch.setattr(gen, '_call_llm_with_retry', lambda *_: {'assignments': []})
    assert assign(gen, agents, [post]) == []


def test_original_brief_survives_a_large_derived_graph_before_event_generation(gen, monkeypatch):
    entities = [entity(f'Actor {i}', f'Type{i}', 'Texto derivado ' * 100) for i in range(146)]
    brief = ('Hechos proporcionados. ' * 200 +
             '\nLa convocatoria es hipotética. La decisión y la huelga están pendientes; no han ocurrido.')
    context = gen._build_context('Qué pasaría si se celebraran elecciones hoy', brief, entities)
    seen = {}

    def capture(prompt, system_prompt):
        seen.update(prompt=prompt, system=system_prompt)
        return {'initial_posts': []}

    monkeypatch.setattr(gen, '_call_llm_with_retry', capture)
    gen._generate_event_config(context, 'Qué pasaría si se celebraran elecciones hoy', entities)
    assert brief in seen['prompt']
    assert context.index('Contenido del documento original') < context.index('Información de entidades')
    assert 'Preserve pending, hypothetical and disputed status explicitly' in seen['system']
    assert 'no fija de antemano el ganador' in seen['prompt']
    assert len(context) <= gen.MAX_CONTEXT_LENGTH


def test_generation_version_is_serialized_only_on_new_configurations():
    params = scg.SimulationParameters('sim_test', 'proj_test', 'graph_test', 'escenario')
    assert params.to_dict()['generation_version'] == scg.GENERATION_VERSION == 2
