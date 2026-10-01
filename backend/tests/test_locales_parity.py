"""
Los tres idiomas (es, en, zh) tienen las mismas claves y las mismas variables `{nombre}` en cada frase.

Una clave que falta en un idioma enseña a esa persona la clave en crudo (`api.imageUnreadable`) o, peor, el
texto de otro idioma; una variable que falta (`{max}`) deja una frase sin su número. Ninguna de las dos se ve en los
tests de lógica: hay que compararlos.
"""

import json
import os
import re

import pytest

LOCALES_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "locales")
LANGS = ("es", "en", "zh")
PLACEHOLDER = re.compile(r"\{([A-Za-z_][A-Za-z0-9_]*)\}")


def flatten(node, prefix=""):
    out = {}
    if isinstance(node, dict):
        for key, value in node.items():
            out.update(flatten(value, f"{prefix}.{key}" if prefix else key))
    elif isinstance(node, list):
        for i, value in enumerate(node):
            out.update(flatten(value, f"{prefix}[{i}]"))
    else:
        out[prefix] = node
    return out


@pytest.fixture(scope="module")
def catalogs():
    data = {}
    for lang in LANGS:
        with open(os.path.join(LOCALES_DIR, f"{lang}.json"), encoding="utf-8") as f:
            data[lang] = flatten(json.load(f))
    return data


def test_all_languages_have_the_same_keys(catalogs):
    reference = set(catalogs["es"])
    for lang in LANGS[1:]:
        keys = set(catalogs[lang])
        assert not (reference - keys), f"Faltan en {lang}: {sorted(reference - keys)[:10]}"
        assert not (keys - reference), f"Sobran en {lang}: {sorted(keys - reference)[:10]}"


def test_no_translation_is_empty(catalogs):
    for lang in LANGS:
        empty = [k for k, v in catalogs[lang].items() if isinstance(v, str) and not v.strip()]
        assert not empty, f"Frases vacías en {lang}: {empty[:10]}"


def test_placeholders_match_across_languages(catalogs):
    problems = []
    for key, text in catalogs["es"].items():
        if not isinstance(text, str):
            continue
        expected = set(PLACEHOLDER.findall(text))
        for lang in LANGS[1:]:
            other = catalogs[lang].get(key)
            if isinstance(other, str) and set(PLACEHOLDER.findall(other)) != expected:
                problems.append(f"{key} [{lang}]: {sorted(set(PLACEHOLDER.findall(other)))} en vez de {sorted(expected)}")
    assert not problems, "Variables distintas entre idiomas:\n" + "\n".join(problems[:15])
