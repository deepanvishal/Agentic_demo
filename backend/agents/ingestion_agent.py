import logging
from pathlib import Path

import fitz

from backend.config import NEW_CONTRACTS_COLLECTION
from backend.rag.indexer import index_document

logger = logging.getLogger(__name__)

MIN_TEXT_CHARS = 500


async def run(state: dict, progress_callback) -> dict:
    pdf_path: str = state["pdf_path"]
    contract_name: str = state["contract_name"]
    logger.info("Ingestion agent starting for '%s'", contract_name)

    if not Path(pdf_path).exists():
        raise ValueError(f"PDF not found: {pdf_path}")

    try:
        doc = fitz.open(pdf_path)
    except Exception as exc:
        raise ValueError(f"Cannot open PDF '{pdf_path}': {exc}") from exc

    raw_text = "\n".join(page.get_text() for page in doc)

    if len(raw_text.strip()) < MIN_TEXT_CHARS:
        raise ValueError(
            f"PDF extracted only {len(raw_text.strip())} characters "
            f"(minimum {MIN_TEXT_CHARS}). Scanned/image PDFs are not supported."
        )

    chunk_count = await index_document(pdf_path, contract_name, progress_callback, collection_name=NEW_CONTRACTS_COLLECTION)

    logger.info("Ingestion complete: %d chunks indexed for '%s'", chunk_count, contract_name)
    return {"raw_text": raw_text, "chunk_count": chunk_count}
