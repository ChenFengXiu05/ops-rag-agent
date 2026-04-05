"""Pydantic models for Prometheus Alertmanager webhook."""

from datetime import datetime, timezone
from typing import Any
from pydantic import BaseModel, ConfigDict, Field


class AlertLabel(BaseModel):
    model_config = ConfigDict(extra="allow")

    alertname: str
    severity: str = "warning"
    namespace: str = ""
    pod: str = ""
    node: str = ""
    job: str = ""


class AlertAnnotation(BaseModel):
    model_config = ConfigDict(extra="allow")

    summary: str = ""
    description: str = ""
    runbook_url: str = ""


class Alert(BaseModel):
    status: str  # firing | resolved
    labels: AlertLabel
    annotations: AlertAnnotation
    startsAt: datetime
    endsAt: datetime | None = None
    generatorURL: str = ""
    fingerprint: str = ""


class AlertmanagerWebhook(BaseModel):
    """Standard Alertmanager webhook payload."""
    version: str = "4"
    groupKey: str = ""
    truncatedAlerts: int = 0
    status: str  # firing | resolved
    receiver: str = ""
    groupLabels: dict[str, str] = {}
    commonLabels: dict[str, str] = {}
    commonAnnotations: dict[str, str] = {}
    externalURL: str = ""
    alerts: list[Alert] = []


class DisposalRecord(BaseModel):
    """Record of an alert disposal action."""
    alert_fingerprint: str
    alertname: str
    severity: str
    triggered_at: datetime
    retrieved_docs: list[str] = []
    suggestion: str = ""
    executed_actions: list[dict[str, Any]] = []
    human_rating: int | None = None  # 1-5
    human_feedback: str = ""
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
