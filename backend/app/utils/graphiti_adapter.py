"""
Graphiti adapter — wraps graphiti-core async API in sync interface
compatible with the existing Zep Cloud usage patterns.
"""
import asyncio
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from graphiti_core import Graphiti
from graphiti_core.nodes import EpisodeType
from graphiti_core.llm_client.openai_client import OpenAIClient
from graphiti_core.llm_client.config import LLMConfig
from graphiti_core.embedder.openai import OpenAIEmbedder, OpenAIEmbedderConfig
from graphiti_core.cross_encoder.openai_reranker_client import OpenAIRerankerClient
from neo4j import GraphDatabase

from ..config import Config


def _run(coro):
    """Run async coroutine from sync context."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = pool.submit(asyncio.run, coro)
                return future.result()
        return loop.run_until_complete(coro)
    except RuntimeError:
        return asyncio.run(coro)


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


@dataclass
class FakeEpisode:
    uuid_: str
    processed: bool = True


@dataclass
class FakeSearchResult:
    edges: list
    nodes: list


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
            props = dict(node.items())
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
                props = dict(rel.items())
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
                props = dict(node.items())
                nodes.append(FakeNode(
                    uuid_=props.get("uuid", str(uuid.uuid4())),
                    name=props.get("name", "Unknown"),
                    labels=list(node.labels),
                    summary=props.get("summary", ""),
                    attributes=props
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
                props = dict(rel.items())
                edges.append(FakeEdge(
                    uuid_=props.get("uuid", str(uuid.uuid4())),
                    name=props.get("name", ""),
                    fact=props.get("fact", ""),
                    source_node_uuid=record["src"],
                    target_node_uuid=record["tgt"],
                    created_at=props.get("created_at"),
                    expired_at=props.get("expired_at"),
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
        llm_client = OpenAIClient(
            config=LLMConfig(
                api_key=Config.LLM_API_KEY,
                base_url=Config.LLM_BASE_URL,
                model=Config.LLM_MODEL_NAME,
            )
        )
        embedder = OpenAIEmbedder(
            config=OpenAIEmbedderConfig(
                api_key=Config.LLM_API_KEY,
                base_url=Config.LLM_BASE_URL,
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
