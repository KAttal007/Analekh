"""Gzip results XBRL already in object storage (one-time, after storage.py began compressing).

Each file checked against SHA-256 in its key before rewrite and read back after; file whose bytes
don't match key left alone and listed. Safe to rerun: compressed files skipped.

    uv run python scripts/compress_raw_files.py [--limit N]
"""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from pathlib import PurePosixPath

from analekh.ingest.storage import GZIP_MAGIC, S3Store, sha256

PREFIX = "results_xbrl/"


def compress(store: S3Store, key: str) -> tuple[str, int, int]:
    raw: bytes = store.client.get_object(Bucket=store.bucket, Key=key)["Body"].read()
    if raw[:2] == GZIP_MAGIC:
        return "already", len(raw), len(raw)
    if sha256(raw) != PurePosixPath(key).stem:
        return "mismatch", len(raw), len(raw)
    store.write(key, raw, "application/xml")
    if sha256(store.get(key)) != PurePosixPath(key).stem:
        store.client.put_object(
            Bucket=store.bucket, Key=key, Body=raw, ContentType="application/xml"
        )
        return "restored", len(raw), len(raw)
    stored = store.client.head_object(Bucket=store.bucket, Key=key)["ContentLength"]
    return "compressed", len(raw), stored


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, help="stop after this many files (for a trial run)")
    args = ap.parse_args()

    store = S3Store()
    keys = []
    for page in store.client.get_paginator("list_objects_v2").paginate(
        Bucket=store.bucket, Prefix=PREFIX
    ):
        keys += [o["Key"] for o in page.get("Contents", [])]
    keys = keys[: args.limit]

    counts: dict[str, int] = {}
    before = after = 0
    problems = []
    with ThreadPoolExecutor(max_workers=8) as pool:
        for n, (key, (status, size, stored)) in enumerate(
            zip(keys, pool.map(lambda k: compress(store, k), keys), strict=True), 1
        ):
            counts[status] = counts.get(status, 0) + 1
            before, after = before + size, after + stored
            if status in ("mismatch", "restored"):
                problems.append((status, key))
            if n % 5000 == 0:
                print(f"{n:,} / {len(keys):,}", flush=True)

    print(f"{len(keys):,} files: {counts}")
    print(f"{before / 1e9:.2f} GB -> {after / 1e9:.2f} GB")
    for status, key in problems:
        print(status, key)


if __name__ == "__main__":
    main()
