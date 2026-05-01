import logging
import re
from contextlib import asynccontextmanager
from pathlib import Path

import aiofiles
import fitz
from fastapi import FastAPI, File, HTTPException, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from backend.agents.orchestrator import run_pipeline
from backend.db.reader import get_all_contracts, get_contract_by_id, get_dashboard_stats
from backend.db.schema import init_db
from backend.rag.reset import reset_chroma, reset_db

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s — %(message)s")
logger = logging.getLogger(__name__)

_BASE = Path(__file__).parent
PRELOADED_DIR = _BASE / "contracts" / "preloaded"
UPLOADS_DIR = _BASE / "contracts" / "uploads"

MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10 MB
MIN_TEXT_CHARS = 500


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    PRELOADED_DIR.mkdir(parents=True, exist_ok=True)
    logger.info("Contract Risk Agent API started")
    yield


app = FastAPI(title="Contract Risk Agent API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── WebSocket: Mode 1 — Risk Assessment ──────────────────────────────────────

@app.websocket("/ws/analyze")
async def analyze_websocket(websocket: WebSocket) -> None:
    """Mode 1: Upload a contract PDF and run full risk assessment."""
    await websocket.accept()
    try:
        data = await websocket.receive_json()
        contract_name: str = data.get("contract_name", "").strip()
        pdf_path: str = data.get("pdf_path", "").strip()

        if not contract_name or not pdf_path:
            await websocket.send_json({"error": "contract_name and pdf_path are required"})
            return

        async def ws_callback(message: dict) -> None:
            try:
                await websocket.send_json(message)
            except Exception:
                pass

        result = await run_pipeline(
            query=contract_name,
            pdf_path=pdf_path,
            contract_name=contract_name,
            websocket_callback=ws_callback,
            mode_hint="risk_assessment",
        )

        summary_result = {
            k: v for k, v in result.items() if k not in ("raw_text", "chunks", "corpus_clauses")
        }
        await websocket.send_json({"agent": "complete", "status": "done", "data": summary_result})

    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected during analysis")
    except Exception as exc:
        logger.error("Pipeline error: %s", exc, exc_info=True)
        try:
            await websocket.send_json({"agent": "error", "status": "error", "data": {"message": str(exc)}})
        except Exception:
            pass
    finally:
        try:
            await websocket.close()
        except Exception:
            pass


# ── WebSocket: Mode 2 & 3 — Corpus Search / Clause Drafting ─────────────────

@app.websocket("/ws/query")
async def query_websocket(websocket: WebSocket) -> None:
    """Mode 2 (corpus_search) and Mode 3 (clause_drafting) entry point."""
    await websocket.accept()
    try:
        data = await websocket.receive_json()
        query: str = data.get("query", "").strip()
        mode_hint: str | None = data.get("mode_hint") or None

        if not query:
            await websocket.send_json({"error": "query is required"})
            return

        async def ws_callback(message: dict) -> None:
            try:
                await websocket.send_json(message)
            except Exception:
                pass

        result = await run_pipeline(
            query=query,
            pdf_path=None,
            contract_name=None,
            websocket_callback=ws_callback,
            mode_hint=mode_hint,
        )

        summary_result = {
            k: v for k, v in result.items() if k not in ("raw_text", "chunks", "corpus_clauses")
        }
        await websocket.send_json({"agent": "complete", "status": "done", "data": summary_result})

    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected during query")
    except Exception as exc:
        logger.error("Query pipeline error: %s", exc, exc_info=True)
        try:
            await websocket.send_json({"agent": "error", "status": "error", "data": {"message": str(exc)}})
        except Exception:
            pass
    finally:
        try:
            await websocket.close()
        except Exception:
            pass


# ── REST endpoints ────────────────────────────────────────────────────────────

@app.get("/contracts")
async def list_contracts() -> list:
    return get_all_contracts()


@app.get("/contracts/{contract_id}")
async def get_contract(contract_id: int) -> dict:
    contract = get_contract_by_id(contract_id)
    if not contract:
        raise HTTPException(status_code=404, detail="Contract not found")
    return contract


@app.get("/dashboard/stats")
async def dashboard_stats() -> dict:
    return get_dashboard_stats()


@app.post("/upload")
async def upload_pdf(file: UploadFile = File(...)) -> dict:
    filename = file.filename or "upload.pdf"
    safe_name = re.sub(r"[^\w\-_.]", "_", filename)
    if not safe_name.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted.")

    content = await file.read()

    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=400, detail="File exceeds 10 MB limit.")

    try:
        doc = fitz.open(stream=content, filetype="pdf")
        extracted = "\n".join(page.get_text() for page in doc)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Invalid PDF: {exc}") from exc

    if len(extracted.strip()) < MIN_TEXT_CHARS:
        raise HTTPException(
            status_code=400,
            detail="PDF contains insufficient text (minimum 500 characters). "
            "Scanned/image-only PDFs are not supported.",
        )

    save_path = UPLOADS_DIR / safe_name
    async with aiofiles.open(save_path, "wb") as f:
        await f.write(content)

    logger.info("Uploaded PDF saved: %s (%d bytes)", safe_name, len(content))
    return {"file_path": str(save_path), "filename": safe_name}


@app.delete("/reset")
async def reset_all() -> dict:
    reset_chroma()
    reset_db()
    logger.info("Demo state reset: ChromaDB + SQLite cleared")
    return {"status": "ok", "message": "ChromaDB collection and SQLite contracts table cleared."}


@app.get("/preloaded")
async def list_preloaded() -> dict:
    if not PRELOADED_DIR.exists():
        return {"contracts": []}
    contracts = [
        {"name": p.stem, "file_path": str(p)}
        for p in sorted(PRELOADED_DIR.glob("*.pdf"))
    ]
    return {"contracts": contracts}
