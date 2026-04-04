"""Common API response models."""

from typing import Any
from pydantic import BaseModel


class AskRequest(BaseModel):
    question: str
    collection_name: str = "ops_knowledge"
    top_k: int = 5
    use_reranker: bool = False
    chat_history: list[dict[str, str]] = []


class SourceDocument(BaseModel):
    content: str
    metadata: dict[str, Any] = {}
    score: float = 0.0


class AskResponse(BaseModel):
    answer: str
    sources: list[SourceDocument] = []
    tokens_used: int = 0
    latency_ms: float = 0.0


class AlertDisposalResponse(BaseModel):
    alert_fingerprint: str
    alertname: str
    suggestion: str
    retrieved_docs: list[str] = []
    notification_sent: bool = False
    requires_approval: bool = False
    approval_url: str = ""


class ApprovalRequest(BaseModel):
    action_id: str
    approved: bool
    approver: str = ""
    comment: str = ""


class HealthResponse(BaseModel):
    status: str
    vector_store: str
    llm_provider: str
    version: str = "1.0.0"
