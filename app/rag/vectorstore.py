"""Vector store abstraction: ChromaDB (dev) or Milvus (prod)."""

from functools import lru_cache
from typing import Any

from langchain_core.documents import Document
from langchain_core.vectorstores import VectorStore
from loguru import logger

from app.rag.embeddings import get_embeddings


def get_vectorstore(collection_name: str = "ops_knowledge") -> VectorStore:
    """Return a vector store instance for the given collection."""
    from app.core.config import get_settings
    settings = get_settings()

    embeddings = get_embeddings()

    if settings.vector_store == "milvus":
        return _get_milvus(collection_name, embeddings, settings)
    else:
        return _get_chroma(collection_name, embeddings, settings)


def _get_chroma(collection_name: str, embeddings: Any, settings: Any) -> VectorStore:
    import os
    from langchain_community.vectorstores import Chroma
    os.makedirs(settings.chroma_persist_dir, exist_ok=True)
    logger.info(f"Using ChromaDB at {settings.chroma_persist_dir}, collection={collection_name}")
    return Chroma(
        collection_name=collection_name,
        embedding_function=embeddings,
        persist_directory=settings.chroma_persist_dir,
    )


def _get_milvus(collection_name: str, embeddings: Any, settings: Any) -> VectorStore:
    from langchain_community.vectorstores import Milvus
    logger.info(f"Using Milvus at {settings.milvus_host}:{settings.milvus_port}")
    return Milvus(
        embedding_function=embeddings,
        collection_name=collection_name,
        connection_args={
            "host": settings.milvus_host,
            "port": settings.milvus_port,
        },
    )


def add_documents(
    docs: list[Document],
    collection_name: str = "ops_knowledge",
) -> int:
    """Add chunked documents to the vector store. Returns number of added chunks."""
    vs = get_vectorstore(collection_name)
    ids = vs.add_documents(docs)
    logger.info(f"Added {len(ids)} chunks to collection '{collection_name}'")
    return len(ids)


def similarity_search(
    query: str,
    collection_name: str = "ops_knowledge",
    top_k: int = 5,
) -> list[Document]:
    """Retrieve top-k similar documents for a query."""
    vs = get_vectorstore(collection_name)
    docs = vs.similarity_search(query, k=top_k)
    return docs


def similarity_search_with_score(
    query: str,
    collection_name: str = "ops_knowledge",
    top_k: int = 5,
) -> list[tuple[Document, float]]:
    """Retrieve top-k docs with relevance scores."""
    vs = get_vectorstore(collection_name)
    return vs.similarity_search_with_relevance_scores(query, k=top_k)
