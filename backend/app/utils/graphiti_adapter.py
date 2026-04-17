"""
Graphiti adapter — wraps graphiti-core async API in sync interface
compatible with the existing Zep Cloud usage patterns.
"""
import asyncio
import json
import logging
import re
import threading
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from difflib import get_close_matches
from typing import Optional

from pydantic import BaseModel, Field, create_model

from graphiti_core import Graphiti
from graphiti_core.nodes import EpisodeType
from graphiti_core.llm_client.openai_client import OpenAIClient
from graphiti_core.llm_client.config import LLMConfig, ModelSize, DEFAULT_MAX_TOKENS
from graphiti_core.embedder.openai import OpenAIEmbedder, OpenAIEmbedderConfig
from graphiti_core.cross_encoder.openai_reranker_client import OpenAIRerankerClient
from neo4j import GraphDatabase

from ..config import Config

logger = logging.getLogger('mirofish.graphiti_adapter')


# ---------------------------------------------------------------------------
# Build Pydantic models dynamically from the ontology dict produced by
# OntologyGenerator.  Graphiti requires:
#   - entity_types: dict[str, type[BaseModel]]
#   - edge_types: dict[str, type[BaseModel]]
#   - edge_type_map: dict[(source, target), list[edge_name]]
#
# All fields must be Optional (default=None) and have a `description` so
# the LLM knows what to extract.  We also blacklist reserved field names
# that conflict with Graphiti's internal node properties.
# ---------------------------------------------------------------------------
_RESERVED_FIELDS = {
    'uuid', 'name', 'labels', 'created_at', 'summary', 'attributes',
    'group_id', 'name_embedding', 'fact_embedding',
}


def _safe_field_name(name: str) -> str:
    """Rename reserved fields to avoid collision with Graphiti internals."""
    if name in _RESERVED_FIELDS:
        return f'{name}_value'
    # Strip non-identifier chars
    name = re.sub(r'[^a-zA-Z0-9_]', '_', name)
    if name and name[0].isdigit():
        name = f'f_{name}'
    return name or 'value'


def _build_entity_model(entity_def: dict) -> type[BaseModel]:
    """Create a Pydantic model class from an ontology entity definition."""
    name = entity_def['name']
    description = entity_def.get('description', f'A {name} entity.')
    attrs = entity_def.get('attributes', [])

    fields: dict = {}
    for attr in attrs:
        attr_name = _safe_field_name(attr.get('name', ''))
        if not attr_name:
            continue
        attr_desc = attr.get('description', attr_name)
        fields[attr_name] = (
            Optional[str],
            Field(default=None, description=attr_desc),
        )

    model_cls = create_model(name, __base__=BaseModel, **fields)
    model_cls.__doc__ = description
    return model_cls


def _build_edge_model(edge_def: dict) -> type[BaseModel]:
    """Create a Pydantic model class from an ontology edge definition."""
    name = edge_def['name']
    # Convert UPPER_SNAKE_CASE → PascalCase for the class name
    class_name = ''.join(word.capitalize() for word in name.split('_')) or name
    description = edge_def.get('description', f'A {name} relationship.')
    attrs = edge_def.get('attributes', [])

    fields: dict = {}
    for attr in attrs:
        attr_name = _safe_field_name(attr.get('name', ''))
        if not attr_name:
            continue
        attr_desc = attr.get('description', attr_name)
        fields[attr_name] = (
            Optional[str],
            Field(default=None, description=attr_desc),
        )

    model_cls = create_model(class_name, __base__=BaseModel, **fields)
    model_cls.__doc__ = description
    return model_cls


def build_ontology_models(ontology: dict) -> tuple[dict, dict, dict]:
    """
    Convert a MiroFish ontology dict (as produced by OntologyGenerator) into
    the three structures Graphiti's add_episode() expects:
      - entity_types: {EntityName: PydanticModel}
      - edge_types:   {EDGE_NAME: PydanticModel}
      - edge_type_map: {(source_entity, target_entity): [edge_names]}

    Returns (entity_types, edge_types, edge_type_map).
    """
    entity_types: dict = {}
    edge_types: dict = {}
    edge_type_map: dict[tuple[str, str], list[str]] = {}

    valid_entity_names: set[str] = set()
    for ent in ontology.get('entity_types', []) or []:
        try:
            model = _build_entity_model(ent)
            entity_types[ent['name']] = model
            valid_entity_names.add(ent['name'])
        except Exception as e:
            logger.warning(f"Failed to build entity model for {ent.get('name')!r}: {e}")

    for edge in ontology.get('edge_types', []) or []:
        try:
            edge_name = edge['name']
            model = _build_edge_model(edge)
            edge_types[edge_name] = model

            # Source-target pairs
            source_targets = edge.get('source_targets', []) or []
            if not source_targets:
                # If no pairs provided, allow this edge between any of our
                # custom entity types.
                for s in valid_entity_names:
                    for t in valid_entity_names:
                        edge_type_map.setdefault((s, t), []).append(edge_name)
            else:
                for st in source_targets:
                    src = st.get('source') or 'Entity'
                    tgt = st.get('target') or 'Entity'
                    edge_type_map.setdefault((src, tgt), []).append(edge_name)
        except Exception as e:
            logger.warning(f"Failed to build edge model for {edge.get('name')!r}: {e}")

    # Graphiti also accepts a wildcard fallback ("Entity", "Entity") → use it
    # so untyped nodes still get edges extracted.
    if edge_types and ('Entity', 'Entity') not in edge_type_map:
        edge_type_map[('Entity', 'Entity')] = list(edge_types.keys())

    return entity_types, edge_types, edge_type_map


# ---------------------------------------------------------------------------
# Fuzzy schema normalization.
#
# MiniMax M2.7 partially honors the response_format json_schema but still
# invents "natural language" variants of field names, e.g.:
#   duplicate_idx     -> duplication_idx
#   name              -> entity_text
#   duplicates        -> duplicate_entries
#
# Before Pydantic validates the response, walk the dict recursively and
# rename any unexpected field to its closest match in the schema using
# difflib.get_close_matches().  Resolves $ref references so nested models
# (List[Entity], etc.) are normalized correctly.
# ---------------------------------------------------------------------------
def _extract_first_json_object(text: str) -> str:
    """
    Extract the first complete, balanced JSON object from text.

    Using a regex like r'\{.*\}' with re.DOTALL is greedy and will span
    across multiple JSON objects (e.g. {"a":1}{"b":2} → the whole string),
    producing "Extra data" on json.loads.  This function counts braces to
    stop exactly at the end of the first balanced object.
    """
    start = text.find('{')
    if start == -1:
        return text
    depth = 0
    in_string = False
    escape_next = False
    for i, ch in enumerate(text[start:], start):
        if escape_next:
            escape_next = False
            continue
        if ch == '\\' and in_string:
            escape_next = True
            continue
        if ch == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch == '{':
            depth += 1
        elif ch == '}':
            depth -= 1
            if depth == 0:
                return text[start:i + 1]
    # Unbalanced — return everything from first '{'
    return text[start:]


def _resolve_ref(schema: dict, root: dict) -> dict:
    """Follow a $ref pointer into the root schema's $defs."""
    if isinstance(schema, dict) and '$ref' in schema:
        ref_name = schema['$ref'].split('/')[-1]
        return root.get('$defs', {}).get(ref_name, schema)
    return schema


# ---------------------------------------------------------------------------
# Explicit field name aliases for models that don't follow the schema.
#
# MiniMax M2.7 does NOT support response_format=json_schema (only Text-01
# does). In json_object mode, M2.7 follows the prompt text, but may still
# use "common" triple-store conventions (subject/predicate/object or IDs).
# These aliases map every known variant to the graphiti-core field name.
# ---------------------------------------------------------------------------
_FIELD_ALIASES: dict[str, str] = {
    # ExtractedEdges / Edge
    'subject':              'source_entity_name',
    'subject_id':           'source_entity_name',
    'source':               'source_entity_name',
    'source_id':            'source_entity_name',
    'source_entity':        'source_entity_name',
    'from':                 'source_entity_name',
    'from_entity':          'source_entity_name',
    'head':                 'source_entity_name',
    'head_entity':          'source_entity_name',
    'entity1':              'source_entity_name',

    'object':               'target_entity_name',
    'object_id':            'target_entity_name',
    'target':               'target_entity_name',
    'target_id':            'target_entity_name',
    'target_entity':        'target_entity_name',
    'to':                   'target_entity_name',
    'to_entity':            'target_entity_name',
    'tail':                 'target_entity_name',
    'tail_entity':          'target_entity_name',
    'entity2':              'target_entity_name',

    'relation':             'relation_type',
    'relationship':         'relation_type',
    'relationship_type':    'relation_type',
    'predicate':            'relation_type',
    'edge_type':            'relation_type',
    'type':                 'relation_type',

    # ExtractedEntities / ExtractedEntity
    'entity_text':          'name',
    'entity_name':          'name',
    'entity':               'name',
    'label':                'name',
    'text':                 'name',
    'type_id':              'entity_type_id',
    'entity_type':          'entity_type_id',

    # NodeResolutions / NodeDuplicate
    'duplication_idx':      'duplicate_idx',
    'duplicate_id':         'duplicate_idx',
    'dup_idx':              'duplicate_idx',
    'idx':                  'duplicate_idx',

    # EdgeDuplicate
    'duplicate_fact':       'duplicate_fact_id',
    'fact_id':              'duplicate_fact_id',
    'contradicted':         'contradicted_facts',
    'contradicting_facts':  'contradicted_facts',
}


def _default_for_type(type_name):
    """Return a type-appropriate default value for a JSON schema type."""
    return {
        'string': '',
        'integer': 0,
        'number': 0.0,
        'boolean': False,
        'array': [],
        'object': {},
        'null': None,
    }.get(type_name, None)


def _autowrap_flat_response(data: dict, schema: dict, root: dict) -> dict:
    """
    Handle MiniMax's habit of returning a flat single item instead of the
    expected wrapper-with-list.  E.g. for ExtractedEntities:
      Got:      {"entity_text": "X", "entity_type_id": 0}
      Expected: {"extracted_entities": [{"name": "X", "entity_type_id": 0}]}

    Detect when the top-level keys don't match any wrapper property, but DO
    match the inner item schema of a list property, and auto-wrap.
    """
    if not isinstance(data, dict) or not data or 'properties' not in schema:
        return data
    expected_top = set(schema['properties'].keys())
    if set(data.keys()) & expected_top:
        return data  # already has a valid wrapper key

    # Find a single "list of object" property in the wrapper schema
    for prop_name, prop_schema in schema['properties'].items():
        resolved_prop = _resolve_ref(prop_schema, root)
        if not isinstance(resolved_prop, dict) or resolved_prop.get('type') != 'array':
            continue
        item_schema = _resolve_ref(resolved_prop.get('items', {}), root)
        item_props = set(item_schema.get('properties', {}).keys()) if isinstance(item_schema, dict) else set()
        if not item_props:
            continue
        # Does our flat data look like an item of this list?
        key_matches = sum(
            1 for k in data
            if k in item_props or _FIELD_ALIASES.get(k) in item_props
        )
        if key_matches >= 1:
            wrapped = {prop_name: [dict(data)]}
            data.clear()
            data.update(wrapped)
            return data
    return data


def _fill_missing_required(data: dict, schema: dict):
    """
    When the LLM returns {} or omits required fields, fill them with
    type-appropriate defaults so Pydantic validation succeeds.
    Applies only to fields marked as `required` in the JSON schema.
    """
    if not isinstance(data, dict) or 'properties' not in schema:
        return
    required = schema.get('required', [])
    for field in required:
        if field in data:
            continue
        field_schema = schema['properties'].get(field, {})
        if not isinstance(field_schema, dict):
            continue
        type_name = field_schema.get('type')
        # Handle anyOf with null union (Optional fields)
        if type_name is None and 'anyOf' in field_schema:
            types = [b.get('type') for b in field_schema['anyOf'] if isinstance(b, dict)]
            type_name = next((t for t in types if t != 'null'), 'null')
        data[field] = _default_for_type(type_name)


def _normalize_json_to_schema(data, schema: dict, root: dict = None):
    """
    Recursively rename / coerce dict keys to match schema field names.

    Strategy (applied in order):
    0. Auto-wrap flat responses into their expected list wrapper.
    1. Explicit aliases (_FIELD_ALIASES) — covers all known LLM variants.
    2. Fuzzy matching (difflib, cutoff 0.6) — catches novel variations.
    3. Type coercion — if schema expects str but value is int/float, stringify.
    4. Fill missing required fields with type-appropriate defaults.
    """
    if root is None:
        root = schema
    schema = _resolve_ref(schema, root)
    if not isinstance(schema, dict):
        return data

    # Unwrap anyOf / oneOf — pick the first object-like branch
    for combinator in ('anyOf', 'oneOf'):
        if combinator in schema:
            for branch in schema[combinator]:
                resolved = _resolve_ref(branch, root)
                if isinstance(resolved, dict) and resolved.get('type') == 'object':
                    schema = resolved
                    break

    if isinstance(data, dict) and 'properties' in schema:
        # --- Pass 0: auto-wrap flat responses ---
        _autowrap_flat_response(data, schema, root)

        expected = set(schema['properties'].keys())

        # --- Pass 1: explicit aliases ---
        for field in list(data.keys()):
            if field not in expected:
                alias_target = _FIELD_ALIASES.get(field)
                if alias_target and alias_target in expected and alias_target not in data:
                    data[alias_target] = data.pop(field)

        # --- Pass 2: fuzzy matching ---
        for field in list(data.keys()):
            if field not in expected:
                remaining = [f for f in expected if f not in data]
                match = get_close_matches(field, remaining, n=1, cutoff=0.6)
                if match:
                    data[match[0]] = data.pop(field)

        # --- Pass 3: type coercion + recurse ---
        for key, val in list(data.items()):
            if key not in schema['properties']:
                continue
            subschema = _resolve_ref(schema['properties'][key], root)
            prop_type = subschema.get('type') if isinstance(subschema, dict) else None

            # Coerce: schema expects string but model returned a number/bool
            if prop_type == 'string' and not isinstance(val, str) and val is not None:
                data[key] = str(val)
            elif isinstance(val, dict):
                _normalize_json_to_schema(val, subschema, root)
            elif isinstance(val, list):
                item_schema = subschema.get('items') if isinstance(subschema, dict) else None
                if item_schema:
                    for item in val:
                        if isinstance(item, dict):
                            _normalize_json_to_schema(item, item_schema, root)

        # --- Pass 4: fill missing required fields ---
        _fill_missing_required(data, schema)

    elif isinstance(data, list) and isinstance(schema, dict) and 'items' in schema:
        for item in data:
            if isinstance(item, dict):
                _normalize_json_to_schema(item, schema['items'], root)
    return data


# ---------------------------------------------------------------------------
# Custom LLM client that handles reasoning models (e.g. MiniMax M2.7) which
# prepend <think>...</think> tokens before the JSON payload.
#
# graphiti-core's OpenAIClient uses `beta.chat.completions.parse()` which
# expects pure JSON.  MiniMax M2.7 (and other chain-of-thought models) return:
#   <think>...reasoning...</think>{"entities": [...]}
# which causes a Pydantic JSON validation error on the first character.
#
# Fix: use regular `chat.completions.create()`, strip the <think> block,
# then validate the remaining JSON against the requested Pydantic model.
# ---------------------------------------------------------------------------
class ThinkingAwareOpenAIClient(OpenAIClient):
    """OpenAIClient subclass that strips <think> reasoning tokens before parsing."""

    async def _generate_response(
        self,
        messages,
        response_model=None,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        model_size: ModelSize = ModelSize.medium,
    ):
        openai_messages = []
        for m in messages:
            m.content = self._clean_input(m.content)
            if m.role in ('user', 'system', 'assistant'):
                openai_messages.append({'role': m.role, 'content': m.content})

        model = (
            (self.small_model or self.model)
            if model_size == ModelSize.small
            else self.model
        )

        kwargs: dict = dict(
            model=model,
            messages=openai_messages,
            temperature=self.temperature,
            max_tokens=max_tokens or self.max_tokens,
        )

        # Pick response_format mode based on model capability:
        #   - MiniMax-Text-01, gpt-4o*, gpt-4-turbo → support json_schema
        #     (strict, schema-enforced output — best for extraction quality)
        #   - MiniMax-M2.7, DeepSeek-R1 (reasoning models) → only json_object
        #     (schema is silently ignored → output drifts to odd field names)
        # We try json_schema first when supported, then fall back step by step.
        model_lower = (model or '').lower()
        # NOTE: exclude reasoning models (deepseek-r1, deepseek-reasoner,
        # minimax-m2.7) — they silently ignore json_schema and produce
        # <think>...</think>{"invented_field": ...}.  Non-reasoning MoE
        # models (deepseek-v3*, deepseek-chat, deepseek-v3-*-YYMMDD) honor
        # it cleanly.
        supports_json_schema = any(k in model_lower for k in (
            'minimax-text', 'gpt-4o', 'gpt-4-turbo', 'gpt-4.1',
            'deepseek-v3', 'deepseek-chat', 'qwen-plus', 'qwen-turbo',
            'qwen-max',
            # BytePlus Seed models with structured_outputs.json_schema=true
            'seed-1-8', 'seed-2-0-lite', 'seed-1-6',
        ))

        attempts: list[dict] = []
        if response_model is not None:
            if supports_json_schema:
                attempts.append({
                    'type': 'json_schema',
                    'json_schema': {
                        'name': response_model.__name__,
                        'schema': response_model.model_json_schema(),
                        'strict': False,  # strict=True rejects $ref/$defs
                    },
                })
            attempts.append({'type': 'json_object'})
        attempts.append(None)  # last resort: no response_format

        response = None
        last_exc: Exception | None = None
        for rf in attempts:
            try_kwargs = dict(kwargs)
            if rf is None:
                try_kwargs.pop('response_format', None)
            else:
                try_kwargs['response_format'] = rf
            try:
                response = await self.client.chat.completions.create(**try_kwargs)
                break
            except Exception as e:
                last_exc = e
                continue
        if response is None:
            raise last_exc  # type: ignore[misc]

        content = response.choices[0].message.content or ""

        # Strip <think>...</think> reasoning blocks (MiniMax M2.7, DeepSeek-R1, etc.)
        content = re.sub(r'<think>.*?</think>', '', content, flags=re.DOTALL).strip()

        # Strip markdown code fences (```json ... ```)
        content = re.sub(r'^```(?:json)?\s*', '', content).rstrip('`\n ').strip()

        if response_model is not None:
            # Extract the first complete balanced JSON object from the cleaned
            # content.  Using a greedy regex can merge multiple JSON objects
            # into one string, causing JSONDecodeError "Extra data".
            json_str = _extract_first_json_object(content)
            if not json_str or json_str == content and '{' not in json_str:
                # No JSON object found — return an empty validated model so
                # graphiti-core gets a valid (empty) response instead of a crash.
                # graphiti will log the retry but continue gracefully.
                return response_model().model_dump()
            data = json.loads(json_str)
            # MiniMax (and other reasoning models) invent field name variants
            # even with json_schema response_format.  Fuzzy-rename unknown keys
            # to their closest expected match before Pydantic validates.
            _normalize_json_to_schema(data, response_model.model_json_schema())
            return response_model.model_validate(data).model_dump()

        return {"content": content}


# ---------------------------------------------------------------------------
# Single persistent event loop running in a background daemon thread.
# All Graphiti / Neo4j async calls are submitted here via
# asyncio.run_coroutine_threadsafe(), which guarantees every coroutine
# runs in the SAME loop regardless of which Flask worker thread calls it.
# This fixes the "Future attached to a different loop" RuntimeError that
# occurs when Flask's threaded mode creates a new event loop per thread.
# ---------------------------------------------------------------------------
_bg_loop: asyncio.AbstractEventLoop | None = None
_bg_loop_lock = threading.Lock()


def _get_bg_loop() -> asyncio.AbstractEventLoop:
    """Return the shared background event loop, starting it if needed."""
    global _bg_loop
    with _bg_loop_lock:
        if _bg_loop is None or not _bg_loop.is_running():
            _bg_loop = asyncio.new_event_loop()
            t = threading.Thread(target=_bg_loop.run_forever, daemon=True, name="graphiti-event-loop")
            t.start()
    return _bg_loop


def _run(coro):
    """Run async coroutine from any sync context using the shared event loop."""
    loop = _get_bg_loop()
    future = asyncio.run_coroutine_threadsafe(coro, loop)
    return future.result()  # blocks until the coroutine finishes


@dataclass
class FakeNode:
    uuid_: str
    name: str
    labels: list
    summary: str = ""
    attributes: dict = None

    def __post_init__(self):
        if self.attributes is None:
            self.attributes = {}


@dataclass
class FakeEdge:
    uuid_: str
    name: str
    fact: str
    source_node_uuid: str = ""
    target_node_uuid: str = ""
    created_at: Optional[datetime] = None
    expired_at: Optional[datetime] = None
    attributes: dict = None

    def __post_init__(self):
        if self.attributes is None:
            self.attributes = {}


@dataclass
class FakeEpisode:
    uuid_: str
    processed: bool = True


@dataclass
class FakeSearchResult:
    edges: list
    nodes: list


def _neo4j_val(v):
    """Convert Neo4j driver types to plain Python JSON-serializable values."""
    # neo4j.time types (DateTime, Date, Time, Duration) have isoformat()
    if hasattr(v, 'isoformat'):
        return v.isoformat()
    # Neo4j Point or other exotic types → stringify
    if hasattr(v, '__class__') and v.__class__.__module__.startswith('neo4j'):
        return str(v)
    return v


def _neo4j_props(props: dict) -> dict:
    """Recursively sanitize a Neo4j property dict for JSON serialization."""
    return {k: _neo4j_val(v) for k, v in props.items()}


class GraphitiNodeClient:
    def __init__(self, graphiti: Graphiti, neo4j_driver):
        self._g = graphiti
        self._driver = neo4j_driver

    def get(self, uuid_: str) -> FakeNode:
        with self._driver.session() as session:
            result = session.run(
                "MATCH (n:Entity {uuid: $uuid}) RETURN n",
                uuid=uuid_
            )
            record = result.single()
            if not record:
                return FakeNode(uuid_=uuid_, name="Unknown", labels=["Entity"])
            node = record["n"]
            props = _neo4j_props(dict(node.items()))
            return FakeNode(
                uuid_=uuid_,
                name=props.get("name", "Unknown"),
                labels=list(node.labels),
                summary=props.get("summary", ""),
                attributes={k: v for k, v in props.items() if k not in ("uuid", "name", "summary", "group_id")}
            )

    def get_entity_edges(self, node_uuid: str) -> list:
        with self._driver.session() as session:
            result = session.run(
                """
                MATCH (s:Entity {uuid: $uuid})-[r:RELATES_TO]->(t:Entity)
                RETURN r, s.uuid as src, t.uuid as tgt
                UNION
                MATCH (s:Entity)-[r:RELATES_TO]->(t:Entity {uuid: $uuid})
                RETURN r, s.uuid as src, t.uuid as tgt
                """,
                uuid=node_uuid
            )
            edges = []
            for record in result:
                rel = record["r"]
                props = _neo4j_props(dict(rel.items()))
                edges.append(FakeEdge(
                    uuid_=props.get("uuid", str(uuid.uuid4())),
                    name=props.get("name", ""),
                    fact=props.get("fact", ""),
                    source_node_uuid=record["src"],
                    target_node_uuid=record["tgt"],
                ))
            return edges

    def get_by_graph_id(self, graph_id: str, limit: int = 100, uuid_cursor: str = None) -> list:
        with self._driver.session() as session:
            if uuid_cursor:
                result = session.run(
                    """
                    MATCH (n:Entity {group_id: $gid})
                    WHERE n.uuid > $cursor
                    RETURN n ORDER BY n.uuid LIMIT $limit
                    """,
                    gid=graph_id, cursor=uuid_cursor, limit=limit
                )
            else:
                result = session.run(
                    "MATCH (n:Entity {group_id: $gid}) RETURN n ORDER BY n.uuid LIMIT $limit",
                    gid=graph_id, limit=limit
                )
            nodes = []
            for record in result:
                node = record["n"]
                props = _neo4j_props(dict(node.items()))
                nodes.append(FakeNode(
                    uuid_=props.get("uuid", str(uuid.uuid4())),
                    name=props.get("name", "Unknown"),
                    labels=list(node.labels),
                    summary=props.get("summary", ""),
                    attributes={k: v for k, v in props.items() if k not in ("uuid", "name", "summary", "group_id")}
                ))
            return nodes


class GraphitiEdgeClient:
    def __init__(self, neo4j_driver):
        self._driver = neo4j_driver

    def get_by_graph_id(self, graph_id: str, limit: int = 100, uuid_cursor: str = None) -> list:
        with self._driver.session() as session:
            if uuid_cursor:
                result = session.run(
                    """
                    MATCH (s:Entity {group_id: $gid})-[r:RELATES_TO]->(t:Entity)
                    WHERE r.uuid > $cursor
                    RETURN r, s.uuid as src, t.uuid as tgt
                    ORDER BY r.uuid LIMIT $limit
                    """,
                    gid=graph_id, cursor=uuid_cursor, limit=limit
                )
            else:
                result = session.run(
                    """
                    MATCH (s:Entity {group_id: $gid})-[r:RELATES_TO]->(t:Entity)
                    RETURN r, s.uuid as src, t.uuid as tgt
                    ORDER BY r.uuid LIMIT $limit
                    """,
                    gid=graph_id, limit=limit
                )
            edges = []
            for record in result:
                rel = record["r"]
                props = _neo4j_props(dict(rel.items()))
                edges.append(FakeEdge(
                    uuid_=props.get("uuid", str(uuid.uuid4())),
                    name=props.get("name", ""),
                    fact=props.get("fact", ""),
                    source_node_uuid=record["src"],
                    target_node_uuid=record["tgt"],
                    created_at=props.get("created_at"),
                    expired_at=props.get("expired_at"),
                    attributes={k: v for k, v in props.items()
                                if k not in ("uuid", "name", "fact", "group_id",
                                             "created_at", "expired_at", "source_node_uuid",
                                             "target_node_uuid")},
                ))
            return edges


class GraphitiEpisodeClient:
    def get(self, uuid_: str) -> FakeEpisode:
        # Graphiti processes episodes async — we just return processed=True
        # since we use synchronous add_episode which blocks until done
        return FakeEpisode(uuid_=uuid_, processed=True)


class GraphitiGraphClient:
    """Main graph client — mimics Zep Cloud's client.graph interface."""

    def __init__(self):
        # Graphiti (graph extraction) uses a DIFFERENT provider than the
        # simulation LLM.  Reasoning models like MiniMax-M2.7 don't honor
        # response_format=json_schema → invalid extractions ~50% of calls.
        # Each GRAPHITI_LLM_* var falls back to its LLM_* counterpart when
        # unset, so single-provider setups still work.
        graphiti_config = LLMConfig(
            api_key=Config.GRAPHITI_LLM_API_KEY,
            base_url=Config.GRAPHITI_LLM_BASE_URL,
            model=Config.GRAPHITI_LLM_MODEL_NAME,
        )
        llm_client = ThinkingAwareOpenAIClient(config=graphiti_config)
        embedder = OpenAIEmbedder(
            config=OpenAIEmbedderConfig(
                api_key=Config.EMBEDDING_API_KEY,
                base_url=Config.EMBEDDING_BASE_URL,
                embedding_model=Config.EMBEDDING_MODEL,
            )
        )
        cross_encoder = OpenAIRerankerClient(config=graphiti_config)
        self._graphiti = Graphiti(
            Config.NEO4J_URI,
            Config.NEO4J_USER,
            Config.NEO4J_PASSWORD,
            llm_client=llm_client,
            embedder=embedder,
            cross_encoder=cross_encoder,
        )
        self._driver = GraphDatabase.driver(
            Config.NEO4J_URI,
            auth=(Config.NEO4J_USER, Config.NEO4J_PASSWORD)
        )
        # Initialize indices once
        _run(self._graphiti.build_indices_and_constraints())

        # Per-graph ontology cache: graph_id → (entity_types, edge_types, edge_type_map)
        # Populated by set_ontology(); consumed by add() to pass custom entity
        # types to add_episode() so Graphiti assigns specific labels (Person,
        # Organization, ...) instead of the generic "Entity".
        self._ontologies: dict[str, tuple[dict, dict, dict]] = {}

        self.node = GraphitiNodeClient(self._graphiti, self._driver)
        self.edge = GraphitiEdgeClient(self._driver)
        self.episode = GraphitiEpisodeClient()

    def create(self, graph_id: str, name: str = "", description: str = "") -> None:
        """No-op — Graphiti creates groups implicitly on first episode add."""
        pass

    def set_ontology(
        self,
        graph_ids: list,
        entities=None,
        edges=None,
        ontology: Optional[dict] = None,
    ) -> None:
        """
        Register a custom ontology for one or more graphs.

        Accepts either:
          - entities/edges: already-built dicts {name: PydanticModel}
            (legacy Zep-Cloud-style parameters), OR
          - ontology: the raw MiroFish ontology dict from OntologyGenerator,
            which we convert to Pydantic models on the fly.

        Graphiti's add_episode() receives `entity_types` and `edge_types`
        parameters that drive the LLM extraction prompt to emit specific
        labels (Person, Organization, …) instead of the default "Entity".
        """
        entity_types: dict = dict(entities or {})
        edge_types: dict = dict(edges or {})
        edge_type_map: dict = {}

        if ontology:
            built_entities, built_edges, built_map = build_ontology_models(ontology)
            # entities/edges passed explicitly take priority over built ones
            for k, v in built_entities.items():
                entity_types.setdefault(k, v)
            for k, v in built_edges.items():
                edge_types.setdefault(k, v)
            edge_type_map = built_map

        if not entity_types and not edge_types:
            logger.info(
                "set_ontology called with empty entity/edge types — "
                "Graphiti will fall back to its default 'Entity' label."
            )

        entry = (entity_types, edge_types, edge_type_map)
        for gid in graph_ids or []:
            self._ontologies[gid] = entry
            logger.info(
                f"Ontology registered for graph {gid}: "
                f"{len(entity_types)} entity types, {len(edge_types)} edge types"
            )

    def add(self, graph_id: str, type: str = "text", data: str = "") -> FakeEpisode:
        ep_uuid = str(uuid.uuid4())
        # Look up any custom ontology registered for this graph via
        # set_ontology().  If present, pass the Pydantic models to
        # add_episode() so Graphiti constrains the LLM extraction to our
        # entity/edge taxonomy (Person, Organization, …).
        entity_types, edge_types, edge_type_map = self._ontologies.get(
            graph_id, ({}, {}, {})
        )

        kwargs = dict(
            name=f"episode_{ep_uuid[:8]}",
            episode_body=data,
            source=EpisodeType.text,
            source_description="MiroFish simulation activity",
            group_id=graph_id,
            reference_time=datetime.now(timezone.utc),
        )
        if entity_types:
            kwargs['entity_types'] = entity_types
        if edge_types:
            kwargs['edge_types'] = edge_types
        if edge_type_map:
            kwargs['edge_type_map'] = edge_type_map

        _run(self._graphiti.add_episode(**kwargs))
        return FakeEpisode(uuid_=ep_uuid, processed=True)

    def add_batch(self, graph_id: str, episodes: list) -> list:
        results = []
        for ep in episodes:
            data = ep.data if hasattr(ep, 'data') else str(ep)
            result = self.add(graph_id=graph_id, data=data)
            results.append(result)
        return results

    def search(self, graph_id: str, query: str, limit: int = 10,
               scope: str = "edges", reranker: str = "rrf") -> FakeSearchResult:
        try:
            raw = _run(self._graphiti.search(
                group_ids=[graph_id],
                query=query,
                num_results=limit,
            ))
            edges = []
            for item in raw:
                edges.append(FakeEdge(
                    uuid_=getattr(item, 'uuid', str(uuid.uuid4())),
                    name=getattr(item, 'name', ''),
                    fact=getattr(item, 'fact', str(item)),
                    source_node_uuid=getattr(item, 'source_node_uuid', ''),
                    target_node_uuid=getattr(item, 'target_node_uuid', ''),
                ))
            return FakeSearchResult(edges=edges, nodes=[])
        except Exception:
            return FakeSearchResult(edges=[], nodes=[])

    def delete(self, graph_id: str) -> None:
        try:
            with self._driver.session() as session:
                session.run(
                    "MATCH (n {group_id: $gid}) DETACH DELETE n",
                    gid=graph_id
                )
        except Exception:
            pass


class GraphitiClient:
    """Top-level client — mimics `from zep_cloud.client import Zep`."""
    def __init__(self, api_key: str = None):
        self.graph = GraphitiGraphClient()


# Singleton
_client_instance = None

def get_graphiti_client() -> GraphitiClient:
    global _client_instance
    if _client_instance is None:
        _client_instance = GraphitiClient()
    return _client_instance
