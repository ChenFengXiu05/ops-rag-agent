"""RAG Q&A chain: retrieval → (optional rerank) → generation."""

import time
from functools import lru_cache

from langchain.chains import RetrievalQA
from langchain_core.documents import Document
from langchain_core.language_models import BaseChatModel
from loguru import logger

from app.core.config import get_settings
from app.rag.vectorstore import similarity_search_with_score
from app.rag.reranker import BGEReranker
from app.models.response import AskRequest, AskResponse, SourceDocument


OPS_SYSTEM_PROMPT = """你是一名专业的运维工程师助手。
根据以下运维知识库内容，回答用户的问题或给出处置建议。

知识库内容：
{context}

回答要求：
1. 直接给出具体的操作步骤，使用有序列表
2. 标注参考文档来源
3. 如果知识库中没有相关内容，明确告知并给出通用建议
4. 中文回答，专业简洁
"""


@lru_cache(maxsize=1)
def get_llm() -> BaseChatModel:
    settings = get_settings()

    if settings.llm_provider == "vllm":
        # vLLM 暴露 OpenAI 兼容接口，直接用 ChatOpenAI 对接
        from langchain_openai import ChatOpenAI
        model_name = settings.vllm_model or settings.llm_model
        logger.info(f"Using vLLM at {settings.vllm_base_url}, model={model_name}")
        return ChatOpenAI(
            model=model_name,
            temperature=settings.llm_temperature,
            max_tokens=settings.llm_max_tokens,
            openai_api_key=settings.vllm_api_key,
            openai_api_base=settings.vllm_base_url,
        )

    elif settings.llm_provider == "openai":
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            model=settings.llm_model,
            temperature=settings.llm_temperature,
            max_tokens=settings.llm_max_tokens,
            openai_api_key=settings.openai_api_key,
        )

    else:  # claude
        from langchain_anthropic import ChatAnthropic
        return ChatAnthropic(
            model=settings.llm_model,
            temperature=settings.llm_temperature,
            max_tokens=settings.llm_max_tokens,
            anthropic_api_key=settings.anthropic_api_key,
        )


def build_context(docs: list[Document]) -> str:
    parts = []
    for i, doc in enumerate(docs, 1):
        source = doc.metadata.get("file_name", "unknown")
        parts.append(f"[{i}] 来源: {source}\n{doc.page_content}")
    return "\n\n---\n\n".join(parts)


async def answer_question(req: AskRequest) -> AskResponse:
    """Full RAG pipeline: retrieve → rerank → generate."""
    settings = get_settings()
    start = time.time()

    # 1. Retrieve
    scored_docs = similarity_search_with_score(
        query=req.question,
        collection_name=req.collection_name,
        top_k=req.top_k,
    )
    docs = [doc for doc, _ in scored_docs]
    scores = [score for _, score in scored_docs]

    # 2. Optional rerank (Phase 4)
    if req.use_reranker:
        reranker = BGEReranker(
            model_name=settings.bge_reranker_model,
            top_k=settings.reranker_top_k,
        )
        docs = reranker.rerank(req.question, docs)

    # 3. Build prompt context
    context = build_context(docs)
    prompt = OPS_SYSTEM_PROMPT.format(context=context)

    # 4. Generate
    llm = get_llm()
    from langchain_core.messages import HumanMessage, SystemMessage
    messages = []
    if req.chat_history:
        from langchain_core.messages import AIMessage
        for turn in req.chat_history:
            # Support both {"role":..,"content":..} and {"human":..,"ai":..} formats
            if "role" in turn:
                role, content = turn.get("role", ""), turn.get("content", "")
                if role == "user":
                    messages.append(HumanMessage(content=content))
                elif role in ("assistant", "ai"):
                    messages.append(AIMessage(content=content))
            elif "human" in turn:
                messages.append(HumanMessage(content=turn["human"]))
                if "ai" in turn:
                    messages.append(AIMessage(content=turn["ai"]))
    messages.append(HumanMessage(content=req.question))

    response = await llm.ainvoke(
        [SystemMessage(content=prompt)] + messages[-6:]  # keep last 3 turns
    )
    answer = response.content
    tokens = getattr(response, "usage_metadata", {})
    total_tokens = tokens.get("total_tokens", 0) if isinstance(tokens, dict) else 0

    latency_ms = (time.time() - start) * 1000
    logger.info(f"Q&A completed in {latency_ms:.0f}ms, tokens={total_tokens}")

    sources = [
        SourceDocument(
            content=doc.page_content[:300],
            metadata=doc.metadata,
            score=scores[i] if i < len(scores) else 0.0,
        )
        for i, doc in enumerate(docs)
    ]

    return AskResponse(
        answer=answer,
        sources=sources,
        tokens_used=total_tokens,
        latency_ms=latency_ms,
    )
