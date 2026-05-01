"""
Reset all demo data — clears ChromaDB and SQLite for a clean demo run.
Run from the project root: python scripts/reset_demo.py
"""

import sys
from pathlib import Path

# Make backend importable when run from project root
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv

load_dotenv()

from backend.rag.reset import reset_chroma, reset_db


def main() -> None:
    print("Resetting demo state...")

    reset_chroma()
    print("ChromaDB cleared")

    reset_db()
    print("SQLite cleared")

    print("\nDemo reset complete.")


if __name__ == "__main__":
    main()
