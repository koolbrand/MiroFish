"""
Etiquetas legibles para los tipos de la ontología.

Los tipos (entidades, relaciones y atributos) llevan un identificador en inglés porque el motor lo exige
(`SmallBusinessOwner`, `WORKS_FOR`, `years_in_business`). Quien usa Simuloo no es técnico: lee «Dueño de
pequeño negocio», «trabaja para», «años en el negocio». Aquí se traducen SOLO para mostrar; el
identificador no cambia en ningún sitio.

Un diccionario compartido por todos los proyectos: cada nombre se traduce UNA vez por idioma (una llamada
pequeña al modelo para los que faltan) y se guarda en disco. Todo es de mejor esfuerzo: si el modelo falla,
la interfaz enseña el identificador "humanizado" en inglés y se reintenta más tarde.
"""

import json
import os
import re
import tempfile
import threading
from typing import Dict, Iterable, List, Optional

from ..config import Config
from ..utils.llm_client import LLMClient
from ..utils.logger import get_logger

logger = get_logger('mirofish.type_labels')

KINDS = ('entity', 'relation', 'attribute')
# 'en' no se traduce: los identificadores ya están en inglés (la interfaz solo los separa en palabras)
TARGET_LANGUAGES = {
    'es': 'neutral Spanish',
    'zh': 'Simplified Chinese',
}
NAME_RE = re.compile(r'^[A-Za-z][A-Za-z0-9_]{0,63}$')     # solo identificadores del motor: sin espacios ni acentos (eso ya es texto)
MAX_NAMES_PER_REQUEST = 80
MAX_LABEL_CHARS = 80

# Lo universal no necesita al modelo
SEED: Dict[str, Dict[str, Dict[str, str]]] = {
    'es': {'entity': {'Entity': 'Entidad', 'Person': 'Persona', 'Organization': 'Organización'}},
    'zh': {'entity': {'Entity': '实体', 'Person': '人物', 'Organization': '组织'}},
}

_lock = threading.Lock()
_cache: Optional[Dict[str, Dict[str, Dict[str, str]]]] = None


def _cache_path() -> str:
    return os.path.join(Config.UPLOAD_FOLDER, 'type_labels.json')


def _load() -> Dict[str, Dict[str, Dict[str, str]]]:
    global _cache
    if _cache is None:
        data = {}
        try:
            with open(_cache_path(), 'r', encoding='utf-8') as f:
                loaded = json.load(f)
            if isinstance(loaded, dict):
                data = loaded
        except (OSError, ValueError):
            pass
        _cache = data
    return _cache


def _save(cache: Dict) -> None:
    path = _cache_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path), suffix='.tmp')
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            json.dump(cache, f, ensure_ascii=False, indent=1, sort_keys=True)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def reset_memory_cache() -> None:
    """Para los tests: olvida lo cargado en memoria (el archivo no se toca)."""
    global _cache
    _cache = None


def clean_names(raw: object) -> List[str]:
    """Lista de identificadores válidos, sin repetir, en orden."""
    if not isinstance(raw, list):
        return []
    seen, out = set(), []
    for item in raw:
        if isinstance(item, str):
            name = item.strip()
            if NAME_RE.match(name) and name not in seen:
                seen.add(name)
                out.append(name)
    return out


def _known(cache: Dict, locale: str, kind: str, name: str) -> Optional[str]:
    return (cache.get(locale, {}).get(kind, {}).get(name)) or SEED.get(locale, {}).get(kind, {}).get(name)


def _clean_label(kind: str, locale: str, value: object) -> Optional[str]:
    if not isinstance(value, str):
        return None
    label = re.sub(r'\s+', ' ', value).strip().strip('"\'«»“”')
    if not label or len(label) > MAX_LABEL_CHARS or re.search(r'[<>{}\[\]\n\\]', label):
        return None
    if locale == 'es':
        # «Dueño de pequeño negocio» (tipos y nada más) · «trabaja para» · «años en el negocio»
        label = label[:1].upper() + label[1:] if kind == 'entity' else label[:1].lower() + label[1:]
    return label


def _prompt(locale: str, wanted: Dict[str, List[str]]) -> List[Dict[str, str]]:
    language = TARGET_LANGUAGES[locale]
    system = (
        f"You translate identifiers of a knowledge-graph ontology into {language}, for marketing and strategy "
        "professionals who are not technical. Answer ONLY with a JSON object of the form "
        '{"entity": {"<identifier>": "<label>"}, "relation": {...}, "attribute": {...}} containing exactly the '
        "identifiers you are given, under the same group.\n"
        "Rules:\n"
        "- entity: a short noun phrase for a kind of person, group or organization, singular "
        '("SmallBusinessOwner" → "Small business owner" in the target language).\n'
        '- relation: a lowercase verb phrase that reads naturally between two entities ("WORKS_FOR" → "works for", '
        '"COMPETES_WITH" → "competes with"), in the target language.\n'
        '- attribute: a short lowercase noun phrase ("years_in_business" → "years in business").\n'
        "- Translate the whole phrase. Only isolated loanwords that marketing professionals in that language already "
        "use in English stay as they are (influencer, blogger, startup, marketing, feed, ranking…): "
        '"StartupFounder" → "founder of a startup", never a half-English phrase. Do not translate brand or product names.\n'
        "- Never leave a label empty, never explain, never add keys."
    )
    user = json.dumps({k: v for k, v in wanted.items() if v}, ensure_ascii=False)
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def _translate(locale: str, wanted: Dict[str, List[str]], client: Optional[LLMClient] = None) -> Dict[str, Dict[str, str]]:
    """Una llamada al modelo para los nombres que faltan. Solo devuelve lo válido y pedido."""
    client = client or LLMClient()
    result = client.chat_json(messages=_prompt(locale, wanted), temperature=0.2, max_tokens=3000)
    out: Dict[str, Dict[str, str]] = {k: {} for k in KINDS}
    if not isinstance(result, dict):
        return out
    for kind in KINDS:
        group = result.get(kind)
        if not isinstance(group, dict):
            continue
        for name in wanted.get(kind, []):
            label = _clean_label(kind, locale, group.get(name))
            if label:
                out[kind][name] = label
    return out


def ontology_names(ontology: Optional[dict]) -> Dict[str, List[str]]:
    """Los identificadores de una ontología (tipos de entidad, de relación y sus atributos)."""
    ontology = ontology or {}
    entities = [e for e in ontology.get('entity_types') or [] if isinstance(e, dict)]
    edges = [e for e in ontology.get('edge_types') or [] if isinstance(e, dict)]
    attributes = [a.get('name') for item in entities + edges for a in (item.get('attributes') or []) if isinstance(a, dict)]
    return {
        'entity': clean_names([e.get('name') for e in entities]),
        'relation': clean_names([e.get('name') for e in edges]),
        'attribute': clean_names(attributes),
    }


def warm_async(ontology: Optional[dict], locale: str) -> None:
    """
    Recién generada la ontología, traduce sus nombres en segundo plano para que estén listos cuando la
    persona abra el paso 1 (la primera traducción tarda unos segundos). No bloquea ni hace fallar a nadie.
    """
    if locale not in TARGET_LANGUAGES:
        return
    names = ontology_names(ontology)
    if not any(names.values()):
        return
    threading.Thread(target=get_labels, args=(locale, names), name='type-labels-warm', daemon=True).start()


def get_labels(locale: str, names: Dict[str, Iterable[str]], client: Optional[LLMClient] = None) -> Dict[str, Dict[str, str]]:
    """
    Etiquetas para `names` ({'entity': [...], 'relation': [...], 'attribute': [...]}) en `locale`.
    Solo trae las que se conocen: lo que el modelo no pudo traducir no está en el resultado.
    """
    result: Dict[str, Dict[str, str]] = {k: {} for k in KINDS}
    if locale not in TARGET_LANGUAGES:
        return result
    wanted = {k: clean_names(list(names.get(k, []))) for k in KINDS}
    budget = MAX_NAMES_PER_REQUEST
    for kind in KINDS:
        wanted[kind] = wanted[kind][:budget]
        budget -= len(wanted[kind])

    with _lock:
        cache = _load()
        missing = {k: [n for n in wanted[k] if not _known(cache, locale, k, n)] for k in KINDS}

    translated: Dict[str, Dict[str, str]] = {k: {} for k in KINDS}
    if any(missing.values()):
        # Fuera del candado: una llamada lenta al modelo no debe bloquear las consultas ya resueltas
        try:
            translated = _translate(locale, missing, client)
        except Exception as exc:  # noqa: BLE001 — de mejor esfuerzo: la interfaz tiene su alternativa
            logger.warning(f"[tipos] No se pudo traducir a {locale}: {exc}")

    with _lock:
        cache = _load()
        added = 0
        for kind in KINDS:
            for name, label in translated[kind].items():
                cache.setdefault(locale, {}).setdefault(kind, {})[name] = label
                added += 1
        if added:
            try:
                _save(cache)
            except OSError as exc:
                logger.warning(f"[tipos] No se pudo guardar el diccionario: {exc}")
            logger.info(f"[tipos] {added} etiqueta(s) nuevas en {locale}")
        for kind in KINDS:
            for name in wanted[kind]:
                label = _known(cache, locale, kind, name)
                if label:
                    result[kind][name] = label
    return result
