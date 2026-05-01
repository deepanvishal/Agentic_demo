import json
import logging

from backend.config import call_llm, extract_json_str

logger = logging.getLogger(__name__)

_PROMPT_TEMPLATE = """You are a contract analyst with access to a corpus of 510 real commercial contracts (CUAD dataset).

USER QUERY: {query}

RELEVANT CORPUS CLAUSES (from multiple contracts):
{corpus_text}

Based on these corpus examples, answer the user's query about typical contract terms, industry benchmarks, and common patterns.

Return ONLY a valid JSON object with this exact structure:
{{
  "answer": "Direct, specific answer to the query in 2-3 sentences",
  "key_findings": [
    "Specific finding from the corpus examples",
    "Specific finding from the corpus examples",
    "Specific finding from the corpus examples"
  ],
  "typical_range": "e.g., 30-90 days notice period, liability cap at 1x annual fees"
}}

Rules:
- answer: directly address the user's query using evidence from the corpus
- key_findings: exactly 3 specific observations drawn from the provided corpus clauses
- typical_range: a concise benchmark string; use "N/A" if not applicable

Return ONLY the JSON object. No markdown, no explanation."""


def run(state: dict) -> dict:
    query: str = state.get("query", "")
    corpus_clauses: list[str] = state.get("corpus_clauses", [])
    logger.info("Comparison agent starting for query='%.60s'", query)

    if not corpus_clauses:
        logger.warning("No corpus clauses available for comparison")
        return {
            "comparison_result": {
                "answer": "No corpus data available for this query.",
                "key_findings": [],
                "typical_range": "N/A",
            }
        }

    corpus_text = "\n\n---\n\n".join(corpus_clauses[:12])

    prompt = _PROMPT_TEMPLATE.format(query=query, corpus_text=corpus_text)
    response = call_llm(prompt, max_tokens=1500)

    try:
        result = json.loads(extract_json_str(response))
        comparison_result = {
            "answer": result.get("answer", ""),
            "key_findings": result.get("key_findings", []),
            "typical_range": result.get("typical_range", "N/A"),
        }
    except (json.JSONDecodeError, KeyError, AttributeError) as exc:
        logger.error("Comparison agent JSON parse error: %s", exc)
        comparison_result = {
            "answer": response.strip()[:500],
            "key_findings": [],
            "typical_range": "N/A",
        }

    logger.info("Comparison complete for query='%.60s'", query)
    return {"comparison_result": comparison_result}
