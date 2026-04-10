"""LangGraph-based ops agent with tool calling and approval node."""

from typing import Annotated, Any, TypedDict

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, ToolMessage
from langgraph.graph import END, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode
from loguru import logger

from app.agent.tools import ALL_TOOLS
from app.agent.approval import create_approval_request, is_approved
from app.core.config import get_settings
from app.rag.qa_chain import get_llm


AGENT_SYSTEM_PROMPT = """你是一名专业的 SRE 运维 Agent。
可用工具：kubectl_get, kubectl_describe, kubectl_logs, query_logs, query_metrics, run_shell_command

工作原则：
1. 每次只调用1个工具，分析结果后决定是否继续
2. 最多调用工具 10 次，超过后必须立即总结输出结论
3. 高危操作（delete/restart/scale）必须先暂停等待人工审批
4. 收集到足够信息后立即输出：问题分析 + 执行结果摘要 + 建议

重要：不要重复调用同一个工具，不要无限循环。收集到关键信息后直接给出结论。

安全边界：禁止执行 rm、mkfs、dd 等危险命令。
"""


MAX_TOOL_CALLS = 10  # 最多调用工具次数，防止无限循环


class AgentState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    alert_context: str
    action_log: list[dict[str, Any]]
    requires_approval: bool
    approval_id: str
    tool_call_count: int  # 已调用工具次数


def _build_llm_with_tools():
    llm = get_llm()
    return llm.bind_tools(ALL_TOOLS)


def agent_node(state: AgentState) -> AgentState:
    """LLM reasoning step — decides which tool to call next."""
    settings = get_settings()
    llm = _build_llm_with_tools()

    from langchain_core.messages import SystemMessage
    system_msg = SystemMessage(content=AGENT_SYSTEM_PROMPT)
    messages = [system_msg] + state["messages"]

    response: AIMessage = llm.invoke(messages)
    logger.debug(f"Agent response: tool_calls={bool(response.tool_calls)}")

    # Check for high-risk tool calls before executing
    if response.tool_calls:
        for tc in response.tool_calls:
            args_str = str(tc.get("args", "")).lower()
            for hrc in settings.high_risk_ops:
                if hrc in args_str:
                    approval_id = create_approval_request(
                        action=tc["name"],
                        parameters=tc.get("args", {}),
                        alert_context=state.get("alert_context", ""),
                    )
                    return {
                        **state,
                        "messages": [response],
                        "requires_approval": True,
                        "approval_id": approval_id,
                    }

    # Increment tool call counter if tools are about to be called
    new_count = state.get("tool_call_count", 0)
    if response.tool_calls:
        new_count += len(response.tool_calls)
    return {**state, "messages": [response], "tool_call_count": new_count}


def should_continue(state: AgentState) -> str:
    """Route: call tools, wait for approval, or finish."""
    if state.get("requires_approval") and not is_approved(state.get("approval_id", "")):
        return "wait_approval"

    # Hard stop: too many tool calls → force finish
    if state.get("tool_call_count", 0) >= MAX_TOOL_CALLS:
        logger.warning(f"Agent reached max tool calls ({MAX_TOOL_CALLS}), stopping.")
        return END

    last = state["messages"][-1]
    if isinstance(last, AIMessage) and last.tool_calls:
        return "tools"
    return END


def approval_wait_node(state: AgentState) -> AgentState:
    """Pause execution and inform that approval is pending."""
    approval_id = state.get("approval_id", "")
    settings = get_settings()
    msg = AIMessage(
        content=(
            f"高危操作需要人工审批。\n"
            f"审批 ID: {approval_id}\n"
            f"审批地址: {settings.approval_webhook_url}/{approval_id}\n"
            f"批准后操作将自动继续。"
        )
    )
    return {**state, "messages": [msg]}


def build_agent_graph() -> Any:
    """Compile the LangGraph state machine."""
    tool_node = ToolNode(tools=ALL_TOOLS)

    graph = StateGraph(AgentState)
    graph.add_node("agent", agent_node)
    graph.add_node("tools", tool_node)
    graph.add_node("wait_approval", approval_wait_node)

    graph.set_entry_point("agent")
    graph.add_conditional_edges(
        "agent",
        should_continue,
        {"tools": "tools", "wait_approval": "wait_approval", END: END},
    )
    graph.add_edge("tools", "agent")
    graph.add_edge("wait_approval", END)

    # recursion_limit = MAX_TOOL_CALLS * 2 + 5 (each tool call = 2 steps: agent + tool)
    return graph.compile()


# Singleton compiled graph
_agent_graph = None


def get_agent() -> Any:
    global _agent_graph
    if _agent_graph is None:
        _agent_graph = build_agent_graph()
    return _agent_graph


async def run_agent(
    question: str,
    alert_context: str = "",
) -> dict[str, Any]:
    """Invoke the agent and return final state."""
    agent = get_agent()
    initial_state: AgentState = {
        "messages": [HumanMessage(content=question)],
        "alert_context": alert_context,
        "action_log": [],
        "requires_approval": False,
        "approval_id": "",
        "tool_call_count": 0,
    }
    import asyncio
    try:
        final_state = await asyncio.wait_for(
            agent.ainvoke(
                initial_state,
                config={"recursion_limit": MAX_TOOL_CALLS * 3 + 5},
            ),
            timeout=180,  # 3 分钟超时，防止无限等待
        )
    except asyncio.TimeoutError:
        logger.error("Agent execution timed out after 180s")
        return {
            "answer": "⏱️ Agent 执行超时（超过3分钟）。\n\n可能原因：\n- LLM 响应较慢，工具调用轮次过多\n- kubectl 命令挂起\n\n建议：换一个更具体的问题，例如「查看 default 命名空间的 Pod」",
            "requires_approval": False,
            "approval_id": "",
            "action_count": 0,
        }

    # Extract final answer
    last_msg = final_state["messages"][-1]
    answer = last_msg.content if hasattr(last_msg, "content") else str(last_msg)

    return {
        "answer": answer,
        "requires_approval": final_state.get("requires_approval", False),
        "approval_id": final_state.get("approval_id", ""),
        "action_count": len([m for m in final_state["messages"] if isinstance(m, ToolMessage)]),
    }
