"""
Entrevistas a personas simuladas: lo que se les dice antes de preguntar.

Una persona simulada no tiene encuestas, recuentos ni firmas: solo su perfil, lo que dijo e hizo en la simulación y el
texto base. Si se le pregunta «¿qué porcentaje de tus vecinos piensa lo mismo?», el modelo rellena con una cifra creíble
(«entre un 78 % y un 85 %», «4.200 firmas»). Quien usa Simuloo en política o comunicación puede citarla como dato.
Caso medido: 4 intentos de 4 inventaron cifras para el perfil «vecinos de barrios periféricos», cuyos 8 mensajes no
tenían ninguna. De ahí la regla de aquí abajo, que viaja en TODAS las vías de entrevista: la API (`/interview`,
`/interview/batch`, `/interview/all`), el fallback con modelo cuando el entorno ya no existe y las entrevistas del
agente de informes.
"""

from ..utils.locale import t
from .profile_memory import is_canonical, render_memory

REFERENCE_MEMORY_RULE = (
    "Distingue el material aportado (no verificado independientemente), las respuestas medidas de una encuesta "
    "y las opiniones/acciones desarrolladas dentro de esta simulación. Un recuerdo de voto no es intención actual. "
    "No añadas biografía, cargos, estudios ni acciones históricas ausentes de la memoria inicial. Las opiniones "
    "nuevas y los cambios de postura son posiciones simuladas; no acreditan hechos reales fuera de esta ejecución."
)

REGLA_CIFRAS = (
    "Regla sobre cifras: no cites porcentajes, resultados de encuestas, recuentos de personas, firmas, adhesiones, "
    "importes de dinero ni fechas que no figuren en tu perfil, en tus memorias o en el texto base de la simulación. "
    "Si te piden una cifra que no tienes, di con claridad que no la tienes y cuenta solo lo que sí consta: lo que viste, "
    "dijiste o hiciste. «No tengo ese dato» más lo que sí consta es una respuesta completa. No sustituyas la cifra por una "
    "estimación, un «más o menos» ni un rango. Puedes decir lo que percibes con palabras («tengo la impresión de que…»), "
    "sin números y dejando claro que es una impresión tuya. Una cifra que solo aparece en una respuesta anterior de esta "
    "conversación tampoco cuenta."
)

# Entrevista suelta (chat con una persona, encuesta): el prefijo antecede a la pregunta que escribe quien usa la app
INTERVIEW_PROMPT_PREFIX = (
    "Basándote en tu perfil, todas tus memorias y acciones pasadas, "
    "responde directamente con texto en español sin invocar ninguna herramienta.\n"
    f"{REGLA_CIFRAS}\n\n"
    f"{REFERENCE_MEMORY_RULE}\n\n"
)

# Entrevista que lanza el agente de informes: varias preguntas en un solo mensaje, con formato fijo para poder separarlas
REPORT_INTERVIEW_PROMPT_PREFIX = (
    "Estás participando en una entrevista. Responde las siguientes preguntas "
    "usando tu personalidad, tus recuerdos y tus acciones pasadas, en texto plano.\n"
    "Instrucciones:\n"
    "1. Responde directamente en lenguaje natural, sin invocar ninguna herramienta.\n"
    "2. No devuelvas formato JSON ni llamadas a herramientas.\n"
    "3. No uses títulos Markdown (#, ##, ###).\n"
    "4. Responde cada pregunta por orden, comenzando cada respuesta con «Pregunta X:» (X = número de pregunta).\n"
    "5. Separa las respuestas con líneas en blanco.\n"
    "6. Da respuestas con contenido real, mínimo 2–3 oraciones por pregunta.\n"
    f"7. {REGLA_CIFRAS}\n\n"
    f"8. {REFERENCE_MEMORY_RULE}\n\n"
)


def optimize_interview_prompt(prompt: str) -> str:
    """Antepone el prefijo (sin herramientas, sin cifras inventadas) a la pregunta; no lo duplica si ya está."""
    if not prompt:
        return prompt
    if prompt.startswith(INTERVIEW_PROMPT_PREFIX):
        return prompt
    return f"{INTERVIEW_PROMPT_PREFIX}{prompt}"


def interview_notice() -> str:
    """Aviso fijo que acompaña a toda respuesta de entrevista (en el idioma de quien la pide)."""
    return t('api.interviewNotice')


def with_notice(result):
    """Copia del resultado de una entrevista con el aviso fijo; lo que no sea un dict se devuelve tal cual."""
    if not isinstance(result, dict):
        return result
    return {**result, "notice": interview_notice()}


def build_context_block(project_name: str = "", simulation_requirement: str = "", analysis_summary: str = "") -> str:
    """Contexto de la simulación para el mensaje de sistema del fallback (vacío si no hay proyecto ni hipótesis)."""
    if not (simulation_requirement or project_name):
        return ""
    lines = ["=== CONTEXTO DE LA SIMULACIÓN ==="]
    if project_name:
        lines.append(f"Proyecto/Producto: {project_name}")
    if simulation_requirement:
        lines.append(f"Hipótesis simulada: {simulation_requirement}")
    if analysis_summary:
        lines.append(f"Descripción: {analysis_summary[:500]}")
    lines.append(
        "\nIMPORTANTE: Responde SOLO con información coherente con el contexto "
        "anterior. No inventes datos sobre el producto, la marca ni sus características. "
        "Si no sabes algo con certeza, habla en términos generales o de tu propia experiencia."
    )
    lines.append("=================================\n")
    return "\n".join(lines) + "\n"


def build_interview_system_prompt(username: str, profession: str, bio: str, context_block: str = "", profile=None) -> str:
    """Mensaje de sistema con el que el modelo hace de la persona cuando ya no hay entorno de simulación."""
    if is_canonical(profile):
        return (f"{context_block}\n{render_memory(profile)}\n\n"
                "Responde en español y en primera persona, con opiniones explícitamente simuladas. "
                "Si no consta una experiencia o un dato, dilo.\n\n"
                f"{REFERENCE_MEMORY_RULE}\n{REGLA_CIFRAS}")
    if isinstance(profile, dict) and profile.get('profile_schema_version') is not None:
        raise ValueError('Versión de perfil incompatible; no se puede sustituir su memoria por una biografía libre')
    return (
        f"{context_block}"
        f"Eres {username}, {profession}.\n"
        f"Tu perfil: {bio[:600] if bio else 'Sin información adicional.'}\n\n"
        "Responde siempre en español, en primera persona, con autenticidad y en el tono "
        "propio de tu profesión e identidad. No uses prefijos ni introducciones: ve directo "
        "al grano como si fuera una conversación real.\n\n"
        f"{REGLA_CIFRAS}"
    )
