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
    manager._last_cleanup = 0.0
    manager.create_task("a")
    manager.create_task("b")
    manager.create_task("c")
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
