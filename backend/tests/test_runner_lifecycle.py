"""
Ciclo de vida de los subprocesos de simulación (sin lanzar OASIS: procesos simulados).
"""

import json
import threading
import time

import pytest

from app.config import Config
from app.services import simulation_runner as runner_module
from app.services.simulation_manager import SimulationManager
from app.services.simulation_runner import RunnerStatus, SimulationRunner, SimulationRunState

SIM = "sim_aaaaaaaaaaa1"
REAL_SLEEP = time.sleep          # `time` es el mismo módulo en todas partes: se guarda antes de parchearlo


class FakeProc:
    """Un Popen simulado: `exit_code` None = sigue vivo."""
    _pids = iter(range(40000, 50000))

    def __init__(self):
        self.pid = next(FakeProc._pids)
        self.exit_code = None
        self.returncode = None

    def poll(self):
        self.returncode = self.exit_code
        return self.exit_code

    def wait(self, timeout=None):
        return self.exit_code

    def kill(self):
        self.exit_code = -9

    terminate = kill


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    monkeypatch.setattr(SimulationManager, "SIMULATION_DATA_DIR", str(tmp_path))
    monkeypatch.setattr(SimulationRunner, "RUN_STATE_DIR", str(tmp_path))
    for registry in ("_run_states", "_processes", "_monitor_threads", "_action_queues", "_stdout_files", "_stderr_files",
                     "_graph_memory_enabled", "_start_locks"):
        monkeypatch.setattr(SimulationRunner, registry, {})
    monkeypatch.setattr(SimulationRunner, "_closed_when_done", set())
    monkeypatch.setattr(runner_module.time, "sleep", lambda s: REAL_SLEEP(0.001))

    def fake_terminate(process, simulation_id, timeout=10):
        process.exit_code = -15

    monkeypatch.setattr(SimulationRunner, "_terminate_process", staticmethod(fake_terminate))
    return tmp_path


def put(sim_id, process, **state_fields):
    state = SimulationRunState(simulation_id=sim_id, **state_fields)
    SimulationRunner._run_states[sim_id] = state
    SimulationRunner._processes[sim_id] = process
    return state


# ---------- tope de procesos vivos ----------

def test_live_processes_ignores_dead_ones():
    alive, dead = FakeProc(), FakeProc()
    dead.exit_code = 0
    put("sim_aaaaaaaaaaa1", alive, runner_status=RunnerStatus.RUNNING)
    put("sim_aaaaaaaaaaa2", dead, runner_status=RunnerStatus.COMPLETED)
    assert list(SimulationRunner.live_processes()) == ["sim_aaaaaaaaaaa1"]


def test_a_finished_simulation_waiting_for_interviews_is_closed_to_make_room(monkeypatch):
    monkeypatch.setattr(Config, "MAX_CONCURRENT_SIMULATIONS", 2, raising=False)
    done, busy = FakeProc(), FakeProc()
    put("sim_aaaaaaaaaaa1", done, runner_status=RunnerStatus.COMPLETED, started_at="2026-10-01T09:00:00")
    put("sim_aaaaaaaaaaa2", busy, runner_status=RunnerStatus.RUNNING, twitter_running=True, started_at="2026-10-01T10:00:00")
    SimulationRunner._ensure_capacity()                          # no lanza: cierra la terminada
    assert done.exit_code == -15 and busy.exit_code is None
    assert "sim_aaaaaaaaaaa1" in SimulationRunner._closed_when_done


def test_when_nothing_can_be_closed_a_new_simulation_is_refused(monkeypatch):
    monkeypatch.setattr(Config, "MAX_CONCURRENT_SIMULATIONS", 2, raising=False)
    a, b = FakeProc(), FakeProc()
    put("sim_aaaaaaaaaaa1", a, runner_status=RunnerStatus.RUNNING, twitter_running=True)
    put("sim_aaaaaaaaaaa2", b, runner_status=RunnerStatus.RUNNING, reddit_running=True)
    with pytest.raises(ValueError):
        SimulationRunner._ensure_capacity()
    assert a.exit_code is None and b.exit_code is None           # no se mata a nadie que esté trabajando


def test_there_is_room_below_the_limit(monkeypatch):
    monkeypatch.setattr(Config, "MAX_CONCURRENT_SIMULATIONS", 2, raising=False)
    put("sim_aaaaaaaaaaa1", FakeProc(), runner_status=RunnerStatus.RUNNING, twitter_running=True)
    SimulationRunner._ensure_capacity()


# ---------- el monitor ----------

def run_monitor(proc, state_fields, polls_alive=3, exit_code=0):
    state = put(SIM, proc, **state_fields)
    calls = {"n": 0}
    real_poll = proc.poll

    def poll():
        calls["n"] += 1
        if calls["n"] > polls_alive:
            proc.exit_code = exit_code
        return real_poll()

    proc.poll = poll
    SimulationRunner._monitor_simulation(SIM, "es")
    return state


def test_killing_a_finished_idle_environment_leaves_it_completed_not_failed():
    state = run_monitor(FakeProc(), {"runner_status": RunnerStatus.COMPLETED, "twitter_completed": True,
                                     "reddit_completed": True}, exit_code=-15)
    assert state.runner_status == RunnerStatus.COMPLETED and not state.error
    state2 = run_monitor(FakeProc(), {"runner_status": RunnerStatus.COMPLETED}, exit_code=-9)       # OOM sobre uno ya terminado
    assert state2.runner_status == RunnerStatus.COMPLETED


def test_a_running_simulation_killed_by_a_signal_is_still_failed():
    state = run_monitor(FakeProc(), {"runner_status": RunnerStatus.RUNNING, "twitter_running": True}, exit_code=-9)
    assert state.runner_status == RunnerStatus.FAILED and state.error


def test_a_replaced_monitor_does_not_unregister_the_new_process():
    old, new = FakeProc(), FakeProc()
    put(SIM, old, runner_status=RunnerStatus.RUNNING)
    saves = []
    real_save = SimulationRunner._save_run_state
    SimulationRunner._save_run_state = classmethod(lambda cls, s: saves.append(s.runner_status))
    try:
        polls = {"n": 0}

        def poll():
            polls["n"] += 1
            if polls["n"] == 2:                                   # «reiniciar con force»: otro proceso ocupa el sitio
                SimulationRunner._processes[SIM] = new
            if polls["n"] > 3:
                old.exit_code = -15
            return old.exit_code

        old.poll = poll
        SimulationRunner._monitor_simulation(SIM, "es")
    finally:
        SimulationRunner._save_run_state = real_save
    assert SimulationRunner._processes.get(SIM) is new           # el registro del proceso nuevo sigue ahí
    assert RunnerStatus.FAILED not in saves                      # y el viejo no marcó nada sobre el estado nuevo


def test_an_unchanged_state_is_not_rewritten_every_two_seconds():
    saves = []
    real_save = SimulationRunner._save_run_state
    SimulationRunner._save_run_state = classmethod(lambda cls, s: saves.append(1))
    try:
        run_monitor(FakeProc(), {"runner_status": RunnerStatus.COMPLETED, "twitter_completed": True,
                                 "reddit_completed": True}, polls_alive=40, exit_code=0)
    finally:
        SimulationRunner._save_run_state = real_save
    assert len(saves) <= 3                                        # antes: una escritura por vuelta (40)


# ---------- reiniciar / borrar ----------

def test_cleanup_kills_a_live_process_and_removes_old_interview_files(isolated):
    folder = isolated / SIM
    (folder / "ipc_responses").mkdir(parents=True)
    (folder / "ipc_commands").mkdir()
    (folder / "ipc_responses" / "r1.json").write_text("{}", encoding="utf-8")
    (folder / "ipc_commands" / "c1.json").write_text("{}", encoding="utf-8")
    (folder / "run_state.json").write_text("{}", encoding="utf-8")
    proc = FakeProc()
    put(SIM, proc, runner_status=RunnerStatus.COMPLETED)

    result = SimulationRunner.cleanup_simulation_logs(SIM)
    assert proc.exit_code == -15                                  # ya no queda vivo sin dueño
    assert result["success"] and not list((folder / "ipc_responses").iterdir()) and not list((folder / "ipc_commands").iterdir())
    assert SIM not in SimulationRunner._processes


def test_terminate_if_alive_is_a_noop_without_a_live_process():
    assert SimulationRunner.terminate_if_alive(SIM) is False
    done = FakeProc()
    done.exit_code = 0
    put(SIM, done)
    assert SimulationRunner.terminate_if_alive(SIM) is False


# ---------- doble «iniciar» ----------

def test_two_simultaneous_starts_launch_one_process(isolated, monkeypatch):
    folder = isolated / SIM
    folder.mkdir()
    (folder / "simulation_config.json").write_text(json.dumps({"time_config": {"total_simulation_hours": 24, "minutes_per_round": 60}}), encoding="utf-8")
    launched = []

    def fake_popen(cmd, **kwargs):
        REAL_SLEEP(0.15)                                          # ensancha la ventana de la carrera
        proc = FakeProc()
        launched.append(proc)
        return proc

    monkeypatch.setattr(runner_module.subprocess, "Popen", fake_popen)
    results, errors = [], []

    def start():
        try:
            results.append(SimulationRunner.start_simulation(SIM, platform="parallel", max_rounds=10))
        except ValueError as exc:
            errors.append(str(exc))

    threads = [threading.Thread(target=start) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(10)
    for proc in launched:
        proc.exit_code = 0                                        # que los hilos monitor terminen
    assert len(launched) == 1 and len(results) == 1 and len(errors) == 1


# ---------- entorno de entrevistas ----------

def test_env_alive_requires_a_live_process_not_just_the_status_file(isolated):
    folder = isolated / SIM
    folder.mkdir()
    (folder / "env_status.json").write_text(json.dumps({"status": "alive"}), encoding="utf-8")
    proc = FakeProc()
    put(SIM, proc, runner_status=RunnerStatus.COMPLETED)
    assert SimulationRunner.check_env_alive(SIM) is True
    proc.exit_code = -9                                           # el sistema lo mató: el archivo sigue diciendo «alive»
    assert SimulationRunner.check_env_alive(SIM) is False


def test_env_alive_after_a_restart_checks_the_pid_in_the_saved_state(isolated):
    folder = isolated / SIM
    folder.mkdir()
    (folder / "env_status.json").write_text(json.dumps({"status": "alive"}), encoding="utf-8")
    state = SimulationRunState(simulation_id=SIM, runner_status=RunnerStatus.COMPLETED, process_pid=2 ** 22 + 12345)   # pid inexistente
    SimulationRunner._run_states[SIM] = state
    assert SimulationRunner.check_env_alive(SIM) is False


def test_interview_responses_are_removed_even_if_the_command_file_is_already_gone(tmp_path):
    from app.services.simulation_ipc import SimulationIPCClient, CommandType
    client = SimulationIPCClient(str(tmp_path))
    import threading as th

    def answer():                                                 # hace de script: borra el comando y escribe la respuesta
        end = time.time() + 5
        while time.time() < end:
            commands = list((tmp_path / "ipc_commands").glob("*.json"))
            if commands:
                command_id = commands[0].stem
                commands[0].unlink()
                (tmp_path / "ipc_responses" / f"{command_id}.json").write_text(
                    json.dumps({"command_id": command_id, "status": "completed", "result": {}}), encoding="utf-8")
                return
            REAL_SLEEP(0.01)

    thread = th.Thread(target=answer)
    thread.start()
    response = client.send_command(CommandType.INTERVIEW, {"agent_id": 1, "prompt": "hola"}, timeout=5, poll_interval=0.05)
    thread.join()
    assert response.status.value == "completed"
    assert list((tmp_path / "ipc_responses").glob("*.json")) == []        # antes se quedaba ahí para siempre


def test_the_simulation_process_does_not_inherit_the_servers_own_secrets(monkeypatch):
    monkeypatch.setenv("API_AUTH_TOKEN", "clave-de-administrador")
    monkeypatch.setenv("NEO4J_PASSWORD", "clave-de-neo4j")
    monkeypatch.setenv("SECRET_KEY", "clave-flask")
    monkeypatch.setenv("LLM_API_KEY", "clave-del-modelo")
    env = SimulationRunner._subprocess_env()
    assert not {"API_AUTH_TOKEN", "NEO4J_PASSWORD", "SECRET_KEY"} & set(env)
    assert env["LLM_API_KEY"] == "clave-del-modelo"                      # lo que el script sí necesita
