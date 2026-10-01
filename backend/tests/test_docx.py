"""
Documentos de Word: lectura de .docx hechos por programas reales, defensas contra documentos hostiles, subida de punta
a punta y el endpoint del borrador (Word y PDF).
"""

import io
import os
import time
import zipfile

import pytest

from app.api import brief as brief_api
from app.config import Config
from app.models.project import ProjectManager
from app.utils import docx_io
from app.utils.docx_io import DocxError, build_docx, extract_docx_text

from test_cost_limits import auth, client, upload  # noqa: F401  (fixtures y ayudas de las pruebas de subida)
from test_pipeline import ontology, storage  # noqa: F401

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")
W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def fixture(name):
    return os.path.join(FIXTURES, name)


def make_docx(body="", parts=None, document=None, content_types=True):
    """Un .docx mínimo hecho a mano (para casos que ningún programa genera: cambios, controles, hostiles)."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        if content_types:
            z.writestr("[Content_Types].xml", '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"/>')
        z.writestr("word/document.xml", document or f'<?xml version="1.0"?><w:document xmlns:w="{W}"><w:body>{body}</w:body></w:document>')
        for name, data in (parts or {}).items():
            z.writestr(name, data)
    return buf.getvalue()


def para(text, style=None):
    ppr = f'<w:pPr><w:pStyle w:val="{style}"/></w:pPr>' if style else ""
    return f"<w:p>{ppr}<w:r><w:t>{text}</w:t></w:r></w:p>"


def read(data):
    return extract_docx_text(io.BytesIO(data))


# ---------- ficheros hechos por programas reales ----------

def test_libreoffice_docx_keeps_headings_lists_and_tables():
    text = extract_docx_text(fixture("libreoffice-brief.docx"))
    lines = text.splitlines()
    assert "# Brief: lanzamiento de Café del Norte" in lines
    assert "## Quién es el público" in lines
    assert "- Estudiantes de la Universidade de Vigo" in lines and "- Vecinos de toda la vida" in lines
    assert "Producto | Antes | Después" in lines and "Café con leche | 1,70 € | 1,90 €" in lines
    assert "Ñandú, açaí, ¿qué opinas? 咖啡价格上调 — «comillas» y “tipográficas”." in lines


def test_apple_textutil_docx_keeps_all_the_text():
    text = extract_docx_text(fixture("textutil-brief.docx"))
    for expected in ("Brief: lanzamiento de Café del Norte", "Estudiantes de la Universidade de Vigo", "Anunciar el cambio",
                     "Café con leche", "1,90 €", "咖啡价格上调", "«comillas»"):
        assert expected in text


def test_python_docx_file_with_word_list_styles():
    text = extract_docx_text(fixture("python-docx-brief.docx"))
    assert "# Título de prueba" in text and "- Elemento" in text      # el estilo «List Bullet» cuenta como lista
    assert "A | B" in text and "1 | 2" in text and "咖啡" in text


# ---------- el escritor ----------

def test_written_docx_round_trips_and_joins_wrapped_lines():
    md = ("# Brief: algo\n\n> Nota con dos\n> líneas.\n>\n> Segundo párrafo de la cita.\n\n## Sección\n\n"
          "Una frase que el editor\npartió en dos líneas.\n\n- Primera viñeta\n  que sigue aquí\n- Segunda\n\n1. Uno\n2. Dos\n\n**Negrita** y *cursiva*.\n")
    lines = read(build_docx(md)).splitlines()
    assert lines[0] == "# Brief: algo"
    assert "Nota con dos líneas." in lines and "Segundo párrafo de la cita." in lines
    assert "Una frase que el editor partió en dos líneas." in lines
    assert any(l.startswith("•") and "Primera viñeta que sigue aquí" in l for l in lines)
    assert any(l.replace("\t", " ").startswith("1. Uno") or l.startswith("1.") for l in lines)
    assert "Negrita y cursiva." in lines


def test_writer_escapes_xml_and_control_characters():
    data = build_docx("# Título <b>&\n\nTexto con <script>alert(1)</script> & \x00\x08 raro")
    text = read(data)
    assert "<script>alert(1)</script>" in text and "&" in text and "\x00" not in text


def test_published_template_matches_its_source():
    """Si se toca la plantilla .md hay que regenerar el .docx (backend/scripts/generar_plantilla_docx.py)."""
    source = os.path.join(BACKEND, "app", "assets", "brief", "plantilla-brief-simuloo.md")
    published = os.path.join(BACKEND, "..", "frontend", "public", "plantilla-brief-simuloo.docx")
    with open(source, encoding="utf-8") as f:
        expected = read(build_docx(f.read()))
    assert extract_docx_text(published) == expected


# ---------- lo que un programa no genera ----------

def test_tracked_changes_read_inserted_text_and_skip_deleted():
    body = ('<w:p><w:r><w:t xml:space="preserve">Hola </w:t></w:r><w:ins><w:r><w:t>nuevo</w:t></w:r></w:ins>'
            '<w:del><w:r><w:delText>borrado</w:delText></w:r></w:del></w:p>')
    assert read(make_docx(body)) == "Hola nuevo"


def test_tabs_breaks_and_content_controls():
    body = ('<w:p><w:r><w:t>A</w:t><w:tab/><w:t>B</w:t><w:br/><w:t>C</w:t></w:r></w:p>'
            f'<w:sdt><w:sdtContent>{para("dentro de un control")}</w:sdtContent></w:sdt>')
    assert read(make_docx(body)) == "A\tB\nC\ndentro de un control"


def test_footnotes_are_read_but_separators_are_not():
    notes = (f'<w:footnotes xmlns:w="{W}"><w:footnote w:type="separator" w:id="-1"><w:p><w:r><w:t>SEPARADOR</w:t></w:r></w:p></w:footnote>'
             f'<w:footnote w:id="1"><w:p><w:r><w:t>Fuente: INE 2025</w:t></w:r></w:p></w:footnote></w:footnotes>')
    text = read(make_docx(para("Cuerpo"), parts={"word/footnotes.xml": notes}))
    assert "Cuerpo" in text and "Fuente: INE 2025" in text and "SEPARADOR" not in text


def test_spanish_heading_style_names_are_recognised():
    assert read(make_docx(para("Mi título", "Ttulo1") + para("Texto"))).splitlines()[0] == "# Mi título"


# ---------- documentos hostiles ----------

def test_decompression_bomb_is_rejected_by_ratio(monkeypatch):
    big = f'<w:document xmlns:w="{W}"><w:body><w:p><w:r><w:t>' + "a" * 8_000_000 + "</w:t></w:r></w:p></w:body></w:document>"
    data = make_docx(document=big)
    assert len(data) < 100_000                               # 8 MB de texto en < 100 KB de zip
    with pytest.raises(DocxError) as exc:
        read(data)
    assert exc.value.code == "docxTooBig"


def test_oversized_part_is_rejected_even_with_a_normal_ratio(monkeypatch):
    monkeypatch.setattr(docx_io, "MAX_XML_BYTES", 200_000)
    noise = os.urandom(150_000).hex()                        # incompresible: la proporción es normal, el tamaño no
    with pytest.raises(DocxError) as exc:
        read(make_docx(para(noise)))
    assert exc.value.code == "docxTooBig"


def test_entity_expansion_bomb_is_rejected_fast():
    laughs = ('<?xml version="1.0"?><!DOCTYPE lolz [<!ENTITY lol "lol"><!ENTITY lol2 "&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;">'
              '<!ENTITY lol3 "&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;">]>'
              f'<w:document xmlns:w="{W}"><w:body><w:p><w:r><w:t>&lol3;</w:t></w:r></w:p></w:body></w:document>')
    started = time.time()
    with pytest.raises(DocxError) as exc:
        read(make_docx(document=laughs))
    assert exc.value.code == "docxUnreadable" and time.time() - started < 1


def test_external_entity_is_never_resolved():
    xxe = ('<?xml version="1.0"?><!DOCTYPE d [<!ENTITY x SYSTEM "file:///etc/passwd">]>'
           f'<w:document xmlns:w="{W}"><w:body><w:p><w:r><w:t>&x;</w:t></w:r></w:p></w:body></w:document>')
    with pytest.raises(DocxError):
        read(make_docx(document=xxe))


@pytest.mark.parametrize("data, code", [
    (b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" + b"\x00" * 600, "docxOld"),          # .doc antiguo o cifrado (OLE)
    (b"esto no es un documento", "docxUnreadable"),
    (b"PK\x03\x04basura que no es un zip", "docxUnreadable"),
])
def test_files_that_are_not_a_docx(data, code):
    with pytest.raises(DocxError) as exc:
        read(data)
    assert exc.value.code == code


def test_a_zip_that_is_not_word_is_rejected():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:                    # lo que sería un .xlsx con la extensión cambiada
        z.writestr("[Content_Types].xml", "<Types/>")
        z.writestr("xl/workbook.xml", "<workbook/>")
    with pytest.raises(DocxError) as exc:
        read(buf.getvalue())
    assert exc.value.code == "docxUnreadable"


def test_truncated_docx_is_rejected():
    data = make_docx(para("texto"))
    with pytest.raises(DocxError):
        read(data[: len(data) // 2])


def test_path_traversal_entries_are_rejected():
    with pytest.raises(DocxError):
        read(make_docx(para("x"), parts={"../evil.txt": "x"}))


def test_too_many_entries_are_rejected():
    parts = {f"word/media/{i}.png": b"x" for i in range(docx_io.MAX_ENTRIES + 5)}
    with pytest.raises(DocxError) as exc:
        read(make_docx(para("x"), parts=parts))
    assert exc.value.code == "docxTooBig"


def test_empty_and_malformed_documents():
    with pytest.raises(DocxError) as exc:
        read(make_docx(""))
    assert exc.value.code == "docxEmpty"
    with pytest.raises(DocxError) as exc:
        read(make_docx(document="<w:document><w:body>sin cerrar"))
    assert exc.value.code == "docxUnreadable"


# ---------- subida de punta a punta ----------

def docx_bytes(name="libreoffice-brief.docx"):
    with open(fixture(name), "rb") as f:
        return f.read()


def test_a_docx_upload_reaches_the_pipeline(client, ontology):
    r = upload(client, [(io.BytesIO(docx_bytes()), "brief.docx")])
    assert r.status_code == 200, r.get_json()
    project = ProjectManager.list_projects()[0]
    text = ProjectManager.get_extracted_text(project.project_id)
    assert "Café del Norte" in text and "Estudiantes de la Universidade de Vigo" in text
    assert "brief.docx" in [f["filename"] for f in project.files]


def test_a_broken_docx_gets_a_clear_400_and_leaves_no_project(client, ontology):
    r = upload(client, [(io.BytesIO(b"PK\x03\x04no soy un zip"), "roto.docx")])
    assert r.status_code == 400 and "No se pudo leer el documento de Word" in r.get_json()["error"]
    assert ProjectManager.list_projects() == []


def test_an_old_doc_renamed_or_password_protected_says_how_to_fix_it(client, ontology):
    r = upload(client, [(io.BytesIO(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" + b"\x00" * 600), "viejo.docx")])
    assert r.status_code == 400 and "Guárdalo como .docx" in r.get_json()["error"]
    assert ProjectManager.list_projects() == []


def test_a_real_old_doc_extension_is_still_not_accepted(client, ontology):
    r = upload(client, [(io.BytesIO(b"\xd0\xcf\x11\xe0" + b"\x00" * 600), "viejo.doc")])
    assert r.status_code == 400
    assert ProjectManager.list_projects() == []


def test_a_text_that_is_too_long_in_a_docx_is_still_capped(client, ontology, monkeypatch):
    monkeypatch.setattr(Config, "MAX_TOTAL_TEXT_CHARS", 2000)
    long_docx = build_docx("\n\n".join(f"Párrafo número {i} con bastante texto para ocupar sitio." for i in range(200)))
    r = upload(client, [(io.BytesIO(long_docx), "largo.docx")])
    assert r.status_code == 413 and ProjectManager.list_projects() == []


def test_brief_review_reads_docx_text(client):
    from app import create_app
    app = create_app()
    data = {"files": (io.BytesIO(docx_bytes()), "brief.docx")}
    with app.test_request_context("/api/brief/check", method="POST", data=data, content_type="multipart/form-data"):
        assert "Café del Norte" in brief_api._text_from_uploads()


# ---------- borrador del brief como documento ----------

def draft(client, **body):
    return client.post("/api/brief/draft-file", json=body, headers=auth())


def test_draft_as_word_is_a_readable_docx(client):
    r = draft(client, markdown="# Brief: mi café\n\n## Público\n\n- Estudiantes\n- Vecinos\n", format="docx")
    assert r.status_code == 200 and r.mimetype.endswith("wordprocessingml.document")
    assert 'filename="brief-simuloo.docx"' in r.headers["Content-Disposition"]
    text = read(r.data)
    assert text.startswith("# Brief: mi café") and "Estudiantes" in text


def test_draft_defaults_to_word(client):
    assert draft(client, markdown="Texto").mimetype.endswith("wordprocessingml.document")


@pytest.mark.parametrize("body", [{}, {"markdown": ""}, {"markdown": "   "}, {"markdown": 5}, {"markdown": "x", "format": "exe"}])
def test_draft_rejects_bad_requests(client, body):
    assert draft(client, **body).status_code == 400


def test_draft_too_long_is_413(client):
    assert draft(client, markdown="x" * (brief_api.DRAFT_MAX_CHARS + 1), format="docx").status_code == 413


def test_draft_needs_authentication(client):
    assert client.post("/api/brief/draft-file", json={"markdown": "x"}).status_code == 401


def _weasyprint_or_skip():
    try:
        import weasyprint  # noqa: F401
    except (ImportError, OSError) as exc:
        pytest.skip(f"WeasyPrint no disponible: {exc}")


def test_draft_as_pdf_uses_the_brief_layout(client):
    _weasyprint_or_skip()
    import fitz
    md = "# Brief: mi café\n\n> Notas de la plantilla que no se pueden perder.\n\n## Público\n\n- Estudiantes\n"
    r = draft(client, markdown=md, format="pdf")
    assert r.status_code == 200 and r.mimetype == "application/pdf" and r.data.startswith(b"%PDF-")
    text = fitz.open(stream=r.data, filetype="pdf")[0].get_text()
    assert "Brief" in text and "Notas de la plantilla que no se pueden perder." in text
    assert "Cómo leer este informe" not in text and "Informe de predicción" not in text      # nada de lo del informe
