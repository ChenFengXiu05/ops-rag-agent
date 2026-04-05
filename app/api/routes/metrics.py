"""Prometheus proxy routes — UI calls these to query metrics without CORS issues."""

import httpx
from fastapi import APIRouter, HTTPException, Query
from loguru import logger

from app.core.config import get_settings

router = APIRouter(prefix="/metrics-query", tags=["metrics"])


@router.get("/instant")
async def instant_query(query: str = Query(..., description="PromQL expression")):
    """
    Proxy a PromQL instant query to Prometheus and return a single scalar value.
    Used by the UI metrics panel to display current metric values.
    """
    settings = get_settings()
    url = f"{settings.prometheus_url}/api/v1/query"
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(url, params={"query": query})
            resp.raise_for_status()
        data = resp.json()
    except httpx.ConnectError:
        raise HTTPException(status_code=503, detail=f"Cannot connect to Prometheus at {settings.prometheus_url}")
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=502, detail=f"Prometheus returned {e.response.status_code}")
    except Exception as e:
        logger.error(f"Prometheus query failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

    if data.get("status") != "success":
        return {"value": None, "error": data.get("error", "unknown")}

    results = data["data"].get("result", [])
    if not results:
        return {"value": None}

    # Return scalar from first result
    first = results[0]
    val = first.get("value")
    if val and len(val) == 2:
        try:
            return {"value": float(val[1])}
        except (ValueError, TypeError):
            return {"value": val[1]}

    return {"value": None}


@router.get("/range")
async def range_query(
    query: str = Query(...),
    start: str = Query("now-1h"),
    end: str = Query("now"),
    step: str = Query("1m"),
):
    """Proxy a PromQL range query — returns raw Prometheus response."""
    settings = get_settings()
    url = f"{settings.prometheus_url}/api/v1/query_range"
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(url, params={"query": query, "start": start, "end": end, "step": step})
            resp.raise_for_status()
        return resp.json()
    except httpx.ConnectError:
        raise HTTPException(status_code=503, detail=f"Cannot connect to Prometheus at {settings.prometheus_url}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
