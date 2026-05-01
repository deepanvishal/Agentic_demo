import logging

from backend.config import CORPUS_COLLECTION, NEW_CONTRACTS_COLLECTION
from backend.rag.retriever import retrieve_chunks

logger = logging.getLogger(__name__)

_CLAUSE_QUERIES = [
    "termination clause notice period cancellation early exit",
    "liability cap limitation of damages maximum liability ceiling",
    "penalty liquidated damages breach default fine",
    "indemnification indemnify hold harmless third party claims",
    "governing law jurisdiction venue dispute resolution arbitration",
]


def run(state: dict) -> dict:
    mode: str = state.get("mode", "risk_assessment")

    if mode == "risk_assessment":
        contract_name: str = state["contract_name"]
        logger.info("Retrieval agent (Mode 1) for '%s'", contract_name)

        # Retrieve clause chunks from the newly uploaded contract
        seen: set[str] = set()
        chunks: list[str] = []
        for query in _CLAUSE_QUERIES:
            for chunk in retrieve_chunks(
                query=query,
                collection_name=NEW_CONTRACTS_COLLECTION,
                contract_name=contract_name,
                top_k=10,
            ):
                if chunk not in seen:
                    seen.add(chunk)
                    chunks.append(chunk)

        # Also retrieve from corpus for corpus_percentile comparison in risk_agent
        seen_corpus: set[str] = set()
        corpus_clauses: list[str] = []
        for query in _CLAUSE_QUERIES:
            for chunk in retrieve_chunks(
                query=query,
                collection_name=CORPUS_COLLECTION,
                top_k=8,
            ):
                if chunk not in seen_corpus:
                    seen_corpus.add(chunk)
                    corpus_clauses.append(chunk)

        logger.info(
            "Retrieval complete: %d contract chunks, %d corpus chunks for '%s'",
            len(chunks),
            len(corpus_clauses),
            contract_name,
        )
        return {"chunks": chunks, "corpus_clauses": corpus_clauses}

    else:
        # Mode 2 (corpus_search) and Mode 3 (clause_drafting): query corpus
        query: str = state.get("query", "")
        top_k = 15 if mode == "corpus_search" else 10
        logger.info("Retrieval agent (Mode=%s) query='%.60s'", mode, query)

        corpus_clauses = retrieve_chunks(
            query=query,
            collection_name=CORPUS_COLLECTION,
            top_k=top_k,
        )
        logger.info("Retrieved %d corpus chunks for query", len(corpus_clauses))
        return {"corpus_clauses": corpus_clauses}
