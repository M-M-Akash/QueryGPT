import hashlib
import logging
from typing import Any

from langchain_ollama import OllamaEmbeddings
# pyrefly: ignore [missing-import]
from llama_index.core import Settings, VectorStoreIndex
from llama_index.core.schema import TextNode
from llama_index.embeddings.langchain import LangchainEmbedding
from llama_index.vector_stores.neo4jvector import Neo4jVectorStore
from neo4j import GraphDatabase

from app.config import settings

logger = logging.getLogger(__name__)

# Module-level singletons (initialised lazily via init_vectorstore)
_embeddings: OllamaEmbeddings | None = None
_neo4j_vector: Neo4jVectorStore | None = None
_retriever = None


def _get_embeddings() -> OllamaEmbeddings:
    global _embeddings
    if _embeddings is None:
        _embeddings = OllamaEmbeddings(
            model=settings.ollama_embed_model,
            base_url=settings.ollama_host,
        )
    return _embeddings


def _get_vector_store() -> Neo4jVectorStore:
    global _neo4j_vector
    if _neo4j_vector is None:
        _neo4j_vector = Neo4jVectorStore(
            username=settings.neo4j_username,
            password=settings.neo4j_password,
            url=settings.neo4j_url,
            embedding_dimension=settings.neo4j_embedding_dimension,
            hybrid_search=False,
        )
    return _neo4j_vector


def init_vectorstore() -> None:
    """Initialise the embedding model and vector store globally."""
    langchain_emb = _get_embeddings()
    llama_emb = LangchainEmbedding(langchain_emb)
    Settings.embed_model = llama_emb

    _get_vector_store()
    logger.info("Vector store initialised")


def _query_text(q: dict) -> str:
    return (
        f"Query: {q['natural_language']}\n"
        f"SQL: {q['sql']}\n"
        f"Description: {q['description']}\n"
    )


def _query_hash(q: dict) -> str:
    """Stable SHA-256 ID derived from the query content."""
    return hashlib.sha256(_query_text(q).encode()).hexdigest()


def _get_indexed_hashes() -> set[str]:
    """Return the content hashes of sample queries already indexed in Neo4j.

    Uses a dedicated ``sample_hash`` property stored in node metadata so
    deduplication is stable across code changes that may alter internal IDs.
    """
    driver = GraphDatabase.driver(
        settings.neo4j_url,
        auth=(settings.neo4j_username, settings.neo4j_password),
    )
    try:
        with driver.session() as session:
            result = session.run(
                "MATCH (n:Chunk) WHERE n.sample_hash IS NOT NULL "
                "RETURN n.sample_hash AS h"
            )
            return {record["h"] for record in result if record["h"]}
    finally:
        driver.close()


def index_sample_queries(sample_queries: list[dict], schema_info: dict[str, Any]) -> None:
    """Embed and index sample queries into Neo4j.

    Each query is identified by a deterministic SHA-256 hash of its text
    content, stored as the ``sample_hash`` node property.  Only queries
    not already present in the store are inserted, so this function is
    safe to call on every startup and correctly handles additions to the
    sample query list.
    """
    indexed_hashes = _get_indexed_hashes()

    new_queries = [
        q for q in sample_queries if _query_hash(q) not in indexed_hashes
    ]

    if not new_queries:
        logger.info("All %d sample queries already indexed, skipping", len(sample_queries))
        return

    emb = _get_embeddings()
    store = _get_vector_store()

    nodes = []
    for q in new_queries:
        text = _query_text(q)
        content_hash = _query_hash(q)
        embedding = emb.embed_query(text)
        nodes.append(
            TextNode(
                id_=content_hash,
                text=text,
                embedding=embedding,
                metadata={"sample_hash": content_hash},
            )
        )

    store.add(nodes)
    logger.info(
        "Indexed %d new sample queries (%d already existed)",
        len(new_queries),
        len(indexed_hashes),
    )


def get_retriever():
    """Return a retriever backed by Neo4j vector store."""
    global _retriever
    if _retriever is None:
        store = _get_vector_store()
        index = VectorStoreIndex.from_vector_store(store)
        _retriever = index.as_retriever(similarity_top_k=settings.similarity_top_k)
    return _retriever
