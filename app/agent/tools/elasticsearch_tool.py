"""Elasticsearch log query tool."""

from langchain_core.tools import tool
from loguru import logger

from app.core.config import get_settings


@tool
def query_logs(
    query: str,
    index_pattern: str = "",
    time_range: str = "15m",
    size: int = 20,
    namespace: str = "",
    pod: str = "",
) -> str:
    """
    Query Elasticsearch for log entries.
    Args:
        query: Full-text search string or Lucene query
        index_pattern: ES index pattern (default from config)
        time_range: e.g. '15m', '1h', '24h'
        size: Max number of log lines to return
        namespace: Filter by Kubernetes namespace label
        pod: Filter by pod name label
    """
    settings = get_settings()
    index = index_pattern or settings.es_index_pattern

    try:
        from elasticsearch import Elasticsearch
        es = Elasticsearch(
            settings.es_host,
            basic_auth=(settings.es_username, settings.es_password),
            verify_certs=False,
        )

        must_clauses: list = [
            {"query_string": {"query": query}},
            {"range": {"@timestamp": {"gte": f"now-{time_range}", "lte": "now"}}},
        ]
        if namespace:
            must_clauses.append({"term": {"kubernetes.namespace_name": namespace}})
        if pod:
            must_clauses.append({"term": {"kubernetes.pod_name": pod}})

        es_query = {
            "query": {"bool": {"must": must_clauses}},
            "sort": [{"@timestamp": {"order": "desc"}}],
            "size": size,
            "_source": ["@timestamp", "log", "message", "kubernetes.pod_name",
                        "kubernetes.namespace_name", "level"],
        }

        resp = es.search(index=index, body=es_query)
        hits = resp["hits"]["hits"]
        if not hits:
            return f"No logs found for query: '{query}' in last {time_range}"

        lines = []
        for hit in hits:
            src = hit["_source"]
            ts = src.get("@timestamp", "")
            pod_name = src.get("kubernetes", {}).get("pod_name", "-")
            msg = src.get("log") or src.get("message") or ""
            lines.append(f"[{ts}] [{pod_name}] {msg}")

        return "\n".join(lines)

    except ImportError:
        return "ERROR: elasticsearch package not installed"
    except Exception as e:
        logger.error(f"ES query failed: {e}")
        return f"ERROR querying Elasticsearch: {e}"
