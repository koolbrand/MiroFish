"""Temas políticos: para unas elecciones, el voto y la ideología de cada persona son LA evidencia (no se dejan al final ni se
neutralizan). Con cualquier otro tema, todo sigue como antes. Bancos sintéticos y un modelo falso."""

import json

import pytest

from app.config import Config
from app.services import poblacion
from app.services.poblacion import jev as J
from app.services.poblacion.banco import Banco
from app.services.poblacion.fuentes import FUENTES
from poblacion_fixture import crear_banco

ELECTORAL = "¿Quién ganaría las elecciones generales si se celebraran hoy en España?\nVotantes de todo el país y los partidos"
CAFE = "Predecir cómo reaccionarán estudiantes y vecinos al precio de 3,50 euros en una cafetería de Vigo"
VOTO = "Intención de voto en unas supuestas elecciones generales [recodificada]"
RECUERDO = "Recuerdo de voto en las elecciones generales de 2023"
IDEOLOGIA = "Escala de autoubicación ideológica (1-10)"


@pytest.fixture()
def banco(tmp_path, monkeypatch):
    ruta = crear_banco(str(tmp_path / "b.sqlite"), n=300)
    monkeypatch.setattr(Config, "POBLACION_BANCO_PATH", ruta)
    monkeypatch.setattr(Config, "POBLACION_BANCOS_DIR", str(tmp_path))
    import sqlite3
    c = sqlite3.connect(ruta)
    for (i,) in c.execute("SELECT id FROM encuestados").fetchall():
        for q, r in ((VOTO, "PP"), (RECUERDO, "PSOE"), (IDEOLOGIA, "5")):
            c.execute("INSERT INTO respuestas VALUES (?,?,?,1)", (i, q, r))
    c.commit(); c.close()
    return Banco(ruta, FUENTES["cis"])


@pytest.fixture(autouse=True)
def sin_jev(monkeypatch):
    monkeypatch.setattr(J, "disponible", lambda: False)


def test_el_tema_politico_se_detecta_por_palabras_sin_jev():
    assert poblacion.tema_politico(ELECTORAL) is True
    assert poblacion.tema_politico("Las elecciones y el voto de los jóvenes") is True
    assert poblacion.tema_politico(CAFE) is False
    assert poblacion.tema_politico("Un comercio apoyado por el gobierno local") is False    # una sola palabra suelta no basta
    assert poblacion.tema_politico("") is False


def test_el_tema_politico_con_jev_manda_y_si_duda_decide_la_palabra(monkeypatch):
    monkeypatch.setattr(J, "disponible", lambda: True)
    visto = {}

    def jev(p):
        def f(state, preguntas):
            visto["q"] = preguntas
            return {"politico": {"noul": p}}
        return f

    monkeypatch.setattr(J, "preguntar", jev(0.95))
    assert poblacion.tema_politico(CAFE) is True and "política" in visto["q"]["politico"]["instructions"]
    monkeypatch.setattr(J, "preguntar", jev(0.05))
    assert poblacion.tema_politico(ELECTORAL) is False
    monkeypatch.setattr(J, "preguntar", jev(0.5))                              # duda: las palabras
    assert poblacion.tema_politico(ELECTORAL) is True and poblacion.tema_politico(CAFE) is False
    monkeypatch.setattr(J, "preguntar", lambda s, q: None)                      # Jev caído: las palabras
    assert poblacion.tema_politico(ELECTORAL) is True


def test_el_catalogo_solo_trae_las_politicas_si_se_piden(banco):
    sin = banco.catalogo()
    con = banco.catalogo(politica=True)
    assert VOTO not in sin and IDEOLOGIA not in sin
    assert {VOTO, RECUERDO, IDEOLOGIA, "¿A qué partido votaría?"} <= set(con) and set(sin) < set(con)


def test_con_tema_politico_el_voto_y_la_ideologia_son_relevantes_y_van_primero(banco):
    pedido = {}

    def llm(prompt):
        pedido["p"] = prompt
        n = [l.split(".")[0] for l in prompt.splitlines() if l[:1].isdigit() and ". " in l[:4]]
        return json.dumps({"indices": list(range(len(n)))})              # elige todas: el orden final lo pone el código

    rel = poblacion.preguntas_relevantes(banco, ELECTORAL, llm)          # sin `politico`: se detecta
    assert "POLÍTICO" in pedido["p"] and VOTO in pedido["p"] and "¿Cuánto confía en sus vecinos?" in pedido["p"]
    assert rel[:3] == [VOTO, RECUERDO, IDEOLOGIA] or {VOTO, RECUERDO, IDEOLOGIA} == set(rel[:3])      # el voto y la ideología, primero
    assert rel.index(VOTO) < rel.index("¿Cuánto confía en sus vecinos?")
    # con un tema que no es político, el catálogo no lleva política y el prompt es el de siempre
    rel2 = poblacion.preguntas_relevantes(banco, CAFE, llm)
    assert "POLÍTICO" not in pedido["p"] and VOTO not in pedido["p"] and not (set(rel2) & {VOTO, RECUERDO, IDEOLOGIA})
    # y se puede forzar
    assert VOTO in poblacion.preguntas_relevantes(banco, CAFE, llm, politico=True)


def test_los_nombres_de_lideres_y_las_baterias_sin_enunciado_no_entran(banco, tmp_path):
    import sqlite3
    c = sqlite3.connect(banco.path if hasattr(banco, "path") else Config.POBLACION_BANCO_PATH)
    for (i,) in c.execute("SELECT id FROM encuestados").fetchall():
        c.execute("INSERT INTO respuestas VALUES (?,?,?,1)", (i, "Yolanda Díaz", "5"))
        c.execute("INSERT INTO respuestas VALUES (?,?,?,1)", (i, "La bandera", "Mucho"))
    c.commit(); c.close()
    visto = {}
    poblacion.preguntas_relevantes(banco, ELECTORAL, lambda p: visto.setdefault("p", p) and '{"indices": []}')
    assert "Yolanda Díaz" not in visto["p"] and "La bandera" not in visto["p"] and VOTO in visto["p"]


def test_la_ficha_de_un_tema_politico_lleva_el_voto_real_primero(banco):
    e = banco.encuestado(banco.segmento({}).ids[0])
    rel = poblacion.preguntas_relevantes(banco, ELECTORAL, lambda p: json.dumps({"indices": [0, 1, 2, 3, 4]}))
    ficha = poblacion.construir_ficha(e, fuente=FUENTES["cis"], tema=ELECTORAL, relevantes=rel)
    lineas = [l for l in ficha.splitlines() if l.startswith("- ") and "→" in l]
    assert lineas and VOTO[:30] in lineas[0] and "PP" in lineas[0]
    sin = poblacion.construir_ficha(e, fuente=FUENTES["cis"], tema=CAFE,
                                    relevantes=poblacion.preguntas_relevantes(banco, CAFE, lambda p: '{"indices": [0, 1]}'))
    assert VOTO[:30] not in sin                                                # un tema de café no lleva el voto de nadie


def test_el_prompt_de_persona_deja_de_neutralizar_el_voto_solo_en_temas_politicos():
    from app.services.oasis_profile_generator import OasisProfileGenerator
    g = OasisProfileGenerator.__new__(OasisProfileGenerator)
    ficha = "Datos sociodemográficos:\n- Edad: 40"
    args = ("Electorado", "Votantes", {}, "contexto", ficha, FUENTES["cis"])
    base = g._build_encuesta_persona_prompt(*args)
    assert "POLITICAL TOPIC" not in base and "a person is not their vote" in base
    g._tema_politico = True
    pol = g._build_encuesta_persona_prompt(*args)
    assert "POLITICAL TOPIC" in pol and "stays exactly as the data sheet says" in pol and "a person is not their vote" in pol
