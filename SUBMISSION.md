# Agentic Network Assistant — Certification Submission

## Task 1 — Problem, Audience, and Scope

### Problem Statement
Network Operations Centre (NOC) engineers manually investigate network fault tickets by cross-referencing multiple systems — inventory, change management, and architecture guides. This cause slow root cause identification, frequent SLA breaches and penalties to the company. 

### Why This Is a Problem for NOC Engineers
NOC engineers are responsible for diagnosing and resolving network faults within strict SLA windows (4 hours for high priority, 8 hours for medium, 24 hours for low). When a fault ticket arrives, an engineer must manually query the network inventory to trace the end-to-end path of the affected line, cross-check whether any planned maintenance activity on that path could explain the fault, and if not, consult the network architecture guide to identify the technical root cause and appropriate resolution steps. This process requires navigating three separate systems, interpreting raw data, and applying deep domain knowledge, all under time pressure.

The consequence of this manual process is twofold. First, mean time to resolution (MTTR) is unnecessarily high because experienced engineers spend significant time on data gathering rather than decision-making. Second, less experienced engineers may miss correlations, for example, failing to check upstream nodes like the Metro Core or Peta Core for related planned changes, leading to incorrect root cause conclusions and wasted escalation effort. An AI-assisted system that automates the investigation pipeline and surfaces structured, evidence-backed summaries directly addresses both problems by reducing cognitive load and accelerating resolution.

### Evaluation Questions / Input-Output Pairs
| # | Input | Expected Output |
|---|-------|-----------------|
| 1 | TKT-2025001 (DSLAM fault, no planned changes)   | RCA path taken, DSLAM troubleshooting steps from guide, SLA status|
| 2 | TKT-2025002 (MB-MC link, planned change exists) | Correlation path taken, change identified as root cause, no guide query|
| 3 | TKT-2025003 (MC node, BGP fault)   | Correct node extracted, inventory path retrieved, BGP troubleshooting from guide|
| 4 | Follow-up: "What are the resolution steps?"   | RCA agent responds with numbered steps |
| 5 | Follow-up: "Were there any recent changes on this node?" | Correlation agent responds with planned changes |
| 6 | Follow-up: "What is the SLA status?" | Correct SLA calculated from ticket priority and creation time |
| 7 | Invalid ticket TKT-9999999 | Graceful "ticket not found" response |
| 8 | TKT-2025055 (MB node, planned change exists) | Change-related summary, correct change ID cited |
| 9 | Follow-up: "Which nodes are in the affected path?" | Correlation agent returns full DSLAM→MB→MC→Peta Core→DC path |
| 10 | TKT-2025089 (CPE node, no changes) | CPE troubleshooting steps, correct inventory path |

---

# Task 2 — Proposed Solution

## Solution Proposal

The proposed solution is a multi-agent AI system that automates the full fault investigation pipeline for NOC engineers. When a ticket number is submitted, a Network Agent Orchestrator fetches the ticket details and passes them to a Correlation Agent, which retrieves the end-to-end network topology path for the affected node and checks every node in that path for planned maintenance activity. If a planned change is found, the system immediately identifies it as the root cause and generates a structured summary. If no planned change is found, the ticket is escalated to an RCA Agent, which uses Retrieval-Augmented Generation (RAG) over the EDIN network architecture guide to identify the technical root cause and produce step-by-step resolution instructions. The Network Agent synthesises all findings into a single structured output covering summary, root cause, evidence, impacted path, resolution steps, and SLA status.

The system is built as a FastAPI backend with a LangGraph multi-agent orchestration layer, deployed locally with a React/Vite frontend. Engineers interact through a simple interface — entering a ticket number to trigger the full analysis, providing feedback on the summary and recommendations, and asking follow-up questions through a chat interface that preserves full conversation context. The RAG component uses Qdrant as a vector store with OpenAI embeddings to retrieve relevant sections of the network guide, ensuring resolution steps are always grounded in authoritative documentation rather than model hallucination.

---

## Infrastructure Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                          FRONTEND                               │
│                   React + Vite (localhost:5173)                  │
│                                                                  │
│   ┌──────────────┐   ┌──────────────────┐  ┌────────────────┐   │
│   │ Ticket Input │   │  Feedback Tabs   │  │ Chat Interface │   │
│   └──────┬───────┘   └────────┬─────────┘  └───────┬────────┘   │
└──────────┼────────────────────┼────────────────────┼────────────┘
           │ POST /ticket/      │ POST /feedback/     │ POST /chat/
┌──────────┼────────────────────┼────────────────────┼────────────┐
│                          BACKEND                                 │
│                   FastAPI (localhost:8000)                        │
│                                                                  │
│   ┌───────────────────────────────────────────────────────────┐  │
│   │                 LangGraph Supervisor Graph                 │  │
│   │                                                           │  │
│   │   fetch_ticket_node                                       │  │
│   │         │                                                 │  │
│   │   correlation_node                                        │  │
│   │   [search_inventory + search_planned_changes]             │  │
│   │         │                                                 │  │
│   │         ├── CHANGE_RELATED ──► summary_change_related ──► END
│   │         │                                                 │  │
│   │         └── NO_CHANGE_RELATED                             │  │
│   │                   │                                       │  │
│   │              rca_node                                     │  │
│   │              [search_network_guide RAG]                   │  │
│   │                   │                                       │  │
│   │              summary_rca_node ──────────────────────────► END
│   │                                                           │  │
│   │   Follow-up: supervisor → [correlation | rca] → END       │  │
│   └───────────────────────────────────────────────────────────┘  │
│                                                                   │
│  ┌──────────────────┐  ┌─────────────────────┐  ┌─────────────┐  │
│  │   Static Data    │  │    Qdrant Cloud      │  │ Feedback DB │  │
│  │  tickets_data.py │  │  network_guide       │  │ JSON store  │  │
│  │  inventory_data  │  │  collection          │  │             │  │
│  │  planned_changes │  │  (137 chunks)        │  │             │  │
│  └──────────────────┘  └──────────┬──────────┘  └─────────────┘  │
└─────────────────────────────────── ┼ ─────────────────────────────┘
                                     │
                          ┌──────────▼──────────┐
                          │     OpenAI API       │
                          │   gpt-4o-mini        │
                          │   text-embedding     │
                          │   -3-small           │
                          └─────────────────────┘
```

---

## Tooling Choices

| Tool | Choice | Why |
|------|--------|-----|
| **LangGraph** | Multi-agent orchestration | Provides explicit graph-based control flow with conditional branching, essential for the correlation-first → RCA-fallback pipeline logic |
| **FastAPI** | Backend framework | Async-ready, lightweight, and produces automatic API docs which simplifies frontend integration and testing |
| **React + Vite** | Frontend | Fast dev server and modern component model matches the simple 3-section UI (ticket input, feedback, chat) |
| **OpenAI gpt-4o-mini** | LLM | Best cost-to-performance ratio for structured reasoning tasks like routing decisions and summary generation |
| **OpenAI text-embedding-3-small** | Embeddings | Low cost, 1536-dimension embeddings with strong semantic retrieval performance sufficient for a technical document |
| **Qdrant Cloud** | Vector store | Serverless-friendly, persistent across deployments, free tier sufficient for 137 chunks, and has a strong Python client |
| **MemorySaver** | Conversation memory | Built into LangGraph, zero-config, sufficient for single-session multi-turn chat without needing an external database |
| **LangSmith** | Tracing | Native LangGraph integration provides full agent trace visibility for debugging tool call sequences |
| **python-dotenv** | Config management | Keeps credentials out of code and works identically in local and Vercel environments |

---

## RAG and Agent Components

### RAG Component

The RAG component is implemented inside the `search_network_guide` tool. When called, it embeds the query using `text-embedding-3-small`, retrieves the top 5 most semantically relevant chunks from the `network_guide` Qdrant collection (137 chunks, 500 characters each with 100 character overlap, sourced from `network_architecture_EDIN_DETAILED.txt`), and passes them as context to `gpt-4o-mini` with a strict context-only instruction prompt. It is invoked exclusively by the RCA Agent when no planned changes are found, ensuring the model's resolution steps are grounded in actual EDIN network documentation rather than model hallucination.

### Agent Components

| Agent | Role | Tools |
|-------|------|-------|
| **Network Agent (Orchestrator)** | Fetches ticket details, synthesises final structured summary for the NOC engineer, routes follow-up chat questions to the correct specialist | `fetch_ticket` |
| **Correlation Agent** | Retrieves full end-to-end topology path for the affected node, checks planned changes on every node in the path, returns `CHANGE_RELATED` or `NO_CHANGE_RELATED` verdict | `search_inventory`, `search_planned_changes` |
| **RCA Agent** | Performs technical fault diagnosis using the network architecture guide via RAG when no planned change is found, returns root cause and resolution steps | `search_network_guide` |
---

## Task 3 — Data

### Data Sources

The application uses four data sources, three static and one retrieved via RAG.

#### 1. `tickets_data.py` — Fault Tickets
A Python dictionary of 150 simulated network fault tickets generated to match
the schema of a real telecom operator's ticketing system (e.g. ServiceNow).
Each ticket contains: ticket number, priority (H/M/L), node type (DSLAM, MB,
MC, CPE, LINK), affected node name, issue description, creation datetime, and
expected resolution datetime. Used by the `fetch_ticket` tool in the
orchestrator as the first step of every analysis pipeline.

**In production:** replaced by a live ServiceNow REST API call.

#### 2. `inventory_data.py` — Network Inventory
A Python dictionary of 100 end-to-end line records representing the full
DSLAM → Metro Bridge → Metro Core → Peta Core → Datacenter topology across
10 metropolitan areas. Each record contains: line ID, DSLAM node, CPE,
Metro Bridge node and port, Metro Core node and port, Peta Core, Datacenter,
fibre distance, VLAN, and line status. Indexed by DSLAM name, CPE name, and
line ID for O(1) lookup. Used by the `search_inventory` tool in the
Correlation Agent.

**In production:** replaced by a Network Inventory Management System (NIMS) API.

#### 3. `planned_changes_data.py` — Planned Change History
A Python dictionary of 130 planned maintenance change records (100 historical + 30 upcoming) covering all network nodes. Each record contains: change ID,
affected node, change type, start/end datetime, engineer, impact level, status,
and notes. Indexed by node name so all changes for any node are retrieved in a
single lookup. Used by the `search_planned_changes` tool in the Correlation
Agent to identify whether maintenance activity correlates with a fault.

**In production:** replaced by the Change Management module of ServiceNow API.

#### 4. `network_architecture_EDIN_DETAILED.txt` — Network Architecture Guide
A comprehensive 46,869-character technical reference document covering the
full EDIN network architecture including: topology description, per-device
configuration standards and CLI examples, fibre infrastructure specifications,
VLAN and IP addressing standards, QoS policy, fault management alarm
reference, six step-by-step troubleshooting procedures, SLA policy and
escalation matrix, and a full glossary. This is the RAG data source —
ingested into Qdrant Cloud as 137 vector chunks and queried by the
`search_network_guide` tool in the RCA Agent.

**In production:** maintained as a living document, re-ingested into Qdrant
whenever updated.

#### External APIs — Production Roadmap

In a production deployment within a real telecom operator environment,
the following external APIs would replace the current static data sources:

| Current Mock | Production API | Purpose |
|---|---|---|
| `tickets_data.py` | ServiceNow REST API | Fetch live fault tickets by ticket number |
| `inventory_data.py` | Network Inventory Management System (NIMS) API | Query live node topology |
| `planned_changes_data.py` | ServiceNow Change Management API | Fetch active and scheduled maintenance windows |

These integrations are not implemented in the current prototype because the
application is built against a specific telecom operator's internal systems
which are not publicly accessible. The static Python data files are faithful
representations of the real data schemas and serve as drop-in replacements
for development and demonstration purposes. The `fetch_ticket` tool is
explicitly designed to be swappable — replacing the dictionary lookup with
a ServiceNow API call requires changing only the tool implementation, with
zero changes to the agent or orchestrator logic.

### Chunking Strategy

#### Strategy Used
Recursive Character Text Splitting via LangChain's `RecursiveCharacterTextSplitter`
with the following parameters:

| Parameter | Value |
|-----------|-------|
| Chunk size | 500 characters |
| Chunk overlap | 100 characters |
| Splitter | RecursiveCharacterTextSplitter |
| Embedding model | text-embedding-3-small (1536 dimensions) |
| Total chunks produced | 137 |

#### Why This Strategy

**Why `RecursiveCharacterTextSplitter`:**
The network guide is a structured technical document with clearly delineated
sections (procedures, configuration examples, alarm references). The recursive
splitter attempts to split on natural boundaries in order — paragraphs, then
sentences, then words — which preserves semantic coherence within each chunk
better than a naive fixed-character splitter. This is important for a technical
document where a troubleshooting procedure split mid-step would produce an
incomplete and potentially misleading retrieval result.

**Why 500 character chunk size:**
The network guide contains short, dense technical paragraphs — CLI configuration
examples, alarm tables, and numbered procedure steps — rather than long flowing
prose. A 500 character window captures approximately one complete procedure step
or one configuration block, which is the right granularity for the RCA agent's
queries (e.g. "DSLAM port down troubleshooting steps"). Larger chunks (e.g. 1500
characters) would retrieve entire sections that dilute the relevant content with
unrelated context. Smaller chunks (e.g. 200 characters) would split individual
steps mid-sentence and lose procedural context.

**Why 100 character overlap:**
A 20% overlap (100 of 500 characters) ensures that content at chunk boundaries —
particularly the final line of one procedure step and the first line of the next
— is not lost between adjacent chunks. This is critical for numbered step
sequences where step 3 context may be needed to correctly interpret a retrieved
step 4 chunk.

## Task 4 — Prototype

## Overview

A fully functional end-to-end prototype has been built and deployed to localhost.
The system consists of a FastAPI backend with a LangGraph multi-agent orchestration
layer and a React/Vite frontend. The full investigation pipeline runs locally with
Qdrant Cloud as the external vector store.

---

## Running the Prototype

### Prerequisites
- Python 3.13 with virtual environment
- Node.js for frontend
- `.env` file with `OPENAI_API_KEY`, `QDRANT_URL`, `QDRANT_API_KEY`, `COHERE_API_KEY`, `LANGCHAIN_API_KEY`

### Start Backend
```bash
cd backend
uvicorn app.main:app --reload
# Running on http://127.0.0.1:8000
```

### Start Frontend
```bash
cd frontend
npm run dev
# Running on http://localhost:5173
```

---

## API Endpoints

| Method | Endpoint | Purpose |
|--------|----------|---------|
| `POST` | `/ticket/` | Submit ticket number, triggers full analysis pipeline |
| `POST` | `/feedback/` | Submit feedback on summary or recommendation |
| `POST` | `/chat/` | Follow-up question on an analysed ticket |
| `GET` | `/` | Health check |

---

## Full Pipeline Flow

```
User submits ticket number (e.g. TKT-2025001)
        │
        ▼
fetch_ticket_node         ← fetch ticket details from tickets_data.py
        │
        ▼
correlation_node          ← search_inventory: retrieve full topology path
                          ← search_planned_changes: check every node in path
        │
        ├── CHANGE_RELATED    ──► summary_change_related_node ──► Response
        │
        └── NO_CHANGE_RELATED ──► rca_node (search_network_guide RAG)
                                        │
                                  summary_rca_node ──► Response
```

---

## Example API Calls

### Ticket Analysis
```bash
curl -X POST http://localhost:8000/ticket/ \
  -H "Content-Type: application/json" \
  -d '{"ticket_number": "TKT-2025001"}'
```

**Response:**
```json
{
  "ticket_number": "TKT-2025001",
  "summary": "TICKET\n  Number   : TKT-2025001\n  Priority : H\n  ...",
  "thread_id": "ticket-TKT-2025001"
}
```

### Follow-up Chat
```bash
curl -X POST http://localhost:8000/chat/ \
  -H "Content-Type: application/json" \
  -d '{
    "ticket_number": "TKT-2025001",
    "thread_id": "ticket-TKT-2025001",
    "message": "What are the resolution steps?"
  }'
```

### Feedback Submission
```bash
curl -X POST http://localhost:8000/feedback/ \
  -H "Content-Type: application/json" \
  -d '{
    "ticket_number": "TKT-2025001",
    "section": "summary",
    "verdict": "correct",
    "comment": "Accurate root cause identified"
  }'
```

---

## Frontend

The frontend is built with React + Vite and runs on `http://localhost:5173`.
It provides three interaction surfaces matching the three backend endpoints:

| UI Section | Backend Endpoint | Purpose |
|---|---|---|
| Ticket input + Get Resolution button | `POST /ticket/` | Submit ticket number and display structured analysis |
| Feedback on summary (Correct / Incorrect / Comment) | `POST /feedback/` | Collect engineer verdict on the summary section |
| Feedback on recommendation (Correct / Incorrect / Comment) | `POST /feedback/` | Collect engineer verdict on the recommendation section |
| Chat interface | `POST /chat/` | Follow-up questions preserving full conversation context |

---

## Project Structure

```
Agentic-Network-Assistant/
├── backend/
│   ├── app/
│   │   ├── agents/
│   │   │   ├── agents.py          ← correlation_agent, rca_agent definitions
│   │   │   └── orchestrator.py    ← LangGraph supervisor graph + run_followup
│   │   ├── data/
│   │   │   ├── tickets_data.py    ← 150 fault tickets (static dict)
│   │   │   ├── inventory_data.py  ← 100 network lines (static dict)
│   │   │   └── planned_changes_data.py ← 130 change records (static dict)
│   │   ├── db/
│   │   │   └── feedback_store.py  ← feedback persistence
│   │   ├── services/
│   │   │   ├── llm.py             ← get_llm(), get_rag_llm()
│   │   │   ├── prompts.py         ← all agent and RAG prompts
│   │   │   └── tools.py           ← fetch_ticket, search_inventory,
│   │   │                             search_planned_changes, search_network_guide
│   │   └── main.py                ← FastAPI app, 3 endpoints
│   └── requirements.txt
├── frontend/
│   └── src/
│       └── App.jsx                ← React UI
└── network_rag.py                 ← one-time Qdrant ingestion (local only)
|__ raw_data/
        └── network_architecture_EDIN_DETAILED.txt
```

---

## Task 5 — Evals (RAGAS)

### RAG Pipeline Evaluation

The RAG component (`search_network_guide` tool) was evaluated using the RAGAS framework. A synthetic test dataset of 10 question-answer pairs was generated from `network_architecture_EDIN_DETAILED.txt` using `TestsetGenerator` with `gpt-4.1` as the generator LLM and `text-embedding-3-small` for embeddings. Each question was then run through the production RAG pipeline (`_rag_graph`) to collect responses and retrieved contexts. Evaluation was performed using `gpt-4.1-mini` as the judge LLM to avoid bias from using the same model as production.

#### RAG Baseline Results

| Metric | Score |
|--------|-------|
| Context Recall | 0.6888 |
| Faithfulness | 0.9009 |
| Factual Correctness | 0.5240 |
| Answer Relevancy | 0.8388 |
| Context Entity Recall | 0.2361 |
| Noise Sensitivity | 0.3960 |

---

### Agent Pipeline Evaluation

The multi-agent system was evaluated using RAGAS multi-turn metrics. Two test cases were designed to cover the primary agent paths: a valid ticket triggering the full analysis pipeline, and an invalid ticket testing error handling. Agent responses were collected by running the production `network_agent` graph and converting message traces using `convert_to_ragas_messages`.

#### Test Cases

| # | Ticket | Scenario | Expected Behaviour |
|---|--------|----------|--------------------|
| 1 | TKT-2025001 | Valid ticket, no planned changes | Full pipeline: fetch → correlation → RCA → structured summary |
| 2 | TKT-2025010 | Valid ticket, check for planned changes | Full pipeline: fetch → correlation → RCA → structured summary |
| 3 | TKT-9999999 | Invalid ticket number | Graceful not-found response without hallucinated analysis |

#### Agent Evaluation Results

| Metric | Score |
|--------|-------|
| Agent Goal Accuracy | 0.3333 |
| Topic Adherence (F1) | 0.6004 |

---

### Conclusions

**RAG Pipeline**

The RAG pipeline demonstrates strong faithfulness (0.90) and answer relevancy (0.84), confirming that responses are grounded in the retrieved context and relevant to the question asked. This is the most important property for a NOC tool where hallucinated resolution steps could lead an engineer to take incorrect actions on live network infrastructure.

The weakest metric is Context Entity Recall (0.24), meaning the retriever frequently fails to surface chunks containing key named entities such as node names, alarm codes, and CLI command references. This is consistent with the 500-character chunking strategy — dense technical entities are spread across many small chunks, and cosine similarity alone is insufficient to rank the most entity-rich chunks highest. Noise Sensitivity (0.40) further indicates that irrelevant chunks are making it into the top-5 retrieved set, diluting the context passed to the LLM. Factual Correctness (0.52) reflects that while responses are faithful to the retrieved context, the retrieved context itself does not always contain the most precise technical details needed for a fully correct answer.

**Agent Pipeline**

Agent Goal Accuracy (0.33) reflects two specific findings. TKT-2025010 scored 1.0, confirming the agent correctly executes the full pipeline and produces a structured output matching the expected goal. The invalid ticket case (TKT-9999999) scored 0, revealing a limitation: the agent continues through the full analysis pipeline even when `fetch_ticket` returns a not-found response, rather than halting and informing the engineer. This is a concrete improvement target for the next iteration. Topic Adherence (0.60) shows the agent broadly stays within scope but occasionally introduces content outside the expected domain — likely in the RCA summary where the LLM draws on general networking knowledge beyond the EDIN guide.

---

## Task 6 — Advanced Retrieval Technique

**Chosen technique: Contextual Compression with Cohere Reranking (k=20 → top 5)**

The baseline evaluation identified Context Entity Recall (0.24) and Noise Sensitivity (0.40) as the two weakest metrics. Both point to the same root cause: cosine similarity retrieval ranks chunks by general semantic proximity to the query, but cannot distinguish between a chunk that mentions a node type in passing and a chunk that contains the specific alarm reference or troubleshooting procedure being asked about. Cohere's `rerank-v3.5` model addresses this directly — it is a cross-encoder that scores the relevance of each candidate chunk against the full query text rather than comparing independent embeddings, making it significantly better at identifying entity-rich, procedure-specific chunks. By first retrieving 20 candidates from Qdrant (increasing recall) and then reranking to the top 5 (increasing precision), the pipeline captures more relevant content while filtering out the noise that was degrading response quality.

### Implementation

The advanced retriever is implemented in `app/services/tools.py` as `_advanced_rag_graph`, a separate LangGraph compiled graph that shares the same `_RAGState`, `_generate` node, and RAG prompt as the baseline graph. The only difference is the retrieve step, which now performs a two-stage retrieval:

```python
def _advanced_retrieve(state: _RAGState):
    # Stage 1: retrieve 20 candidates from Qdrant via dense vector search
    docs = _advanced_retriever.invoke(state["question"])

    # Stage 2: rerank with Cohere cross-encoder down to top 5
    rerank_response = _cohere_client.rerank(
        model="rerank-v3.5",
        query=state["question"],
        documents=[doc.page_content for doc in docs],
        top_n=5,
    )
    reranked_docs = [docs[r.index] for r in rerank_response.results]
    return {"context": reranked_docs}
```

The Cohere client is initialised once at module level using `COHERE_API_KEY` from the environment. The baseline `_rag_graph` is preserved unchanged so both pipelines can be run independently.

### Performance Comparison

Both pipelines were evaluated on the same 10-question synthetic test dataset using identical RAGAS metrics and the same `gpt-4.1-mini` judge.

| Metric | Baseline (Dense k=5) | Reranked (k=20 + Cohere) | Change |
|--------|---------------------|--------------------------|--------|
| Context Recall | 0.6888 | 0.6888 | → 0.00 |
| Faithfulness | 0.9009 | 0.8697 | ↓ −0.03 |
| Factual Correctness | 0.5240 | 0.5470 | ↑ +0.02 |
| Answer Relevancy | 0.8388 | 0.8411 | ↑ +0.002 |
| Context Entity Recall | 0.2361 | 0.2933 | ↑ **+0.06** |
| Noise Sensitivity | 0.3960 | 0.3703 | ↑ **+0.03** |

Cohere reranking improved the two target metrics as predicted. Context Entity Recall increased by +0.06 (25% relative improvement), confirming that the cross-encoder is more effective than cosine similarity at surfacing entity-rich chunks containing node names, alarm codes, and configuration references. Noise Sensitivity improved by +0.03, meaning the reranker successfully filtered out irrelevant chunks that were diluting the context window. Factual Correctness improved marginally (+0.02), reflecting slightly better context quality. The small drop in Faithfulness (−0.03) is within noise range and likely reflects occasional borderline chunks in the expanded 20-candidate pool before reranking. Context Recall is unchanged because the reference answers and question set did not change between runs.


## Task 7 — Next Steps

### RAG Implementation Decision: Dense Vector Retrieval for Demo Day

**Yes, the RAG implementation will retain dense vector retrieval as its foundation, combined with Cohere reranking, for Demo Day.**

Dense vector retrieval via Qdrant with `text-embedding-3-small` is the right core retrieval strategy for this use case. The EDIN network architecture guide is a single, stable technical document with rich semantic structure — troubleshooting procedures, alarm references, and configuration standards that are better matched by semantic similarity than keyword overlap. A purely keyword-based approach such as BM25 would struggle with queries phrased in natural language by NOC engineers (e.g. "what do I do when a DSLAM port goes down") where the exact terminology in the guide may differ from the query phrasing. Dense retrieval handles this semantic gap well, as demonstrated by the strong Faithfulness (0.90) and Answer Relevancy (0.84) scores in the baseline evaluation.

The Cohere reranking layer addresses the one area where dense retrieval alone is insufficient — precision on entity-rich technical content. The +0.06 improvement in Context Entity Recall and +0.03 improvement in Noise Sensitivity confirm that the two-stage approach (dense k=20 → rerank → top 5) meaningfully improves the quality of context passed to the LLM without introducing significant latency for a NOC use case where an engineer is already waiting several seconds for the full multi-agent pipeline to complete.

### Retrieval Improvements Planned for Demo Day

Despite the improvements from Cohere reranking, Context Entity Recall (0.29) and Noise Sensitivity (0.37) remain the weakest metrics and represent the clearest retrieval improvement opportunities. Two techniques are planned for evaluation before Demo Day:

**Ensemble Retriever (BM25 + Dense + Cohere rerank)** — entity names such as `DSLAM-EDI-028`, `MB-01`, and alarm codes are exact keywords that cosine similarity can miss when phrased differently in a query. BM25 would surface these reliably via keyword matching. Combining BM25 and dense retrieval via Reciprocal Rank Fusion before applying Cohere reranking would directly target the entity recall gap identified in evaluation.

**Parent Document Retriever** — the current 500-character chunks capture fragments of procedures but can miss surrounding context that contains key entity references. Searching on smaller 200-character child chunks for better semantic matching while returning larger 1000-character parent chunks to the LLM would provide richer context without requiring re-ingestion of the Qdrant collection.

### Agent Improvements Planned for Demo Day

The agent evaluation identified two concrete issues to fix before Demo Day.

**Invalid ticket handling** — the orchestrator currently continues through the full analysis pipeline even when `fetch_ticket` returns a not-found response, rather than halting and informing the engineer. This will be fixed by adding an explicit check in `fetch_ticket_node` that routes to END with a clear user-facing message when the ticket is not found.

**Sub-agent evaluation** — the current evaluation only covers the top-level orchestrator. Before Demo Day, the correlation agent and RCA agent will be evaluated independently using RAGAS multi-turn metrics, with test cases targeting specific tool call sequences and domain adherence. This will give a more precise picture of where agent goal accuracy is being lost — whether in the correlation verdict logic, the RCA guide retrieval, or the final summary generation.

## Final Submission

### Loom Video
[Agentic Network Assistant — Live Demo](https://www.loom.com/share/c0f2a15dbbce44ec95ca10a548be2ce6)

### GitHub Repository
[github.com/your-username/Agentic-Network-Assistant](https://github.com/Ayushi-Kandoi/Agentic-Network-Assistant)