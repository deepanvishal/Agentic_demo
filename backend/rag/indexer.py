import asyncio
import logging
from pathlib import Path

import fitz
import chromadb
from sentence_transformers import SentenceTransformer
from llama_index.core.node_parser import SentenceSplitter
from llama_index.core.schema import Document

from backend.config import CHROMA_PERSIST_PATH

logger = logging.getLogger(__name__)

COLLECTION_NAME = "contracts"
CHUNK_SIZE = 512
CHUNK_OVERLAP = 64

_embed_model: SentenceTransformer | None = None


def _get_embed_model() -> SentenceTransformer:
    global _embed_model
    if _embed_model is None:
        _embed_model = SentenceTransformer("all-MiniLM-L6-v2")
    return _embed_model


def _get_collection(collection_name: str = COLLECTION_NAME):
    client = chromadb.PersistentClient(path=CHROMA_PERSIST_PATH)
    return client.get_or_create_collection(collection_name)


async def index_document(pdf_path: str, contract_name: str, progress_callback, collection_name: str = COLLECTION_NAME) -> int:
    await progress_callback("Extracting text")

    def _extract() -> str:
        doc = fitz.open(pdf_path)
        return "\n".join(page.get_text() for page in doc)

    raw_text = await asyncio.to_thread(_extract)

    await progress_callback("Chunking document")

    def _chunk() -> list[str]:
        parser = SentenceSplitter(chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP)
        nodes = parser.get_nodes_from_documents([Document(text=raw_text)])
        return [node.get_content() for node in nodes]

    chunks = await asyncio.to_thread(_chunk)
    logger.info("Chunked '%s' into %d pieces", contract_name, len(chunks))

    await progress_callback("Generating embeddings")

    def _embed() -> list[list[float]]:
        return _get_embed_model().encode(chunks, show_progress_bar=False).tolist()

    embeddings = await asyncio.to_thread(_embed)

    await progress_callback("Storing in ChromaDB")

    def _store() -> int:
        collection = _get_collection(collection_name)
        ids = [f"{contract_name}__chunk_{i}" for i in range(len(chunks))]
        metadatas = [{"contract_name": contract_name, "chunk_index": i} for i in range(len(chunks))]
        collection.upsert(
            ids=ids,
            documents=chunks,
            embeddings=embeddings,
            metadatas=metadatas,
        )
        return len(chunks)

    chunk_count = await asyncio.to_thread(_store)

    await progress_callback("Index complete")
    logger.info("Indexed %d chunks for '%s'", chunk_count, contract_name)
    return chunk_count
