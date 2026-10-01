"""
Aislamiento por usuario: quién hace la petición y qué proyectos puede ver.

Cada proyecto guarda el id del usuario de PocketBase que lo creó (`owner_id`). Las simulaciones y los
informes no guardan dueño propio: lo heredan por la cadena informe → simulación → proyecto, así que
no hay dos sitios que puedan desincronizarse.

Quién es quién (`Identity`):
- `user`: un usuario de PocketBase. Solo ve lo suyo.
- `admin`: la clave estática de emergencia (`API_AUTH_TOKEN`), o `API_AUTH_REQUIRED=false` en desarrollo.
  Ve todo.
- `internal`: el propio servidor (modo automático, hilos de simulación). Ve todo; no pasa por la red.
- `none`: petición sin identidad (no debería ocurrir en /api/). No ve nada.

Un proyecto SIN dueño (anterior a este cambio, o creado con la clave de emergencia) solo lo ve el admin,
salvo que se defina `LEGACY_OWNER_ID`: entonces se trata como de ese usuario.

Lo ajeno responde «no encontrado» y no «prohibido»: no se revela que existe.
"""

from __future__ import annotations

import json
import os
import threading
import time
from dataclasses import dataclass
from typing import Callable, Dict, Iterable, Optional, Tuple

from flask import g, has_request_context, jsonify, request

from ..config import Config
from .security import is_valid_storage_id


@dataclass(frozen=True)
class Identity:
    kind: str                          # 'user' | 'admin' | 'internal' | 'none'
    user_id: Optional[str] = None


ADMIN = Identity("admin")
INTERNAL = Identity("internal")
NOBODY = Identity("none")


def user_identity(user_id: str) -> Identity:
    return Identity("user", user_id)


def current_identity() -> Identity:
    """Identidad de la petición en curso. Fuera de una petición (hilos propios del servidor): interna."""
    if not has_request_context():
        return INTERNAL
    return getattr(g, "identity", None) or NOBODY


def current_owner_id() -> Optional[str]:
    """Dueño con el que se sella lo que se crea ahora: el usuario, o nadie (admin / interno)."""
    ident = current_identity()
    return ident.user_id if ident.kind == "user" else None


def effective_owner(owner_id: Optional[str]) -> Optional[str]:
    return owner_id or (getattr(Config, "LEGACY_OWNER_ID", None) or None)


def can_see(identity: Identity, owner_id: Optional[str]) -> bool:
    """¿Puede esta identidad ver algo cuyo dueño es `owner_id`?"""
    if identity.kind in ("admin", "internal"):
        return True
    if identity.kind != "user":
        return False
    owner = effective_owner(owner_id)
    return owner is not None and owner == identity.user_id


# ============== Resolución: id → ¿existe? y dueño ==============
# Se lee del disco (JSON) sin pasar por los gestores: un GET no debe crear carpetas ni cargar informes enteros.

Resolved = Tuple[bool, Optional[str]]     # (existe, dueño)
_MISSING: Resolved = (False, None)


def _read_json(path: str) -> Optional[dict]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else None
    except (OSError, ValueError):
        return None


def owner_of_project(project_id: str) -> Resolved:
    from ..models.project import ProjectManager
    data = _read_json(ProjectManager._get_project_meta_path(project_id))
    if data is None:
        return _MISSING
    return True, data.get("owner_id") or None


def owner_of_simulation(simulation_id: str) -> Resolved:
    from ..services.simulation_manager import SimulationManager
    data = _read_json(os.path.join(SimulationManager.SIMULATION_DATA_DIR, simulation_id, "state.json"))
    if data is None:
        return _MISSING
    project_id = data.get("project_id") or ""
    if not is_valid_storage_id(project_id, "proj_"):
        return True, None                  # simulación huérfana: solo el admin
    found, owner = owner_of_project(project_id)
    return True, (owner if found else None)


def owner_of_report(report_id: str) -> Resolved:
    from ..services.report_agent import ReportManager
    data = _read_json(ReportManager._get_report_path(report_id))
    if data is None:
        data = _read_json(os.path.join(ReportManager.REPORTS_DIR, f"{report_id}.json"))   # formato antiguo
    if data is None:
        return _MISSING
    simulation_id = data.get("simulation_id") or ""
    if not is_valid_storage_id(simulation_id, "sim_"):
        return True, None
    found, owner = owner_of_simulation(simulation_id)
    return True, (owner if found else None)


_GRAPH_MAP: Dict[str, str] = {}
_GRAPH_MAP_AT = 0.0
_GRAPH_LOCK = threading.Lock()
_GRAPH_TTL = 30.0


def _project_of_graph(graph_id: str) -> Optional[str]:
    """graph_id → project_id. Mapa en memoria que se rehace al fallar o a los 30 s."""
    global _GRAPH_MAP, _GRAPH_MAP_AT
    from ..models.project import ProjectManager

    def rebuild() -> None:
        global _GRAPH_MAP, _GRAPH_MAP_AT
        mapping: Dict[str, str] = {}
        base = ProjectManager.PROJECTS_DIR
        try:
            names = os.listdir(base)
        except OSError:
            names = []
        for name in names:
            if not is_valid_storage_id(name, "proj_"):
                continue
            data = _read_json(ProjectManager._get_project_meta_path(name))
            if data and data.get("graph_id"):
                mapping[str(data["graph_id"])] = name
        _GRAPH_MAP, _GRAPH_MAP_AT = mapping, time.monotonic()

    with _GRAPH_LOCK:
        if graph_id in _GRAPH_MAP and time.monotonic() - _GRAPH_MAP_AT < _GRAPH_TTL:
            return _GRAPH_MAP[graph_id]
        rebuild()
        return _GRAPH_MAP.get(graph_id)


def owner_of_graph(graph_id: str) -> Resolved:
    project_id = _project_of_graph(graph_id)
    if not project_id:
        return True, None                  # grafo sin proyecto (huérfano): solo el admin
    found, owner = owner_of_project(project_id)
    return True, (owner if found else None)


def owner_of_task(task_id: str) -> Resolved:
    """Tarea: su dueño es el que la creó. Una tarea sin dueño (creada por el propio servidor) se deja pasar por
    id —no se adivina— pero no sale en los listados de los usuarios."""
    from ..models.task import TaskManager
    task = TaskManager().get_task(task_id)
    if task is None:
        return _MISSING
    return True, (task.metadata or {}).get("owner_id") or None


_RESOLVERS: Dict[str, Callable[[str], Resolved]] = {
    "project_id": owner_of_project,
    "simulation_id": owner_of_simulation,
    "report_id": owner_of_report,
    "graph_id": owner_of_graph,
}
_PREFIXES = {"project_id": "proj_", "simulation_id": "sim_", "report_id": "report_"}


def _memo() -> Dict[Tuple[str, str], Resolved]:
    if not has_request_context():
        return {}
    cache = getattr(g, "_access_memo", None)
    if cache is None:
        cache = g._access_memo = {}
    return cache


def resolve(kind: str, value: str) -> Resolved:
    """Existe y dueño de un id; memorizado durante la petición."""
    memo = _memo()
    key = (kind, value)
    if key not in memo:
        memo[key] = _RESOLVERS[kind](value)
    return memo[key]


def visible_project_id(project_id: Optional[str], identity: Optional[Identity] = None) -> bool:
    """Para filtrar listados: ¿este proyecto lo ve la identidad (por defecto, la de la petición)?"""
    ident = identity or current_identity()
    if ident.kind in ("admin", "internal"):
        return True
    if not project_id or not is_valid_storage_id(project_id, "proj_"):
        return False
    found, owner = resolve("project_id", project_id)
    return found and can_see(ident, owner)


def visible_simulation_id(simulation_id: Optional[str], identity: Optional[Identity] = None) -> bool:
    ident = identity or current_identity()
    if ident.kind in ("admin", "internal"):
        return True
    if not simulation_id or not is_valid_storage_id(simulation_id, "sim_"):
        return False
    found, owner = resolve("simulation_id", simulation_id)
    return found and can_see(ident, owner)


def visible_task(task_metadata: Optional[dict], identity: Optional[Identity] = None) -> bool:
    ident = identity or current_identity()
    if ident.kind in ("admin", "internal"):
        return True
    owner = (task_metadata or {}).get("owner_id")
    return bool(owner) and can_see(ident, owner)


# ============== Control central de acceso ==============

_REF_KEYS = ("project_id", "simulation_id", "report_id", "graph_id", "task_id")


def _request_refs() -> Iterable[Tuple[str, str]]:
    """Los ids que la petición nombra: en la URL, en la query, en el JSON o en un formulario."""
    seen = set()
    sources = [request.view_args or {}, request.args]
    body = request.get_json(silent=True) if request.is_json else None
    if isinstance(body, dict):
        sources.append(body)
    if request.form:
        sources.append(request.form)
    for src in sources:
        for key in _REF_KEYS:
            value = src.get(key) if hasattr(src, "get") else None
            if isinstance(value, str) and value and (key, value) not in seen:
                seen.add((key, value))
                yield key, value


def authorize_request():
    """
    Devuelve una respuesta 404 si la petición nombra algo que su identidad no puede ver; None si pasa.
    Lo que no existe pasa: la ruta responde su propio 404 y no hay nada que proteger.
    """
    ident = current_identity()
    if ident.kind in ("admin", "internal"):
        return None
    if ident.kind != "user":
        return _not_found()
    for key, value in _request_refs():
        if key == "task_id":
            found, owner = owner_of_task(value)
            if found and owner is not None and not can_see(ident, owner):
                return _not_found()
            continue
        prefix = _PREFIXES.get(key)
        if prefix and not is_valid_storage_id(value, prefix):
            continue                       # id mal formado: lo rechaza la validación de ids
        found, owner = resolve(key, value)
        if found and not can_see(ident, owner):
            return _not_found()
    return None


def _not_found():
    return jsonify({"success": False, "error": "No encontrado"}), 404
