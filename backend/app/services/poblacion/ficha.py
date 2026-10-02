"""«Ficha de datos reales»: lo que se sabe de un encuestado, en texto, para el prompt y la memoria del agente."""

import re
import unicodedata
from typing import TYPE_CHECKING, Dict, List, Optional

from .banco import Encuestado
from .vocabulario import ETIQUETAS, ETIQUETAS_VALOR

if TYPE_CHECKING:
    from .fuentes import Fuente

MAX_CHARS = 1800          # tope de la ficha entera
MAX_RESPUESTA = 160       # una respuesta larguísima no entra entera
MAX_AL_FINAL = 4          # como mucho cuatro respuestas políticas o ambiguas: una persona no es su voto
MAX_OTROS = 3             # con preguntas relevantes elegidas para el tema, solo tres de las demás (el resto, fuera)


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


def _sin_enunciado(pregunta: str) -> bool:
    """«La bandera», «China», «Al flamenco»: los elementos de una batería se guardan sin la pregunta que los introduce,
    así que la respuesta («Mucho») no se entiende sola. Cuatro palabras o menos = ambiguo: va al final."""
    return len((pregunta or "").split()) <= 3


_VACIAS = {"grado", "valoracion", "opinion", "posicion", "posicionamiento", "respecto", "sobre", "persona", "personas",
           "entrevistada", "importancia", "necesidad", "frecuencia", "conocimiento", "existencia", "situacion", "actual"}


def _raices(texto: str) -> set:
    """Raíces de seis letras de las palabras con contenido: «preocupación» y «preocupado» comparten «preocu»."""
    plano = "".join(c for c in unicodedata.normalize("NFD", (texto or "").lower()) if unicodedata.category(c) != "Mn")
    return {w[:6] for w in re.findall(r"[a-z]{5,}", plano) if w not in _VACIAS}


def respuestas_priorizadas(e: Encuestado, tema: str = "", max_al_final: int = MAX_AL_FINAL,
                           relevantes: Optional[List[str]] = None) -> List[Dict]:
    """
    Qué entra en la ficha, por este orden: (0) las preguntas que un modelo eligió como relevantes para el tema (si las
    hay; ver `poblacion.preguntas_relevantes`); (1) lo que tiene que ver con el TEMA de la simulación; (2) el resto de lo que
    da vida cotidiana y valores; (3) como mucho `max_al_final` respuestas políticas, de personas con nombre propio o
    sin enunciado. Una encuesta de actualidad pregunta por incendios, fronteras o ministros: si todo eso entra, la
    persona acaba hablando de lo que preguntó el barómetro en vez de reaccionar al brief.
    """
    def al_final(r: Dict) -> bool:
        q = r.get("pregunta", "")
        return bool(r.get("politica")) or _es_nombre_propio(q) or _sin_enunciado(q)

    raices_tema = _raices(tema)

    def afinidad(r: Dict) -> int:
        return len(raices_tema & _raices(r.get("pregunta", ""))) if raices_tema else 0

    buenas = [r for r in e.respuestas if not al_final(r)]
    finales = [r for r in e.respuestas if al_final(r)]
    if raices_tema:                                   # sorted es estable: sin afinidad se conserva el orden del estudio
        buenas = sorted(buenas, key=lambda r: -afinidad(r))
        finales = sorted(finales, key=lambda r: -afinidad(r))
    resto = buenas + finales[:max_al_final]
    if not relevantes:
        return resto
    orden = {q: i for i, q in enumerate(relevantes)}
    primeras = sorted((r for r in e.respuestas if r.get("pregunta") in orden), key=lambda r: orden[r["pregunta"]])
    # Quien no contestó las preguntas relevantes (cada estudio trae las suyas) no debe quedarse con la ficha llena de lo que
    # preguntó el barómetro ese mes: de las demás entran pocas
    return primeras + [r for r in resto if r.get("pregunta") not in orden][:MAX_OTROS]


def construir_ficha(e: Encuestado, max_chars: int = MAX_CHARS, fuente: Optional["Fuente"] = None, tema: str = "",
                    relevantes: Optional[List[str]] = None) -> str:
    partes = ["Datos sociodemográficos:"] + [f"- {l}" for l in lineas_sociodemografia(e, fuente)]
    cabecera = "\n".join(partes)
    resp_txt = ["Lo que respondió en la encuesta:"]
    usado = len(cabecera) + len(resp_txt[0]) + 2
    n = 0
    for r in respuestas_priorizadas(e, tema, relevantes=relevantes):
        linea = f"- {_recortar(r['pregunta'], 140)} → {_recortar(r['respuesta'], MAX_RESPUESTA)}"
        if usado + len(linea) + 1 > max_chars:
            break
        resp_txt.append(linea)
        usado += len(linea) + 1
        n += 1
    return cabecera + ("\n" + "\n".join(resp_txt) if n else "")


def hechos_memoria(e: Encuestado, maximo: int = 12, tema: str = "", relevantes: Optional[List[str]] = None) -> List[str]:
    """Respuestas reales redactadas como hechos que el agente «recuerda» de sí mismo."""
    hechos = []
    for r in respuestas_priorizadas(e, tema, relevantes=relevantes)[:maximo]:
        hechos.append(f"A la pregunta «{_recortar(r['pregunta'], 140)}» respondió: «{_recortar(r['respuesta'], MAX_RESPUESTA)}».")
    return hechos


def genero_oasis(e: Encuestado):
    return {"Hombre": "male", "Mujer": "female"}.get(e.sexo or "")
