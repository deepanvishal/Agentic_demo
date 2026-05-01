import json
import logging
import re

from backend.config import call_llm, extract_json_str

logger = logging.getLogger(__name__)

_WEIGHTS = {
    "termination": 0.25,
    "liability_cap": 0.25,
    "penalty": 0.20,
    "indemnification": 0.20,
    "governing_law": 0.10,
}

_PROMPT_TEMPLATE = """You are a contract risk analyst. Score the following contract clauses for buyer-side risk.

CLAUSES:
{clauses_json}

Scoring guide (buyer perspective):
- 0-32  Low risk    — favorable or standard terms, minimal exposure
- 33-66 Medium risk — some unfavorable terms, negotiable, moderate exposure
- 67-100 High risk  — highly unfavorable, significant financial or legal exposure

Return ONLY a valid JSON object with this exact structure:
{{
  "clause_scores": [
    {{"type": "termination",     "score": <int 0-100>, "reason": "one-sentence risk explanation"}},
    {{"type": "liability_cap",   "score": <int 0-100>, "reason": "one-sentence risk explanation"}},
    {{"type": "penalty",         "score": <int 0-100>, "reason": "one-sentence risk explanation"}},
    {{"type": "indemnification", "score": <int 0-100>, "reason": "one-sentence risk explanation"}},
    {{"type": "governing_law",   "score": <int 0-100>, "reason": "one-sentence risk explanation"}}
  ]
}}

Return ONLY the JSON object. No explanation, no markdown."""

# Keywords to filter corpus chunks per clause type
_CORPUS_KEYWORDS: dict[str, list[str]] = {
    "termination": ["terminat", "notice", "cancel", "days"],
    "liability_cap": ["liability", "cap", "ceiling", "maximum", "limitation"],
    "penalty": ["penalty", "liquidated", "damages", "%", "percent"],
    "indemnification": ["indemnif", "hold harmless"],
    "governing_law": ["govern", "jurisdiction", "law of"],
}

# Regex patterns for extracting numeric values per clause type
_DAYS_RE = re.compile(r"\b(\d+)\s*(?:calendar\s+)?days?\b", re.IGNORECASE)
_PCT_RE = re.compile(r"(\d+(?:\.\d+)?)\s*%")
_DOLLAR_RE = re.compile(r"\$\s*(\d[\d,]*(?:\.\d+)?)")


def _first_float(pattern: re.Pattern, text: str) -> float | None:
    m = pattern.search(text)
    if m:
        try:
            return float(m.group(1).replace(",", ""))
        except (ValueError, IndexError):
            return None
    return None


def _corpus_percentile(
    clause_type: str,
    clause_text: str | None,
    corpus_chunks: list[str],
) -> int | None:
    """Return 0–100 percentile of how risky this clause is vs the corpus. None if not computable."""
    if not clause_text or not corpus_chunks:
        return None

    keywords = _CORPUS_KEYWORDS.get(clause_type, [])
    relevant = [c for c in corpus_chunks if any(kw in c.lower() for kw in keywords)]
    if not relevant:
        return None

    if clause_type == "penalty":
        new_val = _first_float(_PCT_RE, clause_text)
        if new_val is None:
            return None
        corpus_vals = [_first_float(_PCT_RE, c) for c in relevant]
        corpus_vals = [v for v in corpus_vals if v is not None]
        if not corpus_vals:
            return None
        # Higher penalty rate = riskier = higher percentile
        return int(100 * sum(1 for v in corpus_vals if v < new_val) / len(corpus_vals))

    if clause_type == "termination":
        new_val = _first_float(_DAYS_RE, clause_text)
        if new_val is None:
            return None
        corpus_vals = [_first_float(_DAYS_RE, c) for c in relevant]
        corpus_vals = [v for v in corpus_vals if v is not None]
        if not corpus_vals:
            return None
        # Shorter notice = riskier for buyer = higher percentile
        return int(100 * sum(1 for v in corpus_vals if v > new_val) / len(corpus_vals))

    if clause_type == "liability_cap":
        new_val = _first_float(_PCT_RE, clause_text) or _first_float(_DOLLAR_RE, clause_text)
        if new_val is None:
            return None
        corpus_vals = [
            _first_float(_PCT_RE, c) or _first_float(_DOLLAR_RE, c) for c in relevant
        ]
        corpus_vals = [v for v in corpus_vals if v is not None]
        if not corpus_vals:
            return None
        # Lower liability cap = riskier for buyer (can't recover damages) = higher percentile
        return int(100 * sum(1 for v in corpus_vals if v > new_val) / len(corpus_vals))

    return None


def run(state: dict) -> dict:
    clauses: list[dict] = state["clauses"]
    contract_name: str = state["contract_name"]
    corpus_chunks: list[str] = state.get("corpus_clauses", [])
    logger.info("Risk scoring agent starting for '%s'", contract_name)

    prompt = _PROMPT_TEMPLATE.format(clauses_json=json.dumps(clauses, indent=2))
    response = call_llm(prompt, max_tokens=1500)

    try:
        result = json.loads(extract_json_str(response))
        clause_scores: list[dict] = result.get("clause_scores", [])
    except (json.JSONDecodeError, KeyError, AttributeError) as exc:
        logger.error("Risk scoring JSON parse error: %s", exc)
        clause_scores = [{"type": t, "score": 50, "reason": "Scoring unavailable"} for t in _WEIGHTS]

    clause_text_map = {c["type"]: c.get("extracted_text") for c in clauses}

    flagged_clauses = []
    weighted_sum = 0.0
    weight_total = 0.0

    for cs in clause_scores:
        clause_type = cs.get("type", "")
        score = max(0, min(100, int(cs.get("score", 50))))
        weight = _WEIGHTS.get(clause_type, 0.0)
        weighted_sum += score * weight
        weight_total += weight

        extracted_text = clause_text_map.get(clause_type)
        percentile = _corpus_percentile(clause_type, extracted_text, corpus_chunks)

        flagged_clauses.append(
            {
                "type": clause_type,
                "score": score,
                "reason": cs.get("reason", ""),
                "extracted_text": extracted_text,
                "corpus_percentile": percentile,
            }
        )

    overall = int(round(weighted_sum / weight_total)) if weight_total > 0 else 50

    if overall > 66:
        risk_level = "High"
    elif overall >= 33:
        risk_level = "Medium"
    else:
        risk_level = "Low"

    logger.info("Risk score for '%s': %d (%s)", contract_name, overall, risk_level)
    return {
        "flagged_clauses": flagged_clauses,
        "risk_score": overall,
        "risk_level": risk_level,
    }
