"""Скачивает русскую модель Vosk в папку models/.

Usage:
    python scripts/fetch_model.py [--model small|full]

По умолчанию — small (~45 MB). Полная модель — ~1.8 GB.
"""
from __future__ import annotations

import argparse
import io
import shutil
import sys
import urllib.request
import zipfile
from pathlib import Path

# Windows console (cp1252) — принуждаем UTF-8, иначе print с кириллицей падает.
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", line_buffering=True)
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", line_buffering=True)
    except Exception:
        pass

MODELS = {
    "small": (
        "vosk-model-small-ru-0.22",
        "https://alphacephei.com/vosk/models/vosk-model-small-ru-0.22.zip",
    ),
    "full": (
        "vosk-model-ru-0.42",
        "https://alphacephei.com/vosk/models/vosk-model-ru-0.42.zip",
    ),
}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", choices=list(MODELS), default="small")
    parser.add_argument("--dest", default="models")
    args = parser.parse_args()

    name, url = MODELS[args.model]
    dest_root = Path(args.dest)
    dest_root.mkdir(parents=True, exist_ok=True)
    final_dir = dest_root / name

    if final_dir.exists() and any(final_dir.iterdir()):
        print(f"[fetch_model] model already present: {final_dir}")
        return 0

    zip_path = dest_root / f"{name}.zip"
    print(f"[fetch_model] downloading: {url}")

    def _report(block_num: int, block_size: int, total_size: int) -> None:
        if total_size <= 0:
            return
        done = block_num * block_size
        pct = min(100, int(done * 100 / total_size))
        sys.stdout.write(f"\r[fetch_model] {pct:>3}%")
        sys.stdout.flush()

    urllib.request.urlretrieve(url, zip_path, reporthook=_report)
    sys.stdout.write("\n")

    print(f"[fetch_model] extracting into {dest_root}")
    with zipfile.ZipFile(zip_path) as zf:
        zf.extractall(dest_root)

    if not final_dir.exists():
        # Иногда внутренняя папка имеет другое имя — попробуем найти её.
        candidates = [p for p in dest_root.iterdir() if p.is_dir() and p.name.startswith("vosk-model")]
        if candidates:
            candidates[0].rename(final_dir)

    zip_path.unlink(missing_ok=True)

    if not final_dir.exists():
        print("[fetch_model] could not find extracted model directory.", file=sys.stderr)
        return 1

    print(f"[fetch_model] done: {final_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


_ = shutil  # placeholder for future use
