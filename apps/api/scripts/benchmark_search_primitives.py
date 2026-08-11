"""Dependency-free Batch-19 micro-benchmark for local indexing primitives.

This does not claim end-to-end database throughput. It lets operators benchmark the CPU-only
chunk/fingerprint/vector operations on their own deployment hardware.
"""
from __future__ import annotations

import argparse
import time
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.services.search_index.engine import feature_vector, simhash64, chunk_text


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--documents", type=int, default=10_000)
    parser.add_argument("--chars", type=int, default=2200)
    args = parser.parse_args()
    base = ("Section 138 cheque notice payment evidence धारा 138 चेक नोटिस साक्ष्य. " * 80)[: args.chars]
    started = time.perf_counter()
    chunks = vectors = 0
    for i in range(args.documents):
        text = f"Document {i}. {base}"
        for chunk in chunk_text(text):
            simhash64(chunk)
            feature_vector(chunk, expand_legal=False)
            chunks += 1; vectors += 1
    elapsed = time.perf_counter() - started
    print({
        "documents": args.documents,
        "chunks": chunks,
        "elapsed_seconds": round(elapsed, 3),
        "chunks_per_second": round(chunks / elapsed, 1) if elapsed else None,
        "note": "CPU primitive benchmark only; database/IO throughput is deployment-specific",
    })


if __name__ == "__main__":
    main()
