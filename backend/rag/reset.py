import sqlite3
import logging

import chromadb

from backend.config import CHROMA_PERSIST_PATH, SQLITE_PATH
from backend.db.schema import init_db

logger = logging.getLogger(__name__)

COLLECTION_NAME = "contracts"


def reset_chroma() -> None:
    client = chromadb.PersistentClient(path=CHROMA_PERSIST_PATH)
    try:
        client.delete_collection(COLLECTION_NAME)
        logger.info("Deleted ChromaDB collection '%s'", COLLECTION_NAME)
    except Exception:
        logger.info("ChromaDB collection '%s' did not exist", COLLECTION_NAME)
    client.create_collection(COLLECTION_NAME)
    logger.info("Recreated ChromaDB collection '%s'", COLLECTION_NAME)


def reset_db() -> None:
    init_db()
    conn = sqlite3.connect(SQLITE_PATH)
    try:
        conn.execute("DELETE FROM contracts")
        conn.commit()
        logger.info("Cleared all rows from contracts table")
    finally:
        conn.close()
