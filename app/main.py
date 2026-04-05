"""FastAPI application entry point."""

import os
import time

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from loguru import logger
from prometheus_client import Counter, Histogram, make_asgi_app

from app.core.config import get_settings
from app.core.logging import setup_logging
from app.models.response import HealthResponse
from app.api.routes import ask, alert, documents, evaluation, agent

# ── Bootstrap ────────────────────────────────────────────────────────────────
os.makedirs("logs", exist_ok=True)
os.makedirs("data", exist_ok=True)
setup_logging()

settings = get_settings()

# ── Prometheus metrics ────────────────────────────────────────────────────────
REQUEST_COUNT = Counter(
    "http_requests_total", "Total HTTP requests", ["method", "endpoint", "status"]
)
REQUEST_LATENCY = Histogram(
    "http_request_duration_seconds", "HTTP request latency", ["endpoint"]
)
RAG_QUERY_COUNT = Counter("rag_queries_total", "Total RAG queries")
ALERT_COUNT = Counter("alerts_received_total", "Total alerts received", ["alertname", "severity"])

# ── App ───────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="运维智能化 RAG Agent",
    description=(
        "面向运维场景的智能 RAG Agent 平台。\n\n"
        "**功能**：知识库问答 · 告警自动处置 · Agent工具调用 · RAGAS评估\n\n"
        "**技术栈**：LangChain · LangGraph · BGE · ChromaDB · FastAPI"
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Expose Prometheus metrics at /metrics
metrics_app = make_asgi_app()
app.mount("/metrics", metrics_app)


@app.middleware("http")
async def metrics_middleware(request: Request, call_next):
    start = time.time()
    response = await call_next(request)
    latency = time.time() - start
    endpoint = request.url.path
    REQUEST_COUNT.labels(
        method=request.method,
        endpoint=endpoint,
        status=response.status_code,
    ).inc()
    REQUEST_LATENCY.labels(endpoint=endpoint).observe(latency)
    return response


# ── Routes ────────────────────────────────────────────────────────────────────
API_PREFIX = "/api/v1"
app.include_router(ask.router, prefix=API_PREFIX)
app.include_router(alert.router, prefix=API_PREFIX)
app.include_router(documents.router, prefix=API_PREFIX)
app.include_router(evaluation.router, prefix=API_PREFIX)
app.include_router(agent.router, prefix=API_PREFIX)


@app.get("/health", response_model=HealthResponse, tags=["health"])
async def health_check():
    """Health check endpoint for K8s liveness/readiness probes."""
    return HealthResponse(
        status="ok",
        vector_store=settings.vector_store,
        llm_provider=settings.llm_provider,
    )


@app.get("/ui", tags=["ui"], include_in_schema=False)
async def chat_ui():
    """Serve the chat UI single page."""
    import pathlib
    ui_path = pathlib.Path(__file__).parent / "static" / "index.html"
    return FileResponse(str(ui_path), media_type="text/html")


@app.get("/", tags=["health"])
async def root():
    return {"message": "运维智能化 RAG Agent — see /docs or /ui for the chat interface"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.app_host,
        port=settings.app_port,
        reload=settings.app_env == "development",
        log_level=settings.log_level.lower(),
    )
