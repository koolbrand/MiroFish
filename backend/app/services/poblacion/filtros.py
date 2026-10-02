"""Traduce la descripción del público de un brief a filtros del banco, con vocabulario CERRADO.

El LLM solo propone; lo que devuelve se valida contra el vocabulario y lo que no encaja se descarta.
Si el LLM falla, el resultado es «sin filtros» (toda la población adulta): nunca rompe la preparación.
"""

import json
import re
from typing import Callable, Dict, Optional

from .vocabulario import CAMPOS_EDAD, CAMPOS_LISTA

_SCHEMA_TXT = "\n".join(f"- {c}: lista con valores de {list(v)}" for c, v in CAMPOS_LISTA.items())

PROMPT = """Eres un asistente que traduce la descripción de un público objetivo a filtros sobre una encuesta
de población adulta española (CIS). Devuelve SOLO un objeto JSON, sin texto alrededor.

Campos admitidos (si la descripción no dice nada de un campo, NO lo incluyas):
{schema}
- edad_min: entero (18 a 99)
- edad_max: entero (18 a 99)

Reglas: usa solo los valores listados, tal cual. No inventes restricciones que la descripción no sugiera.
Si el público no es de España o no se puede acotar, devuelve {{}}.

Descripción del público:
\"\"\"{descripcion}\"\"\"
"""


def validar(crudo: Dict) -> Dict:
    """Se queda solo con lo que está en el vocabulario cerrado."""
    limpio: Dict = {}
    if not isinstance(crudo, dict):
        return limpio
    for campo, validos in CAMPOS_LISTA.items():
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


def traducir_publico(descripcion: str, llm: Optional[Callable[[str], str]]) -> Dict:
    """`llm(prompt) -> str`. Devuelve filtros validados ({} si no hay LLM, falla o no se puede acotar)."""
    if not descripcion or not descripcion.strip() or llm is None:
        return {}
    try:
        return validar(_extraer_json(llm(PROMPT.format(schema=_SCHEMA_TXT, descripcion=descripcion.strip()[:3000]))))
    except Exception:
        return {}
