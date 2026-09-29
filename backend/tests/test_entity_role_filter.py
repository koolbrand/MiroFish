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
