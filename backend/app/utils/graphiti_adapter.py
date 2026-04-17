"""
Graphiti adapter — wraps graphiti-core async API in sync interface
compatible with the existing Zep Cloud usage patterns.
"""
import asyncio
import json
import re
import threading
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from difflib import get_close_matches
from typing import Optional

from graphiti_core import Graphiti
from graphiti_core.nodes import EpisodeType
from graphiti_core.llm_client.openai_client import OpenAIClient
from graphiti_core.llm_client.config import LLMConfig, ModelSize, DEFAULT_MAX_TOKENS
from graphiti_core.embedder.openai import OpenAIEmbedder, OpenAIEmbedderConfig
from graphiti_core.cross_encoder.openai_reranker_client import OpenAIRerankerClient
from neo4j import GraphDatabase

from ..config import Config


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


def _normalize_json_to_schema(data, schema: dict, root: dict = None):
    """Recursively rename dict keys to match schema field names (fuzzy)."""
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
        expected = set(schema['properties'].keys())
        # Rename unknown keys to their closest expected counterpart
        for field in list(data.keys()):
            if field not in expected:
                remaining = [f for f in expected if f not in data]
                match = get_close_matches(field, remaining, n=1, cutoff=0.5)
                if match:
                    data[match[0]] = data.pop(field)
        # Recurse into nested properties
        for key, val in list(data.items()):
            if key in schema['properties']:
                subschema = schema['properties'][key]
                if isinstance(val, dict):
                    _normalize_json_to_schema(val, subschema, root)
                elif isinstance(val, list):
                    item_schema = subschema.get('items') if isinstance(subschema, dict) else None
                    if item_schema:
                        for item in val:
                            if isinstance(item, dict):
                                _normalize_json_to_schema(item, item_schema, root)
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
            if m.role == 'user':
                openai_messages.append({'role': 'user', 'content': m.content})
            elif m.role == 'system':
                openai_messages.append({'role': 'system', 'content': m.content})

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

        # Pass the Pydantic model's JSON schema as response_format so the model
        # uses the exact field names (e.g. "name" not "entity_text").
        # Most OpenAI-compatible providers (incl. MiniMax) support json_schema.
        # If they don't, we fall back to json_object mode below.
        if response_model is not None:
            schema = response_model.model_json_schema()
            kwargs['response_format'] = {
                'type': 'json_schema',
                'json_schema': {
                    'name': schema.get('title', response_model.__name__),
                    'schema': schema,
                    'strict': False,
                },
            }

        try:
            response = await self.client.chat.completions.create(**kwargs)
        except Exception:
            # Provider doesn't support json_schema — fall back to json_object
            if response_model is not None:
                kwargs['response_format'] = {'type': 'json_object'}
            response = await self.client.chat.completions.create(**kwargs)

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
        llm_client = ThinkingAwareOpenAIClient(
            config=LLMConfig(
                api_key=Config.LLM_API_KEY,
                base_url=Config.LLM_BASE_URL,
                model=Config.LLM_MODEL_NAME,
            )
        )
        embedder = OpenAIEmbedder(
            config=OpenAIEmbedderConfig(
                api_key=Config.EMBEDDING_API_KEY,
                base_url=Config.EMBEDDING_BASE_URL,
                embedding_model=Config.EMBEDDING_MODEL,
            )
        )
        cross_encoder = OpenAIRerankerClient(
            config=LLMConfig(
                api_key=Config.LLM_API_KEY,
                base_url=Config.LLM_BASE_URL,
                model=Config.LLM_MODEL_NAME,
            )
        )
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

        self.node = GraphitiNodeClient(self._graphiti, self._driver)
        self.edge = GraphitiEdgeClient(self._driver)
        self.episode = GraphitiEpisodeClient()

    def create(self, graph_id: str, name: str = "", description: str = "") -> None:
        """No-op — Graphiti creates groups implicitly on first episode add."""
        pass

    def set_ontology(self, graph_ids: list, entities=None, edges=None) -> None:
        """No-op — Graphiti extracts ontology automatically from text."""
        pass

    def add(self, graph_id: str, type: str = "text", data: str = "") -> FakeEpisode:
        ep_uuid = str(uuid.uuid4())
        _run(self._graphiti.add_episode(
            name=f"episode_{ep_uuid[:8]}",
            episode_body=data,
            source=EpisodeType.text,
            source_description="MiroFish simulation activity",
            group_id=graph_id,
            reference_time=datetime.now(timezone.utc),
        ))
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
