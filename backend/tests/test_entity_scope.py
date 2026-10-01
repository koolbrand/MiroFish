"""
Un uuid de nodo de otro grafo no se puede leer desde el grafo propio.
"""

from app.services.zep_entity_reader import ZepEntityReader


class FakeNodeClient:
    def __init__(self, nodes_by_graph):
        self.nodes_by_graph = nodes_by_graph
        self.fetched = []

    def in_graph(self, uuid_, group_id):
        return uuid_ in self.nodes_by_graph.get(group_id, ())

    def get(self, uuid_):
        self.fetched.append(uuid_)
        raise AssertionError("no debe leerse un nodo que no es del grafo")


def make_reader(nodes_by_graph):
    reader = ZepEntityReader.__new__(ZepEntityReader)
    node_client = FakeNodeClient(nodes_by_graph)
    reader.client = type("C", (), {"graph": type("G", (), {"node": node_client})()})()
    reader._call_with_retry = lambda func, operation_name="", **kw: func()
    return reader, node_client


def test_a_node_of_another_graph_is_not_returned():
    reader, node_client = make_reader({"mirofish_a": {"uuid-de-a"}, "mirofish_b": {"uuid-de-b"}})
    assert reader.get_entity_with_context("mirofish_b", "uuid-de-a") is None          # B pide un nodo de A
    assert node_client.fetched == []                                                  # ni siquiera se intentó leer


def test_a_missing_node_in_the_own_graph_is_also_none():
    reader, _ = make_reader({"mirofish_a": set()})
    assert reader.get_entity_with_context("mirofish_a", "no-existe") is None
