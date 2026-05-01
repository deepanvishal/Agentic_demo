import json
import logging

from backend.config import call_llm, extract_json_str

logger = logging.getLogger(__name__)

_RISK_PROMPT = """You are a contract analyst briefing a procurement executive.

CONTRACT: {contract_name}
SUPPLIER: {supplier_name}
OVERALL RISK: {risk_score}/100 — {risk_level}

CLAUSE ANALYSIS:
{clauses_json}

Write an executive summary. Return ONLY a valid JSON object with this exact structure:
{{
  "highlights": [
    "Complete sentence describing finding or risk — be specific",
    "Complete sentence describing finding or risk — be specific",
    "Complete sentence describing finding or risk — be specific"
  ],
  "recommendation": "Approve"
}}

Rules:
- highlights: exactly 3 to 5 complete sentences, each describing a specific finding
- recommendation: must be exactly one of: "Approve", "Renegotiate", or "Reject"
  - Low risk (score < 33)  → Approve
  - Medium risk (33-66)    → Renegotiate
  - High risk (> 66)       → Reject

Return ONLY the JSON object. No explanation, no markdown."""

_CORPUS_SEARCH_PROMPT = """You are a contract analyst summarizing corpus search findings for a procurement team.

USER QUERY: {query}

CORPUS COMPARISON FINDINGS:
Answer: {answer}
Key Findings: {key_findings}
Typical Range: {typical_range}

Write a concise executive summary of these findings. Return ONLY a valid JSON object:
{{
  "highlights": [
    "Key finding 1 in a complete sentence",
    "Key finding 2 in a complete sentence",
    "Key finding 3 in a complete sentence"
  ],
  "summary": "2-3 sentence executive summary of what was found in the corpus"
}}

Return ONLY the JSON object. No markdown."""

_DEFAULT_REC = {"Low": "Approve", "Medium": "Renegotiate", "High": "Reject"}


def run(state: dict) -> dict:
    mode: str = state.get("mode", "risk_assessment")

    if mode == "clause_drafting":
        # drafting_agent already set summary and draft_clause — pass through
        logger.info("Summary agent: pass-through for clause_drafting mode")
        return {}

    if mode == "corpus_search":
        query: str = state.get("query", "")
        comparison: dict = state.get("comparison_result", {})
        logger.info("Summary agent (corpus_search) for query='%.60s'", query)

        key_findings_str = "\n".join(
            f"- {f}" for f in comparison.get("key_findings", [])
        )
        prompt = _CORPUS_SEARCH_PROMPT.format(
            query=query,
            answer=comparison.get("answer", ""),
            key_findings=key_findings_str,
            typical_range=comparison.get("typical_range", "N/A"),
        )
        response = call_llm(prompt, max_tokens=800)

        try:
            result = json.loads(extract_json_str(response))
            highlights: list[str] = result.get("highlights", [])
            summary_text: str = result.get("summary", comparison.get("answer", ""))
        except (json.JSONDecodeError, KeyError, AttributeError) as exc:
            logger.error("Summary (corpus_search) JSON parse error: %s", exc)
            highlights = comparison.get("key_findings", [])
            summary_text = comparison.get("answer", "")

        summary = "\n".join(f"• {h}" for h in highlights)
        logger.info("Summary complete (corpus_search)")
        return {"summary": summary_text, "highlights": highlights, "recommendation": ""}

    # Mode 1: risk_assessment
    contract_name: str = state["contract_name"]
    supplier_name: str = state.get("supplier_name", "Unknown")
    risk_score: int = state["risk_score"]
    risk_level: str = state["risk_level"]
    flagged_clauses: list[dict] = state["flagged_clauses"]
    logger.info("Summary agent (risk_assessment) for '%s'", contract_name)

    prompt = _RISK_PROMPT.format(
        contract_name=contract_name,
        supplier_name=supplier_name,
        risk_score=risk_score,
        risk_level=risk_level,
        clauses_json=json.dumps(flagged_clauses, indent=2),
    )
    response = call_llm(prompt, max_tokens=1000)

    try:
        result = json.loads(extract_json_str(response))
        highlights = result.get("highlights", [])
        recommendation: str = result.get("recommendation", "Renegotiate")
    except (json.JSONDecodeError, KeyError, AttributeError) as exc:
        logger.error("Summary JSON parse error: %s", exc)
        highlights = [f"Overall risk score: {risk_score}/100 ({risk_level} risk level)."]
        recommendation = _DEFAULT_REC.get(risk_level, "Renegotiate")

    if recommendation not in ("Approve", "Renegotiate", "Reject"):
        recommendation = _DEFAULT_REC.get(risk_level, "Renegotiate")

    summary = "\n".join(f"• {h}" for h in highlights)
    logger.info("Summary complete for '%s': recommendation=%s", contract_name, recommendation)
    return {"summary": summary, "highlights": highlights, "recommendation": recommendation}
