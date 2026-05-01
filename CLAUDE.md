# CLAUDE.md — Contract Risk Agent

## Project Goal
End-to-end Agentic AI + RAG demo that answers complex legal questions across 510 real commercial contracts (CUAD dataset), analyzes new contracts for risk, and drafts contract clauses — all powered by one dynamic agent system.

This is a Principal Data Scientist interview demo for Niagara Bottling (GenAI/Agentic AI role).

---

## Three Demo Use Cases

### Mode 1 — Risk Assessment
User uploads or selects a contract. Agent indexes it, retrieves similar clauses from full 510-contract corpus, compares, scores risk relative to corpus, summarizes findings, sends email to deepanvishal@gmail.com, updates dashboard.

### Mode 2 — Cross-Corpus Search
User asks a natural language question about the corpus.
Examples:
- "Which contracts have termination clauses with less than 30 days notice?"
- "Find all supply agreements with uncapped liability"
- "Which contracts expire in 2025 with auto-renewal clauses?"
Agent retrieves relevant clauses across all 510 contracts, synthesizes and displays answer.

### Mode 3 — Clause Drafting
User asks agent to draft a clause based on corpus patterns.
Examples:
- "Draft a termination clause that protects the buyer"
- "Write a liability cap clause based on industry standard supply agreements"
Agent retrieves examples of that clause type from corpus, identifies protective patterns, drafts new clause, explains reasoning behind each element.

---

## Tech Stack

| Layer | Tool |
|---|---|
| Agent orchestration | LangGraph |
| RAG framework | LlamaIndex |
| Vector DB | ChromaDB (local, persistent) |
| Embedding model | sentence-transformers all-MiniLM-L6-v2 |
| LLM (demo) | Claude API claude-sonnet-4-20250514 |
| LLM (dev) | Ollama LLaMA 3 8B Instruct |
| PDF parsing | PyMuPDF (fitz) |
| Backend | FastAPI + WebSockets |
| Database | SQLite |
| Email | Gmail SMTP App Password |
| Frontend | React + Tailwind CSS |
| Charts | Recharts |

---

## Project Structure

```
contract-risk-agent/
├── CLAUDE.md
├── requirements.txt
├── .env
├── .env.example
├── backend/
│   ├── main.py
│   ├── config.py
│   ├── agents/
│   │   ├── __init__.py
│   │   ├── orchestrator.py            <- needs redesign for dynamic routing
│   │   ├── ingestion_agent.py
│   │   ├── retrieval_agent.py         <- needs update for full corpus query
│   │   ├── clause_agent.py
│   │   ├── risk_agent.py              <- needs corpus comparison logic
│   │   ├── comparison_agent.py        <- NOT YET BUILT
│   │   ├── drafting_agent.py          <- NOT YET BUILT
│   │   ├── summary_agent.py
│   │   └── notification_agent.py
│   ├── rag/
│   │   ├── __init__.py
│   │   ├── indexer.py
│   │   ├── retriever.py
│   │   └── reset.py
│   ├── db/
│   │   ├── __init__.py
│   │   ├── schema.py
│   │   ├── writer.py
│   │   └── reader.py
│   ├── email/
│   │   ├── __init__.py
│   │   └── sender.py
│   └── contracts/
│       ├── preloaded/                 <- 5 sample contracts for demo dropdown
│       └── uploads/                  <- user uploaded contracts during demo
├── scripts/
│   ├── README.md
│   ├── setup_all.py
│   ├── setup_db.py
│   ├── download_contracts.py          <- currently downloads 5, needs update for 510
│   ├── index_corpus.py                <- NOT YET BUILT
│   └── reset_demo.py
└── frontend/                          <- NOT YET BUILT
```

---

## Agent Definitions

### Orchestrator Agent (needs redesign)
- Receives user query + optional uploaded contract
- Classifies intent into Mode 1, 2, or 3 using LLM
- Dynamically selects which agents to invoke based on mode
- NOT a fixed linear pipeline
- Manages shared state across all agent calls
- Emits websocket events at each step for frontend visualization

### Ingestion Agent
- Validates PDF — must be readable, minimum 500 chars extracted
- Extracts full text via PyMuPDF
- Calls indexer to chunk, embed, store in new_contracts ChromaDB collection
- Emits RAG progress events: received, extracting, chunking, embedding, indexed
- Only fires in Mode 1

### Retrieval Agent (needs update)
- Queries ChromaDB corpus collection (510 contracts) by default
- Accepts optional filters: contract_name, contract_type, clause_type
- Mode 1: retrieves similar clauses from corpus to compare against new contract
- Mode 2: retrieves across full corpus with no contract filter
- Mode 3: retrieves all examples of requested clause type from corpus
- Uses hybrid search: semantic + BM25 + cross-encoder reranker
- Does NOT call LLM — only fetches chunks

### Clause Extraction Agent
- Extracts: termination, liability cap, penalty, indemnification, governing law clauses
- Extracts supplier/party name from contract text
- Works on both new contract text and retrieved corpus chunks

### Risk Scoring Agent (needs update)
- Scores each clause 0-100 with reason
- Compares against corpus — flags if riskier than X% of similar contracts
- Weighted overall score: termination 25%, liability 25%, penalty 20%, indemnification 20%, governing law 10%
- High >66, Medium 33-66, Low <33
- Only fires in Mode 1

### Comparison Agent (NOT YET BUILT)
- Receives new contract clauses + similar corpus clauses
- Identifies deviations from corpus norms
- Flags unusually risky or unusually favorable terms with evidence from corpus
- Only fires in Mode 1

### Clause Drafting Agent (NOT YET BUILT)
- Receives corpus examples of requested clause type
- Identifies protective patterns across examples
- Drafts new clause with explanation of each element chosen
- Only fires in Mode 3

### Summary Agent
- Adapts output format based on mode:
  - Mode 1: risk highlights + recommendation (approve/renegotiate/reject)
  - Mode 2: synthesized answer across corpus with source contracts cited
  - Mode 3: drafted clause + reasoning per element

### Notification Agent
- Fires only in Mode 1
- Sends HTML email to deepanvishal@gmail.com with risk summary + speedometer snapshot
- Writes structured record to SQLite
- Reports email sent status back to orchestrator

---

## ChromaDB Collections

| Collection | Contents | When indexed |
|---|---|---|
| corpus | All 510 CUAD contracts | Once at setup via scripts/index_corpus.py |
| new_contracts | Contracts uploaded during demo | On demand during Mode 1 |

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

Top row: Speedometer dial (0-100, sporty digital style, Red/Amber/Green zones), total contracts analyzed, High/Medium/Low risk counts
Middle row: Clause risk breakdown bar chart, risk distribution donut chart (Recharts)
Bottom row: Recent contracts table — name, supplier, risk level, recommendation, date, email status

Dashboard reads from SQLite via FastAPI GET endpoints.
Only refreshes after Mode 1 analysis completes.
Dashboard does NOT poll continuously.

---

## RAG Pipeline Details

**Indexing (corpus — one time at setup):**
- Source: all 510 CUAD contracts
- Chunk size: 512 tokens, overlap: 64 tokens
- Embedding: sentence-transformers all-MiniLM-L6-v2
- Metadata per chunk: contract_name, chunk_index, clause_type_hint
- Collection: corpus
- Script: scripts/index_corpus.py

**Indexing (new_contracts — on demand):**
- Triggered by Ingestion Agent during Mode 1
- Same chunking and embedding settings
- Collection: new_contracts
- Progress streamed to frontend via websocket

**Retrieval:**
- Hybrid: ChromaDB cosine similarity + BM25 reciprocal rank fusion
- Reranker: cross-encoder ms-marco-MiniLM-L-6-v2
- Top K: 10 chunks default
- Filter by collection and metadata as needed per mode

---

## Frontend Visualization

**RAG Indexing (Mode 1):**
Sequential steps lighting up:
PDF received → Extracting text → Chunking → Generating embeddings → Storing in ChromaDB → Index complete

**Agent Graph (all modes):**
Live node graph showing agent execution:
- Gray = waiting
- Yellow/pulsing = currently running
- Green = complete
- Red = failed
Nodes connected by animated edges. Status text shown per node.
Powered by FastAPI WebSocket streaming LangGraph state to React.

---

## API Endpoints

| Method | Endpoint | Purpose |
|---|---|---|
| WebSocket | /ws/analyze | Stream agent execution for Mode 1 |
| WebSocket | /ws/query | Stream agent execution for Mode 2 and 3 |
| GET | /contracts | List all analyzed contracts |
| GET | /contracts/{id} | Get single contract |
| GET | /dashboard/stats | Dashboard metrics |
| POST | /upload | Upload PDF, validate, save to uploads/ |
| DELETE | /reset | Wipe ChromaDB + SQLite |
| GET | /preloaded | List 5 preloaded contract names |

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

## Scripts

| Script | Purpose | Status |
|---|---|---|
| setup_all.py | Run DB init + contract download in order | DONE |
| setup_db.py | Initialize SQLite DB | DONE |
| download_contracts.py | Download CUAD contracts from Zenodo | DONE (5 only, needs update for 510) |
| index_corpus.py | Index all contracts into ChromaDB corpus collection | NOT YET BUILT |
| reset_demo.py | Wipe ChromaDB + SQLite for clean demo run | DONE |

---

## Current Build Status

**COMPLETE:**
- All backend files scaffolded (21 files)
- SQLite DB initialized at ./db/contracts.db
- 5 sample CUAD contracts downloaded into backend/contracts/preloaded/
- FastAPI running on port 8000 — all endpoints registered
- scripts/ folder with setup, download, reset scripts
- requirements.txt installed in conda env contract-agent Python 3.11

**NOT YET DONE:**
- download_contracts.py needs update to download all 510 contracts from Zenodo
- scripts/index_corpus.py not yet created
- ChromaDB corpus collection not yet indexed
- Orchestrator needs redesign for dynamic Mode 1/2/3 routing
- comparison_agent.py not yet built
- drafting_agent.py not yet built
- Risk agent needs corpus comparison logic added
- Frontend not yet built

---

## Setup Instructions (fresh machine)

```bash
# 1. Create conda environment
conda create -n contract-agent python=3.11
conda activate contract-agent

# 2. Install dependencies
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu124
pip install -r requirements.txt

# 3. Configure environment
cp .env.example .env
# Edit .env with ANTHROPIC_API_KEY and GMAIL_APP_PASSWORD

# 4. Run setup
python scripts/setup_all.py

# 5. Index corpus (run once, takes ~10-15 mins)
python scripts/index_corpus.py

# 6. Start backend
python -m uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

---

## Key Decisions (do not change without reason)

- Only Notification Agent writes to SQLite
- Only Dashboard reads from SQLite
- Retrieval Agent never calls LLM
- Claude API for demo day, Ollama for dev — switch via LLM_PROVIDER
- Two ChromaDB collections: corpus and new_contracts
- Risk score is 0-100 integer
- Email hardcoded to deepanvishal@gmail.com
- Frontend communicates via WebSocket for live updates
- FastAPI REST for dashboard reads
- No authentication — demo only
- SQLite only — no PostgreSQL

---

## What NOT to Do

- Do not use fixed linear pipeline in orchestrator
- Do not query only the uploaded contract — always query corpus
- Do not index uploads into corpus collection — use new_contracts
- Do not call LLM inside Retrieval Agent
- Do not add authentication
- Do not use PostgreSQL
- Do not use OpenAI API
- Do not add features not listed without confirming first
- Do not hardcode API keys anywhere
