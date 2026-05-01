import json
import logging

from backend.config import call_llm, extract_json_str

logger = logging.getLogger(__name__)

_CLAUSE_TYPES = ["termination", "liability_cap", "penalty", "indemnification", "governing_law"]

_PROMPT_TEMPLATE = """You are a contract law expert. Analyze the contract excerpts below and extract specific clauses.

CONTRACT EXCERPTS:
{context}

Extract the following and return ONLY a valid JSON object with this exact structure:
{{
  "supplier_name": "name of the supplier or vendor party (not the buyer/purchaser), or 'Unknown' if unclear",
  "clauses": [
    {{"type": "termination",      "extracted_text": "exact or paraphrased termination clause text, or null if absent"}},
    {{"type": "liability_cap",    "extracted_text": "exact or paraphrased liability cap text, or null if absent"}},
    {{"type": "penalty",          "extracted_text": "exact or paraphrased penalty/liquidated damages text, or null if absent"}},
    {{"type": "indemnification",  "extracted_text": "exact or paraphrased indemnification clause text, or null if absent"}},
    {{"type": "governing_law",    "extracted_text": "exact or paraphrased governing law/jurisdiction text, or null if absent"}}
  ]
}}

Return ONLY the JSON object. No explanation, no markdown."""


def run(state: dict) -> dict:
    chunks: list[str] = state["chunks"]
    contract_name: str = state["contract_name"]
    logger.info("Clause extraction agent starting for '%s'", contract_name)

    context = "\n\n---\n\n".join(chunks[:20])
    prompt = _PROMPT_TEMPLATE.format(context=context)

    response = call_llm(prompt, max_tokens=2000)

    try:
        result = json.loads(extract_json_str(response))
        clauses: list[dict] = result.get("clauses", [])
        supplier_name: str = result.get("supplier_name", "Unknown") or "Unknown"
    except (json.JSONDecodeError, KeyError, AttributeError) as exc:
        logger.error("Clause extraction JSON parse error: %s", exc)
        clauses = [{"type": t, "extracted_text": None} for t in _CLAUSE_TYPES]
        supplier_name = "Unknown"

    logger.info("Extracted %d clauses, supplier='%s' for '%s'", len(clauses), supplier_name, contract_name)
    return {"clauses": clauses, "supplier_name": supplier_name}
