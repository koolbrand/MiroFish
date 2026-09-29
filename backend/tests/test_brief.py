"""Brief: revisión con Jev y entrevista, sin red."""

import io

import pytest

from app.config import Config
from app.services import brief_service
from tests.test_smoke import TOKEN, auth, client  # noqa: F401  (fixture)


class FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


def fake_jev(present_keys, audience_level=3.0):
    answers = {}
    for s in brief_service.SECTIONS:
        if "levels" in s:
            answers[s["key"]] = {"type": "score", "score": audience_level}
        else:
            answers[s["key"]] = {"type": "noul", "noul": 0.9 if s["key"] in present_keys else 0.1}
    return FakeResponse({"answers": answers})


@pytest.fixture
def jev(monkeypatch):
    monkeypatch.setattr(Config, "TYPESAFE_API_KEY", "test")
    calls = {}

    def install(present_keys, audience_level=3.0):
        def post(self, url, json=None):
            calls["payload"] = json
            return fake_jev(present_keys, audience_level)
        monkeypatch.setattr(brief_service.httpx.Client, "post", post)
        return calls
    return install


def test_check_marks_missing_required(jev):
    calls = jev({"competencia", "precio"}, audience_level=1.0)
    r = brief_service.check_brief("Una app a 49 $. Compite con Cozi.")
    assert r["available"] is True
    assert set(r["missing_required"]) == {"producto", "publico"}
    # el público va como score graduado, el resto como noul, todo en una sola petición
    q = calls["payload"]["questions"]
    assert q["publico"]["type"] == "score" and q["producto"]["type"] == "noul"


def test_check_without_key_is_unavailable(monkeypatch):
    monkeypatch.setattr(Config, "TYPESAFE_API_KEY", None)
    assert brief_service.check_brief("algo")["available"] is False


def test_check_endpoint_reads_uploaded_md(client, jev):  # noqa: F811
    jev({"producto", "competencia"}, audience_level=2.5)
    data = {"files": (io.BytesIO("# Brief\nUna app para familias.".encode()), "brief.md")}
    r = client.post("/api/brief/check", headers=auth(), data=data, content_type="multipart/form-data")
    assert r.status_code == 200
    body = r.get_json()["data"]
    assert body["available"] and body["missing_required"] == []


def test_interview_asks_about_first_missing(monkeypatch, jev):
    jev({"producto"}, audience_level=0.5)
    captured = {}

    def chat(self, messages, **kw):
        captured["user"] = messages[-1]["content"]
        return "¿Quién es exactamente tu cliente?"
    monkeypatch.setattr(brief_service.LLMClient, "__init__", lambda self: None)
    monkeypatch.setattr(brief_service.LLMClient, "chat", chat)
    r = brief_service.next_question("Lanzamiento", [{"question": "¿Qué lanzas?", "answer": "Una app"}])
    assert r["done"] is False and r["section"] == "publico"
    assert "quiénes son exactamente" in captured["user"]


def test_interview_done_when_everything_present(jev):
    jev({s["key"] for s in brief_service.SECTIONS}, audience_level=3.0)
    r = brief_service.next_question("Lanzamiento", [{"question": "q", "answer": "a"}])
    assert r["done"] is True
