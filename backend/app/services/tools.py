import os
import cohere
from langchain_core.tools import tool
from langchain_openai import OpenAIEmbeddings
from langchain_qdrant import QdrantVectorStore
from langgraph.graph import START, StateGraph
from langchain_core.documents import Document
from typing_extensions import List, TypedDict
from qdrant_client import QdrantClient

from app.data.tickets_data import TICKETS
from app.data.inventory_data import INVENTORY_BY_LINE, INVENTORY_BY_DSLAM, INVENTORY_BY_CPE
from app.data.planned_changes_data import CHANGES_BY_NODE
from app.services.llm import get_rag_llm
from app.services.prompts import RAG_PROMPT

# ── Qdrant client (initialised once at module level) ──────────
_qdrant_client = QdrantClient(
    url=os.getenv("QDRANT_URL"),
    api_key=os.getenv("QDRANT_API_KEY"),
)
_embeddings = OpenAIEmbeddings(
    model="text-embedding-3-small",
    api_key=os.getenv("OPENAI_API_KEY"),
)
_vector_store = QdrantVectorStore(
    client=_qdrant_client,
    collection_name="network_guide",
    embedding=_embeddings,
)

# ── RAG prompt + LLM ─────────────────────────────────────────
_rag_llm = get_rag_llm()

# ── Cohere reranker ───────────────────────────────────────────
_cohere_client = cohere.Client(api_key=os.getenv("COHERE_API_KEY"))

# ── Shared state ──────────────────────────────────────────────
class _RAGState(TypedDict):
    question: str
    context: List[Document]
    response: str

# ── Shared generate node (used by both graphs) ────────────────
def _generate(state: _RAGState):
    docs_content = "\n\n".join(doc.page_content for doc in state["context"])
    prompt = RAG_PROMPT.format(
        question=state["question"],
        context=docs_content,
    )
    response = _rag_llm.invoke(prompt)
    return {"response": response.content}

# ─────────────────────────────────────────────
# Baseline RAG graph — dense k=5
# ─────────────────────────────────────────────
_retriever = _vector_store.as_retriever(search_kwargs={"k": 5})

def _retrieve(state: _RAGState):
    return {"context": _retriever.invoke(state["question"])}

_rag_graph_builder = StateGraph(_RAGState)
_rag_graph_builder.add_sequence([_retrieve, _generate])
_rag_graph_builder.add_edge(START, "_retrieve")
_rag_graph = _rag_graph_builder.compile()

# ─────────────────────────────────────────────
# Advanced RAG graph — dense k=20 + Cohere rerank → top 5
# ─────────────────────────────────────────────
_advanced_retriever = _vector_store.as_retriever(search_kwargs={"k": 20})

def _advanced_retrieve(state: _RAGState):
    # Step 1: retrieve 20 candidates from Qdrant
    docs = _advanced_retriever.invoke(state["question"])

    # Step 2: rerank with Cohere down to top 5
    rerank_response = _cohere_client.rerank(
        model="rerank-v3.5",
        query=state["question"],
        documents=[doc.page_content for doc in docs],
        top_n=5,
    )
    reranked_docs = [docs[r.index] for r in rerank_response.results]
    return {"context": reranked_docs}

_advanced_rag_graph_builder = StateGraph(_RAGState)
_advanced_rag_graph_builder.add_sequence([_advanced_retrieve, _generate])
_advanced_rag_graph_builder.add_edge(START, "_advanced_retrieve")
_advanced_rag_graph = _advanced_rag_graph_builder.compile()


# ─────────────────────────────────────────────
# TOOL 1 — Fetch Ticket
# ─────────────────────────────────────────────
@tool
def fetch_ticket(ticket_number: str) -> str:
    """Fetch ticket details given a ticket number."""
    ticket = TICKETS.get(ticket_number)
    if not ticket:
        return f"Ticket {ticket_number} not found."
    return (
        f"Ticket Number: {ticket['ticket_number']}\n"
        f"Priority: {ticket['priority']}\n"
        f"Node Type: {ticket['node_type']}\n"
        f"Node Info: {ticket['node_info']}\n"
        f"Issue: {ticket['issue_summary']}\n"
        f"Created At: {ticket['start_datetime']}\n"
        f"Expected Resolution: {ticket['expected_resolution_datetime']}"
    )


# ─────────────────────────────────────────────
# TOOL 2 — Search Inventory
# ─────────────────────────────────────────────
@tool
def search_inventory(node_name: str) -> str:
    """Search network inventory by node name.
    Accepts a DSLAM name (e.g. DSLAM-LON-001), CPE name (e.g. CPE-LON-001),
    or LINE ID (e.g. LINE-0001) and returns the full end-to-end path for that line:
    DSLAM -> Metro Bridge -> Metro Core -> Peta Core -> Datacenter.
    """
    record = (
        INVENTORY_BY_DSLAM.get(node_name)
        or INVENTORY_BY_CPE.get(node_name)
        or INVENTORY_BY_LINE.get(node_name)
    )
    if not record:
        return (
            f"No inventory record found for '{node_name}'. "
            f"Accepted formats: DSLAM-XXX-000, CPE-XXX-000, LINE-0000."
        )
    return (
        f"Line ID      : {record['line_id']}\n"
        f"DSLAM        : {record['dslam']}\n"
        f"CPE          : {record['cpe']}\n"
        f"Metro Bridge : {record['mb_node']} (Port: {record['mb_port']})\n"
        f"Metro Core   : {record['mc_node']} (Port: {record['mc_port']})\n"
        f"Peta Core    : {record['peta_core']}\n"
        f"Datacenter   : {record['datacenter']}\n"
        f"Fibre Dist   : {record['fibre_dist_km']} km\n"
        f"VLAN         : {record['vlan']}\n"
        f"Status       : {record['status']}"
    )


# ─────────────────────────────────────────────
# TOOL 3 — Search Planned Changes
# ─────────────────────────────────────────────
@tool
def search_planned_changes(node_name: str) -> str:
    """Search planned change history and upcoming schedule for a given network node.
    Accepts any node name (e.g. MB-01, MC-03, DSLAM-LON-001, PETA-CORE-01, DC-NORTH-01).
    Returns all historical and upcoming planned changes on that node, which helps
    correlate whether a recent maintenance activity may have caused a fault.
    """
    changes = CHANGES_BY_NODE.get(node_name)
    if not changes:
        return f"No planned changes found for node '{node_name}'."

    lines = [f"Found {len(changes)} planned change(s) for node: {node_name}\n"]
    lines.append("-" * 60)
    for c in changes:
        lines.append(
            f"Change ID   : {c['change_id']}\n"
            f"Type        : {c['change_type']}\n"
            f"Start       : {c['date_start']}\n"
            f"End         : {c['date_end']}\n"
            f"Engineer    : {c['engineer']}\n"
            f"Impact      : {c['impact']}\n"
            f"Status      : {c['status']}\n"
            f"Notes       : {c['notes']}\n"
        )
        lines.append("-" * 60)
    return "\n".join(lines)


# ─────────────────────────────────────────────
# TOOL 4 — Search Network Guide (RAG)
# ─────────────────────────────────────────────
@tool
def search_network_guide(question: str) -> str:
    """Search the EDIN network architecture guide using RAG.
    Use this to retrieve troubleshooting procedures, device configuration
    standards, SLA policies, alarm references, and topology documentation.
    Accepts a natural language question about the network.
    Examples:
      - 'What are the troubleshooting steps for a DSLAM port down alarm?'
      - 'What is the SLA for a High priority ticket?'
      - 'What are the optical power thresholds for 10GE SFP interfaces?'
    """
    try:
        result = _rag_graph.invoke({"question": question})
        return result["response"]
    except Exception as e:
        return (
            "RAG lookup failed while querying the network guide. "
            f"Error: {str(e)}"
        )
