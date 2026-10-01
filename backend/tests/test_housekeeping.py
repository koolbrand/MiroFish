"""
Limpieza de lo que se acumulaba sin límite: tareas en memoria y registros rotados.
"""

import os
import time
from datetime import datetime, timedelta

from app.models.task import TaskManager, TaskStatus
from app.utils import logger as logger_module


def test_old_tasks_are_purged_including_dead_in_progress_ones():
    manager = TaskManager()
    manager._tasks.clear()
    old = datetime.now() - timedelta(hours=30)
    fresh_id = manager.create_task("fresca")
    done_id = manager.create_task("terminada vieja")
    dead_id = manager.create_task("muerta")
    running_id = manager.create_task("en curso reciente")
    manager._tasks[done_id].created_at, manager._tasks[done_id].status = old, TaskStatus.COMPLETED
    manager._tasks[dead_id].created_at, manager._tasks[dead_id].status = old, TaskStatus.PROCESSING
    manager._tasks[running_id].status = TaskStatus.PROCESSING
    manager.cleanup_old_tasks()
    assert set(manager._tasks) == {fresh_id, running_id}


def test_creating_a_task_triggers_cleanup_at_most_every_half_hour(monkeypatch):
    manager = TaskManager()
    calls = []
    monkeypatch.setattr(manager, "cleanup_old_tasks", lambda *a, **k: calls.append(1))
    manager._last_cleanup = None
    manager.create_task("a")
    manager.create_task("b")
    manager.create_task("c")
    assert len(calls) == 1


def test_the_first_cleanup_runs_even_on_a_freshly_booted_machine(monkeypatch):
    """`time.monotonic()` es el tiempo desde que arrancó la máquina: en un runner de CI nuevo vale menos de 1800 s.
    Con el contador inicial en 0.0 la primera limpieza no se hacía (falló en GitHub, no en local)."""
    manager = TaskManager()
    calls = []
    monkeypatch.setattr(manager, "cleanup_old_tasks", lambda *a, **k: calls.append(1))
    if hasattr(manager, "_last_cleanup"):
        monkeypatch.delattr(manager, "_last_cleanup")              # proceso recién arrancado: nunca se ha limpiado
    monkeypatch.setattr(time, "monotonic", lambda: 100.0)
    manager.create_task("a")
    assert len(calls) == 1
    manager.create_task("b")                                       # y ya no vuelve a limpiar hasta pasada media hora
    assert len(calls) == 1


def test_rotated_log_files_are_purged_too(tmp_path, monkeypatch):
    monkeypatch.setattr(logger_module, "LOG_DIR", str(tmp_path))
    old = time.time() - 40 * 86400
    for name in ("2026-08-01.log", "2026-08-01.log.1", "2026-08-01.log.5", "notas.txt", "2026-10-01.log"):
        path = tmp_path / name
        path.write_text("x", encoding="utf-8")
        if name != "2026-10-01.log":
            os.utime(path, (old, old))
    logger_module._cleanup_old_logs(30)
    assert sorted(p.name for p in tmp_path.iterdir()) == ["2026-10-01.log", "notas.txt"]
