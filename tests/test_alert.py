"""Unit tests for alert parsing and notification."""

import pytest
from datetime import datetime

from app.models.alert import Alert, AlertLabel, AlertAnnotation, AlertmanagerWebhook
from app.alert.parser import build_alert_context, route_alert_query, parse_webhook


def make_alert(**kwargs) -> Alert:
    defaults = dict(
        status="firing",
        labels=AlertLabel(alertname="HighCPU", severity="warning", namespace="default"),
        annotations=AlertAnnotation(
            summary="CPU usage > 80%",
            description="Node node-01 CPU usage has been above 80% for 5 minutes",
        ),
        startsAt=datetime(2024, 1, 1, 12, 0, 0),
        fingerprint="abc123",
    )
    defaults.update(kwargs)
    return Alert(**defaults)


def test_build_alert_context_contains_key_fields():
    alert = make_alert()
    ctx = build_alert_context(alert)
    assert "HighCPU" in ctx
    assert "warning" in ctx
    assert "CPU usage > 80%" in ctx
    assert "2024-01-01" in ctx


def test_route_alert_query_includes_alertname():
    alert = make_alert()
    query = route_alert_query(alert)
    assert "HighCPU" in query


def test_parse_webhook_valid_payload():
    payload = {
        "version": "4",
        "status": "firing",
        "alerts": [
            {
                "status": "firing",
                "labels": {"alertname": "HighMemory", "severity": "critical"},
                "annotations": {"summary": "Memory > 90%"},
                "startsAt": "2024-01-01T12:00:00Z",
            }
        ],
    }
    webhook = parse_webhook(payload)
    assert len(webhook.alerts) == 1
    assert webhook.alerts[0].labels.alertname == "HighMemory"


def test_parse_webhook_resolved_alerts():
    payload = {
        "version": "4",
        "status": "resolved",
        "alerts": [
            {
                "status": "resolved",
                "labels": {"alertname": "HighCPU", "severity": "warning"},
                "annotations": {},
                "startsAt": "2024-01-01T12:00:00Z",
            }
        ],
    }
    webhook = parse_webhook(payload)
    assert webhook.alerts[0].status == "resolved"
