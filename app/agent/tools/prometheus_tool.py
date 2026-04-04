"""Prometheus PromQL query tool."""

import httpx
from langchain_core.tools import tool
from loguru import logger

from app.core.config import get_settings


@tool
def query_metrics(promql: str, time_range: str = "5m", step: str = "1m") -> str:
    """
    Execute a PromQL query against Prometheus.
    Args:
        promql: Valid PromQL expression, e.g. 'rate(http_requests_total[5m])'
        time_range: Duration for range query, e.g. '5m', '1h'
        step: Resolution step for range query, e.g. '1m', '30s'
    Returns:
        Formatted metric results as text
    """
    settings = get_settings()
    try:
        # Use instant query for simple values, range query for trends
        url = f"{settings.prometheus_url}/api/v1/query"
        resp = httpx.get(url, params={"query": promql}, timeout=15)
        resp.raise_for_status()
        data = resp.json()

        if data["status"] != "success":
            return f"Prometheus error: {data.get('error', 'unknown')}"

        results = data["data"]["result"]
        if not results:
            return f"No metrics found for: {promql}"

        lines = [f"PromQL: {promql}", f"Results ({len(results)} series):"]
        for r in results[:10]:  # cap at 10 series
            metric_labels = ", ".join(f"{k}={v}" for k, v in r["metric"].items())
            value = r.get("value", r.get("values", [["", "N/A"]][-1]))
            if isinstance(value, list) and len(value) == 2:
                lines.append(f"  {{{metric_labels}}} = {value[1]}")
        return "\n".join(lines)

    except httpx.HTTPError as e:
        logger.error(f"Prometheus HTTP error: {e}")
        return f"ERROR connecting to Prometheus: {e}"
    except Exception as e:
        logger.error(f"PromQL query failed: {e}")
        return f"ERROR: {e}"
