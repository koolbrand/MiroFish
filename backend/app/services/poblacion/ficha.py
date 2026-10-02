"""«Ficha de datos reales»: lo que se sabe de un encuestado, en texto, para el prompt y la memoria del agente."""

from typing import Dict, List

from .banco import Encuestado
from .vocabulario import ETIQUETAS, ETIQUETAS_VALOR

MAX_CHARS = 1800          # tope de la ficha entera
MAX_RESPUESTA = 160       # una respuesta larguísima no entra entera


def _valor(campo: str, v) -> str:
    return ETIQUETAS_VALOR.get(v, str(v)) if v is not None else ""


def lineas_sociodemografia(e: Encuestado) -> List[str]:
    out = []
    if e.sexo:
        out.append(f"{ETIQUETAS['sexo']}: {e.sexo}")
    if e.edad:
        out.append(f"{ETIQUETAS['edad']}: {e.edad} años")
    if e.ccaa:
        prov = f" (provincia de {e.provincia})" if e.provincia else ""
        out.append(f"{ETIQUETAS['ccaa']}: {e.ccaa}{prov}")
    for campo in ("tamuni", "estudios", "sitlab", "estcivil"):
        v = getattr(e, campo)
        if v:
            out.append(f"{ETIQUETAS[campo]}: {_valor(campo, v)}")
    return out


def _recortar(texto: str, n: int) -> str:
    texto = " ".join(str(texto).split())
    return texto if len(texto) <= n else texto[: n - 1].rstrip() + "…"


def respuestas_priorizadas(e: Encuestado) -> List[Dict]:
    """Primero las no políticas (dan color de vida cotidiana y valores); luego las políticas."""
    no_pol = [r for r in e.respuestas if not r.get("politica")]
    pol = [r for r in e.respuestas if r.get("politica")]
    return no_pol + pol


def construir_ficha(e: Encuestado, max_chars: int = MAX_CHARS) -> str:
    partes = ["Datos sociodemográficos:"] + [f"- {l}" for l in lineas_sociodemografia(e)]
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
