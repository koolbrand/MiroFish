"""PDF del informe: parseo del Markdown, seguridad del HTML y de las URL, y la ruta de descarga.
La parte que maqueta necesita WeasyPrint con pango en el sistema (en la imagen de Docker está; en un Mac,
`DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib`): si no carga, esos tests se saltan.
"""
import pytest

from app import create_app
from app.config import Config
from app.services import report_pdf

TOKEN = "test-token-pdf"
SAMPLE = (
    "# Predicción: cómo reaccionará el público al lanzamiento\n\n"
    "> Resumen en una frase de lo que anticipa la simulación.\n\n---\n\n"
    "## Veredicto\n\nLa mayoría duda. **Dato clave** y una cita:\n\n"
    "> \"Si no puedo probarlo gratis, no lo compro.\"\n\n"
    "| Grupo | A favor |\n|---|---|\n| Habituales | 58 % |\n\n"
    "## Qué frena\n\n- El precio\n- La privacidad\n"
)


def _weasyprint_or_skip():
    try:
        import weasyprint  # noqa: F401
    except (ImportError, OSError) as exc:
        pytest.skip(f"WeasyPrint no disponible: {exc}")


def test_split_report_separates_title_summary_and_body():
    title, summary, body = report_pdf.split_report(SAMPLE)
    assert title == "Predicción: cómo reaccionará el público al lanzamiento"
    assert summary == "Resumen en una frase de lo que anticipa la simulación."
    assert body.startswith("## Veredicto") and "Resumen en una frase" not in body


def test_split_report_without_header_keeps_everything_as_body():
    assert report_pdf.split_report("Solo texto") == ("", "", "Solo texto")


def test_markdown_escapes_raw_html():
    out = report_pdf.markdown_to_html('<script>alert(1)</script> y <img src="http://127.0.0.1:9/x.png"> y <b onclick="x()">negrita</b>')
    assert "<script" not in out and "<img" not in out and "<b " not in out
    assert "&lt;script&gt;" in out


def test_markdown_images_become_alt_text_and_links_are_filtered():
    out = report_pdf.markdown_to_html("![gráfico](http://evil.test/p.png) [ok](https://example.com/x) [mal](javascript:alert(1))")
    assert "<img" not in out and "gráfico" in out
    assert 'href="https://example.com/x"' in out
    assert "javascript:" not in out


def test_markdown_renders_tables_and_keeps_entities():
    out = report_pdf.markdown_to_html("| A | B |\n|---|---|\n| 1&nbsp;€ | 2 |\n")
    assert "<table>" in out and "&nbsp;" in out and "&amp;nbsp;" not in out


def test_fetcher_blocks_network_and_files_outside_fonts():
    _weasyprint_or_skip()
    fetcher = report_pdf._make_fetcher()
    for url in ("http://127.0.0.1:9/x.png", "https://example.com/a.css", "file:///etc/passwd",
                (report_pdf.FONT_DIR.parent / "services" / "report_pdf.py").as_uri()):
        with pytest.raises(Exception):
            fetcher.fetch(url)
    font = next(report_pdf.FONT_DIR.glob("*.ttf"))
    assert fetcher.fetch(font.as_uri()) is not None


def test_render_pdf_has_cover_pages_and_embedded_fonts(tmp_path):
    _weasyprint_or_skip()
    pdf = report_pdf.render_report_pdf(markdown_text=SAMPLE * 3, question="¿Cómo reaccionará el público?",
                                       meta={"people": 23, "rounds": 10, "actions": 97}, locale="es",
                                       completed_at="2026-09-29T17:07:47")
    assert pdf.startswith(b"%PDF") and len(pdf) > 10_000
    import fitz
    doc = fitz.open(stream=pdf, filetype="pdf")
    first = doc[0].get_text()
    assert "Predicción" in first and "23" in first and "PERSONAS SIMULADAS" in first.upper()
    assert "29 de septiembre de 2026" in first.lower()   # la fecha va en mayúsculas por CSS
    assert "Página 1 de" in first
    fonts = {f[3] for page in doc for f in page.get_fonts()}
    assert any("IT-800" in f for f in fonts) and any("JBM" in f for f in fonts)   # las fuentes de la marca van incrustadas


@pytest.mark.parametrize("locale", ["en", "zh"])
def test_render_pdf_other_locales(locale):
    _weasyprint_or_skip()
    pdf = report_pdf.render_report_pdf(markdown_text=SAMPLE, question="Q", meta={"people": 5}, locale=locale)
    assert pdf.startswith(b"%PDF")


# ---------- ruta de descarga ----------

class FakeReport:
    from app.services.report_agent import ReportStatus
    report_id = "report_pdftest00001"
    simulation_id = "sim_pdftest00001"
    simulation_requirement = "¿Cómo reaccionará el público?"
    markdown_content = SAMPLE
    created_at = "2026-09-29T16:56:22"
    completed_at = "2026-09-29T17:07:47"
    status = ReportStatus.COMPLETED


@pytest.fixture()
def client(monkeypatch):
    monkeypatch.setattr(Config, "API_AUTH_REQUIRED", True)
    monkeypatch.setattr(Config, "API_AUTH_TOKEN", TOKEN)
    monkeypatch.setattr(Config, "POCKETBASE_URL", "")
    app = create_app()
    app.config["TESTING"] = True
    app.config["RATELIMIT_ENABLED"] = False
    return app.test_client()


def _auth():
    return {"Authorization": f"Bearer {TOKEN}"}


def test_download_pdf_requires_auth(client):
    assert client.get("/api/report/report_pdftest00001/download?format=pdf").status_code == 401


def test_download_pdf_ok(client, monkeypatch):
    _weasyprint_or_skip()
    from app.api import report as api
    monkeypatch.setattr(api.ReportManager, "get_report", staticmethod(lambda _id: FakeReport()))
    r = client.get("/api/report/report_pdftest00001/download?format=pdf", headers=_auth())
    assert r.status_code == 200 and r.mimetype == "application/pdf"
    assert r.data.startswith(b"%PDF")
    assert ".pdf" in r.headers["Content-Disposition"]


def test_download_pdf_of_unfinished_report_is_409(client, monkeypatch):
    from app.api import report as api
    unfinished = FakeReport()
    unfinished.status = FakeReport.ReportStatus.GENERATING
    monkeypatch.setattr(api.ReportManager, "get_report", staticmethod(lambda _id: unfinished))
    assert client.get("/api/report/report_pdftest00001/download?format=pdf", headers=_auth()).status_code == 409


def test_download_markdown_still_default(client, monkeypatch):
    from app.api import report as api
    monkeypatch.setattr(api.ReportManager, "get_report", staticmethod(lambda _id: FakeReport()))
    monkeypatch.setattr(api.ReportManager, "_get_report_markdown_path", staticmethod(lambda _id: "/no/existe.md"))
    r = client.get("/api/report/report_pdftest00001/download", headers=_auth())
    assert r.status_code == 200 and r.mimetype == "text/markdown"
