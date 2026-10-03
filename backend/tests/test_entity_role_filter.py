"""Filtro de entidades con Jev: descarta infraestructura segura y nunca rompe la preparación."""

from dataclasses import dataclass, field

import pytest

from app.config import Config
from app.services import entity_role_filter as erf


@dataclass
class Entity:
    name: str
    summary: str = ""
    labels: list = field(default_factory=lambda: ["Entity"])


ENTITIES = [Entity("Madres y padres"), Entity("Cozi"), Entity("iCloud"), Entity("App Store"), Entity("Wander")]
ANSWERS = {
    "Madres y padres": {"role": "audiencia", "confidence": 0.97},
    "Cozi": {"role": "competidor", "confidence": 0.95},
    "iCloud": {"role": "infraestructura", "confidence": 0.93},
    "App Store": {"role": "infraestructura", "confidence": 0.6},   # dudosa: se queda
    "Wander": None,                                                 # Jev falla: se queda
}


@pytest.fixture(autouse=True)
def jev_on(monkeypatch):
    monkeypatch.setattr(Config, "JEV_ENTITY_FILTER", True)
    monkeypatch.setattr(Config, "TYPESAFE_API_KEY", "test")
    monkeypatch.setattr(Config, "JEV_DROP_CONFIDENCE", 0.8)
    monkeypatch.setattr(Config, "JEV_MIN_AUDIENCE_RATIO", 0.4)


def test_drops_only_confident_infrastructure(monkeypatch):
    monkeypatch.setattr(erf, "_ask_jev", lambda client, e, topic: ANSWERS[e.name])
    result = erf.filter_entities(ENTITIES, "lanzamiento de una app familiar")
    names = [e.name for e in result.kept]
    assert names == ["Madres y padres", "Cozi", "App Store", "Wander"]
    summary = result.summary()
    assert [d["name"] for d in summary["dropped"]] == ["iCloud"]
    assert summary["roles"] == {"audiencia": 1, "competidor": 1, "infraestructura": 2}
    assert summary["audience_ratio"] == 0.25
    assert summary["low_audience"] is True


def test_no_key_keeps_everything(monkeypatch):
    monkeypatch.setattr(Config, "TYPESAFE_API_KEY", None)
    result = erf.filter_entities(ENTITIES, "x")
    assert len(result.kept) == len(ENTITIES) and not result.applied


def test_service_down_keeps_everything(monkeypatch):
    monkeypatch.setattr(erf, "_ask_jev", lambda client, e, topic: None)
    result = erf.filter_entities(ENTITIES, "x")
    assert len(result.kept) == len(ENTITIES) and not result.applied
    assert result.reason == "Jev no respondió"


def test_never_leaves_zero_agents(monkeypatch):
    monkeypatch.setattr(erf, "_ask_jev", lambda client, e, topic: {"role": "infraestructura", "confidence": 0.99})
    result = erf.filter_entities(ENTITIES, "x")
    assert len(result.kept) == len(ENTITIES) and not result.applied


def test_audience_becomes_individuals_and_expands(monkeypatch):
    monkeypatch.setattr(Config, "AUDIENCE_EXPANSION", True)
    monkeypatch.setattr(Config, "AUDIENCE_MAX_EXTRA", 20)
    monkeypatch.setattr(Config, "AUDIENCE_MAX_VARIANTS", 4)
    ents = [Entity("Madres y padres"), Entity("Padres separados"), Entity("Cozi"), Entity("FamilyWall"),
            Entity("Maple"), Entity("KIN"), Entity("Google Calendar"), Entity("Periodistas")]
    for i, e in enumerate(ents):
        e.uuid = f"u{i}"
        e.attributes = {}
    roles = {"Madres y padres": "audiencia", "Padres separados": "audiencia", "Periodistas": "voz_influyente"}
    monkeypatch.setattr(erf, "_ask_jev", lambda c, e, t: {"role": roles.get(e.name, "competidor"), "confidence": 0.9})
    result = erf.filter_entities(ents, "lanzamiento")
    out = erf.expand_audience(result.kept, result)
    summary = result.summary()
    # 2/8 = 25 % -> hace falta llegar al 40 %: (0.4*8-2)/0.6 = 2 extra
    assert summary["audience_expanded"] == 2
    assert len(out) == 10 and summary["kept"] == 10
    assert summary["audience_ratio"] == 0.4 and summary["low_audience"] is False
    variants = [e for e in out if e.attributes.get(erf.VARIANT_HINT)]
    assert {v.name for v in variants} == {"Madres y padres · 2", "Padres separados · 2"}
    assert len({e.uuid for e in out}) == len(out)            # uuids únicos
    assert all(e.attributes.get(erf.INDIVIDUAL_FLAG) for e in out if "adres" in e.name)
    assert not ents[2].attributes.get(erf.INDIVIDUAL_FLAG)    # los competidores no


def test_expansion_is_capped(monkeypatch):
    monkeypatch.setattr(Config, "AUDIENCE_EXPANSION", True)
    monkeypatch.setattr(Config, "AUDIENCE_MAX_EXTRA", 3)
    monkeypatch.setattr(Config, "AUDIENCE_MAX_VARIANTS", 4)
    ents = [Entity(f"E{i}") for i in range(30)]
    for i, e in enumerate(ents):
        e.uuid, e.attributes = f"u{i}", {}
    monkeypatch.setattr(erf, "_ask_jev", lambda c, e, t: {"role": "audiencia" if e.name == "E0" else "competidor", "confidence": 0.9})
    result = erf.filter_entities(ents, "x")
    out = erf.expand_audience(result.kept, result)
    assert len(out) == 33            # tope total: +3


def test_an_organization_is_not_audience_even_if_it_serves_people(monkeypatch):
    """«Universidad de Vigo» salía como audiencia (afecta a estudiantes) y se generaba como una estudiante de intercambio."""
    monkeypatch.setattr(Config, "AUDIENCE_EXPANSION", False)
    ents = [Entity("Estudiantes de la Universidad de Vigo"), Entity("Universidad de Vigo"), Entity("Marta Ruiz"), Entity("Bar Paco")]
    for i, e in enumerate(ents):
        e.uuid, e.attributes = f"u{i}", {}
    respuestas = {
        "Estudiantes de la Universidad de Vigo": {"role": "audiencia", "confidence": 1.0, "organization": 0.0},
        "Universidad de Vigo": {"role": "audiencia", "confidence": 0.93, "organization": 1.0},        # el fallo real, medido con Jev
        "Marta Ruiz": {"role": "implicado", "confidence": 0.99, "organization": 0.05},
        "Bar Paco": {"role": "competidor", "confidence": 0.5, "organization": 1.0},
    }
    monkeypatch.setattr(erf, "_ask_jev", lambda c, e, t: respuestas[e.name])
    result = erf.filter_entities(ents, "precio del café")
    out = erf.expand_audience(result.kept, result)
    assert result.reclassified == ["Universidad de Vigo"] and result.summary()["reclassified"] == ["Universidad de Vigo"]
    assert result.roles == {"audiencia": 1, "implicado": 2, "competidor": 1}
    assert [e.name for e in out if e.attributes.get(erf.INDIVIDUAL_FLAG)] == ["Estudiantes de la Universidad de Vigo"]
    # y una duda (probabilidad baja de organización) no cambia nada: sigue como audiencia
    dudosa = {"role": "audiencia", "confidence": 0.9, "organization": 0.4}
    monkeypatch.setattr(erf, "_ask_jev", lambda c, e, t: dudosa)
    assert erf.filter_entities([Entity("X")], "t").reclassified == []


def test_the_nature_question_goes_in_the_same_request(monkeypatch):
    """Una petición con las dos preguntas (se evalúan en paralelo); si Jev no trae la de naturaleza, todo sigue como antes."""
    enviado = {}

    class Cliente:
        def post(self, url, json=None):
            enviado.update(json)
            import httpx
            return httpx.Response(200, request=httpx.Request("POST", url), json={"answers": {
                "rol": {"choice": "audiencia", "confidence": 0.9},
                "naturaleza": {"choice": "organizacion", "probabilities": {"organizacion": 0.97, "personas": 0.03}}}})

    r = erf._ask_jev(Cliente(), Entity("Universidad de Vigo", "x"), "tema")
    assert set(enviado["questions"]) == {"rol", "naturaleza"} and r["organization"] == 0.97 and r["role"] == "audiencia"

    class SinNaturaleza(Cliente):
        def post(self, url, json=None):
            import httpx
            return httpx.Response(200, request=httpx.Request("POST", url), json={"answers": {"rol": {"choice": "audiencia", "confidence": 0.9}}})

    assert erf._ask_jev(SinNaturaleza(), Entity("X"), "t")["organization"] == 0.0


def _audiencia(n_grupos, otros):
    ents = [Entity(f"G{i}") for i in range(n_grupos)] + [Entity(f"O{i}") for i in range(otros)]
    for i, e in enumerate(ents):
        e.uuid, e.attributes = f"u{i}", {}
    roles = {f"G{i}": "audiencia" for i in range(n_grupos)}
    return ents, roles


def test_target_size_fills_the_audience_to_that_number_split_by_group(monkeypatch):
    """Una muestra representativa de un electorado: un solo grupo («Electorado») con N personas, sin mirar umbral ni topes."""
    monkeypatch.setattr(Config, "AUDIENCE_EXPANSION", True)
    monkeypatch.setattr(Config, "AUDIENCE_MAX_EXTRA", 3)           # los topes de la configuración no cuentan con target_size
    monkeypatch.setattr(Config, "AUDIENCE_MAX_VARIANTS", 2)
    ents, roles = _audiencia(1, 9)
    monkeypatch.setattr(erf, "_ask_jev", lambda c, e, t: {"role": roles.get(e.name, "competidor"), "confidence": 0.9})
    result = erf.filter_entities(ents, "elecciones")
    out = erf.expand_audience(result.kept, result, "elecciones", target_size=60)
    pers = [e for e in out if e.attributes.get(erf.INDIVIDUAL_FLAG)]
    assert len(pers) == 60 and len(out) == 69 and len({e.uuid for e in out}) == len(out)
    assert {e.attributes[erf.GROUP_KEY] for e in pers} == {"u0"}                     # un solo grupo: una sola muestra
    assert result.summary()["audience_expanded"] == 59
    # varios grupos: reparto por igual
    ents, roles = _audiencia(3, 4)
    monkeypatch.setattr(erf, "_ask_jev", lambda c, e, t: {"role": roles.get(e.name, "competidor"), "confidence": 0.9})
    result = erf.filter_entities(ents, "x")
    out = erf.expand_audience(result.kept, result, "x", target_size=12)
    por_grupo = {}
    for e in out:
        if e.attributes.get(erf.INDIVIDUAL_FLAG):
            por_grupo[e.attributes[erf.GROUP_KEY]] = por_grupo.get(e.attributes[erf.GROUP_KEY], 0) + 1
    assert sorted(por_grupo.values()) == [4, 4, 4]


def test_target_size_has_a_hard_cap_and_never_shrinks(monkeypatch):
    ents, roles = _audiencia(2, 3)
    monkeypatch.setattr(erf, "_ask_jev", lambda c, e, t: {"role": roles.get(e.name, "competidor"), "confidence": 0.9})
    result = erf.filter_entities(ents, "x")
    out = erf.expand_audience(result.kept, result, "x", target_size=10_000)
    assert sum(1 for e in out if e.attributes.get(erf.INDIVIDUAL_FLAG)) == erf.MAX_AUDIENCE_SIZE
    result = erf.filter_entities(ents, "x")
    out = erf.expand_audience(result.kept, result, "x", target_size=1)               # menos que los grupos: no se quita a nadie
    assert len(out) == len(ents) and result.summary()["audience_expanded"] == 0
    # sin target_size, ampliar sigue apagado si AUDIENCE_EXPANSION es false
    monkeypatch.setattr(Config, "AUDIENCE_EXPANSION", False)
    result = erf.filter_entities(ents, "x")
    assert len(erf.expand_audience(result.kept, result, "x")) == len(ents)
