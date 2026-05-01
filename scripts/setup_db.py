"""
Initialize the SQLite database for the Contract Risk Agent.
Run from the project root: python scripts/setup_db.py
"""

import sys
from pathlib import Path

# Make backend importable when run from project root
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv

load_dotenv()

from backend.config import SQLITE_PATH
from backend.db.schema import init_db


def main() -> None:
    db_path = Path(SQLITE_PATH)
    already_existed = db_path.exists()

    init_db()

    if already_existed:
        print(f"Database already exists at {SQLITE_PATH} — skipping")
    else:
        print(f"Database initialized at {SQLITE_PATH}")


if __name__ == "__main__":
    main()
