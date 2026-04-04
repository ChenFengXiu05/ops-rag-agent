"""Document ingestion API routes."""

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from loguru import logger

from app.models.document import ChunkingStrategy, IngestResponse
from app.rag.document_loader import load_document_from_bytes
from app.rag.chunking import chunk_documents
from app.rag.vectorstore import add_documents

router = APIRouter(prefix="/documents", tags=["documents"])


@router.post("/ingest", response_model=IngestResponse)
async def ingest_document(
    file: UploadFile = File(...),
    chunking_strategy: ChunkingStrategy = Form(ChunkingStrategy.recursive),
    chunk_size: int = Form(512),
    chunk_overlap: int = Form(64),
    collection_name: str = Form("ops_knowledge"),
):
    """
    Upload and ingest a document (PDF, Markdown, TXT) into the knowledge base.
    Supports three chunking strategies: fixed, recursive, semantic.
    """
    content = await file.read()
    filename = file.filename or "unknown"

    if len(content) == 0:
        raise HTTPException(status_code=400, detail="Empty file uploaded")

    try:
        # 1. Load
        docs = load_document_from_bytes(content, filename)

        # 2. Chunk
        chunks = chunk_documents(
            docs,
            strategy=chunking_strategy.value,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )

        # 3. Store
        num_chunks = add_documents(chunks, collection_name=collection_name)

        return IngestResponse(
            status="success",
            file_name=filename,
            num_chunks=num_chunks,
            collection_name=collection_name,
            message=f"Ingested {num_chunks} chunks using {chunking_strategy.value} strategy",
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Ingestion failed for {filename}: {e}")
        raise HTTPException(status_code=500, detail=f"Ingestion failed: {e}")
