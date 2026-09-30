"""
Estado persistido del modo automático.

Vive en uploads/projects/<project_id>/pipeline.json, con escritura atómica
(archivo temporal en la misma carpeta + os.replace) y un candado por
proyecto. Este módulo solo guarda y lee estado; el hilo que encadena las
etapas está en services/auto_pipeline.py.
"""

import json
import os
import tempfile
import threading
from datetime import datetime
from typing import Any, Dict, Optional

from ..models.project import ProjectManager
from ..utils.logger import get_logger
from ..utils.security import is_valid_storage_id, validate_storage_id

logger = get_logger('mirofish.pipeline')

PIPELINE_FILENAME = 'pipeline.json'

# ontology y graph comparten la pantalla 1 del proceso
STAGE_INDEX = {
    "ontology": 1,
    "graph": 1,
    "prepare": 2,
    "simulate": 3,
    "report": 4,
    "done": 5,
}

# Lo único que sale al cliente. El resto (run_id, additional_context...) es interno.
PUBLIC_KEYS = (
    "mode", "status", "stage", "stage_index", "project_id", "simulation_id",
    "report_id", "error", "started_at", "updated_at", "finished_at",
)

ERROR_MAX_CHARS = 2000

_LOCKS_COORDINATOR = threading.Lock()
_LOCKS: Dict[str, threading.RLock] = {}


def pipeline_lock(project_id: str) -> threading.RLock:
    """Candado (reentrante) del pipeline de un proyecto."""
    with _LOCKS_COORDINATOR:
        lock = _LOCKS.get(project_id)
        if lock is None:
            lock = threading.RLock()
            _LOCKS[project_id] = lock
        return lock


def now_iso() -> str:
    return datetime.now().isoformat()


def _pipeline_path(project_id: str) -> str:
    validate_storage_id(project_id, "proj_")
    return os.path.join(ProjectManager.PROJECTS_DIR, project_id, PIPELINE_FILENAME)


def read_pipeline(project_id: str) -> Optional[Dict[str, Any]]:
    """Estado completo (con campos internos) o None si el proyecto es manual."""
    path = _pipeline_path(project_id)
    if not os.path.exists(path):
        return None
    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError) as exc:
        logger.error(f"pipeline.json ilegible en {project_id}: {exc}")
        return None
    return data if isinstance(data, dict) else None


def write_pipeline(project_id: str, state: Dict[str, Any]) -> Dict[str, Any]:
    """Escritura atómica. Recalcula stage_index y updated_at."""
    path = _pipeline_path(project_id)
    directory = os.path.dirname(path)
    if not os.path.isdir(directory):
        raise FileNotFoundError(f"El proyecto {project_id} ya no existe")

    state["stage_index"] = STAGE_INDEX.get(state.get("stage"), 1)
    state["updated_at"] = now_iso()
    if state.get("error"):
        state["error"] = str(state["error"])[:ERROR_MAX_CHARS]

    fd, tmp_path = tempfile.mkstemp(prefix='.pipeline.', suffix='.tmp', dir=directory)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, path)
    except BaseException:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise
    return state


def update_pipeline(project_id: str, run_id: str, **fields) -> Optional[Dict[str, Any]]:
    """
    Actualiza el estado solo si la ejecución `run_id` sigue siendo la vigente
    y está en `running`. Devuelve el estado nuevo, o None si ya no le toca
    escribir (cancelada, relevada por un resume, o proyecto borrado).
    """
    with pipeline_lock(project_id):
        state = read_pipeline(project_id)
        if not state or state.get("run_id") != run_id or state.get("status") != "running":
            return None
        state.update(fields)
        try:
            return write_pipeline(project_id, state)
        except FileNotFoundError:
            return None


def public_view(state: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if not state or state.get("mode") != "auto":
        return {"mode": "manual"}
    return {key: state.get(key) for key in PUBLIC_KEYS}


def mark_running_pipelines_interrupted() -> int:
    """
    Al arrancar: todo pipeline en `running` pasa a `interrupted` (el hilo
    murió con el proceso). No se reanuda solo: cuesta dinero de LLM.
    """
    projects_dir = ProjectManager.PROJECTS_DIR
    if not os.path.isdir(projects_dir):
        return 0

    count = 0
    for project_id in os.listdir(projects_dir):
        if not is_valid_storage_id(project_id, "proj_"):
            continue
        with pipeline_lock(project_id):
            state = read_pipeline(project_id)
            if not state or state.get("status") != "running":
                continue
            state["status"] = "interrupted"
            state["error"] = (
                "El servidor se reinició mientras corría el modo automático. "
                "Puedes reanudarlo desde la etapa en la que se quedó."
            )
            state["finished_at"] = now_iso()
            try:
                write_pipeline(project_id, state)
                count += 1
                logger.warning(
                    f"[boot-recovery] Pipeline de {project_id} marcado como interrupted "
                    f"(etapa {state.get('stage')})"
                )
            except OSError as exc:
                logger.warning(f"[boot-recovery] No se pudo marcar el pipeline de {project_id}: {exc}")
    return count
