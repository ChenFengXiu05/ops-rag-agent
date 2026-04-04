"""Pytest configuration and shared fixtures."""

import os
import pytest
from fastapi.testclient import TestClient

# Use test environment settings
os.environ.setdefault("ANTHROPIC_API_KEY", "test-key")
os.environ.setdefault("LLM_PROVIDER", "claude")
os.environ.setdefault("VECTOR_STORE", "chroma")
os.environ.setdefault("CHROMA_PERSIST_DIR", "/tmp/test_chroma")
os.environ.setdefault("APP_ENV", "development")


@pytest.fixture(scope="session")
def client():
    """FastAPI test client."""
    from app.main import app
    return TestClient(app)


@pytest.fixture
def sample_alert_payload():
    return {
        "version": "4",
        "status": "firing",
        "receiver": "ops-agent",
        "alerts": [
            {
                "status": "firing",
                "labels": {
                    "alertname": "HighCPUUsage",
                    "severity": "warning",
                    "namespace": "production",
                    "node": "node-01",
                },
                "annotations": {
                    "summary": "CPU usage exceeded 80%",
                    "description": "Node node-01 has CPU > 80% for the past 5 minutes.",
                },
                "startsAt": "2024-01-15T10:30:00Z",
                "fingerprint": "test-fp-001",
            }
        ],
    }
