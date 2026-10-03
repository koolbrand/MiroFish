"""
Brief de la simulación: revisión con Jev y entrevista guiada.
"""

import os
import tempfile

from flask import Response, jsonify, request

from . import brief_bp
from ..services import brief_service
from ..utils.docx_io import build_docx
from ..utils.file_parser import FileParser
from ..utils.locale import get_locale, t
from ..utils.logger import get_logger
from ..utils.security import error_response, validate_upload_content

logger = get_logger('mirofish.api.brief')

TEXT_EXTENSIONS = {'.md', '.markdown', '.txt', '.pdf', '.docx'}
MAX_TRANSCRIPT_TURNS = 20
MAX_ANSWER_CHARS = 4000


def _text_from_uploads() -> str:
    """Texto de los archivos subidos (las imágenes no se revisan: su análisis cuesta)."""
    parts = []
    for upload in request.files.getlist('files'):
        suffix = os.path.splitext(upload.filename or '')[1].lower()
        if suffix not in TEXT_EXTENSIONS:
            continue
        # El contenido tiene que ser lo que dice la extensión: un .exe renombrado a .pdf no llega a PyMuPDF ni al lector de Word
        try:
            validate_upload_content(upload, suffix.lstrip('.'))
        except ValueError as exc:
            logger.warning(f"Subida del brief rechazada: {upload.filename} ({exc})")
            raise ValueError(t('api.fileContentInvalid', filename=upload.filename))
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=True) as tmp:
            upload.save(tmp.name)
            try:
                parts.append(FileParser.extract_text(tmp.name))
            except Exception as e:  # noqa: BLE001
                logger.warning(f"No se pudo leer {upload.filename} para revisar el brief: {e}")
    return "\n\n".join(p for p in parts if p)


def _clean_transcript(raw) -> list:
    turns = []
    for turn in (raw or [])[:MAX_TRANSCRIPT_TURNS]:
        if not isinstance(turn, dict):
            continue
        turns.append({
            "question": str(turn.get("question") or "")[:1000],
            "answer": str(turn.get("answer") or "")[:MAX_ANSWER_CHARS],
            "section": str(turn.get("section") or "")[:40],
        })
    return turns


@brief_bp.route('/sections', methods=['GET'])
def list_sections():
    return jsonify({"success": True, "data": {
        "jev_available": brief_service.jev_available(),
        "sections": [{k: s[k] for k in ("key", "title", "required")} for s in brief_service.SECTIONS],
    }})


@brief_bp.route('/check', methods=['POST'])
def check():
    """Revisa el brief: multipart con `files` (como la subida normal) o JSON {text}."""
    try:
        text = _text_from_uploads() if request.files else (request.get_json(silent=True) or {}).get('text', '')
        return jsonify({"success": True, "data": brief_service.check_brief(text)})
    except ValueError as e:      # un fichero cuyo contenido no es lo que dice su extensión
        return error_response(str(e), 400)
    except Exception as e:  # noqa: BLE001
        logger.error(f"Fallo al revisar el brief: {e}")
        return error_response("No se pudo revisar el brief", 500)


@brief_bp.route('/interview/next', methods=['POST'])
def interview_next():
    data = request.get_json(silent=True) or {}
    try:
        result = brief_service.next_question(
            topic=str(data.get('topic') or '')[:2000],
            transcript=_clean_transcript(data.get('transcript')),
            seed_text=str(data.get('seed_text') or '')[:brief_service.MAX_BRIEF_CHARS],
        )
        return jsonify({"success": True, "data": result})
    except Exception as e:  # noqa: BLE001
        logger.error(f"Fallo en la entrevista del brief: {e}")
        return error_response("No se pudo generar la siguiente pregunta", 500)


@brief_bp.route('/interview/compose', methods=['POST'])
def interview_compose():
    data = request.get_json(silent=True) or {}
    try:
        markdown = brief_service.compose_brief(
            topic=str(data.get('topic') or '')[:2000],
            transcript=_clean_transcript(data.get('transcript')),
            seed_text=str(data.get('seed_text') or '')[:brief_service.MAX_BRIEF_CHARS],
        )
        return jsonify({"success": True, "data": {"markdown": markdown,
                                                   "coverage": brief_service.check_brief(markdown)}})
    except Exception as e:  # noqa: BLE001
        logger.error(f"Fallo al redactar el brief: {e}")
        return error_response("No se pudo redactar el brief", 500)


# ---------- Descargar el borrador del brief como documento ----------

DRAFT_MAX_CHARS = 40_000
DRAFT_FORMATS = {
    'docx': ('application/vnd.openxmlformats-officedocument.wordprocessingml.document', 'brief-simuloo.docx'),
    'pdf': ('application/pdf', 'brief-simuloo.pdf'),
}


@brief_bp.route('/draft-file', methods=['POST'])
def draft_file():
    """
    El borrador que sale de la entrevista, como Word (editable) o PDF. Sin modelo ni coste: solo maqueta el texto.
    Cuerpo: {"markdown": "# Brief…", "format": "docx" | "pdf"}.
    """
    data = request.get_json(silent=True)
    if not isinstance(data, dict) or not isinstance(data.get('markdown'), str) or not data['markdown'].strip():
        return jsonify({"success": False, "error": t('api.briefDraftInvalid')}), 400
    fmt = data.get('format') or 'docx'
    if fmt not in DRAFT_FORMATS:
        return jsonify({"success": False, "error": t('api.briefDraftInvalid')}), 400
    markdown = data['markdown']
    if len(markdown) > DRAFT_MAX_CHARS:
        return jsonify({"success": False, "error": t('api.briefDraftTooLong', max=f"{DRAFT_MAX_CHARS:,}".replace(",", "."))}), 413

    mimetype, filename = DRAFT_FORMATS[fmt]
    try:
        if fmt == 'docx':
            payload = build_docx(markdown, locale=get_locale())
        else:
            from ..services.report_pdf import render_brief_pdf
            payload = render_brief_pdf(markdown_text=markdown, locale=get_locale())
    except Exception as exc:  # noqa: BLE001 — maquetar nunca debe tumbar la entrevista
        logger.error(f"No se pudo maquetar el borrador del brief ({fmt}): {type(exc).__name__}: {exc}")
        return jsonify({"success": False, "error": t('api.briefDraftFailed')}), 500
    return Response(payload, mimetype=mimetype, headers={
        'Content-Disposition': f'attachment; filename="{filename}"',
        'Content-Length': str(len(payload)),
        'Cache-Control': 'no-store',
    })
