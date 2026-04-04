"""Shell execution tool with strict whitelist enforcement."""

import shlex
import subprocess
from langchain_core.tools import tool
from loguru import logger

from app.core.config import get_settings

# Hard-coded dangerous patterns that are NEVER allowed
_HARD_BLOCKED = {
    "rm", "mkfs", "dd", "shred", "chmod", "chown",
    "wget", "curl",  # prevent data exfiltration
    "nc", "ncat", "socat",  # reverse shells
    ">", ">>", "|",  # redirect/pipe (in args context)
}


@tool
def run_shell_command(command: str) -> str:
    """
    Execute a whitelisted shell command for diagnostics.
    Only commands in SHELL_COMMAND_WHITELIST env var are permitted.
    High-risk operations require human approval.

    Args:
        command: Full command string, e.g. 'kubectl get nodes'
    Returns:
        Command stdout/stderr output (max 3000 chars)
    """
    settings = get_settings()

    try:
        parts = shlex.split(command)
    except ValueError as e:
        return f"ERROR: Invalid command syntax: {e}"

    if not parts:
        return "ERROR: Empty command"

    base_cmd = parts[0].split("/")[-1]  # strip path components

    # Hard block dangerous commands
    if base_cmd in _HARD_BLOCKED:
        return f"ERROR: Command '{base_cmd}' is permanently blocked for security reasons."

    # Whitelist check
    if base_cmd not in settings.allowed_shell_commands:
        return (
            f"ERROR: '{base_cmd}' is not in the allowed command whitelist. "
            f"Allowed: {settings.allowed_shell_commands}"
        )

    # High-risk keyword check
    cmd_str_lower = command.lower()
    for hrc in settings.high_risk_ops:
        if hrc in cmd_str_lower:
            return (
                f"APPROVAL_REQUIRED: Command contains high-risk operation '{hrc}'. "
                f"Please use the approval workflow to authorize: {settings.approval_webhook_url}"
            )

    logger.info(f"Shell exec: {command}")
    try:
        result = subprocess.run(
            parts,
            capture_output=True,
            text=True,
            timeout=60,
        )
        output = (result.stdout + result.stderr).strip()
        return output[:3000] if output else "(no output)"
    except subprocess.TimeoutExpired:
        return "ERROR: Command timed out after 60s"
    except FileNotFoundError:
        return f"ERROR: Command '{base_cmd}' not found in PATH"
    except Exception as e:
        return f"ERROR: {e}"
