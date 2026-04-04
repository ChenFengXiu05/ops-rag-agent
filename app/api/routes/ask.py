"""Q&A and agent query routes."""

from fastapi import APIRouter, HTTPException
from loguru import logger

from app.models.response import AskRequest, AskResponse
from app.rag.qa_chain import answer_question

router = APIRouter(prefix="/ask", tags=["qa"])


@router.post("", response_model=AskResponse)
async def ask(req: AskRequest):
    """
    Ask a question against the ops knowledge base.
    Supports optional reranker (use_reranker=true) for Phase 4.
    """
    if not req.question.strip():
        raise HTTPException(status_code=400, detail="question must not be empty")

    try:
        return await answer_question(req)
    except Exception as e:
        logger.error(f"Q&A failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
