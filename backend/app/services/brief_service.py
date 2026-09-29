"""
Brief de la simulación: plantilla, revisión con Jev y entrevista (grill-me).

La calidad de la simulación depende casi entera del documento semilla: un brief
que describe sobre todo a la competencia produce agentes de empresas en vez de
clientes (visto en Northkin: audiencia 17 %). Aquí se define qué debe contener
un buen brief y se ofrecen dos ayudas:

- check_brief: Jev comprueba en ~1 s qué secciones trae el documento.
- next_question / compose_brief: una entrevista que pregunta, de una en una y
  sin conformarse con respuestas vagas, por lo que falta, y al final redacta el
  brief con la plantilla. Jev decide qué falta; el LLM formula y redacta.
"""

from typing import Dict, List, Optional

import httpx

from ..config import Config
from ..utils.llm_client import LLMClient, strip_reasoning
from ..utils.locale import get_language_instruction
from ..utils.logger import get_logger

logger = get_logger('mirofish.brief')

# Máximo de texto que se manda a Jev en una revisión
MAX_BRIEF_CHARS = 12000

# Las secciones de un buen brief. `required`: sin ella la simulación sale mal.
SECTIONS: List[Dict] = [
    {
        "key": "producto",
        "title": "Qué se lanza",
        "required": True,
        "check": "¿`brief` explica qué es el producto, servicio o propuesta y qué problema resuelve?",
        "ask_about": "qué es exactamente lo que se lanza o propone y qué problema concreto resuelve",
    },
    {
        "key": "publico",
        "title": "Quién es el público",
        "required": True,
        # Graduada: nombrar a los grupos en una lista no basta (Northkin lo hacía
        # y la simulación salió con un 17 % de audiencia).
        "check": "¿Con cuánto detalle describe `brief` a las personas a las que va dirigido o a quienes afecta?",
        "levels": [
            "No menciona a quién va dirigido.",
            "Solo nombra grupos o categorías («familias», «padres separados»), en una lista o una frase, sin describirlos.",
            "Describe la situación o el perfil de al menos un grupo (quiénes son y en qué situación están).",
            "Describe a los grupos con perfiles concretos: situación, qué les duele o preocupa y cómo lo resuelven hoy.",
        ],
        "present_at": 2,
        "ask_about": (
            "quiénes son exactamente esas personas: situación, perfil, qué les duele, "
            "cómo lo resuelven hoy y qué les haría cambiar"
        ),
    },
    {
        "key": "segmentos",
        "title": "Segmentos y cuánto pesa cada uno",
        "required": False,
        "check": "¿`brief` distingue varios grupos o segmentos de público y cuánto importa cada uno?",
        "ask_about": "qué grupos distintos de público hay y cuál pesa más",
    },
    {
        "key": "competencia",
        "title": "Competencia y alternativas",
        "required": True,
        "check": (
            "¿`brief` menciona competidores o las alternativas que el público usa hoy "
            "(incluidas las gratuitas o no hacer nada)?"
        ),
        "ask_about": "con qué compite, incluidas las alternativas gratuitas o no hacer nada",
    },
    {
        "key": "precio",
        "title": "Precio o condiciones",
        "required": False,
        "check": "¿`brief` indica el precio, el coste o las condiciones que asume el público?",
        "ask_about": "cuánto cuesta o qué condiciones asume el público",
    },
    {
        "key": "lanzamiento",
        "title": "Cómo y cuándo se lanza",
        "required": False,
        "check": "¿`brief` explica cómo y cuándo se va a lanzar o comunicar (canal, momento, mensaje)?",
        "ask_about": "por qué canal, cuándo y con qué mensaje se va a lanzar",
    },
    {
        "key": "hipotesis",
        "title": "Dudas e hipótesis a poner a prueba",
        "required": False,
        "check": "¿`brief` plantea dudas, riesgos o hipótesis concretas que se quieren comprobar?",
        "ask_about": "qué dudas o hipótesis concretas quieres poner a prueba con la simulación",
    },
]


def jev_available() -> bool:
    return bool(Config.TYPESAFE_API_KEY)


def check_brief(text: str) -> Dict:
    """Qué secciones trae el brief. Una sola petición a Jev con una pregunta por sección."""
    text = (text or "").strip()
    if not jev_available():
        return {"available": False, "reason": "sin TYPESAFE_API_KEY"}
    if not text:
        return {"available": True, "sections": [], "missing_required": [s["key"] for s in SECTIONS if s["required"]]}

    payload = {
        "model": Config.JEV_MODEL,
        "state": {"brief": text[:MAX_BRIEF_CHARS]},
        "questions": {
            s["key"]: (
                {"type": "score", "instructions": s["check"], "criteria": s["levels"]}
                if "levels" in s else
                {"type": "noul", "instructions": s["check"]}
            )
            for s in SECTIONS
        },
    }
    try:
        with httpx.Client(timeout=20, headers={"Authorization": f"Bearer {Config.TYPESAFE_API_KEY}"}) as client:
            response = client.post(Config.TYPESAFE_API_URL, json=payload)
            response.raise_for_status()
            answers = response.json()["answers"]
    except Exception as e:  # noqa: BLE001 — la revisión es una ayuda, nunca bloquea
        logger.warning(f"Revisión del brief con Jev falló: {type(e).__name__}: {str(e)[:150]}")
        return {"available": False, "reason": "Jev no respondió"}

    sections = []
    for s in SECTIONS:
        answer = answers.get(s["key"], {})
        item = {"key": s["key"], "title": s["title"], "required": s["required"]}
        if "levels" in s:
            # score: posición esperada entre 0 y len(levels)-1
            level = float(answer.get("score", 0))
            item.update(present=level >= s["present_at"], level=round(level, 2),
                        level_text=s["levels"][min(int(round(level)), len(s["levels"]) - 1)],
                        probability=round(min(1.0, level / (len(s["levels"]) - 1)), 3))
        else:
            probability = float(answer.get("noul", 0))
            item.update(present=probability >= 0.5, probability=round(probability, 3))
        sections.append(item)
    return {
        "available": True,
        "truncated": len(text) > MAX_BRIEF_CHARS,
        "sections": sections,
        "missing_required": [x["key"] for x in sections if x["required"] and not x["present"]],
        "missing_recommended": [x["key"] for x in sections if not x["required"] and not x["present"]],
    }


def _transcript_text(topic: str, transcript: List[Dict]) -> str:
    lines = [f"Tema: {topic}"] if topic else []
    for turn in transcript:
        if turn.get("question"):
            lines.append(f"Pregunta: {turn['question']}")
        if turn.get("answer"):
            lines.append(f"Respuesta: {turn['answer']}")
    return "\n".join(lines)


def _section(key: str) -> Optional[Dict]:
    return next((s for s in SECTIONS if s["key"] == key), None)


def next_question(topic: str, transcript: List[Dict], seed_text: str = "") -> Dict:
    """Siguiente pregunta de la entrevista, o done=True si el brief ya está cubierto."""
    material = "\n\n".join(x for x in [seed_text.strip(), _transcript_text(topic, transcript)] if x)
    coverage = check_brief(material) if material else {"available": jev_available(), "sections": []}

    if coverage.get("available") and coverage.get("sections"):
        missing = coverage["missing_required"] + coverage["missing_recommended"]
    else:
        # Sin Jev: recorrer las secciones en orden según las preguntas ya hechas
        asked = {t.get("section") for t in transcript}
        missing = [s["key"] for s in SECTIONS if s["key"] not in asked]

    # Máximo de preguntas: la entrevista no debe eternizarse
    if not missing or len(transcript) >= 12:
        return {"done": True, "coverage": coverage}

    target = _section(missing[0])
    last_answer = transcript[-1].get("answer", "") if transcript else ""
    system = (
        f"{get_language_instruction()}\n"
        "Eres un estratega de marketing que prepara el brief de una simulación de opinión pública. "
        "Entrevistas al cliente como en un «grill me»: una sola pregunta cada vez, concreta, exigente "
        "y fácil de responder, sin rodeos ni cumplidos. Si la última respuesta fue vaga o genérica, "
        "repregunta pidiendo algo concreto (un ejemplo, una cifra, un perfil real). "
        "Devuelve solo la pregunta, en una o dos frases."
    )
    user = (
        f"Tema de la simulación: {topic or '(sin definir)'}\n\n"
        f"Lo que sabemos hasta ahora:\n{material or '(nada todavía)'}\n\n"
        f"Última respuesta del cliente: {last_answer or '(ninguna)'}\n\n"
        f"Lo siguiente que falta en el brief: {target['ask_about']}.\n"
        "Haz la siguiente pregunta."
    )
    question = LLMClient().chat(
        messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
        temperature=0.5,
        max_tokens=2048,
    ).strip().strip('"')
    return {"done": False, "question": question, "section": target["key"],
            "section_title": target["title"], "coverage": coverage}


def compose_brief(topic: str, transcript: List[Dict], seed_text: str = "") -> str:
    """Redacta el brief en la plantilla usando solo lo que ha dicho el cliente."""
    material = "\n\n".join(x for x in [seed_text.strip(), _transcript_text(topic, transcript)] if x)
    headings = "\n".join(f"## {s['title']}" for s in SECTIONS)
    system = (
        f"{get_language_instruction()}\n"
        "Redactas el brief de una simulación de opinión pública a partir de una entrevista. "
        "Usa SOLO la información dada: no inventes cifras, nombres ni datos. Si una sección no tiene "
        "información, escribe «Pendiente: …» indicando qué falta. Escribe frases claras y concretas, "
        "con el público descrito con el máximo detalle disponible. Devuelve solo el Markdown."
    )
    user = (
        f"Tema: {topic or '(sin definir)'}\n\nMaterial:\n{material}\n\n"
        f"Estructura obligatoria (título principal y estas secciones, en este orden):\n# Brief: <nombre>\n{headings}"
    )
    return strip_reasoning(LLMClient().chat(
        messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
        temperature=0.3,
        max_tokens=6000,
    ))
