"""Unit tests for agent tools and approval workflow."""

import pytest
from unittest.mock import patch, MagicMock

from app.agent.approval import (
    create_approval_request,
    is_approved,
    resolve_approval,
    get_approval,
    list_pending,
)
from app.agent.tools.shell_tool import run_shell_command


# ── Approval workflow tests ───────────────────────────────────────────────────

def test_create_and_get_approval():
    action_id = create_approval_request(
        action="kubectl_delete",
        parameters={"resource": "pod", "name": "broken-pod"},
    )
    record = get_approval(action_id)
    assert record is not None
    assert record["status"] == "pending"
    assert record["action"] == "kubectl_delete"


def test_approval_not_approved_before_resolve():
    action_id = create_approval_request("test_action", {})
    assert not is_approved(action_id)


def test_approve_action():
    action_id = create_approval_request("kubectl_restart", {"pod": "my-pod"})
    resolve_approval(action_id, approved=True, approver="oncall-engineer", comment="OK")
    assert is_approved(action_id)


def test_reject_action():
    action_id = create_approval_request("kubectl_delete", {"pod": "important-pod"})
    resolve_approval(action_id, approved=False, approver="manager", comment="Too risky")
    assert not is_approved(action_id)
    record = get_approval(action_id)
    assert record["status"] == "rejected"


def test_list_pending_approvals():
    action_id = create_approval_request("shell_restart", {"cmd": "restart service"})
    pending = list_pending()
    assert any(p["action_id"] == action_id for p in pending)


# ── Shell tool security tests ─────────────────────────────────────────────────

def test_shell_blocked_rm():
    result = run_shell_command.invoke("rm -rf /tmp/test")
    assert "blocked" in result.lower() or "ERROR" in result


def test_shell_blocked_unlisted_command():
    result = run_shell_command.invoke("python3 -c 'print(1)'")
    assert "whitelist" in result.lower() or "ERROR" in result


def test_shell_high_risk_requires_approval():
    with patch("app.agent.tools.shell_tool.get_settings") as mock_settings:
        mock_settings.return_value.allowed_shell_commands = ["kubectl"]
        mock_settings.return_value.high_risk_ops = ["delete", "restart"]
        mock_settings.return_value.approval_webhook_url = "http://localhost/approval"
        result = run_shell_command.invoke("kubectl delete pod my-pod")
        assert "APPROVAL_REQUIRED" in result or "approval" in result.lower()
