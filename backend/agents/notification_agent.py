import logging

from backend.email.sender import send_risk_email
from backend.db.writer import insert_contract

logger = logging.getLogger(__name__)


def run(state: dict) -> dict:
    contract_name: str = state["contract_name"]
    logger.info("Notification agent starting for '%s'", contract_name)

    email_sent = send_risk_email(
        contract_name=contract_name,
        supplier_name=state.get("supplier_name", "Unknown"),
        risk_score=state["risk_score"],
        risk_level=state["risk_level"],
        recommendation=state["recommendation"],
        summary=state.get("highlights") or state.get("summary", ""),
        flagged_clauses=state.get("flagged_clauses", []),
    )

    db_id = insert_contract(
        {
            "contract_name": contract_name,
            "supplier_name": state.get("supplier_name"),
            "risk_score": state["risk_score"],
            "risk_level": state["risk_level"],
            "recommendation": state["recommendation"],
            "flagged_clauses": state.get("flagged_clauses", []),
            "summary": state.get("summary"),
            "email_sent": email_sent,
            "email_recipient": "deepanvishal@gmail.com",
            "contract_text": state.get("raw_text"),
            "chunk_count": state.get("chunk_count"),
        }
    )

    logger.info("Notification complete for '%s': email_sent=%s, db_id=%d", contract_name, email_sent, db_id)
    return {"email_sent": email_sent, "db_id": db_id}
