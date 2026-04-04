"""Orchestrate alert → RAG retrieval → suggestion → notification."""

from loguru import logger

from app.models.alert import Alert
from app.models.response import AlertDisposalResponse, AskRequest
from app.alert.parser import build_alert_context, route_alert_query
from app.alert.notifier import notify, format_disposal_message
from app.rag.qa_chain import answer_question
from app.core.config import get_settings

ALERT_PROMPT_TEMPLATE = """你是一名 SRE 工程师，正在处理以下 Prometheus 告警。
请根据告警信息和知识库文档，给出详细的排查步骤和处置建议。

【告警详情】
{alert_context}

【知识库相关内容】
{kb_context}

请输出：
1. 可能的根因分析（1-3 条）
2. 立即处置步骤（有序列表）
3. 预防措施（可选）
"""


async def handle_alert(alert: Alert) -> AlertDisposalResponse:
    """Full pipeline: parse → retrieve → generate → notify."""
    settings = get_settings()

    # 1. Build retrieval query from alert
    query = route_alert_query(alert)
    alert_ctx = build_alert_context(alert)
    logger.info(f"Handling alert: {alert.labels.alertname} [{alert.labels.severity}]")

    # 2. RAG retrieval
    ask_req = AskRequest(
        question=query,
        collection_name="ops_knowledge",
        top_k=settings.retrieval_top_k,
        use_reranker=False,
    )
    rag_resp = await answer_question(ask_req)

    # Build KB context from sources
    kb_context = "\n\n".join(
        f"[{i+1}] {s.metadata.get('file_name', 'unknown')}:\n{s.content}"
        for i, s in enumerate(rag_resp.sources)
    )

    # 3. Generate disposal suggestion with alert context injected
    from langchain_core.messages import HumanMessage, SystemMessage
    from app.rag.qa_chain import get_llm
    prompt = ALERT_PROMPT_TEMPLATE.format(
        alert_context=alert_ctx,
        kb_context=kb_context,
    )
    llm = get_llm()
    response = await llm.ainvoke([HumanMessage(content=prompt)])
    suggestion = response.content

    source_names = [s.metadata.get("file_name", "unknown") for s in rag_resp.sources]

    # 4. Check if high-risk ops approval is needed (Phase 3 integration point)
    requires_approval = False
    approval_url = ""

    # 5. Notify
    msg = format_disposal_message(
        alert_name=alert.labels.alertname,
        severity=alert.labels.severity,
        suggestion=suggestion,
        retrieved_sources=source_names,
        approval_url=approval_url,
    )
    title = f"【运维智能告警】{alert.labels.alertname} - {alert.labels.severity}"
    notification_sent = await notify(title, msg)

    return AlertDisposalResponse(
        alert_fingerprint=alert.fingerprint or alert.labels.alertname,
        alertname=alert.labels.alertname,
        suggestion=suggestion,
        retrieved_docs=source_names,
        notification_sent=notification_sent,
        requires_approval=requires_approval,
        approval_url=approval_url,
    )
