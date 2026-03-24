"""
Stage 2: generate_script.py — Script Generation

Generates a structured narration script from a Paper using the configured AI provider.

Usage:
    python python/generate_script.py --paper '<json string from stage 1>'

Environment:
    AI_PROVIDER     openai | gemini  (default: openai)
    OPENAI_API_KEY  required when AI_PROVIDER=openai
    GEMINI_API_KEY  required when AI_PROVIDER=gemini

stdout on success: JSON per cli-interface.md Stage 2 contract
stderr on failure: human-readable message
exit 0 = success, 1 = recoverable error
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from python.lib.ai_config import load as load_ai_config
from python.lib.ai_provider import get_provider
from python.lib.voice_profile import ConfigError


def _utcnow() -> str:
    return datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


_SYSTEM_PROMPT = """You are a science educator producing narration scripts for short educational videos.
Your scripts are accurate, jargon-free for a general audience, and cite their sources.
Respond ONLY with a valid JSON object. Do not include markdown code fences."""

_USER_PROMPT_TEMPLATE = """Create an educational video narration script from the following research paper.

Paper ID: {paper_id}
Title: {title}
Authors: {authors}
Abstract:
{abstract}

Requirements:
- learning_objective: one clear sentence stating what the viewer will understand by the end
- outline.intro: engaging opening paragraph (~100 words); state the learning_objective within the first 30 seconds of narration
- outline.key_concepts: array of 4–6 objects, each with:
    - term: the scientific term
    - definition: plain-language definition (1–2 sentences)
    - narration_segment: 2–4 sentences explaining this concept; define the term on first use; cite "{paper_id}" when making factual claims
    - visual_description: 1–2 sentence cinematic scene description for image generation. Describe exactly what to show: subject, action, mood, lighting, style. No text or labels in the image. Example: "A glowing double helix rotating slowly in a dark void, base pairs highlighted in blue and orange, photorealistic."
- outline.conclusion: closing paragraph (~80 words) summarising key takeaways
- narration_text: the complete narration formed by joining intro + all narration_segments + conclusion; target 750–900 words; define each technical term on first use; include arXiv citation "{paper_id}" at least once per factual claim
- word_count: integer count of words in narration_text
- estimated_duration_sec: integer = word_count / 150 * 60
- citations: array of objects {{ "paper_id": "{paper_id}", "claim_excerpt": "..." }} — one entry per factual claim

Return this exact JSON structure:
{{
  "learning_objective": "...",
  "outline": {{
    "intro": "...",
    "key_concepts": [{{ "term": "...", "definition": "...", "narration_segment": "...", "visual_description": "..." }}],
    "conclusion": "..."
  }},
  "narration_text": "...",
  "word_count": 0,
  "estimated_duration_sec": 0,
  "citations": [{{ "paper_id": "...", "claim_excerpt": "..." }}]
}}"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Stage 2: generate narration script")
    parser.add_argument("--paper", required=True, help="JSON string from fetch_paper.py")
    args = parser.parse_args()

    # --- Parse input ---
    try:
        stage1 = json.loads(args.paper)
        paper = stage1["paper"]
        run_id: str = stage1["run_id"]
    except (json.JSONDecodeError, KeyError) as exc:
        print(f"ERROR: --paper JSON invalid or missing keys: {exc}", file=sys.stderr)
        sys.exit(1)

    paper_id: str = paper.get("id", "")
    abstract: str = (paper.get("abstract") or "").strip()
    if not abstract:
        print("ERROR: Paper has empty abstract; cannot generate script.", file=sys.stderr)
        sys.exit(1)

    # --- AI provider config ---
    try:
        ai_cfg = load_ai_config()
    except ConfigError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)

    user_prompt = _USER_PROMPT_TEMPLATE.format(
        paper_id=paper_id,
        title=paper.get("title", ""),
        authors=", ".join(paper.get("authors", [])),
        abstract=abstract,
    )

    ai = get_provider(ai_cfg["provider"], ai_cfg["api_key"])

    try:
        raw_json, model_used = ai.generate_text(_SYSTEM_PROMPT, user_prompt)
    except Exception as exc:
        print(f"ERROR: AI API error ({ai_cfg['provider']}): {exc}", file=sys.stderr)
        sys.exit(1)

    # --- Parse AI response ---
    try:
        gpt_data = json.loads(raw_json)
    except json.JSONDecodeError as exc:
        print(f"ERROR: AI response is not valid JSON: {exc}\nRaw: {raw_json[:200]}", file=sys.stderr)
        sys.exit(1)

    # Warn if any concept is missing visual_description (Stage 4 will fall back to template)
    for concept in (gpt_data.get("outline") or {}).get("key_concepts") or []:
        if not (concept.get("visual_description") or "").strip():
            term = concept.get("term", "<unknown>")
            print(
                f"WARNING: concept '{term}' missing visual_description "
                "— image will use fallback prompt.",
                file=sys.stderr,
            )

    # --- Build script object ---
    narration_text: str = gpt_data.get("narration_text", "")
    word_count: int = len(narration_text.split())
    learning_objective: str = (gpt_data.get("learning_objective") or "").strip()
    citations: list = gpt_data.get("citations") or []

    # Recompute word_count authoritatively
    gpt_data["word_count"] = word_count
    gpt_data["estimated_duration_sec"] = int(word_count / 150 * 60)

    # --- Validations ---
    if not (650 <= word_count <= 950):
        print(
            f"ERROR: word_count={word_count} is outside allowed range [650, 950]. "
            "Re-run to get a different GPT response.",
            file=sys.stderr,
        )
        sys.exit(1)

    if not learning_objective:
        print("ERROR: GPT response missing learning_objective.", file=sys.stderr)
        sys.exit(1)

    citation_paper_ids = [c.get("paper_id", "") for c in citations]
    if paper_id not in citation_paper_ids:
        print(
            f"ERROR: citations do not include source paper '{paper_id}'.",
            file=sys.stderr,
        )
        sys.exit(1)

    script = {
        "paper_id": paper_id,
        "learning_objective": learning_objective,
        "outline": gpt_data.get("outline", {}),
        "narration_text": narration_text,
        "word_count": word_count,
        "estimated_duration_sec": gpt_data["estimated_duration_sec"],
        "citations": citations,
        "generated_at": _utcnow(),
        "model": model_used,
    }

    result = {"script": script, "run_id": run_id}
    print(json.dumps(result))


if __name__ == "__main__":
    main()
