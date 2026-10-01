"""
La ruta /api/graph/build y el borrado de proyectos: candado, parámetros, cambios concurrentes y limpieza.
"""

import threading
import time

import pytest

from app import create_app
from app.api import graph as graph_api
from app.config import Config
from app.models.project import ProjectManager, ProjectStatus
from app.services.simulation_manager import SimulationManager
from app.utils import security

from test_pipeline import storage  # noqa: F401 — disco temporal

TOKEN = "token-build"


def hdr():
    return {"Authorization": f"Bearer {TOKEN}"}


class FakeBuilder:
    """Sustituye al servicio de grafos: sin Neo4j ni modelo."""
    instances = []
    gate = None            # threading.Event: el hilo espera aquí para poder cambiar cosas «durante la construcción»
    fail = None
    deleted = []

    def __init__(self, *a, **k):
        FakeBuilder.instances.append(self)

    def create_graph(self, name):
        return "mirofish_test0000000001"

    def set_ontology(self, graph_id, ontology):
        pass

    def add_text_batches(self, graph_id, chunks, batch_size=3, progress_callback=None):
        FakeBuilder.chunks = list(chunks)
        if FakeBuilder.gate:
            FakeBuilder.gate.wait(10)
        if FakeBuilder.fail:
            raise RuntimeError(FakeBuilder.fail)
        return ["ep1"]

    def _wait_for_episodes(self, uuids, cb):
        pass

    def get_graph_data(self, graph_id):
        return {"node_count": 3, "edge_count": 2}

    def delete_graph(self, graph_id):
        FakeBuilder.deleted.append(graph_id)


@pytest.fixture
def client(storage, monkeypatch):
    monkeypatch.setattr(Config, "API_AUTH_REQUIRED", True)
    monkeypatch.setattr(Config, "API_AUTH_TOKEN", TOKEN)
    monkeypatch.setattr(graph_api, "GraphBuilderService", FakeBuilder)
    FakeBuilder.instances, FakeBuilder.gate, FakeBuilder.fail, FakeBuilder.deleted = [], None, None, []
    graph_api._BUILD_LOCKS.clear()
    app = create_app()
    app.config["TESTING"] = True
    app.config["RATELIMIT_ENABLED"] = False
    return app.test_client()


def ready_project(name="Original", text="Un documento. " * 200):
    project = ProjectManager.create_project(name=name, owner_id=None)
    project.ontology = {"entity_types": [{"name": "Persona", "attributes": []}], "edge_types": []}
    project.status = ProjectStatus.ONTOLOGY_GENERATED
    ProjectManager.save_project(project)
    ProjectManager.save_extracted_text(project.project_id, text)
    return project


def build(client, project_id, **extra):
    return client.post("/api/graph/build", headers=hdr(), json={"project_id": project_id, **extra})


def wait_for(predicate, timeout=10):
    end = time.time() + timeout
    while time.time() < end:
        value = predicate()
        if value:
            return value
        time.sleep(0.05)
    raise AssertionError("tiempo agotado")


def test_a_normal_build_completes(client):
    project = ready_project()
    r = build(client, project.project_id)
    assert r.status_code == 200
    final = wait_for(lambda: (lambda p: p if p.status == ProjectStatus.GRAPH_COMPLETED else None)(ProjectManager.get_project(project.project_id)))
    assert final.graph_id == "mirofish_test0000000001"


@pytest.mark.parametrize("params", [
    {"chunk_size": 10, "chunk_overlap": 25}, {"chunk_size": 0}, {"chunk_size": 99}, {"chunk_size": 5001},
    {"chunk_overlap": 400}, {"chunk_overlap": -1}, {"chunk_size": "500"}, {"chunk_size": True}, {"chunk_size": 500.5},
    {"chunk_size": 100, "chunk_overlap": 51},
])
def test_absurd_chunk_parameters_are_rejected_before_anything_starts(client, params):
    project = ready_project()
    r = build(client, project.project_id, **params)
    assert r.status_code == 400 and "chunk_" in r.get_json()["error"]
    assert ProjectManager.get_project(project.project_id).status == ProjectStatus.ONTOLOGY_GENERATED
    assert FakeBuilder.instances == []
    assert not graph_api._get_build_lock(project.project_id).locked()          # y no queda ningún candado cogido


def test_valid_chunk_parameters_are_used(client):
    project = ready_project()
    assert build(client, project.project_id, chunk_size=200, chunk_overlap=20).status_code == 200
    wait_for(lambda: ProjectManager.get_project(project.project_id).status == ProjectStatus.GRAPH_COMPLETED)
    assert all(len(c) <= 200 for c in FakeBuilder.chunks)


def test_early_exits_do_not_leave_the_build_lock_taken(client):
    """Antes cualquier 400/404/409 dejaba el candado cogido y todo /build posterior daba 409 hasta reiniciar."""
    created = ProjectManager.create_project(name="Sin ontología", owner_id=None)         # estado CREATED: 400
    assert build(client, created.project_id).status_code == 400
    assert not graph_api._get_build_lock(created.project_id).locked()

    no_text = ready_project(text="")                                                    # sin texto extraído: 400
    ProjectManager.save_extracted_text(no_text.project_id, "")
    assert build(client, no_text.project_id).status_code == 400
    assert not graph_api._get_build_lock(no_text.project_id).locked()

    # y tras el 400, un /build correcto del mismo proyecto funciona
    ProjectManager.save_extracted_text(no_text.project_id, "Texto. " * 100)
    assert build(client, no_text.project_id).status_code == 200


def test_malformed_ids_never_create_locks(client):
    before = len(graph_api._BUILD_LOCKS)
    for bad in ("x" * 5000, "../../etc", "", 12345, None):
        assert build(client, bad).status_code == 400
    for inexistent in ("proj_000000000000", "proj_ffffffffffff"):          # buen formato, no existe
        assert build(client, inexistent).status_code == 404
    assert len(graph_api._BUILD_LOCKS) == before


def test_a_rename_and_an_owner_change_during_the_build_survive_it(client):
    FakeBuilder.gate = threading.Event()
    project = ready_project(name="Original")
    assert build(client, project.project_id).status_code == 200
    wait_for(lambda: ProjectManager.get_project(project.project_id).graph_id == "mirofish_test0000000001")   # ya va por la mitad

    assert client.patch(f"/api/graph/project/{project.project_id}", headers=hdr(), json={"name": "Nombre NUEVO"}).status_code == 200
    assert client.put(f"/api/graph/project/{project.project_id}/owner", headers=hdr(), json={"owner_id": "5yg3ot03jo2qibu"}).status_code == 200

    FakeBuilder.gate.set()
    final = wait_for(lambda: (lambda p: p if p.status == ProjectStatus.GRAPH_COMPLETED else None)(ProjectManager.get_project(project.project_id)))
    assert (final.name, final.owner_id) == ("Nombre NUEVO", "5yg3ot03jo2qibu")      # antes se restauraban los valores viejos


def test_a_failed_build_stores_no_traceback_and_drops_the_partial_graph(client):
    FakeBuilder.fail = "el modelo no respondió"
    project = ready_project()
    assert build(client, project.project_id).status_code == 200
    final = wait_for(lambda: (lambda p: p if p.status == ProjectStatus.FAILED else None)(ProjectManager.get_project(project.project_id)))
    assert final.error == "el modelo no respondió"
    assert FakeBuilder.deleted == ["mirofish_test0000000001"]
    task_id = client.get(f"/api/graph/project/{project.project_id}", headers=hdr()).get_json()["data"].get("graph_build_task_id")
    tasks = client.get("/api/graph/tasks", headers=hdr()).get_json()["data"]
    assert tasks and all("Traceback" not in (t.get("error") or "") and "File \"" not in (t.get("error") or "") for t in tasks)


def test_building_in_a_project_deleted_meanwhile_cleans_up(client):
    FakeBuilder.gate = threading.Event()
    project = ready_project()
    assert build(client, project.project_id).status_code == 200
    wait_for(lambda: ProjectManager.get_project(project.project_id).graph_id)
    assert client.delete(f"/api/graph/project/{project.project_id}", headers=hdr()).status_code == 200
    FakeBuilder.gate.set()
    wait_for(lambda: "mirofish_test0000000001" in FakeBuilder.deleted)
    assert ProjectManager.get_project(project.project_id) is None               # no se resucitó
    wait_for(lambda: not graph_api._get_build_lock(project.project_id).locked())    # y el hilo suelta el candado al acabar


def test_a_forced_rebuild_drops_the_previous_graph(client):
    project = ready_project()
    ProjectManager.update_project(project.project_id, lambda p: (setattr(p, "graph_id", "mirofish_viejo000000001"),
                                                                 setattr(p, "status", ProjectStatus.GRAPH_COMPLETED)))
    assert build(client, project.project_id, force=True).status_code == 200
    wait_for(lambda: ProjectManager.get_project(project.project_id).status == ProjectStatus.GRAPH_COMPLETED
             and ProjectManager.get_project(project.project_id).graph_id == "mirofish_test0000000001")
    assert "mirofish_viejo000000001" in FakeBuilder.deleted


# ============== Borrar ==============

def test_delete_project_removes_its_graph_and_everything_under_it(client):
    project = ready_project()
    ProjectManager.update_project(project.project_id, lambda p: setattr(p, "graph_id", "mirofish_g00000000001"))
    sim = SimulationManager().create_simulation(project_id=project.project_id, graph_id="mirofish_g00000000001")
    r = client.delete(f"/api/graph/project/{project.project_id}", headers=hdr())
    assert r.status_code == 200 and r.get_json()["cascaded_simulations"] == 1
    assert SimulationManager().get_simulation(sim.simulation_id) is None
    assert FakeBuilder.deleted == ["mirofish_g00000000001"]


def test_if_the_cascade_fails_nothing_is_deleted(client, monkeypatch):
    project = ready_project()
    SimulationManager().create_simulation(project_id=project.project_id, graph_id="mirofish_g00000000001")

    def boom(self, simulation_id):
        raise OSError("disco lleno")

    monkeypatch.setattr(SimulationManager, "delete_simulation", boom)
    r = client.delete(f"/api/graph/project/{project.project_id}", headers=hdr())
    assert r.status_code == 500
    assert ProjectManager.get_project(project.project_id) is not None               # sigue ahí: se puede reintentar


def test_reset_drops_the_old_graph_and_keeps_concurrent_changes(client):
    project = ready_project()
    ProjectManager.update_project(project.project_id, lambda p: (setattr(p, "graph_id", "mirofish_viejo000000001"),
                                                                 setattr(p, "status", ProjectStatus.GRAPH_COMPLETED)))
    r = client.post(f"/api/graph/project/{project.project_id}/reset", headers=hdr())
    assert r.status_code == 200
    reset = ProjectManager.get_project(project.project_id)
    assert (reset.status, reset.graph_id) == (ProjectStatus.ONTOLOGY_GENERATED, None)
    assert FakeBuilder.deleted == ["mirofish_viejo000000001"]
    assert client.post("/api/graph/project/proj_000000000000/reset", headers=hdr()).status_code == 404
