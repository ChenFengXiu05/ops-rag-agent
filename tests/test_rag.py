"""Unit tests for RAG pipeline."""

import pytest
from unittest.mock import MagicMock, patch
from langchain_core.documents import Document

from app.rag.chunking import chunk_fixed, chunk_recursive, chunk_documents
from app.rag.document_loader import load_document_from_bytes


# ── Chunking tests ────────────────────────────────────────────────────────────

def make_docs(text: str) -> list[Document]:
    return [Document(page_content=text, metadata={"source": "test.txt"})]


def test_chunk_fixed_basic():
    docs = make_docs("A" * 1024)
    chunks = chunk_fixed(docs, chunk_size=256, chunk_overlap=0)
    assert len(chunks) >= 1
    for c in chunks:
        assert len(c.page_content) <= 300  # some tolerance for splitter


def test_chunk_recursive_preserves_metadata():
    docs = make_docs("第一段\n\n第二段\n\n第三段")
    chunks = chunk_recursive(docs, chunk_size=10, chunk_overlap=0)
    assert all(c.metadata["source"] == "test.txt" for c in chunks)


def test_chunk_documents_strategy_dispatch():
    docs = make_docs("测试文档内容 " * 100)
    for strategy in ("fixed", "recursive"):
        chunks = chunk_documents(docs, strategy=strategy, chunk_size=50, chunk_overlap=0)
        assert len(chunks) > 0


def test_chunk_documents_unknown_strategy_falls_back():
    docs = make_docs("Some content")
    chunks = chunk_documents(docs, strategy="unknown_strategy")
    assert len(chunks) > 0


# ── Document loader tests ────────────────────────────────────────────────────

def test_load_txt_from_bytes():
    content = b"This is a test runbook.\nStep 1: Check pod status"
    docs = load_document_from_bytes(content, "test.txt")
    assert len(docs) > 0
    assert "test.txt" in docs[0].metadata["file_name"]


def test_load_unsupported_format_raises():
    with pytest.raises(ValueError, match="Unsupported file type"):
        load_document_from_bytes(b"content", "test.xlsx")


def test_load_markdown_from_bytes():
    md_content = b"# Title\n\n## Section\n\nSome text here."
    docs = load_document_from_bytes(md_content, "runbook.md")
    assert len(docs) > 0
