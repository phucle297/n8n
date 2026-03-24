"""
python/lib/dedup_store.py — Processed-paper ID deduplication store.

Backed by data/processed_papers.json (a JSON array of paper ID strings).
The file is append-only; entries are never deleted.

Note: register() should only be called after successful export (from
validate_manifest.py), so that failed runs do not consume a paper ID.
"""

import json
import os

_DEFAULT_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "data", "processed_papers.json"
)


def _resolve(store_path: str | None) -> str:
    return store_path if store_path else os.path.abspath(_DEFAULT_PATH)


def load(store_path: str | None = None) -> list[str]:
    """Return the current list of processed paper IDs."""
    path = _resolve(store_path)
    if not os.path.isfile(path):
        return []
    with open(path, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    if not isinstance(data, list):
        return []
    return [str(x) for x in data]


def is_duplicate(paper_id: str, store_path: str | None = None) -> bool:
    """Return True if paper_id has already been processed."""
    return paper_id in load(store_path)


def register(paper_id: str, store_path: str | None = None) -> None:
    """
    Append paper_id to the store.

    IMPORTANT: call this only after successful export; failed runs must
    not consume a paper ID.
    """
    path = _resolve(store_path)
    ids = load(store_path)
    if paper_id not in ids:
        ids.append(paper_id)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(ids, fh, indent=2)
