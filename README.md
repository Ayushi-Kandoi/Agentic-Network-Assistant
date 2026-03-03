# Agentic Network Assistant

A multi-agent AI system that automates network fault investigation for NOC (Network Operations Centre) engineers. Submit a ticket number and the system retrieves the full topology path, checks planned maintenance changes, and performs technical root cause analysis using RAG over the EDIN network architecture guide — producing a structured summary with resolution steps and SLA status.

---

## How It Works

```
Ticket Number Submitted
        │
        ▼
fetch_ticket_node         ← fetches ticket details
        │
        ▼
correlation_node          ← search_inventory: full topology path
                          ← search_planned_changes: every node in path
        │
        ├── CHANGE_RELATED    ──► summary_change_related ──► Response
        │
        └── NO_CHANGE_RELATED ──► rca_node (RAG over network guide)
                                        │
                                  summary_rca_node ──► Response
```

Follow-up questions are routed by a supervisor node to the appropriate specialist agent (correlation or RCA) with full conversation context preserved.

---

## Stack

| Layer | Technology |
|-------|------------|
| Agent orchestration | LangGraph |
| Backend | FastAPI |
| Frontend | React + Vite |
| LLM | OpenAI gpt-4o-mini |
| Embeddings | OpenAI text-embedding-3-small |
| Vector store | Qdrant Cloud |
| Reranking | Cohere rerank-v3.5 |
| Memory | LangGraph MemorySaver |
| Tracing | LangSmith |

---

## Project Structure

```
Agentic-Network-Assistant/
├── backend/
│   ├── app/
│   │   ├── agents/
│   │   │   ├── agents.py              ← correlation_agent, rca_agent
│   │   │   └── orchestrator.py        ← LangGraph supervisor graph
│   │   ├── data/
│   │   │   ├── tickets_data.py        ← 150 fault tickets
│   │   │   ├── inventory_data.py      ← 100 network line records
│   │   │   └── planned_changes_data.py← 130 change records
│   │   ├── db/
│   │   │   └── feedback_store.py      ← feedback persistence
│   │   ├── services/
│   │   │   ├── llm.py                 ← get_llm(), get_rag_llm()
│   │   │   ├── prompts.py             ← all agent and RAG prompts
│   │   │   └── tools.py               ← all 4 tools + RAG graphs
│   │   └── main.py                    ← FastAPI app
│   ├── evaluate_agents.ipynb          ← RAGAS agent evaluation notebook
│   ├── evaluate_RAG.ipynb             ← RAGAS RAG evaluation notebook
│   └── requirements.txt
├── frontend/
│   └── src/
│       └── App.jsx
├── raw_data/
│   ├── network_architecture_EDIN_DETAILED.txt  ← RAG source document
│   ├── network_inventory.txt                   ← inventory reference
│   └── planned_changes.txt                     ← change records reference
├── network_rag.py                     ← one-time Qdrant ingestion script
├── .env.example                       ← environment variable template
├── README.md
└── SUBMISSION.md
```

---

## Prerequisites

- Python 3.13
- Node.js 18+
- Qdrant Cloud account (free tier sufficient)
- OpenAI API key
- Cohere API key (free tier sufficient)
- LangSmith API key (optional, for tracing)

---

## Setup

### 1. Clone the repo

```bash
git clone https://github.com/your-username/Agentic-Network-Assistant.git
cd Agentic-Network-Assistant
```

### 2. Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

Create a `.env` file in the project root by copying the provided example:

```bash
cp .env.example .env
```

Then fill in your credentials:

```env
OPENAI_API_KEY=your-openai-api-key
QDRANT_URL=your-qdrant-cloud-url
QDRANT_API_KEY=your-qdrant-api-key
COHERE_API_KEY=your-cohere-api-key
LANGSMITH_API_KEY=your-langsmith-api-key   # optional
LANGCHAIN_TRACING_V2=true                  # optional
LANGCHAIN_PROJECT=agentic-network-assistant # optional
```

### 3. Ingest the network guide into Qdrant

This is a one-time step that chunks and embeds `network_architecture_EDIN_DETAILED.txt` into your Qdrant collection.

```bash
# From project root
python network_rag.py
# Creates collection: network_guide (137 chunks)
```

### 4. Frontend

```bash
cd frontend
npm install
```

---

## Running Locally

### Start the backend

```bash
cd backend
source venv/bin/activate
uvicorn app.main:app --reload
# Running on http://127.0.0.1:8000
```

### Start the frontend

```bash
cd frontend
npm run dev
# Running on http://localhost:5173
```

Open `http://localhost:5173` in your browser.

---

## API Endpoints

### `POST /ticket/`
Triggers the full multi-agent analysis pipeline for a ticket number.

**Request:**
```json
{
  "ticket_number": "TKT-2025001"
}
```

**Response:**
```json
{
  "ticket_number": "TKT-2025001",
  "summary": "TICKET\n  Number   : TKT-2025001\n  Priority : H\n ...",
  "thread_id": "ticket-TKT-2025001"
}
```

---

### `POST /chat/`
Sends a follow-up question on an already-analysed ticket. Requires the `thread_id` from the `/ticket/` response.

**Request:**
```json
{
  "ticket_number": "TKT-2025001",
  "thread_id": "ticket-TKT-2025001",
  "message": "What are the resolution steps?"
}
```

**Response:**
```json
{
  "response": "...",
  "routed_to": "rca"
}
```

---

### `POST /feedback/`
Submits engineer feedback on a summary or recommendation section.

**Request:**
```json
{
  "ticket_number": "TKT-2025001",
  "section": "summary",
  "verdict": "correct",
  "comment": "Accurate root cause identified"
}
```

---

### `GET /`
Health check.

```json
{ "status": "ok" }
```

---

## Running the Evaluations

Two RAGAS evaluation notebooks are in `backend/`:

**RAG evaluation** (`evaluate_RAG.ipynb`) — generates a synthetic test dataset, runs both the baseline dense retrieval and Cohere-reranked pipelines, and produces a comparison metrics table.

**Agent evaluation** (`evaluate_agents.ipynb`) — runs the full multi-agent pipeline against test cases and evaluates agent goal accuracy and topic adherence.

```bash
cd backend
source venv/bin/activate
jupyter notebook
```

Run cells sequentially in each notebook — each cell is independent so expensive steps (dataset generation, LLM evaluation) do not need to be re-run if the kernel stays alive. Requires `COHERE_API_KEY` in your `.env` before running the advanced retrieval cells in `evaluate_RAG.ipynb`.

---

## Environment Variables Reference

| Variable | Required | Description |
|----------|----------|-------------|
| `OPENAI_API_KEY` | Yes | OpenAI API key for LLM and embeddings |
| `QDRANT_URL` | Yes | Qdrant Cloud cluster URL |
| `QDRANT_API_KEY` | Yes | Qdrant Cloud API key |
| `COHERE_API_KEY` | Yes | Cohere API key for reranking |
| `LANGSMITH_API_KEY` | No | LangSmith tracing |
| `LANGCHAIN_TRACING_V2` | No | Set to `true` to enable tracing |
| `LANGCHAIN_PROJECT` | No | LangSmith project name |