# CLAUDE.md — Contract Risk Analysis Agent

## Project Goal
Build an end-to-end Agentic AI + RAG demo that analyzes commercial contracts for risk,
visualizes agent execution in real time, sends email summaries, and updates a dashboard.
This is a Principal Data Scientist interview demo for Niagara Bottling.

---

## Tech Stack

| Layer | Tool |
|---|---|
| Agent orchestration | LangGraph |
| RAG framework | LlamaIndex |
| Vector DB | ChromaDB (local, persistent) |
| Embedding model | sentence-transformers (all-MiniLM-L6-v2) |
| LLM (demo) | Claude API (claude-sonnet-4-20250514) |
| LLM (dev) | Ollama + LLaMA 3 8B Instruct |
| PDF parsing | PyMuPDF (fitz) |
| Backend | FastAPI + WebSockets |
| Database | SQLite |
| Email | Gmail SMTP (App Password) |
| Frontend | React + Tailwind CSS |
| Charts | Recharts |

---

## Project Structure

```
contract-risk-agent/
├── CLAUDE.md
├── backend/
│   ├── main.py                  # FastAPI app, websocket endpoints
│   ├── agents/
│   │   ├── orchestrator.py      # LangGraph graph definition
│   │   ├── ingestion_agent.py   # PDF validation, text extraction, RAG trigger
│   │   ├── retrieval_agent.py   # ChromaDB hybrid search, reranker
│   │   ├── clause_agent.py      # Clause extraction + supplier name
│   │   ├── risk_agent.py        # Risk scoring per clause + overall score
│   │   ├── summary_agent.py     # Human readable summary + recommendation
│   │   └── notification_agent.py# Email + SQLite write
│   ├── rag/
│   │   ├── indexer.py           # Chunking, embedding, ChromaDB upsert
│   │   ├── retriever.py         # Hybrid search (semantic + BM25) + reranker
│   │   └── reset.py             # Wipe ChromaDB collection
│   ├── db/
│   │   ├── schema.py            # SQLite table definition
│   │   ├── writer.py            # Insert contract record
│   │   └── reader.py            # Dashboard queries
│   ├── email/
│   │   └── sender.py            # Gmail SMTP sender
│   ├── contracts/
│   │   └── preloaded/           # 5 CUAD contracts (PDF)
│   └── config.py                # API keys, paths, constants
├── frontend/
│   ├── src/
│   │   ├── App.jsx
│   │   ├── components/
│   │   │   ├── ContractSelector.jsx   # Dropdown + upload
│   │   │   ├── RAGProgress.jsx        # Step-by-step indexing visual
│   │   │   ├── AgentGraph.jsx         # Live agent node visualization
│   │   │   ├── ContractHighlights.jsx # Summary + flagged clauses
│   │   │   ├── Dashboard.jsx          # Single page dashboard
│   │   │   ├── Speedometer.jsx        # 0-100 risk dial
│   │   │   └── ResetButton.jsx        # Wipe demo state
│   └── package.json
├── requirements.txt
└── .env
```

---

## Demo Flow (exact sequence)

1. User selects contract from dropdown (5 preloaded) OR uploads a PDF
2. Ingestion Agent validates PDF, extracts text, triggers RAG indexing
3. UI shows RAG progress steps lighting up sequentially
4. LangGraph orchestrator starts agent graph
5. UI shows agent nodes lighting up: gray → yellow (running) → green (done)
6. Retrieval Agent queries ChromaDB, returns relevant chunks
7. Clause Extraction Agent identifies clause types, extracts supplier name
8. Risk Scoring Agent scores each clause 0-100, produces overall score
9. Summary Agent writes highlights and recommendation
10. Frontend displays contract highlights + speedometer
11. Notification Agent sends email to deepanvishal@gmail.com
12. Notification Agent writes record to SQLite
13. Dashboard updates with new contract entry

---

## Agent Definitions

### 1. Ingestion Agent
- Input: PDF file path or upload
- Validates PDF is readable and text-extractable
- Extracts raw text via PyMuPDF
- Triggers RAG indexer (chunking → embedding → ChromaDB upsert)
- Emits progress events via websocket: received, extracting, chunking, embedding, indexed
- Output: chunk count, index status, raw text

### 2. Retrieval Agent
- Input: query string from orchestrator
- Queries ChromaDB using hybrid search (semantic + BM25)
- Runs cross-encoder reranker on results
- Returns top K chunks (K=10 default)
- Does NOT reason — only fetches
- Output: list of ranked text chunks

### 3. Clause Extraction Agent
- Input: chunks from retrieval agent
- Calls LLM to identify and extract:
  - Termination clause
  - Liability cap clause
  - Penalty / liquidated damages clause
  - Indemnification clause
  - Governing law clause
  - Supplier / party name
- Output: structured dict of clause type → extracted text + supplier name

### 4. Risk Scoring Agent
- Input: structured clauses from clause extraction agent
- Calls LLM to score each clause 0-100
- Produces overall risk score (weighted average)
- Assigns risk level: High (>66), Medium (33-66), Low (<33)
- Provides reason per clause
- Output: per-clause scores + overall score + risk level + reasons

### 5. Summary Agent
- Input: risk scores + clauses + reasons
- Calls LLM to write:
  - 3-5 bullet point highlights
  - One line recommendation: Approve / Renegotiate / Reject
- Output: highlights list + recommendation string

### 6. Notification Agent
- Input: full analysis result from summary agent
- Sends email via Gmail SMTP to deepanvishal@gmail.com
  - Subject: "Contract Risk Alert: [contract name] — [risk level]"
  - Body: highlights + speedometer snapshot + flagged clauses + recommendation
- Writes record to SQLite (see DB schema below)
- Reports email sent status back to orchestrator
- Output: email status + DB record ID

---

## DB Schema (SQLite — contracts table)

```sql
CREATE TABLE contracts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    contract_name TEXT NOT NULL,
    supplier_name TEXT,
    risk_score INTEGER,
    risk_level TEXT,
    recommendation TEXT,
    flagged_clauses JSON,
    summary TEXT,
    email_sent BOOLEAN DEFAULT FALSE,
    email_recipient TEXT DEFAULT 'deepanvishal@gmail.com',
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    contract_text TEXT,
    chunk_count INTEGER
);
```

---

## Dashboard (single page)

**Top row:**
- Speedometer dial (0-100, sporty digital style, Red/Amber/Green zones)
- Total contracts analyzed (count)
- Risk breakdown counts (High / Medium / Low)

**Middle row:**
- Bar chart: clause types flagged most frequently (Recharts)
- Donut chart: risk level distribution across all contracts (Recharts)

**Bottom row:**
- Recent contracts table: name, supplier, risk level, recommendation, date, email status

Dashboard reads from SQLite via FastAPI GET endpoints.
Dashboard does NOT poll — refreshes after each new analysis completes.

---

## RAG Pipeline Details

**Indexing (one time per contract):**
- Chunk size: 512 tokens, overlap: 64 tokens
- Embedding: sentence-transformers all-MiniLM-L6-v2
- Storage: ChromaDB persistent local collection named "contracts"
- Metadata stored per chunk: contract_name, chunk_index, clause_type_hint

**Retrieval (per query):**
- Semantic search: cosine similarity via ChromaDB
- BM25 keyword search: LlamaIndex BM25Retriever
- Fusion: reciprocal rank fusion of both results
- Reranker: cross-encoder ms-marco-MiniLM-L-6-v2
- Top K: 10 chunks returned to agent

---

## Reset Functionality
Reset button in UI triggers:
1. ChromaDB collection "contracts" — delete and recreate
2. SQLite — DELETE all rows from contracts table
3. Frontend state — cleared
4. Does NOT delete preloaded contract PDFs

---

## Upload Guardrails
For user uploaded PDFs:
- Max file size: 10MB
- Must be valid PDF (PyMuPDF check)
- Must extract minimum 500 characters of text (rejects scanned/image PDFs)
- If fails: show clear error in UI, do not crash pipeline
- Sanitize filename before storing

---

## LLM Configuration

**Demo (Claude API):**
```python
model = "claude-sonnet-4-20250514"
max_tokens = 1000
```

**Dev (Ollama local):**
```python
model = "llama3:8b-instruct"
base_url = "http://localhost:11434"
```

Switch via LLM_PROVIDER env var: "claude" or "ollama"

---

## Environment Variables (.env)

```
ANTHROPIC_API_KEY=
GMAIL_ADDRESS=
GMAIL_APP_PASSWORD=
LLM_PROVIDER=claude
CHROMA_PERSIST_PATH=./chroma_db
SQLITE_PATH=./db/contracts.db
```

---

## Key Decisions (do not change without reason)

- Only Notification Agent writes to SQLite
- Only Dashboard reads from SQLite
- Retrieval Agent does not call LLM — only fetches chunks
- Claude API used for demo day — Ollama for dev only
- ChromaDB collection name is always "contracts"
- Risk score is 0-100 integer, not float
- Email recipient is hardcoded deepanvishal@gmail.com
- 5 preloaded contracts live in backend/contracts/preloaded/
- Frontend communicates with backend via WebSocket for live updates
- FastAPI REST endpoints for dashboard data reads

---

## Preloaded Contracts (CUAD)
Select 5 contracts from CUAD dataset with varying risk profiles:
- 1 Low risk (score ~20)
- 2 Medium risk (score ~45-55)
- 2 High risk (score ~75-85)
This ensures demo shows full speedometer range.

---

## What NOT to do
- Do not add authentication — this is a demo
- Do not add multi-user support
- Do not use PostgreSQL — SQLite only
- Do not call LLM inside Retrieval Agent
- Do not store embeddings anywhere except ChromaDB
- Do not add features not listed here without confirming first
- Do not use OpenAI API — Claude or Ollama only
