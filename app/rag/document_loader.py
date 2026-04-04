"""Document loaders for PDF, Markdown, and TXT files."""

from pathlib import Path
from typing import BinaryIO

from langchain_community.document_loaders import (
    PyPDFLoader,
    TextLoader,
    UnstructuredMarkdownLoader,
)
from langchain_core.documents import Document
from loguru import logger


SUPPORTED_EXTENSIONS = {".pdf", ".md", ".txt", ".markdown"}


def load_document(file_path: str | Path) -> list[Document]:
    """Load a document from disk and return raw LangChain Document objects."""
    path = Path(file_path)
    ext = path.suffix.lower()

    if ext not in SUPPORTED_EXTENSIONS:
        raise ValueError(f"Unsupported file type: {ext}. Supported: {SUPPORTED_EXTENSIONS}")

    logger.info(f"Loading document: {path.name} ({ext})")

    if ext == ".pdf":
        loader = PyPDFLoader(str(path))
    elif ext in (".md", ".markdown"):
        loader = UnstructuredMarkdownLoader(str(path))
    else:  # .txt
        loader = TextLoader(str(path), encoding="utf-8")

    docs = loader.load()

    # Enrich metadata
    for doc in docs:
        doc.metadata["source"] = str(path)
        doc.metadata["file_name"] = path.name
        doc.metadata["file_type"] = ext

    logger.info(f"Loaded {len(docs)} raw pages/sections from {path.name}")
    return docs


def load_document_from_bytes(content: bytes, filename: str) -> list[Document]:
    """Load a document from in-memory bytes (for file upload endpoints)."""
    import tempfile
    suffix = Path(filename).suffix.lower()
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(content)
        tmp_path = tmp.name
    docs = load_document(tmp_path)
    # Replace temp path with original filename in metadata
    for doc in docs:
        doc.metadata["source"] = filename
        doc.metadata["file_name"] = filename
    Path(tmp_path).unlink(missing_ok=True)
    return docs
