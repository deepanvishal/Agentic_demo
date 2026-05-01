import json
import logging

from backend.config import call_llm, extract_json_str

logger = logging.getLogger(__name__)

_PROMPT_TEMPLATE = """You are a commercial contracts attorney. Draft a contract clause based on real corpus examples.

DRAFTING REQUEST: {query}

CORPUS EXAMPLES (from real commercial contracts):
{corpus_text}

Draft a balanced clause that:
- Protects the buyer while being commercially reasonable
- Uses clear, professional legal language
- Follows patterns observed in the provided corpus examples
- Is complete and ready to insert into a contract

Return ONLY a valid JSON object with this exact structure:
{{
  "draft_clause": "The complete drafted clause text, ready to use",
  "summary": "2-3 sentence explanation of what this clause does and why it is structured this way",
  "clause_type": "e.g., termination, liability_cap, penalty, indemnification, governing_law"
}}

Return ONLY the JSON object. No markdown, no explanation."""


def run(state: dict) -> dict:
    query: str = state.get("query", "")
    corpus_clauses: list[str] = state.get("corpus_clauses", [])
    logger.info("Drafting agent starting for query='%.60s'", query)

    if not corpus_clauses:
        logger.warning("No corpus clauses available for drafting")
        return {
            "draft_clause": "",
            "summary": "No corpus examples were available to inform the draft.",
            "comparison_result": {"clause_type": "unknown"},
        }

    corpus_text = "\n\n---\n\n".join(corpus_clauses[:8])

    prompt = _PROMPT_TEMPLATE.format(query=query, corpus_text=corpus_text)
    response = call_llm(prompt, max_tokens=2000)

    try:
        result = json.loads(extract_json_str(response))
        draft_clause = result.get("draft_clause", "")
        summary = result.get("summary", "")
        clause_type = result.get("clause_type", "unknown")
    except (json.JSONDecodeError, KeyError, AttributeError) as exc:
        logger.error("Drafting agent JSON parse error: %s", exc)
        draft_clause = response.strip()
        summary = "Draft generated from corpus examples."
        clause_type = "unknown"

    logger.info("Drafting complete for query='%.60s' (type=%s)", query, clause_type)
    return {
        "draft_clause": draft_clause,
        "summary": summary,
        # store clause_type in comparison_result so orchestrator/frontend can access it
        "comparison_result": {"clause_type": clause_type},
    }
