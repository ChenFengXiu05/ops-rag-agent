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
你有以下工具可以使用：kubectl_get, kubectl_describe, kubectl_logs, query_logs, query_metrics, run_shell_command

工作原则：
1. 先分析告警/问题，制定排查思路，然后逐步调用工具收集信息
2. 高危操作（delete/restart/scale 等）必须先创建审批请求，等待人工确认
3. 每次工具调用后分析结果，判断是否需要继续调查
4. 最终输出：根因分析 + 已执行操作 + 结果摘要 + 后续建议

安全边界：禁止执行 rm、mkfs、dd 等危险命令。
"""


class AgentState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    alert_context: str
    action_log: list[dict[str, Any]]
    requires_approval: bool
    approval_id: str


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

    return {**state, "messages": [response]}


def should_continue(state: AgentState) -> str:
    """Route: call tools, wait for approval, or finish."""
    if state.get("requires_approval") and not is_approved(state.get("approval_id", "")):
        return "wait_approval"

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
    }
    final_state = await agent.ainvoke(initial_state)

    # Extract final answer
    last_msg = final_state["messages"][-1]
    answer = last_msg.content if hasattr(last_msg, "content") else str(last_msg)

    return {
        "answer": answer,
        "requires_approval": final_state.get("requires_approval", False),
        "approval_id": final_state.get("approval_id", ""),
        "action_count": len([m for m in final_state["messages"] if isinstance(m, ToolMessage)]),
    }
