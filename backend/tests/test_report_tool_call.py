"""
Una sección del informe nunca debe quedarse con una llamada a herramienta como contenido.

Caso real (1-oct-2026, informe `report_89eb981c8da3`): el modelo escribió la etiqueta sin el «<»
inicial («tool_call>»). El analizador no la reconocía como llamada y, con ya tres herramientas usadas,
la rama «sin Final Answer» guardó ese texto tal cual como el contenido de la sección.
"""

import pytest

from app.services.report_agent import ReportAgent, ReportOutline, ReportSection

CALL = '{"name": "panorama_search", "parameters": {"query": "Northkin vs Cozi", "include_expired": false}}'
PROSE = (
    "Las familias estadounidenses ven a Northkin como una alternativa de pago frente a opciones "
    "gratuitas: el 49,99 $ anual sin plan gratis es la principal barrera, según las entrevistas."
)


class ScriptedLLM:
    """Responde con una lista fija, en orden; recuerda lo que se le pidió."""

    def __init__(self, replies):
        self.replies = list(replies)
        self.calls = []

    def chat(self, messages, **kwargs):
        self.calls.append([m["content"] for m in messages])
        return self.replies.pop(0) if self.replies else None


@pytest.fixture
def agent():
    def make(replies):
        a = ReportAgent("g", "s", "predecir la reacción", llm_client=ScriptedLLM(replies), zep_tools=object())
        a.executed = []
        a._execute_tool = lambda name, params, **kw: (a.executed.append(name), "RESULTADO")[1]
        return a
    return make


def run(agent_):
    outline = ReportOutline(title="T", summary="S", sections=[ReportSection(title="Barreras")])
    return agent_._generate_section_react(outline.sections[0], outline, [], None, 1)


# ── analizador ────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("text", [
    f"<tool_call>\n{CALL}\n</tool_call>",             # bien escrita
    f"tool_call>\n{CALL}\n</tool_call>",              # sin el «<» inicial (el caso real)
    f"<tool_call>\n{CALL}\n",                         # sin cierre
    f"tool_call>\n{CALL}",                            # sin «<» ni cierre
    f"Voy a buscar.\n<TOOL_CALL>{CALL}</TOOL_CALL>",  # con texto antes y en mayúsculas
])
def test_parser_recupera_la_llamada_aunque_este_mal_escrita(agent, text):
    calls = agent([])._parse_tool_calls(text)
    assert [c["name"] for c in calls] == ["panorama_search"]


def test_parser_no_inventa_llamadas_en_un_texto_normal(agent):
    assert agent([])._parse_tool_calls(PROSE) == []


# ── limpieza ──────────────────────────────────────────────────────────────────

def test_limpieza_quita_el_bloque_y_conserva_el_texto(agent):
    a = agent([])
    assert a._clean_section_text(f"{PROSE}\n\ntool_call>\n{CALL}\n</tool_call>") == PROSE


def test_limpieza_quita_un_json_suelto_con_forma_de_llamada(agent):
    a = agent([])
    assert a._clean_section_text(f"{PROSE}\n\n{CALL}") == PROSE


@pytest.mark.parametrize("text", [
    f"tool_call>\n{CALL}\n</tool_call>",              # solo la llamada (el caso real)
    "tool_call>",                                     # solo la marca
    "<tool_call>\n{ no es json",                      # bloque roto: no se puede ni recuperar
    f"{PROSE}\n<tool_call>\n{{ cortado",              # texto + marca suelta: no se guarda a medias
    "",                                               # vacío
    "ok",                                             # un resto, no una sección
])
def test_limpieza_rechaza_lo_que_no_es_una_seccion(agent, text):
    assert agent([])._clean_section_text(text) is None


def test_limpieza_no_toca_texto_legitimo_que_menciona_json(agent):
    legit = 'El campo {"name": "Cozi"} del informe de mercado confirma el precio gratuito para familias.'
    assert agent([])._clean_section_text(legit) == legit


# ── bucle de la sección ───────────────────────────────────────────────────────

def test_etiqueta_sin_menor_que_se_ejecuta_como_llamada_y_no_acaba_en_el_texto(agent):
    # lo que pasó de verdad: dos etiquetas mal escritas y luego el texto
    a = agent([
        f"<tool_call>\n{CALL}\n</tool_call>",
        f"tool_call>\n{CALL.replace('panorama_search', 'quick_search')}\n</tool_call>",
        f"tool_call>\n{CALL.replace('panorama_search', 'insight_forge')}\n</tool_call>",
        f"Final Answer: {PROSE}",
    ])
    assert run(a) == PROSE
    assert a.executed == ["panorama_search", "quick_search", "insight_forge"]


def test_sin_final_answer_con_basura_pide_de_nuevo_en_vez_de_guardarla(agent):
    a = agent([
        f"<tool_call>\n{CALL}\n</tool_call>",
        f"<tool_call>\n{CALL.replace('panorama_search', 'quick_search')}\n</tool_call>",
        f"<tool_call>\n{CALL.replace('panorama_search', 'insight_forge')}\n</tool_call>",
        "tool_call>\n{ cortado a mitad",   # ya con 3 herramientas: antes se guardaba tal cual
        PROSE,                             # sin «Final Answer:» pero ya es texto: se acepta
    ])
    assert run(a) == PROSE
    # y se le dijo qué estaba mal
    assert any("[Error de formato]" in c for c in a.llm.calls[-1])


def test_final_answer_con_una_llamada_dentro_se_rechaza(agent):
    a = agent([
        f"<tool_call>\n{CALL}\n</tool_call>",
        f"<tool_call>\n{CALL.replace('panorama_search', 'quick_search')}\n</tool_call>",
        f"<tool_call>\n{CALL.replace('panorama_search', 'insight_forge')}\n</tool_call>",
        f"Final Answer: tool_call>\n{CALL}\n</tool_call>",   # nada de texto
        f"Final Answer: {PROSE}",
    ])
    assert run(a) == PROSE


def test_el_cierre_forzado_nunca_guarda_una_llamada_como_contenido(agent, monkeypatch):
    # el modelo no entrega texto jamás: ni en el bucle ni en el cierre forzado ni en el reintento
    mala = f"tool_call>\n{CALL}\n</tool_call>"
    a = agent([mala] * 20)
    a.MAX_TOOL_CALLS_PER_SECTION = 1
    out = run(a)
    assert "tool_call" not in out and "panorama_search" not in out
    assert "no pudo redactarse" in out or "could not be written" in out or "未能撰写" in out
    assert a._forced_sections == ["Barreras"]


def test_el_cierre_forzado_acepta_el_texto_si_llega_en_el_reintento(agent):
    mala = f"tool_call>\n{CALL}\n</tool_call>"
    a = agent([mala] * 7 + [mala, f"Final Answer: {PROSE}"])
    a.MAX_TOOL_CALLS_PER_SECTION = 5
    assert run(a) == PROSE


def test_respuesta_normal_sigue_igual(agent):
    a = agent([
        f"<tool_call>\n{CALL}\n</tool_call>",
        f"<tool_call>\n{CALL.replace('panorama_search', 'quick_search')}\n</tool_call>",
        f"<tool_call>\n{CALL.replace('panorama_search', 'insight_forge')}\n</tool_call>",
        f"Final Answer: {PROSE}",
    ])
    assert run(a) == PROSE


@pytest.mark.parametrize("text", [
    "Tengo información suficiente. Las entrevistas cubren los seis perfiles clave con citas directas muy ricas. Procedo al Final Answer.",
    "I have enough information now. Proceeding to the Final Answer.",
    "Tengo la información suficiente para redactar. Procedo a escribir la sección.",
])
def test_limpieza_rechaza_el_razonamiento_interno_del_modelo(agent, text):
    """Visto en producción (3-oct-2026): la sección «Reacciones previstas» quedó con solo «Procedo al Final Answer.»"""
    assert agent([])._clean_section_text(text) is None


def test_limpieza_conserva_una_seccion_larga_aunque_mencione_la_respuesta_final(agent):
    larga = ("El informe distingue tres tipos de reacción ante el precio. " * 14) + "Esto no es la respuesta final de nadie, es el análisis."
    assert len(larga) > 600 and agent([])._clean_section_text(larga) == larga.strip()
