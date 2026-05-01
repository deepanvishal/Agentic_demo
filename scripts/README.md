# Scripts

Run these from the project root (`contract-risk-agent/`).

## Setup (first time)

```bash
python scripts/setup_all.py
```

## Individual scripts

```bash
python scripts/download_contracts.py   # Download 5 CUAD contracts
python scripts/setup_db.py             # Initialize SQLite database
python scripts/reset_demo.py           # Reset all demo data
```

## Start the backend

```bash
python -m uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```
