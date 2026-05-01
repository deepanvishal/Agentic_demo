"""
Download all 510 CUAD contract PDFs into backend/contracts/preloaded/ from Zenodo.
Run from the project root: python scripts/download_contracts.py
"""

import os
import sys
import zipfile
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

PROJECT_ROOT = Path(__file__).parent.parent
DEST_DIR = PROJECT_ROOT / "backend" / "contracts" / "preloaded"
ZIP_URL = "https://zenodo.org/records/4595826/files/CUAD_v1.zip"
ZIP_PATH = PROJECT_ROOT / "CUAD_v1.zip"

FULL_CORPUS_SIZE = 510


def _progress_hook(block_num: int, block_size: int, total_size: int) -> None:
    if total_size > 0:
        downloaded = min(block_num * block_size, total_size)
        pct = downloaded * 100 // total_size
        mb_done = downloaded // (1024 * 1024)
        mb_total = total_size // (1024 * 1024)
        print(f"\r  {pct:3d}%  {mb_done} / {mb_total} MB", end="", flush=True)


def main() -> int:
    DEST_DIR.mkdir(parents=True, exist_ok=True)

    # If the full corpus is already present, skip the entire download.
    existing = [p for p in DEST_DIR.iterdir() if p.suffix.lower() == ".pdf"]
    if len(existing) >= FULL_CORPUS_SIZE:
        print(f"Skipping — {len(existing)} contracts already exist in"
              f" {DEST_DIR.relative_to(PROJECT_ROOT)}/")
        return len(existing)

    if existing:
        print(f"Found {len(existing)} existing PDFs — will skip those during extraction.")

    # ── Step 1: Download zip ──────────────────────────────────────────────────
    print("Downloading CUAD_v1.zip from Zenodo (~300 MB) ...")
    try:
        urllib.request.urlretrieve(ZIP_URL, ZIP_PATH, reporthook=_progress_hook)
        print()  # end the progress line
        size_mb = ZIP_PATH.stat().st_size // (1024 * 1024)
        print(f"  Saved CUAD_v1.zip ({size_mb} MB)")
    except Exception as exc:
        print(f"\n  Download failed: {exc}")
        if ZIP_PATH.exists():
            ZIP_PATH.unlink()
        sys.exit(1)

    # ── Step 2: Extract all PDFs from zip ────────────────────────────────────
    success = 0
    skipped = 0

    try:
        with zipfile.ZipFile(ZIP_PATH, "r") as zf:
            all_entries = [
                (entry, os.path.basename(entry))
                for entry in zf.namelist()
                if entry.lower().endswith(".pdf") and os.path.basename(entry)
            ]
            total = len(all_entries)
            print(f"\nFound {total} PDF files in archive.")
            print(f"Extracting into {DEST_DIR.relative_to(PROJECT_ROOT)}/\n")

            for i, (zip_entry, basename) in enumerate(all_entries, start=1):
                dest = DEST_DIR / basename
                print(f"Downloading {i}/{total}: {basename}")

                if dest.exists():
                    print(f"  Skipped (already exists)")
                    skipped += 1
                    success += 1
                    continue

                try:
                    dest.write_bytes(zf.read(zip_entry))
                    size_kb = dest.stat().st_size // 1024
                    print(f"  Done ({size_kb} KB)")
                    success += 1
                except Exception as exc:
                    print(f"  Failed: {exc}")

    except zipfile.BadZipFile as exc:
        print(f"Invalid zip file: {exc}")
    except Exception as exc:
        print(f"Extraction error: {exc}")
    finally:
        # ── Step 3: Delete zip ────────────────────────────────────────────────
        if ZIP_PATH.exists():
            ZIP_PATH.unlink()
            print("\nDeleted CUAD_v1.zip")

    if skipped:
        print(f"\n{success}/{total} contracts extracted ({skipped} already existed, skipped).")
    else:
        print(f"\n{success}/{total} contracts extracted.")
    return success


if __name__ == "__main__":
    result = main()
    sys.exit(0 if result >= FULL_CORPUS_SIZE else 1)
