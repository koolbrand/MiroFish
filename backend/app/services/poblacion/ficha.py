"""«Ficha de datos reales»: lo que se sabe de un encuestado, en texto, para el prompt y la memoria del agente."""

import re
from typing import TYPE_CHECKING, Dict, List, Optional

from .banco import Encuestado
from .vocabulario import ETIQUETAS, ETIQUETAS_VALOR

if TYPE_CHECKING:
    from .fuentes import Fuente

MAX_CHARS = 1800          # tope de la ficha entera
MAX_RESPUESTA = 160       # una respuesta larguísima no entra entera


def _valor(campo: str, v) -> str:
    return ETIQUETAS_VALOR.get(v, str(v)) if v is not None else ""


def lineas_sociodemografia(e: Encuestado, fuente: Optional["Fuente"] = None) -> List[str]:
    etiqueta_region = fuente.etiqueta_region if fuente else ETIQUETAS["region"]
    out = []
    if e.sexo:
        out.append(f"{ETIQUETAS['sexo']}: {e.sexo}")
    if e.edad:
        out.append(f"{ETIQUETAS['edad']}: {e.edad} años")
    if e.region:
        # Solo la región. La provincia queda en el banco pero no sale hacia el modelo: junto a edad, sexo, estudios
        # y respuestas sería un cuasi-identificador de más (minimización de datos).
        out.append(f"{etiqueta_region}: {e.region}")
    for campo in ("tamuni", "estudios", "sitlab", "estcivil"):
        v = getattr(e, campo)
        if v:
            out.append(f"{ETIQUETAS[campo]}: {_valor(campo, v)}")
    return out


def _recortar(texto: str, n: int) -> str:
    texto = " ".join(str(texto).split())
    return texto if len(texto) <= n else texto[: n - 1].rstrip() + "…"


# «Sara Aagesen», «José Manuel Albares»…: las encuestas preguntan si conoces a cada ministro o líder y lo guardan con el
# nombre propio como pregunta. Llenarían la ficha sin decir nada de la persona: van al final, con las políticas.
_NOMBRE_PROPIO = re.compile(r"^[A-ZÁÉÍÓÚÑ][\wáéíóúñü.\-]*(\s+(de|del|la|las|los|y|i)?\s*[A-ZÁÉÍÓÚÑ][\wáéíóúñü.\-]*){1,3}$")


def _es_nombre_propio(pregunta: str) -> bool:
    return bool(_NOMBRE_PROPIO.match((pregunta or "").strip()))


def respuestas_priorizadas(e: Encuestado) -> List[Dict]:
    """Primero las que dan color de vida cotidiana y valores; luego las políticas y las de personas con nombre propio."""
    def al_final(r: Dict) -> bool:
        return bool(r.get("politica")) or _es_nombre_propio(r.get("pregunta", ""))
    return [r for r in e.respuestas if not al_final(r)] + [r for r in e.respuestas if al_final(r)]


def construir_ficha(e: Encuestado, max_chars: int = MAX_CHARS, fuente: Optional["Fuente"] = None) -> str:
    partes = ["Datos sociodemográficos:"] + [f"- {l}" for l in lineas_sociodemografia(e, fuente)]
    cabecera = "\n".join(partes)
    resp_txt = ["Lo que respondió en la encuesta:"]
    usado = len(cabecera) + len(resp_txt[0]) + 2
    n = 0
    for r in respuestas_priorizadas(e):
        linea = f"- {_recortar(r['pregunta'], 140)} → {_recortar(r['respuesta'], MAX_RESPUESTA)}"
        if usado + len(linea) + 1 > max_chars:
            break
        resp_txt.append(linea)
        usado += len(linea) + 1
        n += 1
    return cabecera + ("\n" + "\n".join(resp_txt) if n else "")


def hechos_memoria(e: Encuestado, maximo: int = 12) -> List[str]:
    """Respuestas reales redactadas como hechos que el agente «recuerda» de sí mismo."""
    hechos = []
    for r in respuestas_priorizadas(e)[:maximo]:
        hechos.append(f"A la pregunta «{_recortar(r['pregunta'], 140)}» respondió: «{_recortar(r['respuesta'], MAX_RESPUESTA)}».")
    return hechos


def genero_oasis(e: Encuestado):
    return {"Hombre": "male", "Mujer": "female"}.get(e.sexo or "")
