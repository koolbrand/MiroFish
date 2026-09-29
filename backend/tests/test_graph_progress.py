"""El build del grafo informa por fragmento y manda latidos mientras procesa."""

import time

from app.services.graph_builder import GraphBuilderService


class SlowGraph:
    def add_batch(self, graph_id, episodes):
        time.sleep(0.35)
        return []


class FakeClient:
    graph = SlowGraph()


def test_progress_per_chunk_with_heartbeat(monkeypatch):
    builder = GraphBuilderService.__new__(GraphBuilderService)
    builder.client = FakeClient()
    monkeypatch.setattr(GraphBuilderService, "HEARTBEAT_SECONDS", 0.1)

    calls = []
    builder.add_text_batches("g", ["a", "b"], progress_callback=lambda msg, p: calls.append(p))

    # Arranca en 0 (no salta al final antes de procesar), sube por fragmento y acaba en 1
    assert calls[0] == 0
    assert 0.5 in calls
    assert calls[-1] == 1.0
    # Latidos: más avisos que fragmentos mientras cada uno tarda
    assert len(calls) > 4
    assert calls == sorted(calls)
