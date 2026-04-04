"""Prometheus Alertmanager webhook and alert handling routes."""

from fastapi import APIRouter, HTTPException, Body
from loguru import logger

from app.models.alert import AlertmanagerWebhook, DisposalRecord
from app.models.response import AlertDisposalResponse, ApprovalRequest
from app.alert.handler import handle_alert
from app.agent.approval import (
    resolve_approval,
    get_approval,
    list_pending,
)

router = APIRouter(tags=["alerts"])


@router.post("/alert", response_model=list[AlertDisposalResponse])
async def receive_alert(webhook: AlertmanagerWebhook):
    """
    Receive Alertmanager webhook (POST /alert).
    Processes each firing alert through RAG → suggestion → notification.
    """
    firing_alerts = [a for a in webhook.alerts if a.status == "firing"]
    if not firing_alerts:
        return []

    logger.info(f"Received {len(firing_alerts)} firing alert(s)")
    results = []
    for alert in firing_alerts:
        try:
            result = await handle_alert(alert)
            results.append(result)
        except Exception as e:
            logger.error(f"Failed to handle alert {alert.labels.alertname}: {e}")
            results.append(
                AlertDisposalResponse(
                    alert_fingerprint=alert.fingerprint or alert.labels.alertname,
                    alertname=alert.labels.alertname,
                    suggestion=f"处理失败: {e}",
                )
            )
    return results


@router.post("/approval/{action_id}")
async def approve_action(
    action_id: str,
    req: ApprovalRequest,
):
    """
    Human approval endpoint for high-risk agent actions.
    POST /approval/{action_id} with {approved: true/false, approver: "name"}
    """
    record = get_approval(action_id)
    if not record:
        raise HTTPException(status_code=404, detail=f"Approval request {action_id} not found")

    success = resolve_approval(
        action_id=action_id,
        approved=req.approved,
        approver=req.approver,
        comment=req.comment,
    )
    if not success:
        raise HTTPException(status_code=400, detail="Could not resolve approval")

    return {
        "action_id": action_id,
        "status": "approved" if req.approved else "rejected",
        "approver": req.approver,
    }


@router.get("/approval/pending")
async def list_pending_approvals():
    """List all pending high-risk action approvals."""
    return list_pending()
