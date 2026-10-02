"""¿De qué país es el público? Decide qué encuesta oficial se usa.

La evidencia lo pide por dos razones: (1) el modelo, por defecto, se parece al público de EE. UU. y de los países
occidentales (Durmus et al. 2023; AlKhamissi et al. 2024), y (2) en un preprint de 2026 con la European Social Survey,
el nombre del país aportaba casi toda la mejora (Wang 2026, arXiv 2609.16395). Es decir: acertar el PAÍS es lo que más
rinde; un ama de casa de EE. UU. no es una de España.

Cómo se decide, por orden:
 1. Lo que pide la persona en la interfaz (un país concreto) manda, si hay banco de ese país.
 2. «Automático»: el modelo lee el brief y el público y responde con un país de la lista de los que TIENEN banco, o
    ninguno. Si duda, ninguno: es mejor no anclar que anclar a la gente equivocada.
 3. Si hay un único banco y el texto no menciona otro país, no se adivina: también hace falta que el modelo lo confirme.
Sin país claro, o sin banco para ese país, el público se genera como siempre y la interfaz lo dice.
"""

import json
import re
from dataclasses import dataclass
from typing import Callable, List, Optional

from . import jev
from .fuentes import Fuente, disponibles, fuente_de_pais

PROMPT = """Decide de qué país es el PÚBLICO objetivo de este estudio (las personas cuya opinión se quiere simular).
No importa en qué país está la empresa, ni en qué idioma está escrito el texto: importa dónde vive el público.

Países posibles (los únicos para los que hay datos de encuestas reales):
{paises}

Devuelve SOLO un objeto JSON, sin texto alrededor:
{{"pais": "<código de la lista, o null>", "motivo": "<una frase>"}}

Reglas:
- Elige un código SOLO si el texto dice o implica con claridad que el público vive en ese país.
- Si el público es de otro país que no está en la lista, es de varios países o no se puede saber, devuelve null.
- No supongas el país por el idioma del texto ni por el nombre de la empresa.

Pregunta del estudio:
\"\"\"{pregunta}\"\"\"

Brief y contexto:
\"\"\"{contexto}\"\"\"
"""


@dataclass
class Deteccion:
    fuente: Optional[Fuente]
    motivo: str
    origen: str            # 'pedido' | 'automatico' | 'ninguno'

    @property
    def pais(self) -> Optional[str]:
        return self.fuente.pais if self.fuente else None


def _lista(fuentes: List[Fuente]) -> str:
    return "\n".join(f"- {f.pais}: {f.pais_nombre}" for f in fuentes)


def _extraer(texto: str) -> dict:
    m = re.search(r"\{.*\}", texto or "", flags=re.S)
    if not m:
        return {}
    try:
        d = json.loads(m.group(0))
        return d if isinstance(d, dict) else {}
    except json.JSONDecodeError:
        return {}


def _detectar_con_jev(pregunta: str, contexto: str, quedan: List[Fuente]) -> Optional[Deteccion]:
    """
    ¿De cuál de los países con banco es el público? Una pregunta de sí o no por país, todas en UNA petición a Jev (~1 s). Devuelve None
    si Jev no está, falla o no está seguro (entonces decide el modelo grande); «ninguno» solo si todas las respuestas son un no claro.
    """
    if not jev.disponible() or not ((pregunta or "").strip() or (contexto or "").strip()):
        return None
    preguntas = {f"pais::{f.pais}": jev.noul(
        f"¿El público cuya reacción se quiere simular vive en {f.pais_nombre}? Importa dónde vive ese público, no dónde está la empresa ni "
        "en qué idioma está escrito el texto. Si el público es de varios países o de todo el mundo, no.") for f in quedan}
    r = jev.preguntar({"pregunta_del_estudio": (pregunta or "").strip()[:1500], "brief": (contexto or "").strip()[:4000]}, preguntas)
    if not r:
        return None
    p = {f: float(r.get(f"pais::{f.pais}", {}).get("noul", 0)) for f in quedan}
    mejor = max(p, key=p.get)
    if p[mejor] >= 0.65 and all(v < 0.5 for f, v in p.items() if f is not mejor):
        return Deteccion(mejor, f"El público parece de {mejor.pais_nombre} (Jev, probabilidad {p[mejor]:.2f}).", "automatico")
    if all(v < 0.35 for v in p.values()):
        return Deteccion(None, "El público no parece de ninguno de los países con datos reales (Jev).", "ninguno")
    return None


def detectar(pedido: Optional[str], pregunta: str, contexto: str,
             llm: Optional[Callable[[str], str]]) -> Deteccion:
    """`pedido`: código ISO elegido por la persona, 'auto'/None = decidir según el texto."""
    quedan = disponibles()
    if not quedan:
        return Deteccion(None, "No hay ningún banco de datos reales en este servidor.", "ninguno")

    if pedido and str(pedido).lower() not in ("auto", "automatico", "automático"):
        f = fuente_de_pais(pedido)
        if f:
            return Deteccion(f, f"País elegido por la persona: {f.pais_nombre}.", "pedido")
        return Deteccion(None, f"No hay datos reales para el país pedido ({pedido}).", "ninguno")

    try:
        rapido = _detectar_con_jev(pregunta, contexto, quedan)
    except Exception:  # noqa: BLE001 — sin Jev se sigue con el modelo grande
        rapido = None
    if rapido is not None:
        return rapido
    if llm is None or not (pregunta or contexto):
        return Deteccion(None, "No hay texto para decidir el país.", "ninguno")
    try:
        crudo = _extraer(llm(PROMPT.format(paises=_lista(quedan), pregunta=(pregunta or "").strip()[:1500],
                                           contexto=(contexto or "").strip()[:4000])))
    except Exception:
        return Deteccion(None, "No se pudo decidir el país del público.", "ninguno")
    f = fuente_de_pais(crudo.get("pais")) if crudo.get("pais") else None
    motivo = str(crudo.get("motivo") or "").strip()[:240]
    if f:
        return Deteccion(f, motivo or f"El público parece de {f.pais_nombre}.", "automatico")
    return Deteccion(None, motivo or "El país del público no es claro o no tiene datos reales.", "ninguno")
