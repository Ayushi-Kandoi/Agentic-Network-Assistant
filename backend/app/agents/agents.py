from langchain.agents import create_agent
from langgraph.checkpoint.memory import MemorySaver
from app.services.llm import get_llm
from app.services.tools import (
    search_inventory,
    search_planned_changes,
    search_network_guide,
)
from app.services.prompts import (
    CORRELATION_AGENT_PROMPT,
    RCA_AGENT_PROMPT,
)


# ─────────────────────────────────────────────
# Correlation Agent
# Tools : search_inventory + search_planned_changes
# Role  : Retrieve full topology path for the affected
#         node and check planned changes on every node
#         in the path. Returns CHANGE_RELATED or
#         NO_CHANGE_RELATED verdict.
# ─────────────────────────────────────────────
correlation_agent = create_agent(
    model=get_llm(),
    tools=[search_inventory, search_planned_changes],
    system_prompt=CORRELATION_AGENT_PROMPT,
    checkpointer=MemorySaver(),
)


# ─────────────────────────────────────────────
# RCA Agent
# Tools : search_network_guide RAG tool only
# Role  : Technical fault diagnosis using the EDIN
#         network guide. Called only when correlation
#         finds no planned changes. Does NOT search
#         inventory — already done by correlation agent
#         and passed in context.
# ─────────────────────────────────────────────
rca_agent = create_agent(
    model=get_llm(),
    tools=[search_network_guide],
    system_prompt=RCA_AGENT_PROMPT,
    checkpointer=MemorySaver(),
)

