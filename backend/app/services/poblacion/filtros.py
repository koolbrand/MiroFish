"""Traduce la descripción de un público (o de varios grupos) a filtros del banco, con vocabulario CERRADO.

El LLM solo propone; lo que devuelve se valida contra el vocabulario de la fuente y lo que no encaja se descarta.
Si el LLM falla, el resultado es «sin filtros» (toda la población adulta del país): nunca rompe la preparación.

ANTIESTEREOTIPO: un filtro demográfico solo se pone cuando la descripción lo DICE («jubilados», «madres»,
«universitarios», «de Galicia»). Nunca se deduce de una afición, un producto o un tópico («amante del café» no es una
edad ni un sexo; «joyería» no es «mujer de 25 a 44 años»). Deducirlo es justo cómo se cuela el cliché por la puerta de
atrás: la persona se eligiría ya con el sesgo que queremos evitar. Lo que la descripción no acota, lo decide el azar
ponderado de la encuesta real.
"""

import json
import re
from typing import Callable, Dict, List, Optional

from .vocabulario import CAMPOS_EDAD, campos_lista


def _regiones(fuente) -> tuple:
    return tuple(fuente.regiones) if fuente is not None else ()


def _esquema_txt(fuente) -> str:
    return "\n".join(f"- {c}: lista con valores de {list(v)}" for c, v in campos_lista(_regiones(fuente)).items())


def _nombres(fuente):
    if fuente is None:
        return "del país", "oficial"
    return fuente.pais_nombre, fuente.nombre


FUERA_DEL_LUGAR = "_fuera_del_lugar"      # marca interna: el grupo no es del lugar del alcance (la quita quien la consume)

REGLAS = """Reglas:
- Usa solo los valores listados, tal cual. Si la descripción no dice nada de un campo, NO lo incluyas.
- Pon un filtro SOLO si la descripción lo afirma o lo exige por definición («jubilados» → situación laboral «jubilado»;
  «madres» → sexo «Mujer»; «estudiantes universitarios» → estudiante y estudios universitarios; «del <nombre de una
  región de la lista>» → esa región). NO deduzcas edad, sexo, estudios ni ingresos de aficiones, productos, profesiones sueltas o tópicos.
- Un LUGAR nombrado (ciudad, comarca, región) sí es explícito: filtra por la región de la lista que lo contiene.
- Si el grupo no es del país de la encuesta o no se puede acotar, devuelve {{}} para ese grupo.
- Si hay un alcance de lugar y el grupo es de FUERA de ese lugar por definición (visitantes, turistas, peregrinos, asistentes que
  llegan de otros sitios), añade "fuera_del_lugar": true para que no se le aplique el lugar del alcance."""

PROMPT_UNO = """Eres un asistente que traduce la descripción de un público objetivo a filtros sobre una encuesta
de población adulta de {pais} ({fuente}). Devuelve SOLO un objeto JSON, sin texto alrededor.

Campos admitidos:
{schema}
- edad_min: entero (18 a 99)
- edad_max: entero (18 a 99)

""" + REGLAS + """

Descripción del público:
\"\"\"{descripcion}\"\"\"
"""

PROMPT_GRUPOS = """Eres un asistente que traduce la descripción de VARIOS grupos de un público a filtros sobre una
encuesta de población adulta de {pais} ({fuente}). Devuelve SOLO un objeto JSON {{"<clave>": {{filtros}}, ...}} con
EXACTAMENTE las claves que te doy, sin texto alrededor.

Campos admitidos en cada grupo:
{schema}
- edad_min: entero (18 a 99)
- edad_max: entero (18 a 99)

""" + REGLAS + """

Contexto general del público (aplica a todos; no lo repitas en cada grupo salvo que el grupo lo diga):
\"\"\"{general}\"\"\"
{alcance}

Grupos:
{grupos}
"""


def validar(crudo: Dict, fuente=None) -> Dict:
    """Se queda solo con lo que está en el vocabulario cerrado de la fuente."""
    limpio: Dict = {}
    if not isinstance(crudo, dict):
        return limpio
    for campo, validos in campos_lista(_regiones(fuente)).items():
        v = crudo.get(campo)
        if isinstance(v, str):
            v = [v]
        if isinstance(v, list):
            ok = [x for x in v if x in validos]
            if ok:
                limpio[campo] = ok
    for campo in CAMPOS_EDAD:
        v = crudo.get(campo)
        try:
            v = int(v)
        except (TypeError, ValueError):
            continue
        if 18 <= v <= 99:
            limpio[campo] = v
    if "edad_min" in limpio and "edad_max" in limpio and limpio["edad_min"] > limpio["edad_max"]:
        limpio.pop("edad_min")
        limpio.pop("edad_max")
    return limpio


def _extraer_json(texto: str) -> Dict:
    texto = (texto or "").strip()
    m = re.search(r"\{.*\}", texto, flags=re.S)
    if not m:
        return {}
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError:
        return {}


def traducir_publico(descripcion: str, llm: Optional[Callable[[str], str]], fuente=None) -> Dict:
    """`llm(prompt) -> str`. Devuelve filtros validados ({} si no hay LLM, falla o no se puede acotar)."""
    if not descripcion or not descripcion.strip() or llm is None:
        return {}
    pais, nombre = _nombres(fuente)
    try:
        prompt = PROMPT_UNO.format(pais=pais, fuente=nombre, schema=_esquema_txt(fuente),
                                   descripcion=descripcion.strip()[:3000])
        return validar(_extraer_json(llm(prompt)), fuente)
    except Exception:
        return {}


def nota_de_alcance(alcance) -> str:
    """Qué debe saber el traductor de filtros sobre el ALCANCE: el lugar lo pone el alcance, no cada grupo."""
    if alcance is None:
        return ""
    if getattr(alcance, "acota_por_lugar", False):
        return (f"Alcance de la simulación: {alcance.descripcion()}. Ese lugar ya acota a TODOS los grupos; no lo repitas: "
                "filtra por región solo si el grupo se define por OTRO lugar; los visitantes o turistas de fuera llevan \"fuera_del_lugar\": true.\n")
    if getattr(alcance, "nivel", "") in ("nacional", "multinacional", "mundial"):
        return ("Alcance de la simulación: NACIONAL o mayor. La gente es de todo el país: NO filtres por región ni por tamaño de "
                "municipio salvo que el nombre o la descripción del propio grupo se defina por un lugar (aunque el brief cite una "
                "ciudad como sede o como sitio de un evento).\n")
    return ""


def traducir_grupos(grupos: List[Dict], general: str, llm: Optional[Callable[[str], str]], fuente=None,
                    alcance=None) -> Dict[str, Dict]:
    """
    Filtros de varios grupos en UNA sola llamada. `grupos` = [{"clave": "g0", "nombre": ..., "descripcion": ...}].
    Devuelve {clave: filtros validados}; un grupo que el modelo no devuelve, o devuelve mal, queda en {} (sin filtros).
    """
    vacio = {g["clave"]: {} for g in grupos}
    if not grupos or llm is None:
        return vacio
    pais, nombre = _nombres(fuente)
    lista = "\n".join(
        f'- clave "{g["clave"]}": {g.get("nombre", "")}. {" ".join(str(g.get("descripcion", "")).split())[:500]}'
        for g in grupos[:40]
    )
    try:
        prompt = PROMPT_GRUPOS.format(pais=pais, fuente=nombre, schema=_esquema_txt(fuente),
                                      general=(general or "").strip()[:2000] or "(sin contexto general)", grupos=lista,
                                      alcance=nota_de_alcance(alcance))
        crudo = _extraer_json(llm(prompt))
    except Exception:
        return vacio
    if not isinstance(crudo, dict):
        return vacio
    resultado = {}
    for g in grupos:
        bruto = crudo.get(g["clave"])
        f = validar(bruto, fuente)
        if isinstance(bruto, dict) and bruto.get("fuera_del_lugar") is True:
            f[FUERA_DEL_LUGAR] = True
        resultado[g["clave"]] = f
    return resultado
