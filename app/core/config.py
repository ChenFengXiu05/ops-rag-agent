"""Application configuration via pydantic-settings."""

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── LLM ──────────────────────────────────────────────────────────────
    anthropic_api_key: str = ""
    openai_api_key: str = ""
    llm_provider: Literal["claude", "openai"] = "claude"
    llm_model: str = "claude-opus-4-6"
    llm_temperature: float = 0.0
    llm_max_tokens: int = 4096

    # ── Embedding ─────────────────────────────────────────────────────────
    embedding_provider: Literal["bge", "openai"] = "bge"
    bge_model_name: str = "BAAI/bge-large-zh-v1.5"
    bge_reranker_model: str = "BAAI/bge-reranker-v2-m3"

    # ── Vector Store ──────────────────────────────────────────────────────
    vector_store: Literal["chroma", "milvus"] = "chroma"
    chroma_persist_dir: str = "./data/chroma"
    milvus_host: str = "localhost"
    milvus_port: int = 19530
    milvus_collection: str = "ops_knowledge"

    # ── RAG ───────────────────────────────────────────────────────────────
    retrieval_top_k: int = 5
    reranker_top_k: int = 3
    chunk_size: int = 512
    chunk_overlap: int = 64
    # Options: fixed, recursive, semantic
    chunking_strategy: str = "recursive"

    # ── Elasticsearch ─────────────────────────────────────────────────────
    es_host: str = "http://localhost:9200"
    es_username: str = "elastic"
    es_password: str = "changeme"
    es_index_pattern: str = "logs-*"

    # ── Prometheus ────────────────────────────────────────────────────────
    prometheus_url: str = "http://localhost:9090"

    # ── Notification ──────────────────────────────────────────────────────
    dingtalk_webhook: str = ""
    dingtalk_secret: str = ""
    wechat_webhook: str = ""

    # ── LangSmith ─────────────────────────────────────────────────────────
    langchain_tracing_v2: bool = False
    langchain_api_key: str = ""
    langchain_project: str = "ops-rag-agent"

    # ── App ───────────────────────────────────────────────────────────────
    app_env: Literal["development", "production"] = "development"
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    log_level: str = "INFO"

    # ── Security ──────────────────────────────────────────────────────────
    shell_command_whitelist: str = "kubectl,helm,df,free,top,ps,netstat,ss,ping"
    high_risk_commands: str = "delete,restart,scale,rollout,apply,patch"
    approval_webhook_url: str = "http://localhost:8000/api/v1/approval"

    @property
    def allowed_shell_commands(self) -> list[str]:
        return [c.strip() for c in self.shell_command_whitelist.split(",") if c.strip()]

    @property
    def high_risk_ops(self) -> list[str]:
        return [c.strip() for c in self.high_risk_commands.split(",") if c.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
