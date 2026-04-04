"""Agent execution routes."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from loguru import logger

from app.agent.graph import run_agent

router = APIRouter(prefix="/agent", tags=["agent"])


class AgentRequest(BaseModel):
    question: str
    alert_context: str = ""


class AgentResponse(BaseModel):
    answer: str
    requires_approval: bool = False
    approval_id: str = ""
    action_count: int = 0


@router.post("/run", response_model=AgentResponse)
async def run_ops_agent(req: AgentRequest):
    """
    Run the LangGraph ops agent with tool-calling capability.
    The agent can invoke kubectl, query ES logs, run PromQL, and execute whitelisted shell commands.
    High-risk operations will be paused pending human approval.
    """
    if not req.question.strip():
        raise HTTPException(status_code=400, detail="question must not be empty")

    try:
        result = await run_agent(
            question=req.question,
            alert_context=req.alert_context,
        )
        return AgentResponse(**result)
    except Exception as e:
        logger.error(f"Agent execution failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
