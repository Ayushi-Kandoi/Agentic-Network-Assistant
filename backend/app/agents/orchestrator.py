from typing import Literal
from uuid import uuid4
from typing_extensions import TypedDict, Annotated
from pydantic import BaseModel

from langchain_core.messages import (
    BaseMessage,
    HumanMessage,
    AIMessage,
    SystemMessage,
)
from langgraph.graph import START, END, StateGraph
from langgraph.graph.message import add_messages
from langgraph.checkpoint.memory import MemorySaver

from app.services.llm import get_llm
from app.services.tools import fetch_ticket
from app.agents.agents import correlation_agent, rca_agent
from app.services.prompts import (
    NETWORK_AGENT_PROMPT,
    SUMMARY_CHANGE_RELATED_PROMPT,
    SUMMARY_RCA_PROMPT,
)


# ═════════════════════════════════════════════
# STATE
# ═════════════════════════════════════════════
class SupervisorState(TypedDict):
    """
    Full state carried through the supervisor graph.

    ticket_number       : e.g. "TKT-2025001" — pinned for session lifetime
    ticket_details      : raw output of fetch_ticket(), set by fetch_ticket_node
    inventory_path      : topology path extracted from correlation agent response
                          passed to RCA agent so it does not re-query inventory
    correlation_findings: full raw output of correlation_agent
    rca_findings        : full raw output of rca_agent (empty if change-related)
    changes_found       : True if correlation agent found CHANGE_RELATED verdict
    next                : routing decision for follow-up supervisor node
    messages            : full conversation history (LangGraph managed)
    """
    messages            : Annotated[list[BaseMessage], add_messages]
    ticket_number       : str
    ticket_details      : str
    inventory_path      : str
    correlation_findings: str
    rca_findings        : str
    changes_found       : bool
    next                : str


# ═════════════════════════════════════════════
# ROUTING MODEL (follow-up only)
# ═════════════════════════════════════════════
class RouterOutput(BaseModel):
    """Structured output for follow-up routing decision."""
    next: Literal["correlation", "rca"]
    reasoning: str


# LLMs — initialised once at module level
_routing_llm = get_llm().with_structured_output(RouterOutput)
_summary_llm = get_llm()


def _fresh_agent_thread_id(prefix: str, ticket_number: str) -> str:
    """Create a fresh sub-agent thread ID to avoid stale chat history reuse."""
    return f"{prefix}-{ticket_number}-{uuid4().hex}"


def _latest_user_message(state: SupervisorState) -> str:
    """Extract the latest follow-up question from conversation state."""
    for msg in reversed(state["messages"]):
        if isinstance(msg, HumanMessage):
            return msg.content
    return ""


# ═════════════════════════════════════════════
# NODE 1 — FETCH TICKET
# Owned by: Orchestrator
# Calls   : fetch_ticket tool
# Sets    : ticket_details
# ═════════════════════════════════════════════
def fetch_ticket_node(state: SupervisorState):
    """
    Fetches ticket details from the static tickets data.
    This is the only place fetch_ticket is called.
    Output is stored in state and passed downstream.
    """
    print(f"[Orchestrator] Fetching ticket: {state['ticket_number']}")

    ticket_details = fetch_ticket.invoke(
        {"ticket_number": state["ticket_number"]}
    )

    if "not found" in ticket_details.lower():
        print(f"[Orchestrator] Ticket not found: {state['ticket_number']}")

    print("[Orchestrator] Ticket fetched — passing to Correlation Agent.")
    return {
        "ticket_details": ticket_details,
        "messages": [
            SystemMessage(content=f"Ticket details:\n{ticket_details}")
        ],
    }


# ═════════════════════════════════════════════
# NODE 2 — CORRELATION AGENT
# Owned by: Correlation Agent
# Calls   : search_inventory + search_planned_changes
# Sets    : correlation_findings, inventory_path, changes_found
# ═════════════════════════════════════════════
def correlation_node(state: SupervisorState):
    """
    Passes ticket details to correlation agent.
    Agent searches inventory for full topology path,
    then checks planned changes on every node in the path.
    Returns CHANGE_RELATED or NO_CHANGE_RELATED verdict.

    Also extracts and stores the inventory path from the
    agent's tool responses so it can be passed to the RCA
    agent without re-querying.
    """
    print("[Correlation Agent] Checking inventory and planned changes...")

    context = (
        f"Ticket Details:\n{state['ticket_details']}\n\n"
        f"Follow your steps exactly:\n"
        f"1) Search inventory for the affected node in the ticket.\n"
        f"2) Check planned changes on every node in the returned path.\n"
        f"3) Return your findings and verdict."
    )

    result = correlation_agent.invoke(
        {"messages": [HumanMessage(content=context)]},
        config={"configurable": {
            "thread_id": _fresh_agent_thread_id("correlation", state["ticket_number"])
        }},
    )

    findings = result["messages"][-1].content

    # Determine verdict from agent response
    changes_found = "VERDICT: NO_CHANGE_RELATED" not in findings

    # Extract inventory path from correlation agent tool call results.
    # search_inventory returns lines with labels like "Metro Bridge",
    # "Metro Core" etc. — find the tool response message that contains
    # the inventory output and store it for the RCA agent.
    inventory_path = ""
    for msg in result["messages"]:
        content = getattr(msg, "content", "")
        if isinstance(content, str) and "Metro Bridge" in content:
            inventory_path = content
            break

    print(f"[Correlation Agent] Complete. Changes found: {changes_found}")
    return {
        "correlation_findings": findings,
        "inventory_path": inventory_path,
        "changes_found": changes_found,
        "messages": [
            SystemMessage(content=f"Correlation findings:\n{findings}")
        ],
    }


# ═════════════════════════════════════════════
# NODE 3 — RCA AGENT
# Owned by: RCA Agent
# Calls   : search_network_guide only
# Sets    : rca_findings
# Note    : Does NOT search inventory — already done
#           by correlation agent and passed in context
# ═════════════════════════════════════════════
def rca_node(state: SupervisorState):
    """
    Called only when correlation agent finds no planned changes.
    Passes ticket details + inventory path (from state) to RCA agent.
    RCA agent uses search_network_guide for technical fault diagnosis.
    Does not re-query inventory.
    """
    print("[RCA Agent] No changes found — performing technical RCA...")

    context = (
        f"Ticket Details:\n{state['ticket_details']}\n\n"
        f"Inventory Path (already retrieved by Correlation Agent — "
        f"do NOT search inventory again):\n"
        f"{state['inventory_path']}\n\n"
        f"Planned Changes: The Correlation Agent confirmed no planned "
        f"changes were found on any node in the path.\n\n"
        f"Your task: Use search_network_guide to find the technical root "
        f"cause and resolution steps for the fault described in the ticket. "
        f"Focus on the affected node type and issue description only. "
        f"Return raw findings — do not write a summary."
    )

    result = rca_agent.invoke(
        {"messages": [HumanMessage(content=context)]},
        config={"configurable": {
            "thread_id": _fresh_agent_thread_id("rca", state["ticket_number"])
        }},
    )

    findings = result["messages"][-1].content

    print("[RCA Agent] Complete.")
    return {
        "rca_findings": findings,
        "messages": [
            SystemMessage(content=f"RCA findings:\n{findings}")
        ],
    }


# ═════════════════════════════════════════════
# NODE 4a — SUMMARY: CHANGE RELATED
# Owned by: Network Agent
# Called when: correlation found planned changes
# ═════════════════════════════════════════════
def summary_change_related_node(state: SupervisorState):
    """
    Network Agent synthesises the correlation findings into
    a clean structured summary for the NOC engineer.
    Called when changes_found = True.
    """
    print("[Network Agent] Building change-related summary...")

    messages = SUMMARY_CHANGE_RELATED_PROMPT.format_messages(
        ticket_details=state["ticket_details"],
        correlation_findings=state["correlation_findings"],
    )
    response = _summary_llm.invoke(messages)

    print("[Network Agent] Summary complete.")
    return {
        "messages": [
            AIMessage(
                content=response.content,
                name="network_agent",
            )
        ]
    }


# ═════════════════════════════════════════════
# NODE 4b — SUMMARY: RCAa
# Owned by: Network Agent
# Called when: no planned changes, RCA complete
# ═════════════════════════════════════════════
def summary_rca_node(state: SupervisorState):
    """
    Network Agent synthesises the RCA findings into
    a clean structured summary for the NOC engineer.
    Called when changes_found = False.
    """
    print("[Network Agent] Building RCA summary...")

    messages = SUMMARY_RCA_PROMPT.format_messages(
        ticket_details=state["ticket_details"],
        inventory_path=state["inventory_path"],
        rca_findings=state["rca_findings"],
    )
    response = _summary_llm.invoke(messages)

    print("[Network Agent] Summary complete.")
    return {
        "messages": [
            AIMessage(
                content=response.content,
                name="network_agent",
            )
        ]
    }


# ═════════════════════════════════════════════
# NODE 5 — SUPERVISOR (follow-up routing only)
# Owned by: Network Agent
# Called when: user sends follow-up chat message
# Routes to: correlation or rca based on question
# ═════════════════════════════════════════════
def supervisor_node(state: SupervisorState):
    """
    Used only for follow-up chat questions after initial analysis.
    Reads the latest human message and routes to the appropriate
    specialist agent based on question content.
    NOT used during initial ticket analysis pipeline.
    """
    print("[Supervisor] Routing follow-up question...")

    user_message = _latest_user_message(state)

    prompt_value = NETWORK_AGENT_PROMPT.invoke({
        "question": user_message,
        "ticket_number": state.get("ticket_number", ""),
    })
    result = _routing_llm.invoke(prompt_value)

    print(f"[Supervisor] Routing to : {result.next}")
    print(f"[Supervisor] Reason     : {result.reasoning}")
    return {"next": result.next}


# ═════════════════════════════════════════════
# NODE 6a — CORRELATION FOLLOW-UP
# Owned by: Correlation Agent
# Called when: supervisor routes follow-up to correlation
# ═════════════════════════════════════════════
def correlation_followup_node(state: SupervisorState):
    """
    Handles follow-up chat questions that belong to correlation scope
    (topology path, inventory, planned changes, maintenance links).
    """
    print("[Correlation Agent] Handling follow-up question...")

    question = _latest_user_message(state)
    prompt = (
        "You are the Correlation Agent follow-up assistant.\n"
        "Answer ONLY from correlation scope: topology path, node mapping, "
        "inventory path, and planned changes correlation.\n"
        "Do not provide full incident templates.\n\n"
        f"Ticket Number: {state.get('ticket_number', '')}\n\n"
        f"Ticket Details:\n{state.get('ticket_details', '')}\n\n"
        f"Correlation Findings:\n{state.get('correlation_findings', '')}\n\n"
        f"User Question:\n{question}\n\n"
        "Return a concise direct answer with short bullets if helpful."
    )
    answer = _summary_llm.invoke(prompt).content

    return {
        "messages": [
            AIMessage(
                content=f"[CORRELATION AGENT]\n{answer}",
                name="correlation_agent",
            )
        ]
    }


# ═════════════════════════════════════════════
# NODE 6b — RCA FOLLOW-UP
# Owned by: RCA Agent
# Called when: supervisor routes follow-up to rca
# ═════════════════════════════════════════════
def rca_followup_node(state: SupervisorState):
    """
    Handles follow-up chat questions that belong to RCA scope
    (root cause, troubleshooting, resolution steps, SLA).
    """
    print("[RCA Agent] Handling follow-up question...")

    question = _latest_user_message(state)
    prompt = (
        "You are the RCA Agent follow-up assistant.\n"
        "Answer ONLY from RCA scope: root cause, troubleshooting actions, "
        "resolution steps, and SLA implications.\n"
        "Do not provide full incident templates unless user asks.\n\n"
        f"Ticket Number: {state.get('ticket_number', '')}\n\n"
        f"Ticket Details:\n{state.get('ticket_details', '')}\n\n"
        f"Inventory Path:\n{state.get('inventory_path', '')}\n\n"
        f"RCA Findings:\n{state.get('rca_findings', '')}\n\n"
        f"User Question:\n{question}\n\n"
        "Return a concise direct answer with actionable next steps."
    )
    answer = _summary_llm.invoke(prompt).content

    return {
        "messages": [
            AIMessage(
                content=f"[RCA AGENT]\n{answer}",
                name="rca_agent",
            )
        ]
    }


# ═════════════════════════════════════════════
# ROUTING FUNCTIONS
# ═════════════════════════════════════════════
def _route_after_correlation(state: SupervisorState) -> str:
    """
    After correlation agent completes:
      - changes found     → summary_change_related (network agent summarises)
      - no changes found  → rca (technical diagnosis needed)
    """
    return "summary_change_related" if state["changes_found"] else "rca"


def _route_followup(state: SupervisorState) -> str:
    """After supervisor decision: route to correlation or rca."""
    return state["next"]


# ═════════════════════════════════════════════
# BUILD GRAPH
# ═════════════════════════════════════════════
_workflow = StateGraph(SupervisorState)

# Register all nodes
_workflow.add_node("fetch_ticket",           fetch_ticket_node)
_workflow.add_node("correlation",            correlation_node)
_workflow.add_node("rca",                    rca_node)
_workflow.add_node("summary_change_related", summary_change_related_node)
_workflow.add_node("summary_rca",            summary_rca_node)
_workflow.add_node("supervisor",             supervisor_node)
_workflow.add_node("correlation_followup",   correlation_followup_node)
_workflow.add_node("rca_followup",           rca_followup_node)

# ── Initial analysis pipeline (sequential) ──────────────────
# START → fetch_ticket → correlation → [branch] → summary → END
_workflow.add_edge(START,           "fetch_ticket")
_workflow.add_edge("fetch_ticket",  "correlation")

# After correlation: branch to summary or rca
_workflow.add_conditional_edges(
    "correlation",
    _route_after_correlation,
    {
        "summary_change_related": "summary_change_related",
        "rca":                    "rca",
    },
)

# After rca: always go to rca summary
_workflow.add_edge("rca",                    "summary_rca")

# Both summaries terminate the initial pipeline
_workflow.add_edge("summary_change_related", END)
_workflow.add_edge("summary_rca",            END)

# ── Follow-up chat path ──────────────────────────────────────
# supervisor → [correlation_followup | rca_followup] → END
# Note: follow-up uses entry_point="supervisor" in /chat endpoint
# so the initial pipeline is skipped entirely
_workflow.add_conditional_edges(
    "supervisor",
    _route_followup,
    {
        "correlation": "correlation_followup",
        "rca":         "rca_followup",
    },
)
_workflow.add_edge("correlation_followup", END)
_workflow.add_edge("rca_followup", END)

# Compile with MemorySaver for multi-turn conversation support
network_agent = _workflow.compile(checkpointer=MemorySaver())


def run_followup(ticket_number: str, thread_id: str, message: str) -> tuple[str, str]:
    """
    Run follow-up routing directly without re-entering the initial analysis
    pipeline. Returns (response_text, routed_to).
    """
    config = {"configurable": {"thread_id": thread_id}}

    # Recover the latest stored state from the initial /ticket/ analysis thread.
    snapshot = network_agent.get_state(config)
    values = snapshot.values if snapshot and snapshot.values else {}

    messages = list(values.get("messages", []))
    messages.append(HumanMessage(content=message))

    state: SupervisorState = {
        "messages": messages,
        "ticket_number": values.get("ticket_number", ticket_number),
        "ticket_details": values.get("ticket_details", ""),
        "inventory_path": values.get("inventory_path", ""),
        "correlation_findings": values.get("correlation_findings", ""),
        "rca_findings": values.get("rca_findings", ""),
        "changes_found": values.get("changes_found", False),
        "next": "",
    }

    route_result = supervisor_node(state)
    routed_to = route_result["next"]
    state["next"] = routed_to

    if routed_to == "correlation":
        response = correlation_followup_node(state)["messages"][-1].content
    else:
        response = rca_followup_node(state)["messages"][-1].content

    return response, routed_to

print("=" * 55)
print("Network Agent (Supervisor) ready.")
print("─" * 55)
print("Initial flow:")
print("  START → fetch_ticket → correlation")
print("            ├─ CHANGE_RELATED  → summary_change_related → END")
print("            └─ NO_CHANGE_FOUND → rca → summary_rca      → END")
print("Follow-up flow:")
print("  supervisor → [correlation_followup | rca_followup] → END")
print("=" * 55)
