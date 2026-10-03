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


def test_normalizadores_con_las_etiquetas_reales_del_cis():
    """Etiquetas copiadas de los ficheros reales (MD3505, MD3535, MD3571, MD3577). Antes «F.P.» salía sin categoría y
    «En paro y ha trabajado antes» salía como «trabaja»: el primer volcado con datos reales lo destapó."""
    assert [bc.norm_estudios(x) for x in ("Superiores", "F.P.", "Secundaria 2ª etapa", "Secundaria 1ª etapa",
                                          "Primaria", "Sin estudios")] == \
        ["universitarios", "fp", "secundarios", "secundarios", "primarios", "sin_estudios"]
    assert bc.norm_estudios("N.C.") is None and bc.norm_estudios("Otros") is None
    assert [bc.norm_sitlab(x) for x in (
        "Trabaja", "Jubilado/a o pensionista (anteriormente ha trabajado)", "En paro y ha trabajado antes",
        "Estudiante", "Trabajo doméstico no remunerado", "Pensionista (anteriormente no ha trabajado)",
        "Otra situación", "En paro y busca su primer empleo")] == \
        ["trabaja", "jubilado", "parado", "estudiante", "labores_hogar", "jubilado", "otra", "parado"]
    assert bc.norm_sitlab("N.C.") is None
    assert [bc.norm_estcivil(x) for x in ("Casado/a", "Soltero/a", "Divorciado/a", "Viudo/a", "Separado/a")] == \
        ["casado", "soltero", "separado_divorciado", "viudo", "separado_divorciado"]
    assert [bc.norm_tamuni(x) for x in (
        "Menos o igual a 2.000 habitantes", "2.001 a 10.000 habitantes", "10.001 a 50.000 habitantes",
        "50.001 a 100.000 habitantes", "100.001 a 400.000 habitantes", "400.001 a 1.000.000 habitantes",
        "Más de 1.000.000 habitantes")] == ["rural", "pequeño", "mediano", "mediano", "grande", "grande", "grande"]


def test_respuestas_sin_ns_nc_y_preguntas_limpias():
    assert bc.respuesta_valida("N.S.") is None and bc.respuesta_valida("N.C.") is None
    assert bc.respuesta_valida("No sabe") is None and bc.respuesta_valida("  ") is None
    assert bc.respuesta_valida("Mucho") == "Mucho"
    assert bc.limpiar_pregunta("P7. Satisfacción con la vida") == "Satisfacción con la vida"
    # paradatos del trabajo de campo (salen en TODOS los estudios reales) fuera; los líderes y partidos cuentan como política
    assert all(bc.es_paradato(x) for x in ("Tipo de teléfono", "Hora de realización", "Capital", "Rechazo por desconfianza hacia las encuestas",
                                           "Grado de sinceridad de la persona entrevistada según el/la entrevistador/a"))
    assert all(bc.es_paradato(x) for x in ("Día de realización", "Día de la semana que se realiza la entrevista", "Valoración de la supervisión",
                                           "Entrevista válida", "Rehúsa porque su pareja/familia/hogar no quiere", "Supervisor",
                                           "Ha tenido prisa por acabar la entrevista", "Dificultad con el idioma", "N.C."))
    assert not bc.es_paradato("Grado de preocupación por el cambio climático") and not bc.es_paradato("Capital social")
    assert not bc.es_paradato("Nivel de ingresos netos del hogar") and not bc.es_paradato("Religiosidad de la persona entrevistada")
    assert bc.respuesta_valida("(NO LEER) N.S., duda") is None and bc.respuesta_valida("(NO LEER) N.S./N.C.") is None
    assert bc.respuesta_valida("(NO LEER) Ninguno") == "Ninguno" and bc.respuesta_valida("Mucho") == "Mucho"
    assert bc.es_politica("Pedro Sánchez") and bc.es_politica("Alberto Núñez Feijóo") and bc.es_politica("Voto en el PP")
    assert not bc.es_politica("Grado de preocupación por los incendios") and not bc.es_politica("Valoración de la situación económica personal")
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
    assert (e.sexo, e.edad, e.region, e.tramo) == ("Hombre", 30, "Galicia", "25-34")
    assert any(r["pregunta"] == "Confianza en vecinos" and r["respuesta"] == "Mucha" for r in e.respuestas)
    assert any(r["politica"] == 1 for r in e.respuestas)
    sin_nc = banco.encuestado(2)                              # su P1 era N.S.: no se guarda
    assert not any(r["pregunta"] == "Confianza en vecinos" for r in sin_nc.respuestas)


def test_peso_acepta_coma_decimal_y_no_se_traga_el_error():
    # Los .sav del CIS 3535 y 3577 entregan PESO como TEXTO con coma («2,87887», «,39533»): antes caía a 1.0 en silencio
    assert bc._leer_peso("0,39533", "3535", "peso") == pytest.approx(0.39533)
    assert bc._leer_peso(",39533", "3535", "peso") == pytest.approx(0.39533)
    assert bc._leer_peso("2,87887", "3577", "peso") == pytest.approx(2.87887)
    assert bc._leer_peso("0.5", "3530", "peso") == 0.5 and bc._leer_peso(1.25, "3571", "peso") == 1.25
    for malo in ("abc", "", None, float("nan"), 0, -1, "0,0"):
        with pytest.raises(SystemExit, match="3535"):
            bc._leer_peso(malo, "3535", "peso")


def test_pesos_como_texto_con_coma_llegan_al_banco_y_ccaa_se_usa_en_el_segmento(tmp_path):
    pd = pytest.importorskip("pandas")
    pyreadstat = pytest.importorskip("pyreadstat")
    df = pd.DataFrame({
        "SEXO": [1, 2, 2, 1], "EDAD": [30, 45, 70, 50], "CCAA": [12, 12, 12, 12],
        "PESO": ["0,5", ",25", "2,0", "1,0"], "PESOCCAA": ["1,0", "1,0", "3,0", "1,0"], "P1": [1, 1, 1, 1],
    })
    sav = tmp_path / "x.sav"
    pyreadstat.write_sav(df, str(sav), column_labels=["Sexo", "Edad", "CCAA", "Peso", "Peso autonómico", "P1. Confianza en vecinos"],
                         variable_value_labels={"SEXO": {1: "Hombre", 2: "Mujer"}, "CCAA": {12: "Galicia"}, "P1": {1: "Mucha"}})
    zp = tmp_path / "MD9998.zip"
    with zipfile.ZipFile(zp, "w") as z:
        z.write(sav, "MD9998.sav")
    from app.services.poblacion import banco as B
    salida = tmp_path / "b.sqlite"
    bc.main([str(zp), "--salida", str(salida)])
    banco = B.Banco(str(salida))
    filas = banco.conn.execute("SELECT peso, peso_ccaa FROM encuestados ORDER BY id").fetchall()
    assert [r["peso"] for r in filas] == [0.5, 0.25, 2.0, 1.0] and [r["peso_ccaa"] for r in filas] == [1.0, 1.0, 3.0, 1.0]
    general = banco.segmento({}, minimo=0)
    ccaa = banco.segmento({}, minimo=0, pesos_ccaa=True)
    assert general.pesos == pytest.approx([0.5 / 3.75, 0.25 / 3.75, 2.0 / 3.75, 1.0 / 3.75])
    assert ccaa.pesos == pytest.approx([1 / 6, 1 / 6, 3 / 6, 1 / 6])
    assert "peso" not in {r["pregunta"] for e in [banco.encuestado(1)] for r in e.respuestas}   # PESO* no es una pregunta
