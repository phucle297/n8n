"""
python/lib/nasa_rss_client.py — NASA RSS / APOD feed parser.

Usage:
    from lib.nasa_rss_client import search
    papers = search("black holes")
"""

import sys
from datetime import datetime, timezone

try:
    import feedparser  # type: ignore
except ImportError:
    feedparser = None  # type: ignore

_NASA_FEED_URL = "https://www.nasa.gov/rss/dyn/breaking_news.rss"
_APOD_FEED_URL = "https://apod.nasa.gov/apod.rss"


def _utcnow() -> str:
    return datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_feed(url: str, topic: str) -> list[dict]:
    """Parse a single RSS feed and return matching Paper dicts."""
    if feedparser is None:
        print("WARNING: feedparser not installed; NASA RSS unavailable.", file=sys.stderr)
        return []

    try:
        feed = feedparser.parse(url)
    except Exception as exc:
        print(f"WARNING: NASA RSS parse failure ({url}): {exc}", file=sys.stderr)
        return []

    if feed.bozo and feed.bozo_exception:
        print(
            f"WARNING: NASA RSS bozo exception ({url}): {feed.bozo_exception}",
            file=sys.stderr,
        )

    results = []
    topic_lower = topic.lower()
    retrieved_at = _utcnow()

    for entry in feed.entries:
        title = getattr(entry, "title", "") or ""
        summary = getattr(entry, "summary", "") or ""
        combined = f"{title} {summary}".lower()

        if topic_lower not in combined:
            continue

        link = getattr(entry, "link", "") or ""
        published = ""
        if hasattr(entry, "published_parsed") and entry.published_parsed:
            try:
                from time import strftime, mktime
                published = strftime("%Y-%m-%d", entry.published_parsed)
            except Exception:
                pass

        # Build a stable NASA ID from the link or title
        raw_id = link.split("/")[-1].strip("#").strip() or title[:40].replace(" ", "-")
        canonical_id = f"nasa:{raw_id}"

        authors = []
        if hasattr(entry, "author"):
            authors = [entry.author]

        results.append(
            {
                "id": canonical_id,
                "title": title,
                "authors": authors,
                "published_date": published,
                "abstract": summary,
                "source": "nasa_rss",
                "source_url": link,
                "licence": "arxiv-non-exclusive",  # NASA content — public domain
                "full_text_available": bool(summary),
                "retrieved_at": retrieved_at,
            }
        )

    return results


def search(topic: str) -> list[dict]:
    """
    Search NASA RSS feeds for articles matching topic.

    Tries the NASA Breaking News feed then the APOD feed.
    Returns [] on parse failure.
    """
    results = _parse_feed(_NASA_FEED_URL, topic)
    if not results:
        results = _parse_feed(_APOD_FEED_URL, topic)
    return results
