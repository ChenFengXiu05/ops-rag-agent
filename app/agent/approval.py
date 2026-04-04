"""Human approval node for high-risk agent actions."""

import uuid
from datetime import datetime, timedelta
from typing import Any

from loguru import logger

# In-memory approval store (use Redis/DB in production)
_pending_approvals: dict[str, dict[str, Any]] = {}


def create_approval_request(
    action: str,
    parameters: dict,
    alert_context: str = "",
    ttl_minutes: int = 30,
) -> str:
    """
    Register a pending high-risk action and return an approval ID.
    The agent must pause and wait for /api/v1/approval/{action_id} to be called.
    """
    action_id = str(uuid.uuid4())
    _pending_approvals[action_id] = {
        "action_id": action_id,
        "action": action,
        "parameters": parameters,
        "alert_context": alert_context,
        "status": "pending",  # pending | approved | rejected
        "created_at": datetime.utcnow().isoformat(),
        "expires_at": (datetime.utcnow() + timedelta(minutes=ttl_minutes)).isoformat(),
        "approver": None,
        "comment": "",
    }
    logger.warning(f"Approval required for action '{action}' — ID: {action_id}")
    return action_id


def get_approval(action_id: str) -> dict | None:
    return _pending_approvals.get(action_id)


def resolve_approval(action_id: str, approved: bool, approver: str, comment: str) -> bool:
    """Mark an approval as approved or rejected."""
    record = _pending_approvals.get(action_id)
    if not record:
        return False
    record["status"] = "approved" if approved else "rejected"
    record["approver"] = approver
    record["comment"] = comment
    logger.info(f"Approval {action_id}: {'APPROVED' if approved else 'REJECTED'} by {approver}")
    return True


def is_approved(action_id: str) -> bool:
    record = _pending_approvals.get(action_id)
    if not record:
        return False
    # Check expiry
    expires = datetime.fromisoformat(record["expires_at"])
    if datetime.utcnow() > expires:
        record["status"] = "expired"
        return False
    return record["status"] == "approved"


def list_pending() -> list[dict]:
    now = datetime.utcnow()
    return [
        r for r in _pending_approvals.values()
        if r["status"] == "pending"
        and datetime.fromisoformat(r["expires_at"]) > now
    ]
