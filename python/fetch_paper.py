"""
Stage 1: fetch_paper.py — Source Data

Finds a non-duplicate science paper via ArXiv or NASA RSS.

Usage:
    python python/fetch_paper.py --topic "black holes" [--source arxiv|nasa|auto]

stdout on success: JSON per cli-interface.md Stage 1 contract
stderr on failure: human-readable message
exit 0 = success, 1 = recoverable error
"""

import argparse
import json
import sys
import uuid
from datetime import datetime, timezone

# Ensure lib/ is importable when invoked from repo root
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from python.lib import arxiv_client, dedup_store, nasa_rss_client, voice_profile
from python.lib.ai_config import load as load_ai_config
from python.lib.voice_profile import ConfigError


def _utcnow() -> str:
    return datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ArXiv category codes focused on physics and quantum physics.
# See: https://arxiv.org/category_taxonomy
_DEFAULT_CATEGORIES = [
    "quant-ph",   # Quantum Physics (primary)
    "hep-th",     # High Energy Physics - Theory (QFT, string theory)
    "hep-ph",     # High Energy Physics - Phenomenology
    "gr-qc",      # General Relativity & Quantum Cosmology
    "cond-mat",   # Condensed Matter (includes quantum materials)
    "physics",    # Physics (general)
]


def main() -> None:
    parser = argparse.ArgumentParser(description="Stage 1: fetch science paper")
    parser.add_argument("--topic", required=True, help="Topic keyword to search")
    parser.add_argument(
        "--source",
        choices=["arxiv", "nasa", "auto"],
        default="auto",
        help="Paper source (default: auto — arxiv first, nasa fallback)",
    )
    parser.add_argument(
        "--categories",
        nargs="*",
        default=_DEFAULT_CATEGORIES,
        help="ArXiv category codes to restrict results to (default: physics categories)",
    )
    args = parser.parse_args()

    # --- Fail-fast: validate voice profile + AI provider before any API spend ---
    try:
        voice_profile.load()
    except ConfigError as exc:
        print(f"ERROR: Voice profile misconfigured: {exc}", file=sys.stderr)
        sys.exit(1)

    try:
        load_ai_config()
    except ConfigError as exc:
        print(f"ERROR: AI provider misconfigured: {exc}", file=sys.stderr)
        sys.exit(1)

    run_id = str(uuid.uuid4())
    topic = args.topic.strip()

    # --- Fetch papers ---
    papers: list[dict] = []

    if args.source in ("arxiv", "auto"):
        papers = arxiv_client.search(topic, max_results=10, categories=args.categories)

    if not papers and args.source in ("nasa", "auto"):
        papers = nasa_rss_client.search(topic)

    if not papers:
        print(
            f"ERROR: No papers found for topic '{topic}' from source '{args.source}'.",
            file=sys.stderr,
        )
        sys.exit(1)

    # --- Deduplication: find first non-duplicate with a non-empty abstract ---
    chosen: dict | None = None
    for paper in papers:
        paper_id = paper.get("id", "")
        abstract = (paper.get("abstract") or "").strip()
        if not abstract:
            continue
        if dedup_store.is_duplicate(paper_id):
            print(
                f"INFO: Skipping duplicate paper '{paper_id}'.",
                file=sys.stderr,
            )
            continue
        chosen = paper
        break

    if chosen is None:
        print(
            f"ERROR: All papers for topic '{topic}' are either duplicates or have empty abstracts.",
            file=sys.stderr,
        )
        sys.exit(1)

    # --- Ensure retrieved_at is present ---
    if not chosen.get("retrieved_at"):
        chosen["retrieved_at"] = _utcnow()

    result = {
        "paper": chosen,
        "run_id": run_id,
    }
    print(json.dumps(result))


if __name__ == "__main__":
    main()
