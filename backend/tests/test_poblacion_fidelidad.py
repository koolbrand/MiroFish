"""Medición de fidelidad: métricas y flujo completo con un LLM falso y el banco sintético."""

import importlib.util
import json
import sys
from pathlib import Path

import pytest

from app.services.poblacion.banco import Banco
from poblacion_fixture import crear_banco

RUTA = Path(__file__).resolve().parents[1] / "scripts" / "poblacion" / "fidelidad.py"
spec = importlib.util.spec_from_file_location("fidelidad", RUTA)
fd = importlib.util.module_from_spec(spec)
sys.modules["fidelidad"] = fd
spec.loader.exec_module(fd)


def test_jsd_extremos_y_simetria():
    assert fd.jsd({"a": 1, "b": 1}, {"a": 1, "b": 1}) == pytest.approx(0)
    assert fd.jsd({"a": 1}, {"b": 1}) == pytest.approx(1)
    p, q = {"a": 3, "b": 1}, {"a": 1, "b": 3}
    assert fd.jsd(p, q) == pytest.approx(fd.jsd(q, p)) and 0 < fd.jsd(p, q) < 1


def test_distribucion_con_pesos():
    d = fd.distribucion(["x", "y", "x", None], [1, 2, 3, 9], ["x", "y"])
    assert d == {"x": 4, "y": 2}


@pytest.fixture()
def muestra(tmp_path):
    banco = Banco(crear_banco(str(tmp_path / "b.sqlite"), n=120))
    return fd.cargar_muestra(banco, "9001", 50, 1)


def test_elegir_preguntas_solo_no_politicas(muestra):
    qs = fd.elegir_preguntas(muestra, 10)
    assert qs and all("partido" not in q and "ideología" not in q for q, _ in qs)
    assert all(3 <= len(ops) <= 7 for _, ops in qs)


def test_prompt_b_lleva_respuestas_y_oculta_las_escondidas(muestra):
    qs = fd.elegir_preguntas(muestra, 2)
    ocultas = {q for q, _ in qs}
    a = fd.prompt_persona(muestra[0], ocultas, False, qs)
    b = fd.prompt_persona(muestra[0], ocultas, True, qs)
    assert "Lo que ya respondiste" not in a and "Lo que ya respondiste" in b
    resto = b.split("Ahora responde")[0]
    assert not any(q in resto for q in ocultas)       # las escondidas no se cuelan en la ficha


def test_estimar_coste_es_pequeño_y_crece_con_la_muestra(muestra):
    qs = fd.elegir_preguntas(muestra, 5)
    c = fd.estimar_coste(muestra, qs)
    assert c["llamadas"] == 2 * len(muestra) and 0 < c["usd"] < 1
    assert fd.estimar_coste(muestra[:10], qs)["usd"] < c["usd"]


def test_parsear_tolera_prosa_y_opciones_invalidas():
    qs = [("P", ["Si", "No", "Tal vez"])]
    assert fd.parsear('Claro {"1": "si"}', qs) == {1: "Si"}
    assert fd.parsear('{"1": "quizá"}', qs) == {1: None}
    assert fd.parsear("nada", qs) == {1: None}


def test_evaluar_un_oraculo_gana_al_azar_y_al_modelo_ciego(muestra):
    qs = fd.elegir_preguntas(muestra, 4)
    verdad = {id(e): {r["pregunta"]: r["respuesta"] for r in e.respuestas} for e in muestra}

    def llm(prompt):
        # «Oráculo» para la condición b (la que lleva respuestas), y siempre la 1.ª opción para la a
        con = "Lo que ya respondiste" in prompt
        out = {}
        for i, (q, ops) in enumerate(qs, 1):
            out[str(i)] = ops[0]
        if con:
            for e in muestra:
                if all(f"{x}" in prompt for x in [f"Edad: {e.edad} años"]) and e.sexo and e.sexo in prompt:
                    for i, (q, ops) in enumerate(qs, 1):
                        out[str(i)] = verdad[id(e)].get(q, ops[0])
                    break
        return json.dumps(out)

    res = fd.evaluar(muestra, qs, llm)
    assert set(res) == {"a_sociodemografia", "b_con_respuestas", "moda_del_grupo", "azar"}
    assert res["b_con_respuestas"]["acierto"] >= res["a_sociodemografia"]["acierto"]
    assert res["b_con_respuestas"]["jsd_medio"] <= res["a_sociodemografia"]["jsd_medio"] + 1e-9
    md = fd.informe_md("9001", len(muestra), qs, res, {"usd": 0.1, "llamadas": 100})
    assert "Fuente de datos: CIS" in md and "| azar |" in md
