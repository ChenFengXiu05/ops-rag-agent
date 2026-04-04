"""kubectl tool for the ops agent."""

import subprocess
from langchain_core.tools import tool
from loguru import logger

from app.core.config import get_settings

_SAFE_KUBECTL_VERBS = {
    "get", "describe", "logs", "top", "explain",
    "rollout", "status", "history",
}


@tool
def kubectl_get(resource: str, namespace: str = "default", extra_args: str = "") -> str:
    """
    Run `kubectl get <resource>` in a namespace.
    Example: kubectl_get("pods", namespace="kube-system")
    """
    cmd = ["kubectl", "get", resource, "-n", namespace, "--output=wide"]
    if extra_args:
        cmd += extra_args.split()
    return _run_kubectl(cmd)


@tool
def kubectl_describe(resource: str, name: str, namespace: str = "default") -> str:
    """
    Run `kubectl describe <resource> <name>` for detailed info.
    Example: kubectl_describe("pod", "my-pod-xxx", namespace="default")
    """
    cmd = ["kubectl", "describe", resource, name, "-n", namespace]
    return _run_kubectl(cmd)


@tool
def kubectl_logs(pod: str, namespace: str = "default", tail: int = 100, container: str = "") -> str:
    """
    Fetch logs from a pod. Returns last `tail` lines.
    Example: kubectl_logs("my-pod-xxx", namespace="default", tail=200)
    """
    cmd = ["kubectl", "logs", pod, "-n", namespace, f"--tail={tail}"]
    if container:
        cmd += ["-c", container]
    return _run_kubectl(cmd)


def _run_kubectl(cmd: list[str]) -> str:
    settings = get_settings()
    # Safety: only allow safe verbs
    if len(cmd) >= 2 and cmd[1] not in _SAFE_KUBECTL_VERBS:
        verb = cmd[1]
        if any(hrc in verb for hrc in settings.high_risk_ops):
            return f"ERROR: verb '{verb}' requires human approval via the approval workflow."

    logger.info(f"kubectl exec: {' '.join(cmd)}")
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30,
        )
        output = result.stdout or result.stderr
        return output[:4000]  # cap output length
    except subprocess.TimeoutExpired:
        return "ERROR: kubectl command timed out after 30s"
    except FileNotFoundError:
        return "ERROR: kubectl not found in PATH"
    except Exception as e:
        return f"ERROR: {e}"
