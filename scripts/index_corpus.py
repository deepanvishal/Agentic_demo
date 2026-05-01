"""
Index all CUAD contracts in backend/contracts/preloaded/ into ChromaDB corpus collection.
Run from the project root: python scripts/index_corpus.py

This is a one-time setup step. Safe to re-run — already-indexed contracts are skipped.
Takes ~10-15 minutes on first run for 510 contracts.
"""

import asyncio
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv

load_dotenv()

import chromadb

from backend.config import CHROMA_PERSIST_PATH
from backend.rag.indexer import index_document

logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s — %(message)s")

PRELOADED_DIR = Path(__file__).parent.parent / "backend" / "contracts" / "preloaded"
CORPUS_COLLECTION = "corpus"


def _get_corpus_collection():
    client = chromadb.PersistentClient(path=CHROMA_PERSIST_PATH)
    return client.get_or_create_collection(CORPUS_COLLECTION)


def _get_indexed_names(collection) -> set[str]:
    """Return the set of contract names already indexed in the corpus collection."""
    results = collection.get(include=["metadatas"])
    names: set[str] = set()
    for meta in results.get("metadatas") or []:
        if meta and meta.get("contract_name"):
            names.add(meta["contract_name"])
    return names


async def _run_indexing() -> None:
    pdfs = sorted(PRELOADED_DIR.glob("*.pdf"))

    if not pdfs:
        print("No PDFs found in backend/contracts/preloaded/.")
        print("Run: python scripts/download_contracts.py first.")
        sys.exit(1)

    total = len(pdfs)
    print(f"Found {total} contracts in preloaded/.")

    collection = _get_corpus_collection()
    already_indexed = _get_indexed_names(collection)

    if already_indexed:
        print(f"{len(already_indexed)} contracts already indexed — those will be skipped.\n")

    indexed_count = 0
    skipped_count = 0
    total_chunks = 0
    failed: list[str] = []

    for i, pdf_path in enumerate(pdfs, start=1):
        contract_name = pdf_path.stem

        if contract_name in already_indexed:
            print(f"Indexing {i}/{total}: {contract_name} — skipped (already indexed)")
            skipped_count += 1
            indexed_count += 1
            continue

        print(f"Indexing {i}/{total}: {contract_name}")

        async def _noop_progress(step: str) -> None:
            pass

        try:
            chunk_count = await index_document(
                str(pdf_path),
                contract_name,
                _noop_progress,
                collection_name=CORPUS_COLLECTION,
            )
            total_chunks += chunk_count
            indexed_count += 1
            print(f"  Done ({chunk_count} chunks)")
        except Exception as exc:
            print(f"  ERROR: {exc}")
            failed.append(contract_name)

    # ── Summary ───────────────────────────────────────────────────────────────
    newly_indexed = indexed_count - skipped_count
    print(f"\nCorpus indexed: {indexed_count} contracts, {total_chunks} total chunks")
    if skipped_count:
        print(f"  {skipped_count} already indexed (skipped), {newly_indexed} newly indexed")
    if failed:
        print(f"\nFailed ({len(failed)} contracts):")
        for name in failed:
            print(f"  {name}")


def main() -> None:
    asyncio.run(_run_indexing())


if __name__ == "__main__":
    main()
