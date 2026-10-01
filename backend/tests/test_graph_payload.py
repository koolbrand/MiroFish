"""
Los vectores de embedding no salen del adaptador del grafo: ni a la pantalla ni a los prompts de los perfiles.
"""

from app.utils import graphiti_adapter


def test_embeddings_are_dropped_from_node_and_edge_properties():
    vector = [0.0123456789] * 1024
    node = {"uuid": "n1", "name": "Marta", "summary": "Resumen", "name_embedding": vector, "full_name": "Marta Ruiz",
            "labels": ["Entity", "Person"], "created_at": "2026-10-01"}
    edge = {"uuid": "e1", "name": "OWNS", "fact": "Marta posee una cafetería", "fact_embedding": vector,
            "source_node_uuid": "n1", "target_node_uuid": "n2"}
    clean_node = graphiti_adapter._neo4j_props(node)
    clean_edge = graphiti_adapter._neo4j_props(edge)
    assert "name_embedding" not in clean_node and "fact_embedding" not in clean_edge
    assert clean_node["full_name"] == "Marta Ruiz" and clean_node["summary"] == "Resumen"
    assert clean_edge["fact"] == "Marta posee una cafetería"
    import json
    assert len(json.dumps(clean_node)) < 400          # antes: ~20 KB por nodo


def test_only_keys_ending_in_embedding_are_dropped():
    props = {"embedding_model": "x", "name": "Ana", "tipo_embedding": [1], "my_embedding_notes": "keep"}
    assert graphiti_adapter._neo4j_props(props) == {"embedding_model": "x", "name": "Ana", "my_embedding_notes": "keep"}
