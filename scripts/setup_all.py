"""
Master setup script — runs all first-time setup steps in order.
Run from the project root: python scripts/setup_all.py
"""

import sys
from pathlib import Path

# Ensure project root is on sys.path for backend imports
sys.path.insert(0, str(Path(__file__).parent.parent))
# Ensure scripts/ is on sys.path so sibling scripts can be imported directly
scripts_dir = str(Path(__file__).parent)
if scripts_dir not in sys.path:
    sys.path.insert(0, scripts_dir)

import setup_db
import download_contracts
import index_corpus


def main() -> None:
    print("=" * 50)
    print("  Contract Risk Agent — First-Time Setup")
    print("=" * 50)

    print("\n=== Step 1: Initializing Database ===")
    setup_db.main()

    print("\n=== Step 2: Downloading Contracts ===")
    download_contracts.main()

    print("\n=== Step 3: Index Corpus into ChromaDB ===")
    print("This may take 10-15 minutes on first run...")
    index_corpus.main()

    print("\n" + "=" * 50)
    print("Setup complete.")
    print("Run: python -m uvicorn backend.main:app --reload")
    print("=" * 50)


if __name__ == "__main__":
    main()
