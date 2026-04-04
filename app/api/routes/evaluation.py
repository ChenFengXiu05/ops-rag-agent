"""RAGAS evaluation API routes."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

from app.evaluation.ragas_eval import run_evaluation

router = APIRouter(prefix="/evaluation", tags=["evaluation"])


class EvalRequest(BaseModel):
    questions: list[str]
    answers: list[str]
    contexts: list[list[str]]
    ground_truths: Optional[list[str]] = None
    output_path: str = "./data/ragas_report.json"


@router.post("/ragas")
async def evaluate_rag(req: EvalRequest):
    """
    Run RAGAS evaluation on provided Q&A samples.
    Phase 1: faithfulness + answer_relevancy
    Phase 4: + context_precision + context_recall (requires ground_truths)
    """
    if len(req.questions) != len(req.answers) or len(req.questions) != len(req.contexts):
        raise HTTPException(
            status_code=400,
            detail="questions, answers, and contexts must have the same length"
        )
    result = run_evaluation(
        questions=req.questions,
        answers=req.answers,
        contexts=req.contexts,
        ground_truths=req.ground_truths,
        output_path=req.output_path,
    )
    if "error" in result:
        raise HTTPException(status_code=500, detail=result["error"])
    return result
