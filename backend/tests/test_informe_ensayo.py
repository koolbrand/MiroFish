"""
El informe es un ensayo, no un pronóstico.

La home dice «Primero ensaya. Después decide.» y la caja «Cómo leer este informe» del PDF dice «sirve para ensayar la decisión…
no para garantizarla»; pero la etiqueta del PDF (portada y cabecera de cada página, en mayúsculas) decía «INFORME DE PREDICCIÓN» y
el cuerpo lo escribe un modelo al que los prompts llamaban «Reportes de predicción del futuro», de ahí «pronostica». Aquí se fija
la etiqueta en los tres idiomas y que ningún prompt del redactor vuelva a hablar de predicción fuera de la propia lista de lo vetado.
"""

import json
import os

import pytest

from app.services.report_agent import (
    CHAT_SYSTEM_PROMPT_TEMPLATE, PLAN_SYSTEM_PROMPT, PLAN_USER_PROMPT_TEMPLATE, REGLA_LENGUAJE_ENSAYO,
    SECTION_SYSTEM_PROMPT_TEMPLATE, SECTION_USER_PROMPT_TEMPLATE, VOCABULARIO_VETADO,
)
from app.services.report_pdf import TEXTS, build_html

LOCALES_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "locales")
PROMPTS = {
    "PLAN_SYSTEM_PROMPT": PLAN_SYSTEM_PROMPT,
    "PLAN_USER_PROMPT_TEMPLATE": PLAN_USER_PROMPT_TEMPLATE,
    "SECTION_SYSTEM_PROMPT_TEMPLATE": SECTION_SYSTEM_PROMPT_TEMPLATE,
    "SECTION_USER_PROMPT_TEMPLATE": SECTION_USER_PROMPT_TEMPLATE,
    "CHAT_SYSTEM_PROMPT_TEMPLATE": CHAT_SYSTEM_PROMPT_TEMPLATE,
}


# ---------------------------------------------------------------- los prompts del redactor
@pytest.mark.parametrize("nombre", sorted(PROMPTS))
def test_ningun_prompt_del_redactor_habla_de_prediccion(nombre):
    texto = PROMPTS[nombre].replace(REGLA_LENGUAJE_ENSAYO, "").lower()
    asomados = [raiz for raiz in VOCABULARIO_VETADO if raiz in texto]
    assert not asomados, f"{nombre} usa vocabulario de pronóstico: {asomados}"


@pytest.mark.parametrize("nombre", ["PLAN_SYSTEM_PROMPT", "SECTION_SYSTEM_PROMPT_TEMPLATE", "CHAT_SYSTEM_PROMPT_TEMPLATE"])
def test_los_prompts_que_escriben_llevan_la_regla_de_lenguaje(nombre):
    assert REGLA_LENGUAJE_ENSAYO in PROMPTS[nombre]


def test_la_regla_dice_los_verbos_vetados_y_lo_de_las_probabilidades():
    for pieza in ("pronostica", "predice", "vaticina", "el futuro será", "se prevé", "probabilidades", "porcentajes",
                  "EN LA SIMULACIÓN"):
        assert pieza in REGLA_LENGUAJE_ENSAYO, pieza


def test_el_vocabulario_vetado_cubre_cada_palabra_que_la_regla_prohibe():
    for palabra in ("pronostica", "predice", "vaticina", "anticipa", "el futuro será", "se prevé", "predicción", "pronóstico"):
        assert palabra in REGLA_LENGUAJE_ENSAYO, palabra
        assert any(raiz in palabra for raiz in VOCABULARIO_VETADO), f"ninguna raíz vetada atrapa «{palabra}»"


def test_las_plantillas_siguen_rellenandose():
    """Al partir los textos para colar la regla no se ha roto ninguna llave de `.format`."""
    section = SECTION_SYSTEM_PROMPT_TEMPLATE.format(
        report_title="TITULO", report_summary="S", simulation_requirement="R", section_title="X", tools_description="(herramientas)")
    assert "TITULO" in section and "{report_title}" not in section and REGLA_LENGUAJE_ENSAYO in section
    plan = PLAN_USER_PROMPT_TEMPLATE.format(
        simulation_requirement="R", total_nodes=1, total_edges=2, entity_types="[]", total_entities=3, related_facts_json="[]")
    assert "[Escenario simulado]" in plan
    chat = CHAT_SYSTEM_PROMPT_TEMPLATE.format(simulation_requirement="R", report_content="C", tools_description="(herramientas)")
    assert "Condición simulada: R" in chat and REGLA_LENGUAJE_ENSAYO in chat
    assert '"title"' in PLAN_SYSTEM_PROMPT and '"sections"' in PLAN_SYSTEM_PROMPT      # el esquema JSON sigue igual


def test_el_ensayo_se_conserva_como_encuadre():
    for texto in (PLAN_SYSTEM_PROMPT, SECTION_SYSTEM_PROMPT_TEMPLATE):
        assert "ensayo" in texto and "Informes de simulación" in texto


# ---------------------------------------------------------------- las etiquetas
def test_la_etiqueta_del_pdf_es_informe_de_simulacion_en_los_tres_idiomas():
    assert TEXTS["es"]["kind"] == "Informe de simulación"
    assert TEXTS["en"]["kind"] == "Simulation report"
    assert TEXTS["zh"]["kind"] == "模拟报告"
    for locale, etiqueta in (("es", "Informe de simulación"), ("en", "Simulation report"), ("zh", "模拟报告")):
        pagina = build_html(title="Línea 14: cómo reaccionan los barrios", summary="", question="", body_html="<p>x</p>",
                            meta={}, locale=locale)
        assert f'<div class="cover-tag">{etiqueta}</div>' in pagina                      # portada
        assert f'content: "{etiqueta}"' in pagina                                       # cabecera de cada página


@pytest.mark.parametrize("lang", ["es", "en", "zh"])
def test_ninguna_etiqueta_de_informe_promete_una_prediccion(lang):
    with open(os.path.join(LOCALES_DIR, f"{lang}.json"), encoding="utf-8") as f:
        data = json.load(f)
    etiquetas = {
        "ui.predictionReport": data["ui"]["predictionReport"],
        "home.reportKicker": data["home"]["reportKicker"],
        "home.deliverable1Title": data["home"]["deliverable1Title"],
        **{f"report.{k}": v for k, v in data["report"].items() if k.startswith("fallback")},
        "step4.scenarioLabel": data["step4"]["scenarioLabel"],
    }
    for clave, texto in etiquetas.items():
        plano = texto.lower()
        assert not any(raiz in plano for raiz in ("predic", "predec", "pronóstic", "预测", "forecast")), f"{lang} {clave}: {texto}"
    assert data["ui"]["predictionReport"] == {"es": "Informe de simulación", "en": "Simulation Report", "zh": "模拟报告"}[lang]


def test_las_herramientas_ya_no_devuelven_vocabulario_de_prediccion_al_redactor():
    from app.services.zep_tools import InsightForgeResult
    texto = InsightForgeResult(query="q", simulation_requirement="R", sub_queries=["a"]).to_text()
    assert "Escenario simulado: R" in texto and "Hechos simulados relevantes" in texto
    assert "predic" not in texto.lower()


def test_la_tarjeta_de_insight_forge_entiende_el_texto_nuevo_y_el_de_los_informes_guardados():
    """`Step4Report.vue` lee estas etiquetas con una expresión regular: debe seguir casando con las dos redacciones."""
    import re
    ruta = os.path.join(os.path.dirname(LOCALES_DIR), "frontend", "src", "components", "Step4Report.vue")
    fuente = open(ruta, encoding="utf-8").read()
    for texto in ("Escenario simulado: R", "Escenario predicho: R"):
        assert re.search(r"(?:预测场景|Escenario predicho|Escenario simulado):", texto)
    for etiqueta in ("Escenario simulado", "Escenario predicho", "Hechos simulados relevantes", "Hechos predichos relevantes",
                     "Hechos predichos relacionados"):
        assert etiqueta in fuente, etiqueta
