import asyncio
import logging
from typing import TypedDict, List

from langgraph.graph import StateGraph, END

from backend.agents import (
    ingestion_agent,
    retrieval_agent,
    clause_agent,
    risk_agent,
    comparison_agent,
    drafting_agent,
    summary_agent,
    notification_agent,
)
from backend.config import call_llm

logger = logging.getLogger(__name__)


class AgentState(TypedDict):
    # inputs
    query: str
    pdf_path: str
    contract_name: str
    mode: str  # "risk_assessment" | "corpus_search" | "clause_drafting"
    # ingestion
    raw_text: str
    chunk_count: int
    # retrieval
    chunks: List[str]         # new contract chunks (Mode 1 only)
    corpus_clauses: List[str] # corpus chunks for comparison / drafting (all modes)
    # clause extraction
    clauses: List[dict]
    # risk scoring
    risk_score: int
    risk_level: str
    flagged_clauses: List[dict]
    # comparison (Mode 2)
    comparison_result: dict
    # drafting (Mode 3)
    draft_clause: str
    # summary / output
    highlights: List[str]
    summary: str
    recommendation: str
    supplier_name: str
    # persistence (Mode 1 only)
    email_sent: bool
    db_id: int
    # meta
    status_updates: List[dict]
    error: str


_VALID_MODES = {"risk_assessment", "corpus_search", "clause_drafting"}

_INTENT_PROMPT = """Classify the user's intent into exactly one of three categories:

1. risk_assessment — the user uploaded a contract PDF and wants risk analysis
2. corpus_search   — the user wants to search or benchmark against the CUAD contract corpus
3. clause_drafting — the user wants to draft or generate a contract clause

User query: {query}

Respond with ONLY one of: risk_assessment, corpus_search, clause_drafting"""


async def run_pipeline(
    query: str,
    pdf_path: str | None,
    contract_name: str | None,
    websocket_callback,
    mode_hint: str | None = None,
) -> dict:
    async def _send(agent: str, status: str, data: dict | None = None) -> None:
        try:
            await websocket_callback({"agent": agent, "status": status, "data": data or {}})
        except Exception as exc:
            logger.warning("websocket_callback failed (%s/%s): %s", agent, status, exc)

    # ── Node definitions ──────────────────────────────────────────────────────

    async def intent_classifier_node(state: AgentState) -> dict:
        if state.get("mode") in _VALID_MODES:
            await _send("intent_classifier", "done", {"mode": state["mode"]})
            return {}

        # pdf_path present → always risk_assessment
        if state.get("pdf_path"):
            await _send("intent_classifier", "done", {"mode": "risk_assessment"})
            return {"mode": "risk_assessment"}

        await _send("intent_classifier", "running")
        prompt = _INTENT_PROMPT.format(query=state.get("query", ""))
        raw = await asyncio.to_thread(call_llm, prompt, 20)
        mode = "corpus_search"
        for m in _VALID_MODES:
            if m in raw.lower():
                mode = m
                break
        await _send("intent_classifier", "done", {"mode": mode})
        return {"mode": mode}

    async def ingestion_node(state: AgentState) -> dict:
        await _send("ingestion", "running")

        async def rag_progress(step: str) -> None:
            await _send("ingestion", "progress", {"step": step})

        try:
            result = await ingestion_agent.run(state, rag_progress)
        except Exception as exc:
            await _send("ingestion", "error", {"error": str(exc)})
            raise
        await _send("ingestion", "done", {"chunk_count": result.get("chunk_count", 0)})
        return result

    async def retrieval_node(state: AgentState) -> dict:
        await _send("retrieval", "running")
        result = await asyncio.to_thread(retrieval_agent.run, state)
        await _send(
            "retrieval",
            "done",
            {
                "chunks_retrieved": len(result.get("chunks", [])),
                "corpus_chunks": len(result.get("corpus_clauses", [])),
            },
        )
        return result

    async def clause_node(state: AgentState) -> dict:
        await _send("clause_extraction", "running")
        result = await asyncio.to_thread(clause_agent.run, state)
        await _send("clause_extraction", "done", {"supplier_name": result.get("supplier_name")})
        return result

    async def risk_node(state: AgentState) -> dict:
        await _send("risk_scoring", "running")
        result = await asyncio.to_thread(risk_agent.run, state)
        await _send(
            "risk_scoring",
            "done",
            {"risk_score": result.get("risk_score"), "risk_level": result.get("risk_level")},
        )
        return result

    async def comparison_node(state: AgentState) -> dict:
        await _send("comparison", "running")
        result = await asyncio.to_thread(comparison_agent.run, state)
        await _send("comparison", "done")
        return result

    async def drafting_node(state: AgentState) -> dict:
        await _send("drafting", "running")
        result = await asyncio.to_thread(drafting_agent.run, state)
        await _send("drafting", "done", {"clause_type": result.get("comparison_result", {}).get("clause_type", "")})
        return result

    async def summary_node(state: AgentState) -> dict:
        await _send("summary", "running")
        result = await asyncio.to_thread(summary_agent.run, state)
        await _send("summary", "done", {"recommendation": result.get("recommendation", "")})
        return result

    async def notification_node(state: AgentState) -> dict:
        await _send("notification", "running")
        result = await asyncio.to_thread(notification_agent.run, state)
        await _send(
            "notification",
            "done",
            {"email_sent": result.get("email_sent"), "db_id": result.get("db_id")},
        )
        return result

    # ── Routing functions ─────────────────────────────────────────────────────

    def route_from_classifier(state: AgentState) -> str:
        if state.get("mode") == "risk_assessment":
            return "ingestion"
        return "retrieval"

    def route_from_retrieval(state: AgentState) -> str:
        mode = state.get("mode", "corpus_search")
        if mode == "risk_assessment":
            return "clause_extraction"
        if mode == "clause_drafting":
            return "drafting"
        return "comparison"

    def route_from_summary(state: AgentState) -> str:
        if state.get("mode") == "risk_assessment":
            return "notification"
        return END

    # ── Graph construction ────────────────────────────────────────────────────

    builder = StateGraph(AgentState)
    builder.add_node("intent_classifier", intent_classifier_node)
    builder.add_node("ingestion", ingestion_node)
    builder.add_node("retrieval", retrieval_node)
    builder.add_node("clause_extraction", clause_node)
    builder.add_node("risk_scoring", risk_node)
    builder.add_node("comparison", comparison_node)
    builder.add_node("drafting", drafting_node)
    builder.add_node("summary", summary_node)
    builder.add_node("notification", notification_node)

    builder.set_entry_point("intent_classifier")
    builder.add_conditional_edges("intent_classifier", route_from_classifier)
    builder.add_edge("ingestion", "retrieval")
    builder.add_conditional_edges("retrieval", route_from_retrieval)
    builder.add_edge("clause_extraction", "risk_scoring")
    builder.add_edge("risk_scoring", "summary")
    builder.add_edge("comparison", "summary")
    builder.add_edge("drafting", "summary")
    builder.add_conditional_edges("summary", route_from_summary)
    builder.add_edge("notification", END)

    graph = builder.compile()

    initial_state: AgentState = {
        "query": query,
        "pdf_path": pdf_path or "",
        "contract_name": contract_name or "",
        "mode": mode_hint if mode_hint in _VALID_MODES else "",
        "raw_text": "",
        "chunk_count": 0,
        "chunks": [],
        "corpus_clauses": [],
        "clauses": [],
        "risk_score": 0,
        "risk_level": "Low",
        "flagged_clauses": [],
        "comparison_result": {},
        "draft_clause": "",
        "highlights": [],
        "summary": "",
        "recommendation": "",
        "supplier_name": "",
        "email_sent": False,
        "db_id": 0,
        "status_updates": [],
        "error": "",
    }

    result = await graph.ainvoke(initial_state)
    return dict(result)
