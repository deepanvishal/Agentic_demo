import logging
from typing import List

import chromadb
from sentence_transformers import SentenceTransformer, CrossEncoder

from backend.config import CHROMA_PERSIST_PATH, CORPUS_COLLECTION

logger = logging.getLogger(__name__)

_embed_model: SentenceTransformer | None = None
_cross_encoder: CrossEncoder | None = None


def _get_embed_model() -> SentenceTransformer:
    global _embed_model
    if _embed_model is None:
        _embed_model = SentenceTransformer("all-MiniLM-L6-v2")
    return _embed_model


def _get_cross_encoder() -> CrossEncoder:
    global _cross_encoder
    if _cross_encoder is None:
        _cross_encoder = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")
    return _cross_encoder


def _get_collection(collection_name: str):
    client = chromadb.PersistentClient(path=CHROMA_PERSIST_PATH)
    return client.get_or_create_collection(collection_name)


def _reciprocal_rank_fusion(rankings: List[List[str]], k: int = 60) -> List[str]:
    scores: dict[str, float] = {}
    for ranking in rankings:
        for rank, doc_id in enumerate(ranking):
            scores[doc_id] = scores.get(doc_id, 0.0) + 1.0 / (k + rank + 1)
    return sorted(scores.keys(), key=lambda d: scores[d], reverse=True)


def retrieve_chunks(
    query: str,
    collection_name: str = CORPUS_COLLECTION,
    contract_name: str | None = None,
    top_k: int = 10,
) -> List[str]:
    """Retrieve and rerank chunks using hybrid BM25 + semantic search + CrossEncoder.

    When contract_name is provided, restricts search to that contract's chunks.
    When contract_name is None, searches corpus-wide (semantic candidates first, then BM25).
    """
    from rank_bm25 import BM25Okapi

    collection = _get_collection(collection_name)
    query_embedding = _get_embed_model().encode(query).tolist()

    if contract_name is not None:
        all_docs = collection.get(
            where={"contract_name": contract_name},
            include=["documents"],
        )
        doc_texts: list[str] = all_docs.get("documents") or []
        doc_ids: list[str] = all_docs.get("ids") or []

        if not doc_texts:
            logger.warning("No chunks for '%s' in collection '%s'", contract_name, collection_name)
            return []

        n_results = min(top_k * 2, len(doc_texts))
        semantic_results = collection.query(
            query_embeddings=[query_embedding],
            n_results=n_results,
            where={"contract_name": contract_name},
            include=["documents"],
        )
        semantic_ids: list[str] = semantic_results["ids"][0] if semantic_results.get("ids") else []

        tokenized_corpus = [t.lower().split() for t in doc_texts]
        bm25 = BM25Okapi(tokenized_corpus)
        bm25_scores = bm25.get_scores(query.lower().split())
        bm25_ranked = sorted(range(len(bm25_scores)), key=lambda i: bm25_scores[i], reverse=True)
        bm25_ids = [doc_ids[i] for i in bm25_ranked[: top_k * 2]]

        id_to_text = dict(zip(doc_ids, doc_texts))

    else:
        # Corpus-wide: semantic search first, BM25 only on those candidates
        total_docs = collection.count()
        if total_docs == 0:
            logger.warning("Collection '%s' is empty", collection_name)
            return []

        n_candidates = min(top_k * 4, total_docs)
        semantic_results = collection.query(
            query_embeddings=[query_embedding],
            n_results=n_candidates,
            include=["documents"],
        )
        candidate_ids: list[str] = semantic_results["ids"][0] if semantic_results.get("ids") else []
        candidate_texts: list[str] = (
            semantic_results["documents"][0] if semantic_results.get("documents") else []
        )

        if not candidate_texts:
            return []

        tokenized = [t.lower().split() for t in candidate_texts]
        bm25 = BM25Okapi(tokenized)
        bm25_scores = bm25.get_scores(query.lower().split())
        bm25_ranked = sorted(range(len(bm25_scores)), key=lambda i: bm25_scores[i], reverse=True)
        bm25_ids = [candidate_ids[i] for i in bm25_ranked[: top_k * 2]]
        semantic_ids = candidate_ids[: top_k * 2]
        id_to_text = dict(zip(candidate_ids, candidate_texts))

    fused_ids = _reciprocal_rank_fusion([semantic_ids, bm25_ids])
    candidates = [id_to_text[did] for did in fused_ids if did in id_to_text][: top_k * 2]

    if not candidates:
        return []

    scores_ce = _get_cross_encoder().predict([(query, t) for t in candidates])
    ranked = [text for _, text in sorted(zip(scores_ce, candidates), reverse=True)]

    result = ranked[:top_k]
    logger.info(
        "Retrieved %d chunks for query '%.50s' (collection=%s, contract=%s)",
        len(result),
        query,
        collection_name,
        contract_name,
    )
    return result
