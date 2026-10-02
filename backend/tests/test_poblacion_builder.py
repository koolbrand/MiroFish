"""Constructor del banco: normalizadores puros y, si pyreadstat está, ida y vuelta con un .sav sintético."""

import importlib.util
import sys
import zipfile
from pathlib import Path

import pytest

RUTA = Path(__file__).resolve().parents[1] / "scripts" / "poblacion" / "build_banco_cis.py"
spec = importlib.util.spec_from_file_location("build_banco_cis", RUTA)
bc = importlib.util.module_from_spec(spec)
sys.modules["build_banco_cis"] = bc
spec.loader.exec_module(bc)


def test_normalizadores():
    assert bc.norm_sexo("Mujer") == "Mujer" and bc.norm_sexo("Hombre") == "Hombre" and bc.norm_sexo("N.C.") is None
    assert bc.norm_ccaa("Asturias (Principado de)") == "Asturias"
    assert bc.norm_ccaa("Comunitat Valenciana") == "Comunidad Valenciana"
    assert bc.norm_ccaa("Balears (Illes)") == "Baleares"
    assert bc.norm_ccaa("Madrid (Comunidad de)") == "Madrid"
    assert bc.norm_tamuni("Menos o igual a 2.000 habitantes") == "rural"
    assert bc.norm_tamuni("De 2.001 a 10.000") == "pequeño"
    assert bc.norm_tamuni("De 50.001 a 100.000") == "mediano"
    assert bc.norm_tamuni("Más de 1.000.000") == "grande"
    assert bc.norm_estudios("Sin estudios") == "sin_estudios"
    assert bc.norm_estudios("Primaria") == "primarios"
    assert bc.norm_estudios("Secundaria 1ª etapa") == "secundarios"
    assert bc.norm_estudios("Formación Profesional 2º grado") == "fp"
    assert bc.norm_estudios("Superiores") == "universitarios"
    assert bc.norm_sitlab("Jubilado/a o pensionista (anteriormente ha trabajado)") == "jubilado"
    assert bc.norm_sitlab("Parado/a y ha trabajado antes") == "parado"
    assert bc.norm_sitlab("Trabaja") == "trabaja"
    assert bc.norm_sitlab("Trabajo doméstico no remunerado") == "labores_hogar"
    assert bc.norm_estcivil("Casado/a") == "casado" and bc.norm_estcivil("Soltero/a") == "soltero"


def test_respuestas_sin_ns_nc_y_preguntas_limpias():
    assert bc.respuesta_valida("N.S.") is None and bc.respuesta_valida("N.C.") is None
    assert bc.respuesta_valida("No sabe") is None and bc.respuesta_valida("  ") is None
    assert bc.respuesta_valida("Mucho") == "Mucho"
    assert bc.limpiar_pregunta("P7. Satisfacción con la vida") == "Satisfacción con la vida"
    assert bc.es_politica("Voto en las últimas elecciones") and not bc.es_politica("Cuánto confía en sus vecinos")


def test_ida_y_vuelta_con_sav_sintetico(tmp_path):
    pd = pytest.importorskip("pandas")
    pyreadstat = pytest.importorskip("pyreadstat")
    df = pd.DataFrame({
        "SEXO": [1, 2, 2, 1], "EDAD": [30, 45, 70, 17], "CCAA": [12, 9, 1, 12], "PESO": [1.0, 0.8, 1.2, 1.0],
        "P1": [1, 2, 1, 1], "P2": [1, 2, 2, 1],
    })
    sav = tmp_path / "x.sav"
    pyreadstat.write_sav(df, str(sav), column_labels=["Sexo", "Edad", "CCAA", "Peso", "P1. Confianza en vecinos", "P2. Voto"],
                         variable_value_labels={"SEXO": {1: "Hombre", 2: "Mujer"}, "CCAA": {12: "Galicia", 9: "Cataluña", 1: "Andalucía"},
                                                "P1": {1: "Mucha", 2: "N.S."}, "P2": {1: "Partido A", 2: "Partido B"}})
    zp = tmp_path / "MD9999.zip"
    with zipfile.ZipFile(zp, "w") as z:
        z.write(sav, "MD9999.sav")
    from app.services.poblacion import banco as B
    salida = tmp_path / "b.sqlite"
    bc.main([str(zp), "--salida", str(salida)])
    banco = B.Banco(str(salida))
    assert B.Banco.disponible(str(salida))
    assert banco.estudios()[0]["n"] == 3                      # el de 17 años no entra
    e = banco.encuestado(1)
    assert (e.sexo, e.edad, e.ccaa, e.tramo) == ("Hombre", 30, "Galicia", "25-34")
    assert any(r["pregunta"] == "Confianza en vecinos" and r["respuesta"] == "Mucha" for r in e.respuestas)
    assert any(r["politica"] == 1 for r in e.respuestas)
    sin_nc = banco.encuestado(2)                              # su P1 era N.S.: no se guarda
    assert not any(r["pregunta"] == "Confianza en vecinos" for r in sin_nc.respuestas)
