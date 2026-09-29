"""
Tests del parseo de respuestas de modelos de razonamiento (MiniMax M3/M2.7):
<think>, arrays sueltos, YAML y respuestas cortadas. Sin red.
"""

import asyncio

from graphiti_core.prompts.dedupe_nodes import NodeResolutions
from graphiti_core.prompts.extract_edges import ExtractedEdges
from graphiti_core.prompts.extract_nodes import ExtractedEntities

from app.utils.graphiti_adapter import (
    _extract_top_level_array,
    _normalize_json_to_schema,
    _sanitize_embed_inputs,
    _wrap_array_for_schema,
)
from app.utils.llm_client import strip_reasoning


def test_strip_reasoning_closed_and_fenced():
    raw = '<think>\npienso</think>\n\n```json\n{"a": 1}\n```'
    assert strip_reasoning(raw) == '{"a": 1}'


def test_strip_reasoning_unclosed_think_is_dropped():
    assert strip_reasoning('<think>me quedé sin tokens pensando...') == ''
    assert strip_reasoning(None) == ''


def test_bare_array_is_wrapped_into_schema_list():
    raw = '</think>\n[{"name": "Marta Ruiz", "entity_type_id": 0}, {"name": "Kool [Café]", "entity_type_id": 1}]'
    schema = ExtractedEntities.model_json_schema()
    data = _wrap_array_for_schema(_extract_top_level_array(raw), schema)
    _normalize_json_to_schema(data, schema)
    parsed = ExtractedEntities.model_validate(data)
    assert [e.name for e in parsed.extracted_entities] == ["Marta Ruiz", "Kool [Café]"]


def test_empty_array_in_prose_gives_empty_edges():
    raw = 'No hay hechos.\n```json\n[]\n```'
    data = _wrap_array_for_schema(_extract_top_level_array(raw), ExtractedEdges.model_json_schema())
    assert ExtractedEdges.model_validate(data).edges == []


def test_object_is_not_mistaken_for_array():
    assert _extract_top_level_array('{"edges": [1, 2]}') is None


def test_empty_fallback_validates_for_required_fields():
    empty = {}
    _normalize_json_to_schema(empty, NodeResolutions.model_json_schema())
    assert NodeResolutions.model_validate(empty).entity_resolutions == []


def test_empty_embedding_batch_skips_api_call():
    calls = []

    class FakeEmbedder:
        async def create(self, input_data):
            calls.append(input_data)
            return [0.0]

        async def create_batch(self, input_data_list):
            calls.append(input_data_list)
            return [[0.0] for _ in input_data_list]

    emb = FakeEmbedder()
    _sanitize_embed_inputs(emb)
    assert asyncio.run(emb.create_batch([])) == []
    assert calls == []
    assert asyncio.run(emb.create_batch(["hola"])) == [[0.0]]
