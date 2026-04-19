import json
import os
import re
import threading
from flask import request, has_request_context

_thread_local = threading.local()

_locales_dir = os.path.join(os.path.dirname(__file__), '..', '..', '..', 'locales')

# Load language registry
with open(os.path.join(_locales_dir, 'languages.json'), 'r', encoding='utf-8') as f:
    _languages = json.load(f)

# Load translation files
_translations = {}
for filename in os.listdir(_locales_dir):
    if filename.endswith('.json') and filename != 'languages.json':
        locale_name = filename[:-5]
        with open(os.path.join(_locales_dir, filename), 'r', encoding='utf-8') as f:
            _translations[locale_name] = json.load(f)


def set_locale(locale: str):
    """Set locale for current thread. Call at the start of background threads."""
    _thread_local.locale = locale


def get_locale() -> str:
    if has_request_context():
        raw = request.headers.get('Accept-Language', 'es')
        return raw if raw in _translations else 'es'
    return getattr(_thread_local, 'locale', 'es')


def t(key: str, **kwargs) -> str:
    locale = get_locale()
    messages = _translations.get(locale, _translations.get('zh', {}))

    value = messages
    for part in key.split('.'):
        if isinstance(value, dict):
            value = value.get(part)
        else:
            value = None
            break

    if value is None:
        value = _translations.get('zh', {})
        for part in key.split('.'):
            if isinstance(value, dict):
                value = value.get(part)
            else:
                value = None
                break

    if value is None:
        return key

    if kwargs:
        for k, v in kwargs.items():
            value = value.replace(f'{{{k}}}', str(v))

    return value


def get_language_instruction() -> str:
    locale = get_locale()
    lang_config = _languages.get(locale, _languages.get('zh', {}))
    return lang_config.get('llmInstruction', 'Por favor, responde en español.')


def get_language_name(locale: str = None) -> str:
    """Human-readable name of a locale, used inside LLM prompts."""
    locale = locale or get_locale()
    lang_config = _languages.get(locale, {})
    return lang_config.get('name') or lang_config.get('label') or locale


# ── Foreign-script detection ───────────────────────────────────────────
# CJK unified ideographs (and the common extension A range) — this is the
# exact character set that leaks into Spanish/English reports when an LLM
# falls back to Chinese defaults.
_CJK_RE = re.compile(r'[\u4e00-\u9fff\u3400-\u4dbf]')


def count_cjk_chars(text: str) -> int:
    if not text:
        return 0
    return len(_CJK_RE.findall(text))


def has_foreign_script(text: str, target_locale: str = None) -> bool:
    """
    Detect script that shouldn't appear in ``target_locale``.

    For zh the check is a no-op (Chinese script is expected). For every
    other locale we look for CJK characters, which is the most common
    contamination source in this project (default LLM fallback language).
    """
    if not text:
        return False
    locale = target_locale or get_locale()
    if locale == 'zh':
        return False
    return _CJK_RE.search(text) is not None


def cjk_ratio(text: str) -> float:
    """Fraction of characters in ``text`` that are CJK ideographs (0-1)."""
    if not text:
        return 0.0
    total = len(text)
    if total == 0:
        return 0.0
    return count_cjk_chars(text) / total
