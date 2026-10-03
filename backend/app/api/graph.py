"""
图谱相关API路由
采用项目上下文机制，服务端持久化状态
"""

import io
import os
import re
import traceback
import threading
from flask import request, jsonify, send_file

from . import graph_bp
from ..config import Config
from ..services import web_research as web_research_service
from ..services import type_labels as type_labels_service
from ..services.ontology_generator import OntologyGenerator
from ..services.graph_builder import GraphBuilderService
from ..services.text_processor import TextProcessor
from ..utils.file_parser import FileParser
from ..utils.logger import get_logger
from ..utils.access import can_see, current_identity, visible_task
from ..utils.locale import t, get_locale, set_locale
from ..utils.security import validate_upload_content, sanitize_user_text, is_valid_storage_id, clamp_limit
from ..models.task import TaskManager, TaskStatus
from ..models.project import ProjectManager, ProjectStatus

# 获取日志器
logger = get_logger('mirofish.api')


# Per-project locks for the build endpoint.
#
# Without this, two concurrent `POST /build` requests for the same project
# both see `status == ONTOLOGY_GENERATED`, both pass the conflict check, and
# both spawn build threads that write to the same Neo4j graph_id — silently
# corrupting the graph. The coordinator lock serialises check-then-act
# without serialising builds for different projects.
_BUILD_LOCKS_COORDINATOR = threading.Lock()
_BUILD_LOCKS: dict = {}


def _get_build_lock(project_id: str) -> threading.Lock:
    """Return (and lazily create) the per-project build lock."""
    with _BUILD_LOCKS_COORDINATOR:
        lock = _BUILD_LOCKS.get(project_id)
        if lock is None:
            lock = threading.Lock()
            _BUILD_LOCKS[project_id] = lock
        return lock


def _chunk_params_ok(size, overlap) -> bool:
    """Tamaño y solape del troceado: enteros razonables (None = el valor del proyecto o el de por defecto)."""
    for value in (size, overlap):
        if value is not None and (isinstance(value, bool) or not isinstance(value, int)):
            return False
    effective_size = size if size is not None else Config.DEFAULT_CHUNK_SIZE
    if not 100 <= effective_size <= 5000:
        return False
    return overlap is None or 0 <= overlap <= effective_size // 2


def allowed_file(filename: str) -> bool:
    """检查文件扩展名是否允许"""
    if not filename or '.' not in filename:
        return False
    ext = os.path.splitext(filename)[1].lower().lstrip('.')
    return ext in Config.ALLOWED_EXTENSIONS


# ============== 项目管理接口 ==============

@graph_bp.route('/project/<project_id>', methods=['GET'])
def get_project(project_id: str):
    """
    获取项目详情
    """
    project = ProjectManager.get_project(project_id)

    if not project:
        return jsonify({
            "success": False,
            "error": t('api.projectNotFound', id=project_id)
        }), 404

    # Self-heal: if status is GRAPH_BUILDING but no live task is tracking
    # progress (e.g. the server was restarted mid-build, the in-memory task
    # table was cleared, or the task finished/failed without flipping the
    # project status), reconcile against the actual graph state in Neo4j.
    if project.status == ProjectStatus.GRAPH_BUILDING:
        task_manager = TaskManager()
        task = task_manager.get_task(project.graph_build_task_id) if project.graph_build_task_id else None
        task_alive = task is not None and task.status in (TaskStatus.PENDING, TaskStatus.PROCESSING)

        if not task_alive:
            # The build thread is no longer running. Check whether the
            # graph actually has data; if it does, promote the project.
            try:
                if project.graph_id:
                    builder = GraphBuilderService()
                    graph_data = builder.get_graph_data(project.graph_id)
                    node_count = graph_data.get('node_count', 0) if graph_data else 0
                    if node_count > 0:
                        project.status = ProjectStatus.GRAPH_COMPLETED
                        ProjectManager.save_project(project)
                        logger.info(
                            f"[self-heal] Promoted project {project_id} "
                            f"from graph_building → graph_completed "
                            f"(graph_id={project.graph_id}, nodes={node_count})"
                        )
                    elif task is not None and task.status == TaskStatus.FAILED:
                        project.status = ProjectStatus.FAILED
                        project.error = task.error or 'Graph build failed'
                        ProjectManager.save_project(project)
                        logger.warning(
                            f"[self-heal] Marked project {project_id} FAILED "
                            f"(task {task.task_id} ended in failed state)"
                        )
                elif task is not None and task.status == TaskStatus.FAILED:
                    project.status = ProjectStatus.FAILED
                    project.error = task.error or 'Graph build failed'
                    ProjectManager.save_project(project)
                    logger.warning(
                        f"[self-heal] Marked project {project_id} FAILED "
                        f"(no graph_id, task {task.task_id} failed)"
                    )
            except Exception as heal_err:
                # Self-heal is best-effort; never break the GET endpoint.
                logger.warning(
                    f"[self-heal] Could not reconcile project {project_id}: {heal_err}"
                )

    return jsonify({
        "success": True,
        "data": project.to_dict()
    })


@graph_bp.route('/project/<project_id>/research', methods=['GET'])
def download_project_research(project_id: str):
    """
    Descarga el documento de la investigación en internet del proyecto
    (text/markdown, investigacion-internet.md). 404 si no la tiene: solo
    existe cuando la investigación encontró algo y entró en el material.
    """
    project = ProjectManager.get_project(project_id)
    if not project:
        return jsonify({
            "success": False,
            "error": t('api.projectNotFound', id=project_id)
        }), 404

    markdown = ProjectManager.get_research_document(project_id)
    if markdown is None:
        return jsonify({
            "success": False,
            "error": "Este proyecto no tiene investigación en internet"
        }), 404

    return send_file(
        io.BytesIO(markdown.encode('utf-8')),
        mimetype='text/markdown',
        as_attachment=True,
        download_name=ProjectManager.RESEARCH_DOCUMENT_FILENAME
    )


BRIEF_PREVIEW_CHARS = 20_000      # cuánto del texto del brief se manda a la pantalla (el resto se dice, no se envía)


@graph_bp.route('/project/<project_id>/brief', methods=['GET'])
def project_brief(project_id: str):
    """
    El punto de partida de un proyecto, para enseñarlo en el paso 1: el objetivo de la simulación, los archivos subidos y el
    texto del brief tal como se subió (SIN la investigación en internet, que se guarda mezclada al final del texto extraído
    y tiene su propia tarjeta). 404 si el proyecto no existe o no es del usuario.
    """
    project = ProjectManager.get_project(project_id)
    if not project:
        return jsonify({"success": False, "error": t('api.projectNotFound', id=project_id)}), 404

    extracted = (ProjectManager.get_extracted_text(project_id) or "").split(_RESEARCH_TEXT_HEADER, 1)[0].strip()
    return jsonify({"success": True, "data": {
        "simulation_requirement": project.simulation_requirement or "",
        "files": [{"filename": f.get("filename", ""), "size": f.get("size")} for f in (project.files or [])
                  if not f.get("generated")],
        "text": extracted[:BRIEF_PREVIEW_CHARS],
        "text_length": len(extracted),
        "truncated": len(extracted) > BRIEF_PREVIEW_CHARS,
    }})


@graph_bp.route('/project/list', methods=['GET'])
def list_projects():
    """
    列出所有项目
    """
    limit = clamp_limit(request.args.get('limit', 50, type=int), default=50, high=200)
    # Aislamiento por usuario: primero se filtra y después se corta (cortar antes dejaría fuera lo propio)
    identity = current_identity()
    projects = [p for p in ProjectManager.list_projects(limit=100000) if can_see(identity, p.owner_id)][:limit]
    
    return jsonify({
        "success": True,
        "data": [p.to_dict() for p in projects],
        "count": len(projects)
    })


@graph_bp.route('/project/<project_id>', methods=['PATCH'])
def update_project(project_id: str):
    """
    Actualiza metadatos de un proyecto existente.
    Por ahora solo se admite el campo `name` (renombrar).
    """
    project = ProjectManager.get_project(project_id)

    if not project:
        return jsonify({
            "success": False,
            "error": t('api.projectNotFound', id=project_id)
        }), 404

    data = request.get_json(silent=True) or {}
    new_name = data.get('name')

    if new_name is None:
        return jsonify({
            "success": False,
            "error": "Falta el campo 'name'"
        }), 400

    # Sanitizar: trim + limitar longitud a 120 chars
    new_name = sanitize_user_text(str(new_name)[:200], max_chars=200, field='name').strip()     # sin caracteres de control
    if not new_name:
        return jsonify({
            "success": False,
            "error": "El nombre del proyecto no puede estar vacío"
        }), 400
    if len(new_name) > 120:
        new_name = new_name[:120]

    project = ProjectManager.update_project(project_id, lambda p: setattr(p, 'name', new_name))
    if project is None:
        return jsonify({"success": False, "error": t('api.projectNotFound', id=project_id)}), 404
    logger.info(f"Proyecto {project_id} renombrado a: {new_name}")

    return jsonify({
        "success": True,
        "data": project.to_dict()
    })


@graph_bp.route('/type-labels', methods=['POST'])
def type_labels():
    """
    Etiquetas legibles (en el idioma pedido) para los tipos de la ontología, solo para mostrar.

    Cuerpo: {"locale": "es", "entity": ["SmallBusinessOwner"], "relation": ["WORKS_FOR"], "attribute": ["industry"]}
    Respuesta: {"success": true, "data": {"locale": "es", "labels": {"entity": {...}, "relation": {...}, "attribute": {...}}}}
    Solo trae las que conoce o ha podido traducir; si el modelo falla, faltan y la interfaz usa el identificador
    separado en palabras. Con "en" (u otro idioma sin traducción) no devuelve nada. No depende de ningún proyecto.
    """
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"success": False, "error": t('api.typeLabelsInvalid')}), 400
    locale = data.get('locale') if isinstance(data.get('locale'), str) else get_locale()
    names = {kind: data.get(kind) for kind in type_labels_service.KINDS}
    if any(v is not None and not isinstance(v, list) for v in names.values()):
        return jsonify({"success": False, "error": t('api.typeLabelsInvalid')}), 400
    labels = type_labels_service.get_labels(locale, {k: (v or []) for k, v in names.items()})
    return jsonify({"success": True, "data": {"locale": locale, "labels": labels}})


_OWNER_ID_RE = re.compile(r'[A-Za-z0-9]{8,32}')     # ids de PocketBase: 15 caracteres alfanuméricos


@graph_bp.route('/project/<project_id>/owner', methods=['PUT'])
def set_project_owner(project_id: str):
    """
    Cambia el dueño de un proyecto (y con él, de su grafo, simulaciones e informes: lo heredan).
    Solo el administrador (la clave estática): un usuario, aunque sea el dueño, no puede cederlo.

    Cuerpo: {"owner_id": "<id del usuario en PocketBase>"}, o {"owner_id": null} para dejarlo sin dueño
    (entonces lo ve el administrador, o el usuario de LEGACY_OWNER_ID si está definido).
    Pensado para proyectos anteriores al aislamiento por usuario, que quedaron sin dueño.
    """
    if current_identity().kind != 'admin':
        return jsonify({"success": False, "error": t('api.ownerAdminOnly')}), 403

    project = ProjectManager.get_project(project_id)
    if not project:
        return jsonify({
            "success": False,
            "error": t('api.projectNotFound', id=project_id)
        }), 404

    data = request.get_json(silent=True)
    if not isinstance(data, dict) or 'owner_id' not in data:
        return jsonify({"success": False, "error": t('api.ownerInvalid')}), 400
    new_owner = data['owner_id']
    if new_owner is not None and not (isinstance(new_owner, str) and _OWNER_ID_RE.fullmatch(new_owner)):
        return jsonify({"success": False, "error": t('api.ownerInvalid')}), 400

    changes = {}

    def hand_over(p):
        changes['previous'] = p.owner_id
        p.owner_id = new_owner

    if ProjectManager.update_project(project_id, hand_over) is None:
        return jsonify({"success": False, "error": t('api.projectNotFound', id=project_id)}), 404
    previous = changes['previous']
    logger.info(f"[acceso] Dueño del proyecto {project_id}: {previous or 'sin dueño'} -> {new_owner or 'sin dueño'}")

    return jsonify({
        "success": True,
        "data": {
            "project_id": project_id,
            "owner_id": new_owner,
            "previous_owner_id": previous,
        }
    })


def _delete_graph_quietly(graph_id) -> bool:
    """Borra un grafo de Neo4j sin que un fallo estropee lo que se está haciendo (mejor esfuerzo)."""
    if not graph_id:
        return False
    try:
        GraphBuilderService().delete_graph(graph_id)
        logger.info(f"Grafo {graph_id} borrado")
        return True
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"No se pudo borrar el grafo {graph_id} (queda huérfano en Neo4j): {exc}")
        return False


@graph_bp.route('/project/<project_id>', methods=['DELETE'])
def delete_project(project_id: str):
    """
    删除项目，并级联清理相关的 simulations 和 reports（y su grafo en Neo4j).

    Si la limpieza en cascada falla, NO se borra el proyecto: se responde 500 y se puede reintentar.
    Antes se seguía igualmente y quedaban simulaciones e informes huérfanos que solo veía el administrador.
    """
    project = ProjectManager.get_project(project_id)       # None si no existe o está ilegible (se borra igual)

    # Cascade: remove associated simulations (which also remove their reports)
    cascaded_sims = 0
    try:
        from ..services.simulation_manager import SimulationManager
        from ..services.simulation_runner import SimulationRunner, RunnerStatus
        from ..services.report_agent import ReportManager
        sim_manager = SimulationManager()
        for sim_state in sim_manager.list_simulations(project_id=project_id):
            sid = sim_state.simulation_id
            try:
                run_state = SimulationRunner.get_run_state(sid)
                if run_state and run_state.runner_status in (RunnerStatus.RUNNING, RunnerStatus.STARTING):
                    SimulationRunner.stop_simulation(sid)
                SimulationRunner.terminate_if_alive(sid, finished=True)      # también la ya terminada que espera entrevistas
            except Exception as stop_err:
                logger.warning(f"Fallo al detener la simulación en cascada: {sid}: {stop_err}")
            for rep in ReportManager.list_reports(simulation_id=sid):
                rid = getattr(rep, 'report_id', None)
                if rid:
                    ReportManager.delete_report(rid)
            if sim_manager.delete_simulation(sid):
                cascaded_sims += 1
    except Exception as cascade_err:
        logger.error(f"Fallo en la limpieza en cascada; el proyecto NO se borra: {project_id}: {cascade_err}")
        return jsonify({
            "success": False,
            "error": t('api.projectCascadeFailed', id=project_id)
        }), 500

    graph_id = project.graph_id if project else None
    success = ProjectManager.delete_project(project_id)
    with _BUILD_LOCKS_COORDINATOR:
        lock = _BUILD_LOCKS.get(project_id)
        if lock is not None and not lock.locked():
            _BUILD_LOCKS.pop(project_id, None)          # si hay una construcción en vuelo, su hilo lo suelta y se ve en el siguiente borrado

    if not success:
        return jsonify({
            "success": False,
            "error": t('api.projectDeleteFailed', id=project_id)
        }), 404

    _delete_graph_quietly(graph_id)

    if cascaded_sims:
        logger.info(f"Proyecto {project_id} eliminado · {cascaded_sims} simulaciones limpiadas en cascada")

    return jsonify({
        "success": True,
        "message": t('api.projectDeleted', id=project_id),
        "cascaded_simulations": cascaded_sims
    })


@graph_bp.route('/project/<project_id>/reset', methods=['POST'])
def reset_project(project_id: str):
    """
    重置项目状态（用于重新构建图谱）
    """
    old_graph = {}

    def reset(p):
        old_graph['id'] = p.graph_id
        # 重置到本体已生成状态
        p.status = ProjectStatus.ONTOLOGY_GENERATED if p.ontology else ProjectStatus.CREATED
        p.graph_id = None
        p.graph_build_task_id = None
        p.error = None

    project = ProjectManager.update_project(project_id, reset)
    if not project:
        return jsonify({
            "success": False,
            "error": t('api.projectNotFound', id=project_id)
        }), 404

    _delete_graph_quietly(old_graph.get('id'))      # el grafo anterior ya no lo referencia nadie
    
    return jsonify({
        "success": True,
        "message": t('api.projectReset', id=project_id),
        "data": project.to_dict()
    })


# ============== 接口1：上传文件并生成本体 ==============
#
# La lógica va en tres helpers que usan tanto esta ruta como el modo
# automático (api/pipeline.py), que crea el proyecto en la petición y genera
# la ontología en segundo plano.

class OntologyUploadError(Exception):
    """Subida rechazada con respuesta pública (el proyecto, si lo hubo, ya se ha borrado)."""

    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def read_ontology_form(form, files):
    """
    Lee y valida el multipart de ontology/generate.

    Devuelve (simulation_requirement, project_name, additional_context, uploaded_files).
    Lanza OntologyUploadError si falta un campo obligatorio y ValueError si un
    texto excede los límites de sanitize_user_text.
    """
    simulation_requirement = form.get('simulation_requirement', '')
    project_name = form.get('project_name', 'Unnamed Project')
    additional_context = form.get('additional_context', '')

    logger.debug(f"Nombre del proyecto: {project_name}")
    logger.debug(f"Requisitos de simulación: {simulation_requirement[:100]}...")

    if not simulation_requirement:
        raise OntologyUploadError(t('api.requireSimulationRequirement'))

    # Cap and strip control characters from anything that will reach the
    # LLM or be persisted as project metadata.
    simulation_requirement = sanitize_user_text(
        simulation_requirement, field='simulation_requirement'
    )
    additional_context = sanitize_user_text(
        additional_context, field='additional_context'
    )
    project_name = sanitize_user_text(
        project_name, max_chars=200, field='project_name'
    )

    # 获取上传的文件
    uploaded_files = files.getlist('files')
    if not uploaded_files or all(not f.filename for f in uploaded_files):
        raise OntologyUploadError(t('api.requireFileUpload'))

    # Topes por petición: 990 imágenes de 75 bytes eran 990 llamadas al modelo de visión en una sola petición
    named = [f for f in uploaded_files if f and f.filename]
    if len(named) > Config.MAX_UPLOAD_FILES:
        raise OntologyUploadError(t('api.tooManyFiles', max=Config.MAX_UPLOAD_FILES), 413)
    images = [f for f in named if os.path.splitext(f.filename)[1].lower() in FileParser.IMAGE_EXTENSIONS]
    if len(images) > Config.MAX_UPLOAD_IMAGES:
        raise OntologyUploadError(t('api.tooManyImages', max=Config.MAX_UPLOAD_IMAGES), 413)

    return simulation_requirement, project_name, additional_context, uploaded_files


def _delete_project_quietly(project_id: str) -> None:
    try:
        ProjectManager.delete_project(project_id)
    except Exception as cleanup_error:  # noqa: BLE001
        logger.warning(f"No se pudo limpiar el proyecto {project_id}: {cleanup_error}")


def create_project_from_upload(simulation_requirement: str, project_name: str, uploaded_files):
    """
    Crea el proyecto, guarda los archivos y extrae su texto.

    Devuelve (project, document_texts). En disco quedan el proyecto (estado
    CREATED), los archivos y el texto extraído; `simulation_requirement`,
    `files` y `total_text_length` se fijan en el objeto y quien llama decide
    cuándo guardarlo. Si la subida no vale o algo falla, borra el proyecto
    antes de propagar la excepción (no deja proyectos huérfanos).
    """
    project = ProjectManager.create_project(name=project_name)
    project.simulation_requirement = simulation_requirement
    logger.info(f"Proyecto creado: {project.project_id}")

    try:
        # 保存文件并提取文本
        document_texts = []
        all_text = ""

        for file in uploaded_files:
            if not (file and file.filename and allowed_file(file.filename)):
                continue

            # Validate content matches the declared extension. A user could
            # rename `evil.exe` to `evil.pdf` and the parsers downstream
            # (PyMuPDF, Pillow) would then attempt to process arbitrary
            # bytes. Reject before we ever touch disk.
            ext = os.path.splitext(file.filename)[1].lower().lstrip(".")
            try:
                validate_upload_content(file, ext)
            except ValueError as exc:
                logger.warning(
                    f"Upload rechazado: {file.filename} ({exc})"
                )
                raise OntologyUploadError(t('api.fileContentInvalid', filename=file.filename))

            # 保存文件到项目目录
            file_info = ProjectManager.save_file_to_project(
                project.project_id,
                file,
                file.filename
            )
            project.files.append({
                "filename": file_info["original_filename"],
                "size": file_info["size"]
            })

            # 提取文本
            try:
                text = FileParser.extract_text(file_info["path"])
            except ValueError as exc:
                # El parser rechaza el archivo por una razón que la persona puede entender (imagen enorme...): 400
                raise OntologyUploadError(str(exc), 400)
            text = TextProcessor.preprocess_text(text)
            document_texts.append(text)
            all_text += f"\n\n=== {file_info['original_filename']} ===\n{text}"
            if len(all_text) > Config.MAX_TOTAL_TEXT_CHARS:
                # El grafo gasta un episodio (varias llamadas al modelo) por cada ~500 caracteres: 50 MB de texto
                # eran unos 130.000 episodios desde una sola petición
                raise OntologyUploadError(t('api.textTooLong', max=f"{Config.MAX_TOTAL_TEXT_CHARS:,}".replace(",", ".")), 413)

        if not document_texts:
            raise OntologyUploadError(t('api.noDocProcessed'))

        # 保存提取的文本
        project.total_text_length = len(all_text)
        ProjectManager.save_extracted_text(project.project_id, all_text)
        logger.info(f"Extracción de texto completada, {len(all_text)} caracteres en total")
    except Exception:
        _delete_project_quietly(project.project_id)
        raise

    return project, document_texts


# ============== Investigación en internet (opcional, antes de la ontología) ==============

WEB_RESEARCH_GENERATED = "web_research"
# Cabecera del documento dentro del texto extraído. Distinta de la de un archivo
# subido («=== nombre ===») para poder quitarla sin tocar el material del usuario.
_RESEARCH_TEXT_HEADER = (
    f"\n\n=== {ProjectManager.RESEARCH_DOCUMENT_FILENAME} (investigación automática) ===\n"
)
_RESEARCH_KEYS = ("status", "sources", "queries", "error", "note", "usage", "model",
                  "created_at", "duration_s")


def read_web_research_flag(form) -> bool:
    """Campo de formulario opcional `web_research` ("true"/"1"). Sin él, desactivado."""
    value = form.get('web_research', '')
    return isinstance(value, str) and value.strip().lower() in ('true', '1')


def _drop_previous_research(project, extracted: str) -> str:
    """
    Quita del material una investigación anterior (solo pasa si se repite tras
    un corte a medias). Devuelve el texto extraído sin ella.
    """
    stripped = extracted.split(_RESEARCH_TEXT_HEADER, 1)[0]
    project.files = [f for f in project.files if f.get("generated") != WEB_RESEARCH_GENERATED]
    if stripped != extracted:
        ProjectManager.save_extracted_text(project.project_id, stripped)
        project.total_text_length = len(stripped)
    ProjectManager.delete_research_document(project.project_id)
    return stripped


def run_project_web_research(project, document_texts=None, locale=None):
    """
    Investiga en internet el tema del proyecto y, si encuentra algo
    (`status == done`), lo añade al material: `files/investigacion-internet.md`,
    una entrada en `project.files` con `"generated": "web_research"` y su texto
    al final del texto extraído (así entra en la ontología y en el grafo).

    Guarda el resultado (sin el Markdown) en `project.web_research` y el
    proyecto en disco. Nunca lanza: si falla o no encuentra nada, el proyecto
    sigue sin ella. Devuelve `document_texts` con el documento añadido si entró
    (None si se pasó None: quien llama leerá el texto extraído de disco).
    """
    texts = list(document_texts) if document_texts is not None else None
    project_id = project.project_id
    extracted = None
    try:
        extracted = _drop_previous_research(project, ProjectManager.get_extracted_text(project_id) or "")
        material = extracted or "\n\n".join(texts or [])
        result = web_research_service.research_for_brief(
            project.simulation_requirement or "", material, locale or get_locale()
        )
    except Exception as exc:  # noqa: BLE001 — la investigación nunca tumba el proyecto
        logger.error(f"Error preparando la investigación en internet de {project_id}: {type(exc).__name__}: {exc}")
        result = web_research_service.failed_result("Error interno al preparar la investigación en internet")

    in_material, document = False, None
    if result.get("status") == "done" and result.get("markdown") and extracted is not None:
        markdown = result["markdown"]
        try:
            info = ProjectManager.save_research_document(project_id, markdown)
            document = ProjectManager.RESEARCH_DOCUMENT_FILENAME
            # Al material va el cuerpo del informe, no la lista de fuentes ni lo no confirmado (ver graph_text)
            graph_markdown = web_research_service.graph_text(markdown)
            new_text = extracted + _RESEARCH_TEXT_HEADER + graph_markdown
            ProjectManager.save_extracted_text(project_id, new_text)
            project.files.append({
                "filename": document,
                "size": info["size"],
                "generated": WEB_RESEARCH_GENERATED,
            })
            project.total_text_length = len(new_text)
            if texts is not None:
                texts.append(graph_markdown)
            in_material = True
        except OSError as exc:
            logger.warning(f"No se pudo añadir la investigación al material de {project_id}: {exc}")
            result = {**result, "error": "No se pudo añadir la investigación al material"}

    stored = {key: result.get(key) for key in _RESEARCH_KEYS}
    stored.update(in_material=in_material, document=document if in_material else None)
    project.web_research = stored
    try:
        ProjectManager.save_project(project)
    except OSError as exc:
        logger.warning(f"No se pudo guardar la investigación en el proyecto {project_id}: {exc}")
    logger.info(
        f"Investigación en internet de {project_id}: {stored['status']}"
        f"{' (añadida al material)' if in_material else ''}"
    )
    return texts


def generate_project_ontology(project, document_texts, additional_context=None):
    """
    Genera la ontología con el LLM y la guarda en el proyecto
    (estado ONTOLOGY_GENERATED). No borra nada si falla: eso lo decide quien llama.
    """
    logger.info("Llamando al LLM para generar la ontología...")
    generator = OntologyGenerator()
    ontology = generator.generate(
        document_texts=document_texts,
        simulation_requirement=project.simulation_requirement,
        additional_context=additional_context if additional_context else None
    )

    # 保存本体到项目
    entity_count = len(ontology.get("entity_types", []))
    edge_count = len(ontology.get("edge_types", []))
    logger.info(f"Ontología generada: {entity_count} tipos de entidad, {edge_count} tipos de relación")

    project.ontology = {
        "entity_types": ontology.get("entity_types", []),
        "edge_types": ontology.get("edge_types", [])
    }
    project.analysis_summary = ontology.get("analysis_summary", "")
    project.status = ProjectStatus.ONTOLOGY_GENERATED
    ProjectManager.save_project(project)
    logger.info(f"=== Ontología generada === project_id: {project.project_id}")
    # Los nombres de los tipos se traducen ya, en segundo plano: listos cuando se abra el paso 1
    type_labels_service.warm_async(project.ontology, get_locale())
    return project


@graph_bp.route('/ontology/generate', methods=['POST'])
def generate_ontology():
    """
    接口1：上传文件，分析生成本体定义
    
    请求方式：multipart/form-data
    
    参数：
        files: 上传的文件（PDF/MD/TXT），可多个
        simulation_requirement: 模拟需求描述（必填）
        project_name: 项目名称（可选）
        additional_context: 额外说明（可选）
        web_research: "true"/"1" para investigar en internet antes de la
            ontología (opcional; sin él la respuesta no cambia). Con él, la
            respuesta añade "web_research" (el resultado, sin el Markdown).

    返回：
        {
            "success": true,
            "data": {
                "project_id": "proj_xxxx",
                "ontology": {
                    "entity_types": [...],
                    "edge_types": [...],
                    "analysis_summary": "..."
                },
                "files": [...],
                "total_text_length": 12345
            }
        }
    """
    project = None
    try:
        logger.info("=== Iniciando la generación de la ontología ===")

        # Un texto que excede los límites lanza ValueError y cae en el
        # except genérico de abajo (500), igual que antes de separar helpers.
        try:
            simulation_requirement, project_name, additional_context, uploaded_files = \
                read_ontology_form(request.form, request.files)
            web_research = read_web_research_flag(request.form)
            # 创建项目 + 保存文件并提取文本
            project, document_texts = create_project_from_upload(
                simulation_requirement, project_name, uploaded_files
            )
        except OntologyUploadError as rejected:
            return jsonify({
                "success": False,
                "error": rejected.message
            }), rejected.status_code

        # Investigación en internet (opcional): si encuentra algo, entra en el material
        if web_research:
            document_texts = run_project_web_research(project, document_texts, get_locale())

        # Generar ontología
        generate_project_ontology(project, document_texts, additional_context)

        data = {
            "project_id": project.project_id,
            "project_name": project.name,
            "ontology": project.ontology,
            "analysis_summary": project.analysis_summary,
            "files": project.files,
            "total_text_length": project.total_text_length
        }
        if web_research:
            data["web_research"] = project.web_research
        return jsonify({
            "success": True,
            "data": data
        })
        
    except Exception as e:
        logger.error(f"Fallo al generar la ontología: {e}")
        # No dejar proyectos huérfanos a medio crear (sin ontología)
        if project is not None and project.status != ProjectStatus.ONTOLOGY_GENERATED:
            try:
                ProjectManager.delete_project(project.project_id)
            except Exception as cleanup_error:  # noqa: BLE001
                logger.warning(f"No se pudo limpiar el proyecto {project.project_id}: {cleanup_error}")
        return jsonify({
            "success": False,
            "error": str(e),
            **({"traceback": traceback.format_exc()} if Config.DEBUG else {})
        }), 500


# ============== 接口2：构建图谱 ==============

@graph_bp.route('/build', methods=['POST'])
def build_graph():
    """
    接口2：根据project_id构建图谱
    
    请求（JSON）：
        {
            "project_id": "proj_xxxx",  // 必填，来自接口1
            "graph_name": "图谱名称",    // 可选
            "chunk_size": 500,          // 可选，默认500
            "chunk_overlap": 50         // 可选，默认50
        }
        
    返回：
        {
            "success": true,
            "data": {
                "project_id": "proj_xxxx",
                "task_id": "task_xxxx",
                "message": "图谱构建任务已启动"
            }
        }
    """
    try:
        logger.info("=== Iniciando la construcción del grafo ===")

        # Parsear petición
        data = request.get_json() or {}
        project_id = data.get('project_id')
        logger.debug(f"Parámetros de la petición: project_id={project_id}")
        
        if not project_id or not isinstance(project_id, str) or not is_valid_storage_id(project_id, "proj_"):
            return jsonify({
                "success": False,
                "error": t('api.requireProjectId')
            }), 400
        
        force = data.get('force', False)  # Forzar la reconstrucción

        # Troceado del texto: sin validar, overlap >= chunk_size colgaba el hilo para siempre y chunk_size=1
        # lanzaba un episodio (varias llamadas al modelo) por carácter
        requested_size, requested_overlap = data.get('chunk_size'), data.get('chunk_overlap')
        if not _chunk_params_ok(requested_size, requested_overlap):
            return jsonify({"success": False, "error": t('api.chunkParamsInvalid')}), 400

        # Un id con buen formato pero inexistente no merece un candado (el diccionario crecería con ids inventados)
        if ProjectManager.get_project(project_id) is None:
            return jsonify({"success": False, "error": t('api.projectNotFound', id=project_id)}), 404

        # Serialise the check-then-act for this project so two concurrent
        # /build calls cannot both pass the conflict check and both launch
        # build threads against the same graph_id.
        build_lock = _get_build_lock(project_id)
        if not build_lock.acquire(blocking=False):
            return jsonify({
                "success": False,
                "error": t('api.graphBuilding'),
            }), 409

        thread_started = False
        try:
            # Re-read the project inside the lock — the writer above might
            # have promoted it to GRAPH_BUILDING just before we got here.
            project = ProjectManager.get_project(project_id)
            if not project:
                return jsonify({
                    "success": False,
                    "error": t('api.projectNotFound', id=project_id)
                }), 404

            if project.status == ProjectStatus.CREATED:
                return jsonify({
                    "success": False,
                    "error": t('api.ontologyNotGenerated')
                }), 400

            if project.status == ProjectStatus.GRAPH_BUILDING and not force:
                return jsonify({
                    "success": False,
                    "error": t('api.graphBuilding'),
                    "task_id": project.graph_build_task_id
                }), 409

            # 如果强制重建，重置状态
            replaced_graph_id = None
            if force and project.status in [ProjectStatus.GRAPH_BUILDING, ProjectStatus.FAILED, ProjectStatus.GRAPH_COMPLETED]:
                replaced_graph_id = project.graph_id       # el grafo anterior queda sin dueño: se borra al guardar
                project.status = ProjectStatus.ONTOLOGY_GENERATED
                project.graph_id = None
                project.graph_build_task_id = None
                project.error = None

            # 获取配置
            graph_name = sanitize_user_text(str(data.get('graph_name') or project.name or 'Simuloo Graph')[:200], max_chars=200, field='graph_name')
            chunk_size = requested_size if requested_size is not None else (project.chunk_size or Config.DEFAULT_CHUNK_SIZE)
            chunk_overlap = requested_overlap if requested_overlap is not None else (project.chunk_overlap or Config.DEFAULT_CHUNK_OVERLAP)
            if not _chunk_params_ok(chunk_size, chunk_overlap):          # lo guardado en el proyecto también
                chunk_size, chunk_overlap = Config.DEFAULT_CHUNK_SIZE, Config.DEFAULT_CHUNK_OVERLAP

            # 更新项目配置
            project.chunk_size = chunk_size
            project.chunk_overlap = chunk_overlap

            # 获取提取的文本
            text = ProjectManager.get_extracted_text(project_id)
            if not text:
                return jsonify({
                    "success": False,
                    "error": t('api.textNotFound')
                }), 400

            # 获取本体
            ontology = project.ontology
            if not ontology:
                return jsonify({
                    "success": False,
                    "error": t('api.ontologyNotFound')
                }), 400

            # 创建异步任务
            task_manager = TaskManager()
            task_id = task_manager.create_task(f"Construir grafo: {graph_name}")
            logger.info(f"Tarea de construcción del grafo creada: task_id={task_id}, project_id={project_id}")

            # 更新项目状态
            project.status = ProjectStatus.GRAPH_BUILDING
            project.graph_build_task_id = task_id
            ProjectManager.save_project(project)
            if replaced_graph_id:
                _delete_graph_quietly(replaced_graph_id)
            thread_started = True       # a partir de aquí el candado lo suelta el hilo
        finally:
            if not thread_started:
                build_lock.release()    # cualquier salida temprana (400, 404, 409, error): el candado no se queda cogido
        # Lock stays held — released inside `build_task()` once the thread
        # has reached its terminal state (completed/failed). This prevents
        # a second /build call from racing in while the first thread is
        # still mid-flight.
        
        # Capture locale before spawning background thread
        current_locale = get_locale()

        # 启动后台任务
        def build_task():
            set_locale(current_locale)
            build_logger = get_logger('mirofish.build')
            graph_id = None
            try:
                build_logger.info(f"[{task_id}] Iniciando la construcción del grafo...")
                task_manager.update_task(
                    task_id, 
                    status=TaskStatus.PROCESSING,
                    message=t('progress.initGraphService')
                )
                
                # 创建图谱构建服务
                builder = GraphBuilderService()
                
                # 分块
                task_manager.update_task(
                    task_id,
                    message=t('progress.textChunking'),
                    progress=5
                )
                chunks = TextProcessor.split_text(
                    text, 
                    chunk_size=chunk_size, 
                    overlap=chunk_overlap
                )
                total_chunks = len(chunks)
                
                # 创建图谱
                task_manager.update_task(
                    task_id,
                    message=t('progress.creatingZepGraph'),
                    progress=10
                )
                graph_id = builder.create_graph(name=graph_name)
                
                # 更新项目的graph_id (solo ese campo, sobre la copia más reciente del disco: durante minutos el
                # proyecto puede haber cambiado de nombre o de dueño y no se pisa)
                if ProjectManager.update_project(project_id, lambda p: setattr(p, 'graph_id', graph_id)) is None:
                    raise RuntimeError("El proyecto se borró mientras se construía su grafo")
                
                # 设置本体
                task_manager.update_task(
                    task_id,
                    message=t('progress.settingOntology'),
                    progress=15
                )
                builder.set_ontology(graph_id, ontology)
                
                # 添加文本（progress_callback 签名是 (msg, progress_ratio)）
                def add_progress_callback(msg, progress_ratio):
                    progress = 15 + int(progress_ratio * 40)  # 15% - 55%
                    task_manager.update_task(
                        task_id,
                        message=msg,
                        progress=progress
                    )
                
                task_manager.update_task(
                    task_id,
                    message=t('progress.addingChunks', count=total_chunks),
                    progress=15
                )
                
                episode_uuids = builder.add_text_batches(
                    graph_id, 
                    chunks,
                    batch_size=3,
                    progress_callback=add_progress_callback
                )
                
                # 等待Zep处理完成（查询每个episode的processed状态）
                task_manager.update_task(
                    task_id,
                    message=t('progress.waitingZepProcess'),
                    progress=55
                )
                
                def wait_progress_callback(msg, progress_ratio):
                    progress = 55 + int(progress_ratio * 35)  # 55% - 90%
                    task_manager.update_task(
                        task_id,
                        message=msg,
                        progress=progress
                    )
                
                builder._wait_for_episodes(episode_uuids, wait_progress_callback)
                
                # 获取图谱数据
                task_manager.update_task(
                    task_id,
                    message=t('progress.fetchingGraphData'),
                    progress=95
                )
                graph_data = builder.get_graph_data(graph_id)

                # Un grafo sin entidades no sirve para simular: fallar aquí con
                # un motivo claro en vez de "completado" y romper en el paso 2.
                if not graph_data or graph_data.get("node_count", 0) == 0:
                    raise RuntimeError(
                        "El grafo se construyó sin entidades: el LLM no extrajo "
                        "nada del documento (revisa el log del backend)"
                    )

                # 更新项目状态
                if ProjectManager.update_project(project_id, lambda p: setattr(p, 'status', ProjectStatus.GRAPH_COMPLETED)) is None:
                    raise RuntimeError("El proyecto se borró mientras se construía su grafo")
                
                node_count = graph_data.get("node_count", 0)
                edge_count = graph_data.get("edge_count", 0)
                build_logger.info(f"[{task_id}] Grafo construido: graph_id={graph_id}, nodos={node_count}, aristas={edge_count}")
                
                # 完成
                task_manager.update_task(
                    task_id,
                    status=TaskStatus.COMPLETED,
                    message=t('progress.graphBuildComplete'),
                    progress=100,
                    result={
                        "project_id": project_id,
                        "graph_id": graph_id,
                        "node_count": node_count,
                        "edge_count": edge_count,
                        "chunk_count": total_chunks
                    }
                )
                
            except Exception as e:
                # Actualizar el estado del proyecto a fallido
                build_logger.error(f"[{task_id}] Fallo en la construcción del grafo: {str(e)}")
                build_logger.warning(traceback.format_exc())      # el detalle va al log, no al cliente

                def mark_failed(p):
                    p.status = ProjectStatus.FAILED
                    p.error = str(e)
                    p.graph_build_task_id = None

                try:
                    ProjectManager.update_project(project_id, mark_failed)
                except Exception as save_err:  # noqa: BLE001 — que un fallo al guardar no deje la tarea «en curso»
                    build_logger.warning(f"[{task_id}] No se pudo guardar el estado fallido: {save_err}")
                # Un grafo a medias (o de un proyecto ya borrado) no lo referencia nadie: se borra
                if graph_id:
                    _delete_graph_quietly(graph_id)

                task_manager.update_task(
                    task_id,
                    status=TaskStatus.FAILED,
                    message=t('progress.buildFailed', error=str(e)),
                    error=str(e)
                )
            finally:
                # Release the per-project build lock so a subsequent /build
                # request can proceed (whether the build succeeded or failed).
                try:
                    build_lock.release()
                except RuntimeError:
                    build_logger.warning(
                        f"[{task_id}] Build lock for project {project_id} "
                        f"was not held at release time — likely already freed."
                    )

        # 启动后台线程
        thread = threading.Thread(target=build_task, daemon=True)
        try:
            thread.start()
        except Exception:
            build_lock.release()            # sin hilo no habrá quien suelte el candado
            ProjectManager.update_project(project_id, lambda p: setattr(p, 'status', ProjectStatus.FAILED))
            raise
        
        return jsonify({
            "success": True,
            "data": {
                "project_id": project_id,
                "task_id": task_id,
                "message": t('api.graphBuildStarted', taskId=task_id)
            }
        })
        
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e),
            **({"traceback": traceback.format_exc()} if Config.DEBUG else {})
        }), 500


# ============== 任务查询接口 ==============

@graph_bp.route('/task/<task_id>', methods=['GET'])
def get_task(task_id: str):
    """
    查询任务状态
    """
    task = TaskManager().get_task(task_id)
    
    if not task:
        return jsonify({
            "success": False,
            "error": t('api.taskNotFound', id=task_id)
        }), 404
    
    return jsonify({
        "success": True,
        "data": task.to_dict()
    })


@graph_bp.route('/tasks', methods=['GET'])
def list_tasks():
    """
    列出所有任务
    """
    # list_tasks() ya devuelve diccionarios (antes se llamaba a .to_dict() otra vez y la ruta daba 500)
    tasks = [t for t in TaskManager().list_tasks() if visible_task(t.get('metadata'))]
    
    return jsonify({
        "success": True,
        "data": tasks,
        "count": len(tasks)
    })


# ============== 图谱数据接口 ==============

@graph_bp.route('/data/<graph_id>', methods=['GET'])
def get_graph_data(graph_id: str):
    """
    获取图谱数据（节点和边）
    """
    try:
        builder = GraphBuilderService()
        graph_data = builder.get_graph_data(graph_id)
        
        return jsonify({
            "success": True,
            "data": graph_data
        })
        
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e),
            **({"traceback": traceback.format_exc()} if Config.DEBUG else {})
        }), 500


@graph_bp.route('/delete/<graph_id>', methods=['DELETE'])
def delete_graph(graph_id: str):
    """
    删除Zep图谱
    """
    try:
        builder = GraphBuilderService()
        builder.delete_graph(graph_id)
        
        return jsonify({
            "success": True,
            "message": t('api.graphDeleted', id=graph_id)
        })
        
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e),
            **({"traceback": traceback.format_exc()} if Config.DEBUG else {})
        }), 500
