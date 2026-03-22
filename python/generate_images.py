"""
Stage 4: generate_images.py — Image Generation

Generates one image per key concept in the script using the configured AI provider.
- OpenAI: DALL-E 3 (1792x1024)
- Gemini: Imagen 3 (16:9)

Usage:
    python python/generate_images.py --script '<json>' --run-id '<uuid>'

Environment:
    AI_PROVIDER     openai | gemini  (default: openai)
    OPENAI_API_KEY  required when AI_PROVIDER=openai
    GEMINI_API_KEY  required when AI_PROVIDER=gemini

stdout on success: JSON per cli-interface.md Stage 4 contract
stderr on failure: human-readable message
exit 0 = success, 1 = recoverable error
"""

import argparse
import json
import os
import sys
import uuid
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from python.lib.ai_config import load as load_ai_config
from python.lib.ai_provider import get_provider
from python.lib.voice_profile import ConfigError


def _utcnow() -> str:
    return datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


_PROMPT_TEMPLATE = (
    "Educational diagram or vivid scientific illustration for a science video about: {concept}. "
    "Definition: {definition}. "
    "Style: clean, vibrant, photorealistic or detailed illustration, no text, no labels, "
    "suitable for a general science audience. 16:9 aspect ratio."
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Stage 4: generate concept images")
    parser.add_argument("--script", required=True, help="JSON string from generate_script.py")
    parser.add_argument("--run-id", required=True, help="Pipeline run UUID")
    args = parser.parse_args()

    # --- Parse input ---
    try:
        stage2 = json.loads(args.script)
        script = stage2["script"]
        run_id: str = args.run_id
    except (json.JSONDecodeError, KeyError) as exc:
        print(f"ERROR: --script JSON invalid or missing keys: {exc}", file=sys.stderr)
        sys.exit(1)

    key_concepts: list[dict] = (script.get("outline") or {}).get("key_concepts") or []
    if not key_concepts:
        print("ERROR: Script has no key_concepts in outline.", file=sys.stderr)
        sys.exit(1)

    # --- AI provider config ---
    try:
        ai_cfg = load_ai_config()
    except ConfigError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)

    provider = ai_cfg["provider"]
    ai = get_provider(provider, ai_cfg["api_key"])

    # Map provider to asset metadata
    _SOURCE_MAP = {"openai": "dalle3", "gemini": "imagen3"}
    _LICENCE_MAP = {"openai": "openai-tos-commercial", "gemini": "openai-tos-commercial"}
    source = _SOURCE_MAP.get(provider, provider)
    licence = _LICENCE_MAP.get(provider, "openai-tos-commercial")

    out_dir = f"/tmp/science_narrator/{run_id}"
    os.makedirs(out_dir, exist_ok=True)

    images: list[dict] = []

    for idx, concept in enumerate(key_concepts):
        term = concept.get("term", f"concept_{idx + 1}")
        definition = concept.get("definition", "")
        prompt = _PROMPT_TEMPLATE.format(concept=term, definition=definition)

        img_filename = f"image_{idx + 1:02d}.png"
        img_path = os.path.join(out_dir, img_filename)

        try:
            ai.generate_image(prompt, img_path)
        except Exception as exc:
            print(f"ERROR: Image generation failed for concept '{term}': {exc}", file=sys.stderr)
            sys.exit(1)

        if not os.path.isfile(img_path) or os.path.getsize(img_path) == 0:
            print(f"ERROR: Image file for '{term}' not written to disk.", file=sys.stderr)
            sys.exit(1)

        images.append(
            {
                "asset_id": str(uuid.uuid4()),
                "type": "image",
                "source": source,
                "generation_prompt": prompt,
                "licence": licence,
                "verified": True,
                "created_at": _utcnow(),
                "file_path": img_path,
            }
        )

    result = {"images": images, "run_id": run_id}
    print(json.dumps(result))


if __name__ == "__main__":
    main()
