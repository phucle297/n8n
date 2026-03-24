"""
python/lib/arxiv_client.py — ArXiv Atom API wrapper.

Usage:
    from lib.arxiv_client import search
    papers = search("black holes", max_results=5)
"""

import sys
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

_API_URL = "https://export.arxiv.org/api/query"
_NS = {"atom": "http://www.w3.org/2005/Atom"}


def _text(el: ET.Element | None) -> str:
    if el is None:
        return ""
    return (el.text or "").strip()


def search(
    topic: str,
    max_results: int = 5,
    categories: list[str] | None = None,
) -> list[dict]:
    """
    Query the ArXiv API for papers matching topic.

    categories: optional list of ArXiv category codes (e.g. ["quant-ph", "hep-th"])
                to restrict results. When provided, only papers in those categories
                are returned.

    Returns a list of Paper dicts. Returns [] on HTTP error or no results.
    """
    query = f"all:{topic}"
    if categories:
        cat_filter = " OR ".join(f"cat:{c}" for c in categories)
        query = f"({query}) AND ({cat_filter})"

    params = urllib.parse.urlencode(
        {
            "search_query": query,
            "start": 0,
            "max_results": max_results,
            "sortBy": "submittedDate",
            "sortOrder": "descending",
        }
    )
    url = f"{_API_URL}?{params}"

    try:
        with urllib.request.urlopen(url, timeout=15) as resp:
            xml_bytes = resp.read()
    except Exception as exc:
        print(f"WARNING: ArXiv HTTP error: {exc}", file=sys.stderr)
        return []

    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError as exc:
        print(f"WARNING: ArXiv XML parse error: {exc}", file=sys.stderr)
        return []

    entries = root.findall("atom:entry", _NS)
    if not entries:
        return []

    papers = []
    retrieved_at = datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    for entry in entries:
        raw_id = _text(entry.find("atom:id", _NS))
        # e.g. http://arxiv.org/abs/2401.00001v1 → arxiv:2401.00001
        arxiv_id = raw_id.split("/abs/")[-1].split("v")[0] if "/abs/" in raw_id else raw_id
        canonical_id = f"arxiv:{arxiv_id}"

        title = _text(entry.find("atom:title", _NS)).replace("\n", " ")
        abstract = _text(entry.find("atom:summary", _NS)).replace("\n", " ")
        published = _text(entry.find("atom:published", _NS))[:10]  # YYYY-MM-DD

        authors = [
            _text(a.find("atom:name", _NS))
            for a in entry.findall("atom:author", _NS)
        ]

        # Determine licence from <link> rel="license" if present
        licence = "arxiv-non-exclusive"
        for link in entry.findall("atom:link", _NS):
            if link.get("rel") == "license":
                href = link.get("href", "")
                if "creativecommons.org/licenses/by/4.0" in href:
                    licence = "cc-by-4.0"
                elif "creativecommons.org/licenses/by-nc" in href:
                    licence = "cc-by-nc"
                elif "creativecommons.org/publicdomain/zero" in href:
                    licence = "cc0"
                break

        source_url = f"https://arxiv.org/abs/{arxiv_id}"

        papers.append(
            {
                "id": canonical_id,
                "title": title,
                "authors": authors,
                "published_date": published,
                "abstract": abstract,
                "source": "arxiv",
                "source_url": source_url,
                "licence": licence,
                "full_text_available": True,
                "retrieved_at": retrieved_at,
            }
        )

    return papers
