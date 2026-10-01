"""
Fallos pasajeros de Neo4j y plazos de las llamadas al modelo.
"""

import pytest
from neo4j.exceptions import ServiceUnavailable, SessionExpired, TransientError

from app.config import Config
from app.utils import zep_paging
from app.utils.llm_client import LLMClient


@pytest.fixture(autouse=True)
def no_waiting(monkeypatch):
    monkeypatch.setattr(zep_paging.time, "sleep", lambda s: None)


@pytest.mark.parametrize("error", [ServiceUnavailable("reiniciando"), SessionExpired("sesión caducada"),
                                   TransientError("líder cambiando"), ConnectionError("x"), TimeoutError("x")])
def test_transient_neo4j_errors_are_retried(error):
    calls = {"n": 0}

    def api(**kwargs):
        calls["n"] += 1
        if calls["n"] < 3:
            raise error
        return ["ok"]

    assert zep_paging._fetch_page_with_retry(api) == ["ok"]
    assert calls["n"] == 3


def test_a_permanent_error_is_not_retried():
    calls = {"n": 0}

    def api(**kwargs):
        calls["n"] += 1
        raise ValueError("consulta mal formada")

    with pytest.raises(ValueError):
        zep_paging._fetch_page_with_retry(api)
    assert calls["n"] == 1


def test_the_error_is_raised_after_the_last_attempt():
    def api(**kwargs):
        raise ServiceUnavailable("sigue caído")

    with pytest.raises(ServiceUnavailable):
        zep_paging._fetch_page_with_retry(api, max_retries=3)


def test_the_model_client_has_a_deadline_and_a_bounded_retry_budget(monkeypatch):
    monkeypatch.setattr(Config, "LLM_API_KEY", "clave-de-prueba")
    client = LLMClient()
    assert client.client.timeout == Config.LLM_TIMEOUT_SECONDS <= 300
    assert client.client.max_retries == Config.LLM_MAX_RETRIES <= 3
