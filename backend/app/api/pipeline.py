"""
Modo automático: el servidor encadena las etapas hasta el informe.

    POST /api/pipeline/auto                 multipart igual que ontology/generate
    GET  /api/pipeline/<project_id>         estado ({"mode": "manual"} si no hay)
    POST /api/pipeline/<project_id>/cancel  para el bucle y la simulación
    POST /api/pipeline/<project_id>/resume  sigue desde la primera etapa sin completar

La lógica de las etapas está en services/auto_pipeline.py.
"""

import traceback

from flask import current_app, jsonify, request

from . import pipeline_bp
from .graph import (
    OntologyUploadError,
    _delete_project_quietly,
    create_project_from_upload,
    read_ontology_form,
    read_web_research_flag,
)
from ..config import Config
from ..models.project import ProjectManager
from ..services.auto_pipeline import (
    PipelineConflict,
    active_pipeline_counts,
    cancel_pipeline,
    get_pipeline_state,
    start_pipeline,
)
from ..utils.locale import get_locale, t
from ..utils.logger import get_logger

logger = get_logger('mirofish.api.pipeline')

_CONFLICT_MESSAGE = "Ya hay un modo automático en marcha para este proyecto"


def _project_not_found(project_id: str):
    return jsonify({
        "success": False,
        "error": t('api.projectNotFound', id=project_id)
    }), 404


def _internal_error(exc: Exception):
    return jsonify({
        "success": False,
        "error": str(exc),
        **({"traceback": traceback.format_exc()} if Config.DEBUG else {})
    }), 500


def _pipeline_limit_error():
    """Mensaje si ya hay demasiados pipelines vivos (globales o de este usuario); None si cabe otro."""
    from ..utils.access import current_owner_id
    owner = current_owner_id()
    total, mine = active_pipeline_counts(owner)
    if total >= Config.MAX_ACTIVE_PIPELINES:
        return t('api.tooManyPipelines')
    if owner and mine >= Config.MAX_ACTIVE_PIPELINES_PER_USER:
        return t('api.tooManyPipelinesYours', max=Config.MAX_ACTIVE_PIPELINES_PER_USER)
    return None


def _read_max_rounds(form):
    """
    Campo opcional `max_rounds`: tope de rondas de la simulación (entero entre
    SIMULATION_MIN_ROUNDS y SIMULATION_MAX_ROUNDS). Devuelve (valor | None, error | None);
    sin campo, valor None y el pipeline usa el de por defecto.
    """
    raw = form.get('max_rounds')
    raw = raw.strip() if isinstance(raw, str) else ''
    if not raw:
        return None, None
    try:
        value = int(raw)
    except ValueError:
        return None, t('api.maxRoundsInvalid')
    low, high = Config.SIMULATION_MIN_ROUNDS, Config.SIMULATION_MAX_ROUNDS
    if not low <= value <= high:
        return None, t('api.maxRoundsOutOfRange', min=low, max=high)
    return value, None


@pipeline_bp.route('/auto', methods=['POST'])
def start_auto_pipeline():
    """
    Crea el proyecto y guarda los archivos en la petición (mismas validaciones
    y límites que ontology/generate) y lanza en segundo plano la ontología y
    todo lo que sigue. Responde en pocos segundos. Con `web_research`
    ("true"/"1"), antes de la ontología va la etapa «research». Con `max_rounds`
    (10–100), el tope de rondas de la simulación; sin él, 40.

    Devuelve: {"success": true, "data": {"project_id": "proj_…", "pipeline": <estado>}}
    """
    logger.info("=== Modo automático: nuevo proyecto ===")
    max_rounds, rounds_error = _read_max_rounds(request.form)
    if rounds_error:
        return jsonify({"success": False, "error": rounds_error}), 400

    # Cada pipeline son horas de modelo y una simulación de ~1 GB: sin tope, una sola persona (o un script con
    # 30 peticiones por minuto) podía lanzar decenas y reventar el contenedor de todos
    too_many = _pipeline_limit_error()
    if too_many:
        return jsonify({"success": False, "error": too_many}), 429

    try:
        simulation_requirement, project_name, additional_context, uploaded_files = \
            read_ontology_form(request.form, request.files)
        web_research = read_web_research_flag(request.form)
        project, document_texts = create_project_from_upload(
            simulation_requirement, project_name, uploaded_files
        )
    except OntologyUploadError as rejected:
        return jsonify({"success": False, "error": rejected.message}), rejected.status_code
    except ValueError:
        # Límites de texto y archivos ilegibles: 400 por el manejador global
        raise
    except Exception as exc:  # noqa: BLE001
        logger.error(f"Fallo al crear el proyecto del modo automático: {exc}")
        return _internal_error(exc)

    try:
        # Requisito, archivos y longitud del texto quedan en disco antes del hilo
        ProjectManager.save_project(project)
        state = start_pipeline(
            current_app._get_current_object(),
            project.project_id,
            locale=get_locale(),
            document_texts=document_texts,
            additional_context=additional_context,
            web_research=web_research,
            max_rounds=max_rounds,
        )
    except PipelineConflict:
        return jsonify({"success": False, "error": _CONFLICT_MESSAGE}), 409
    except Exception as exc:  # noqa: BLE001
        logger.error(f"Fallo al lanzar el modo automático: {exc}")
        _delete_project_quietly(project.project_id)
        return _internal_error(exc)

    return jsonify({
        "success": True,
        "data": {
            "project_id": project.project_id,
            "pipeline": state,
        }
    })


@pipeline_bp.route('/<project_id>', methods=['GET'])
def get_pipeline(project_id: str):
    if not ProjectManager.get_project(project_id):
        return _project_not_found(project_id)
    return jsonify({"success": True, "data": get_pipeline_state(project_id)})


@pipeline_bp.route('/<project_id>/cancel', methods=['POST'])
def cancel_auto_pipeline(project_id: str):
    if not ProjectManager.get_project(project_id):
        return _project_not_found(project_id)
    try:
        state = cancel_pipeline(current_app._get_current_object(), project_id, locale=get_locale())
    except Exception as exc:  # noqa: BLE001
        logger.error(f"Fallo al cancelar el modo automático de {project_id}: {exc}")
        return _internal_error(exc)
    return jsonify({"success": True, "data": state})


@pipeline_bp.route('/<project_id>/resume', methods=['POST'])
def resume_auto_pipeline(project_id: str):
    """
    Para pipelines interrupted, failed o cancelled, y para proyectos manuales
    (pasar a automático desde donde estén). Reutiliza proyecto, grafo,
    simulación (nunca crea una segunda) e informe. 409 si ya hay uno en marcha.
    """
    if not ProjectManager.get_project(project_id):
        return _project_not_found(project_id)
    too_many = _pipeline_limit_error()
    if too_many:
        return jsonify({"success": False, "error": too_many}), 429
    try:
        state = start_pipeline(current_app._get_current_object(), project_id, locale=get_locale())
    except PipelineConflict:
        return jsonify({
            "success": False,
            "error": _CONFLICT_MESSAGE,
            "data": get_pipeline_state(project_id),
        }), 409
    except LookupError:
        return _project_not_found(project_id)
    except Exception as exc:  # noqa: BLE001
        logger.error(f"Fallo al reanudar el modo automático de {project_id}: {exc}")
        return _internal_error(exc)
    return jsonify({"success": True, "data": state})
