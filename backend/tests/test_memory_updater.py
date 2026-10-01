"""
Actualizador de memoria del grafo: nada lento se hace con un candado cogido y parar tiene plazo.
"""

import threading
import time

import pytest

from app.services import zep_graph_memory_updater as module
from app.services.zep_graph_memory_updater import AgentActivity, ZepGraphMemoryManager, ZepGraphMemoryUpdater

REAL_SLEEP = time.sleep


class SlowClient:
    """Cada envío tarda `delay` segundos; guarda lo que recibe."""

    def __init__(self, delay=0.0):
        self.delay, self.sent = delay, []
        self.graph = self

    def add(self, graph_id, type, data):
        REAL_SLEEP(self.delay)
        self.sent.append(data)


def make(delay=0.0, monkeypatch=None):
    client = SlowClient(delay)
    monkeypatch.setattr(module, "get_graphiti_client", lambda: client)
    updater = ZepGraphMemoryUpdater("mirofish_test00000001")
    return updater, client


def activity(i, platform="twitter"):
    return AgentActivity(platform=platform, agent_id=i, agent_name=f"Agente {i}", action_type="CREATE_POST",
                         action_args={"content": f"mensaje {i}"}, round_num=1, timestamp="2026-10-01T10:00:00")


@pytest.fixture(autouse=True)
def fast(monkeypatch):
    monkeypatch.setattr(ZepGraphMemoryUpdater, "SEND_INTERVAL", 0.0)
    monkeypatch.setattr(ZepGraphMemoryManager, "_updaters", {})
    monkeypatch.setattr(ZepGraphMemoryManager, "_stop_all_done", False)


def test_buffers_stay_usable_while_a_batch_is_being_sent(monkeypatch):
    """Antes el envío (segundos) se hacía con `_buffer_lock` cogido: get_stats y add_activity se quedaban esperando."""
    updater, client = make(delay=1.0, monkeypatch=monkeypatch)
    updater.start()
    try:
        for i in range(updater.BATCH_SIZE):
            updater.add_activity(activity(i))
        REAL_SLEEP(0.3)                                          # el hilo ya está dentro del envío lento
        started = time.monotonic()
        updater.get_stats()
        assert time.monotonic() - started < 0.2
    finally:
        updater.stop(timeout=5)
    assert len(client.sent) >= 1


def test_stop_flushes_the_backlog_in_chunks_not_as_one_giant_episode(monkeypatch):
    updater, client = make(monkeypatch=monkeypatch)
    for i in range(110):                                         # sin hilo: todo queda en la cola
        updater.add_activity(activity(i))
    updater.stop(timeout=10)
    assert sum(text.count("mensaje") for text in client.sent) == 110
    assert len(client.sent) == 5                                 # 110 / 25 por trozo (antes: UN episodio de 110)
    assert max(text.count("mensaje") for text in client.sent) <= updater.FLUSH_CHUNK


def test_stop_gives_up_after_the_deadline_instead_of_blocking_for_minutes(monkeypatch):
    updater, client = make(delay=0.5, monkeypatch=monkeypatch)
    for i in range(200):
        updater.add_activity(activity(i))
    started = time.monotonic()
    updater.stop(timeout=1.2)
    assert time.monotonic() - started < 3
    assert 1 <= len(client.sent) < 8                             # envió lo que cupo y soltó el resto


def test_stopping_one_updater_does_not_block_creating_another(monkeypatch):
    slow, _ = make(delay=0.4, monkeypatch=monkeypatch)
    for i in range(60):
        slow.add_activity(activity(i))
    ZepGraphMemoryManager._updaters["sim_aaaaaaaaaaa1"] = slow
    stopper = threading.Thread(target=ZepGraphMemoryManager.stop_updater, args=("sim_aaaaaaaaaaa1",))
    stopper.start()
    REAL_SLEEP(0.1)                                              # parar ya está volcando
    started = time.monotonic()
    other = ZepGraphMemoryManager.create_updater("sim_aaaaaaaaaaa2", "mirofish_test00000002")
    waited = time.monotonic() - started
    other.stop(timeout=1)
    stopper.join(15)
    assert waited < 0.3                                          # antes esperaba todo el volcado del otro
