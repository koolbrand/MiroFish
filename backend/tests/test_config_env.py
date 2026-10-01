"""
Lectura tolerante de variables de entorno: una variable vacía (compose pasa `VAR=` cuando no se definió) o con un
typo no debe tumbar la app al importar `Config`.
"""

import os
import subprocess
import sys

import pytest

from app import config as cfg

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@pytest.mark.parametrize("raw, expected", [("7", 7), (" 7 ", 7), ("", 5), ("   ", 5), ("30s", 5), ("7.5", 5), ("0", 5), ("-3", 5)])
def test_env_int_falls_back_on_garbage(monkeypatch, raw, expected):
    monkeypatch.setenv("X_INT", raw)
    assert cfg.env_int("X_INT", 5, minimum=1) == expected


def test_env_int_unset_and_maximum(monkeypatch):
    monkeypatch.delenv("X_INT", raising=False)
    assert cfg.env_int("X_INT", 5) == 5
    monkeypatch.setenv("X_INT", "99")
    assert cfg.env_int("X_INT", 5, minimum=1, maximum=10) == 5


@pytest.mark.parametrize("raw, expected", [("2.5", 2.5), ("", 9.0), ("abc", 9.0), ("nan", 9.0), ("inf", 9.0), ("-1", 9.0)])
def test_env_float_falls_back_on_garbage(monkeypatch, raw, expected):
    monkeypatch.setenv("X_FLOAT", raw)
    assert cfg.env_float("X_FLOAT", 9.0, minimum=0) == expected


@pytest.mark.parametrize("raw, default, expected", [
    ("true", False, True), ("1", False, True), ("YES", False, True), ("on", False, True),
    ("false", True, False), ("0", True, False), ("No", True, False), ("off", True, False),
    ("", True, True), ("", False, False), ("quizás", True, True), ("quizás", False, False),
])
def test_env_bool(monkeypatch, raw, default, expected):
    monkeypatch.setenv("X_BOOL", raw)
    assert cfg.env_bool("X_BOOL", default) is expected


def test_env_str_empty_is_default(monkeypatch):
    monkeypatch.setenv("X_STR", "  ")
    assert cfg.env_str("X_STR", "por-defecto") == "por-defecto"
    monkeypatch.setenv("X_STR", " valor ")
    assert cfg.env_str("X_STR", "por-defecto") == "valor"


def _config_in_subprocess(env_overrides: dict):
    """Importa Config en un proceso limpio (no se puede recargar aquí: otros módulos guardan la clase)."""
    env = {k: v for k, v in os.environ.items() if not k.startswith(("MAX_", "LLM_", "WEB_RESEARCH", "SIMULATION_", "TRUSTED_"))}
    env.update(env_overrides)
    code = (
        "from app.config import Config as C;"
        "print(C.MAX_BODY_BYTES, C.MAX_CONCURRENT_SIMULATIONS, C.LLM_TIMEOUT_SECONDS, C.TRUSTED_PROXIES,"
        " C.WEB_RESEARCH_ENABLED, C.SIMULATION_MAX_ROUNDS, C.NEO4J_URI)"
    )
    return subprocess.run([sys.executable, "-c", code], cwd=BACKEND_DIR, env=env, capture_output=True, text=True, timeout=60)


def test_config_imports_with_empty_and_garbage_values():
    """Lo que antes tumbaba el arranque: valores vacíos y typos en variables numéricas y booleanas."""
    done = _config_in_subprocess({
        "MAX_BODY_BYTES": "", "MAX_CONCURRENT_SIMULATIONS": "dos", "LLM_TIMEOUT_SECONDS": "30s",
        "TRUSTED_PROXIES": "", "WEB_RESEARCH_ENABLED": "", "SIMULATION_MAX_ROUNDS": "5", "NEO4J_URI": "",
    })
    assert done.returncode == 0, done.stderr
    assert done.stdout.split() == ["1048576", "2", "240.0", "1", "True", "100", "bolt://neo4j:7687"]
    assert "MAX_CONCURRENT_SIMULATIONS" in done.stderr           # avisa de qué variable estaba mal
    assert "SIMULATION_MAX_ROUNDS" in done.stderr


def test_config_honours_valid_values():
    done = _config_in_subprocess({"MAX_CONCURRENT_SIMULATIONS": "3", "LLM_TIMEOUT_SECONDS": "90", "WEB_RESEARCH_ENABLED": "off"})
    assert done.returncode == 0, done.stderr
    parts = done.stdout.split()
    assert parts[1] == "3" and parts[2] == "90.0" and parts[4] == "False"
