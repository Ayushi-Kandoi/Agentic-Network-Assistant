from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from langchain_core.messages import HumanMessage

from app.db.feedback_store import save_feedback
from app.agents.orchestrator import network_agent, run_followup


app = FastAPI(title="Agentic Network Assistant")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─────────────────────────────────────────────
# Health Check
# ─────────────────────────────────────────────
@app.get("/")
def read_root():
    return {"message": "Backend is up and running!"}


# ═════════════════════════════════════════════
# ENDPOINT 1 — Ticket Analysis
# Triggers full pipeline:
#   fetch_ticket → correlation → [summary_change_related | rca → summary_rca]
# ═════════════════════════════════════════════
class TicketRequest(BaseModel):
    ticket_number: str

class TicketResponse(BaseModel):
    ticket_number: str
    summary: str
    thread_id: str      # returned to frontend for use in /chat/ calls


@app.post("/ticket/", response_model=TicketResponse)
def analyze_ticket(ticket: TicketRequest):
    """
    Accepts a ticket number and runs the full analysis pipeline:
      1. fetch_ticket       — fetch ticket details
      2. correlation agent  — inventory path + planned changes check
      3a. If changes found  → summary_change_related (network agent)
      3b. If no changes     → rca agent → summary_rca (network agent)

    Returns the structured summary produced by the Network Agent.
    thread_id is tied to this ticket and must be passed back on /chat/ calls.
    """
    thread_id = f"ticket-{ticket.ticket_number}"

    try:
        result = network_agent.invoke(
            {
                "messages": [
                    HumanMessage(
                        content=f"Analyse ticket {ticket.ticket_number}"
                    )
                ],
                "ticket_number": ticket.ticket_number,
                "ticket_details": "",
                "inventory_path": "",
                "correlation_findings": "",
                "rca_findings": "",
                "changes_found": False,
                "next": "",
            },
            config={"configurable": {"thread_id": thread_id}},
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    summary = result["messages"][-1].content

    return TicketResponse(
        ticket_number=ticket.ticket_number,
        summary=summary,
        thread_id=thread_id,
    )


# ═════════════════════════════════════════════
# ENDPOINT 2 — Feedback Collection
# Stores feedback from summary and recommendation tabs
# ═════════════════════════════════════════════
class FeedbackRequest(BaseModel):
    ticket_number: str
    section: str        # "summary" or "recommendation"
    verdict: str        # "correct" or "incorrect"
    comment: str | None = None


@app.post("/feedback/")
def submit_feedback(feedback: FeedbackRequest):
    """
    Stores NOC engineer feedback on the analysis output.
    section: which tab the feedback came from (summary / recommendation)
    verdict: whether the analysis was correct or incorrect
    comment: optional free-text from the engineer
    """
    try:
        save_feedback(feedback.dict())
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    return {"status": "feedback stored"}


# ═════════════════════════════════════════════
# ENDPOINT 3 — Follow-up Chat
# Uses same thread_id as /ticket/ so memory is intact.
# Skips full pipeline — goes directly to supervisor
# which routes based on the question content.
# ═════════════════════════════════════════════
class ChatRequest(BaseModel):
    ticket_number: str
    thread_id: str      # must match thread_id returned from /ticket/
    message: str

class ChatResponse(BaseModel):
    response: str
    routed_to: str      # "correlation" or "rca" — useful for frontend debugging


@app.post("/chat/")
def follow_up(chat: ChatRequest):
    """
    Handles follow-up questions on an already-analysed ticket.
    Uses the same thread_id from /ticket/ so the full conversation
    history (ticket details, inventory, findings) is preserved in memory.

    Supervisor routes the question to the correct specialist:
      - correlation : topology, path, planned changes questions
      - rca         : root cause, resolution, SLA, guide questions
    """
    try:
        last_message, routed_to = run_followup(
            ticket_number=chat.ticket_number,
            thread_id=chat.thread_id,
            message=chat.message,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    return ChatResponse(
        response=last_message,
        routed_to=routed_to,
    )


# ─────────────────────────────────────────────
# Helper
# ─────────────────────────────────────────────
def _extract_routed_to(content: str) -> str:
    """Infer which specialist agent handled the response."""
    if "[CORRELATION AGENT]" in content:
        return "correlation"
    elif "[RCA AGENT]" in content:
        return "rca"
    return "network_agent"
