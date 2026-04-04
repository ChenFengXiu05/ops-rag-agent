"""Pydantic models for document ingestion."""

from enum import Enum
from pydantic import BaseModel, Field


class ChunkingStrategy(str, Enum):
    fixed = "fixed"
    recursive = "recursive"
    semantic = "semantic"


class IngestRequest(BaseModel):
    chunking_strategy: ChunkingStrategy = ChunkingStrategy.recursive
    chunk_size: int = Field(default=512, ge=64, le=4096)
    chunk_overlap: int = Field(default=64, ge=0, le=512)
    collection_name: str = Field(default="ops_knowledge", min_length=1)


class IngestResponse(BaseModel):
    status: str
    file_name: str
    num_chunks: int
    collection_name: str
    message: str = ""


class DocumentChunk(BaseModel):
    chunk_id: str
    content: str
    metadata: dict = {}
