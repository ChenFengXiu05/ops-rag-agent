"""Embedding model factory: BGE (local) or OpenAI."""

from functools import lru_cache
from langchain_core.embeddings import Embeddings
from loguru import logger


@lru_cache(maxsize=1)
def get_embeddings() -> Embeddings:
    from app.core.config import get_settings
    settings = get_settings()

    if settings.embedding_provider == "openai":
        from langchain_openai import OpenAIEmbeddings
        logger.info("Using OpenAI embeddings")
        return OpenAIEmbeddings(
            model="text-embedding-ada-002",
            openai_api_key=settings.openai_api_key,
        )
    else:
        # BGE large zh — best for Chinese ops documents
        from langchain_community.embeddings import HuggingFaceEmbeddings
        logger.info(f"Loading BGE model: {settings.bge_model_name}")
        return HuggingFaceEmbeddings(
            model_name=settings.bge_model_name,
            model_kwargs={"device": "cpu"},
            encode_kwargs={"normalize_embeddings": True},
        )
