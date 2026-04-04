"""Three chunking strategies: fixed-size, recursive, and semantic."""

from langchain_core.documents import Document
from langchain_text_splitters import (
    CharacterTextSplitter,
    RecursiveCharacterTextSplitter,
)
from loguru import logger


def chunk_fixed(
    docs: list[Document],
    chunk_size: int = 512,
    chunk_overlap: int = 64,
) -> list[Document]:
    """Fixed-size character chunking."""
    splitter = CharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separator="\n",
    )
    chunks = splitter.split_documents(docs)
    logger.info(f"Fixed chunking: {len(docs)} docs → {len(chunks)} chunks")
    return chunks


def chunk_recursive(
    docs: list[Document],
    chunk_size: int = 512,
    chunk_overlap: int = 64,
) -> list[Document]:
    """Recursive character text splitting — best for mixed structured docs."""
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=["\n\n", "\n", "。", "！", "？", "；", " ", ""],
    )
    chunks = splitter.split_documents(docs)
    logger.info(f"Recursive chunking: {len(docs)} docs → {len(chunks)} chunks")
    return chunks


def chunk_semantic(
    docs: list[Document],
    chunk_size: int = 512,
    chunk_overlap: int = 64,
) -> list[Document]:
    """
    Semantic chunking using sentence-transformers similarity.
    Falls back to recursive if dependencies are unavailable.
    """
    try:
        from langchain_experimental.text_splitter import SemanticChunker
        from langchain_community.embeddings import HuggingFaceEmbeddings

        embeddings = HuggingFaceEmbeddings(model_name="BAAI/bge-large-zh-v1.5")
        splitter = SemanticChunker(
            embeddings=embeddings,
            breakpoint_threshold_type="percentile",
            breakpoint_threshold_amount=95,
        )
        chunks = splitter.split_documents(docs)
        logger.info(f"Semantic chunking: {len(docs)} docs → {len(chunks)} chunks")
        return chunks
    except ImportError:
        logger.warning("langchain_experimental not available, falling back to recursive chunking")
        return chunk_recursive(docs, chunk_size, chunk_overlap)


def chunk_documents(
    docs: list[Document],
    strategy: str = "recursive",
    chunk_size: int = 512,
    chunk_overlap: int = 64,
) -> list[Document]:
    """Dispatch to the chosen chunking strategy."""
    strategy = strategy.lower()
    if strategy == "fixed":
        return chunk_fixed(docs, chunk_size, chunk_overlap)
    elif strategy == "semantic":
        return chunk_semantic(docs, chunk_size, chunk_overlap)
    else:
        return chunk_recursive(docs, chunk_size, chunk_overlap)
