"""Parse Alertmanager webhook payload into structured objects."""

from app.models.alert import Alert, AlertmanagerWebhook


def parse_webhook(payload: dict) -> AlertmanagerWebhook:
    """Validate and parse raw webhook dict."""
    return AlertmanagerWebhook(**payload)


def build_alert_context(alert: Alert) -> str:
    """Convert an Alert into a plain-text context block for the LLM prompt."""
    lines = [
        f"告警名称: {alert.labels.alertname}",
        f"严重级别: {alert.labels.severity}",
        f"状态: {alert.status}",
        f"触发时间: {alert.startsAt.strftime('%Y-%m-%d %H:%M:%S UTC')}",
    ]
    if alert.labels.namespace:
        lines.append(f"命名空间: {alert.labels.namespace}")
    if alert.labels.pod:
        lines.append(f"Pod: {alert.labels.pod}")
    if alert.labels.node:
        lines.append(f"节点: {alert.labels.node}")
    if alert.annotations.summary:
        lines.append(f"摘要: {alert.annotations.summary}")
    if alert.annotations.description:
        lines.append(f"描述: {alert.annotations.description}")
    if alert.annotations.runbook_url:
        lines.append(f"Runbook: {alert.annotations.runbook_url}")

    # Extra labels
    extra = {k: v for k, v in alert.labels.model_extra.items()} if alert.labels.model_extra else {}
    for k, v in extra.items():
        lines.append(f"{k}: {v}")

    return "\n".join(lines)


def route_alert_query(alert: Alert) -> str:
    """Build a search query from the alert for knowledge base retrieval."""
    parts = [alert.labels.alertname]
    if alert.annotations.summary:
        parts.append(alert.annotations.summary)
    if alert.labels.namespace:
        parts.append(alert.labels.namespace)
    return " ".join(parts)
