"""Send disposal suggestions to DingTalk / WeChat Work webhook."""

import hashlib
import hmac
import time
import base64
import urllib.parse
from typing import Any

import httpx
from loguru import logger

from app.core.config import get_settings


async def send_dingtalk(title: str, content: str, alert_name: str = "") -> bool:
    """Push a markdown message to DingTalk group robot."""
    settings = get_settings()
    if not settings.dingtalk_webhook:
        logger.warning("DingTalk webhook not configured, skipping")
        return False

    webhook_url = settings.dingtalk_webhook

    # Sign if secret is configured
    if settings.dingtalk_secret:
        timestamp = str(round(time.time() * 1000))
        sign_str = f"{timestamp}\n{settings.dingtalk_secret}"
        sign = base64.b64encode(
            hmac.new(
                settings.dingtalk_secret.encode("utf-8"),
                sign_str.encode("utf-8"),
                digestmod=hashlib.sha256,
            ).digest()
        ).decode()
        webhook_url += f"&timestamp={timestamp}&sign={urllib.parse.quote_plus(sign)}"

    payload: dict[str, Any] = {
        "msgtype": "markdown",
        "markdown": {
            "title": title,
            "text": f"## {title}\n\n{content}",
        },
        "at": {"isAtAll": False},
    }

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(webhook_url, json=payload)
            resp.raise_for_status()
            data = resp.json()
            if data.get("errcode") == 0:
                logger.info(f"DingTalk notification sent: {title}")
                return True
            logger.error(f"DingTalk error: {data}")
            return False
    except Exception as e:
        logger.error(f"DingTalk send failed: {e}")
        return False


async def send_wechat(title: str, content: str) -> bool:
    """Push a markdown message to WeChat Work group bot."""
    settings = get_settings()
    if not settings.wechat_webhook:
        logger.warning("WeChat webhook not configured, skipping")
        return False

    payload = {
        "msgtype": "markdown",
        "markdown": {"content": f"## {title}\n\n{content}"},
    }

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(settings.wechat_webhook, json=payload)
            resp.raise_for_status()
            data = resp.json()
            if data.get("errcode") == 0:
                logger.info(f"WeChat notification sent: {title}")
                return True
            logger.error(f"WeChat error: {data}")
            return False
    except Exception as e:
        logger.error(f"WeChat send failed: {e}")
        return False


async def notify(title: str, content: str, alert_name: str = "") -> bool:
    """Try DingTalk first, fall back to WeChat."""
    sent = await send_dingtalk(title, content, alert_name)
    if not sent:
        sent = await send_wechat(title, content)
    return sent


def format_disposal_message(
    alert_name: str,
    severity: str,
    suggestion: str,
    retrieved_sources: list[str],
    approval_url: str = "",
) -> str:
    """Format the disposal suggestion as markdown for notification."""
    sources_md = "\n".join(f"- {s}" for s in retrieved_sources) if retrieved_sources else "- 无"
    approval_section = f"\n\n> [点击审批高危操作]({approval_url})" if approval_url else ""
    return (
        f"**告警**: `{alert_name}`  \n"
        f"**级别**: `{severity}`\n\n"
        f"### 处置建议\n{suggestion}\n\n"
        f"### 参考文档\n{sources_md}"
        f"{approval_section}"
    )
