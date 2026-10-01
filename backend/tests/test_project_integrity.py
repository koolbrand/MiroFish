"""
Integridad de los proyectos en disco: escritura atómica, lectura tolerante y nada de cambios perdidos.
"""

import json
import os
import threading

import pytest

from app.models.project import ProjectManager, ProjectStatus


@pytest.fixture(autouse=True)
def projects_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(ProjectManager, "PROJECTS_DIR", str(tmp_path / "projects"))
    return tmp_path / "projects"


def test_a_broken_project_file_is_skipped_by_listings_instead_of_breaking_them(projects_dir):
    good = ProjectManager.create_project(name="Bueno", owner_id="userA")
    bad = ProjectManager.create_project(name="Roto", owner_id="userB")
    (projects_dir / bad.project_id / "project.json").write_text('{"project_id": "proj_x", "na', encoding="utf-8")
    empty = ProjectManager.create_project(name="Vacío", owner_id="userB")
    (projects_dir / empty.project_id / "project.json").write_text("", encoding="utf-8")

    assert ProjectManager.get_project(bad.project_id) is None
    assert ProjectManager.get_project(empty.project_id) is None
    assert [p.project_id for p in ProjectManager.list_projects()] == [good.project_id]


def test_a_project_missing_required_fields_is_skipped_too(projects_dir):
    p = ProjectManager.create_project(name="Incompleto", owner_id="userA")
    (projects_dir / p.project_id / "project.json").write_text(json.dumps({"name": "sin id"}), encoding="utf-8")
    assert ProjectManager.get_project(p.project_id) is None
    assert ProjectManager.list_projects() == []


def test_save_does_not_resurrect_a_deleted_project(projects_dir):
    project = ProjectManager.create_project(name="A borrar", owner_id="userA")
    assert ProjectManager.delete_project(project.project_id)
    with pytest.raises(FileNotFoundError):
        ProjectManager.save_project(project)               # el hilo largo que seguía vivo
    assert not (projects_dir / project.project_id).exists()


def test_save_leaves_no_temporary_files_and_is_valid_json(projects_dir):
    project = ProjectManager.create_project(name="Uno", owner_id="userA")
    project.name = "Dos"
    ProjectManager.save_project(project)
    names = os.listdir(projects_dir / project.project_id)
    assert not [n for n in names if n.endswith(".tmp")]
    assert json.loads((projects_dir / project.project_id / "project.json").read_text(encoding="utf-8"))["name"] == "Dos"


def test_update_project_only_touches_its_own_fields(projects_dir):
    """El caso real: un hilo largo leyó el proyecto al empezar; mientras tanto cambió el nombre y el dueño."""
    project = ProjectManager.create_project(name="Original", owner_id="userA")
    stale = ProjectManager.get_project(project.project_id)                      # la copia que tiene el hilo largo

    ProjectManager.update_project(project.project_id, lambda p: setattr(p, "name", "Nombre NUEVO"))
    ProjectManager.update_project(project.project_id, lambda p: setattr(p, "owner_id", "userB"))

    def finish_build(p):                                                        # el hilo termina solo con lo suyo
        p.graph_id = "mirofish_abc"
        p.status = ProjectStatus.GRAPH_COMPLETED

    ProjectManager.update_project(stale.project_id, finish_build)
    final = ProjectManager.get_project(project.project_id)
    assert (final.name, final.owner_id, final.graph_id, final.status) == (
        "Nombre NUEVO", "userB", "mirofish_abc", ProjectStatus.GRAPH_COMPLETED)

    # y guardar la copia vieja entera SÍ pisaría (es lo que ya no deben hacer los hilos largos)
    ProjectManager.save_project(stale)
    assert ProjectManager.get_project(project.project_id).name == "Original"


def test_update_project_on_missing_or_broken_projects_returns_none(projects_dir):
    assert ProjectManager.update_project("proj_000000000000", lambda p: None) is None
    broken = ProjectManager.create_project(name="Roto", owner_id="userA")
    (projects_dir / broken.project_id / "project.json").write_text("{", encoding="utf-8")
    assert ProjectManager.update_project(broken.project_id, lambda p: setattr(p, "name", "x")) is None


def test_concurrent_updates_do_not_lose_each_other(projects_dir):
    project = ProjectManager.create_project(name="Contador", owner_id="userA")
    project.error = "0"
    ProjectManager.save_project(project)

    def bump(p):
        p.error = str(int(p.error) + 1)

    def work():
        for _ in range(25):
            ProjectManager.update_project(project.project_id, bump)

    threads = [threading.Thread(target=work) for _ in range(6)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert ProjectManager.get_project(project.project_id).error == "150"


def test_a_reader_during_saves_never_gets_a_half_file(projects_dir):
    project = ProjectManager.create_project(name="Escribiendo", owner_id="userA")
    project.analysis_summary = "x" * 30000
    stop, bad = threading.Event(), []

    def writer():
        while not stop.is_set():
            ProjectManager.save_project(project)

    t = threading.Thread(target=writer)
    t.start()
    try:
        for _ in range(400):
            if ProjectManager.get_project(project.project_id) is None:
                bad.append(1)
    finally:
        stop.set()
        t.join()
    assert bad == []
