"""
Stage 4: generate_images.py — Image Generation

Generates one image per key concept in the script using DALL-E 3.

Usage:
    python python/generate_images.py --script '<json>' --run-id '<uuid>'

Environment:
    OPENAI_API_KEY  (required)

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

    # --- API key ---
    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not api_key:
        print("ERROR: OPENAI_API_KEY environment variable is not set.", file=sys.stderr)
        sys.exit(1)

    try:
        from openai import OpenAI  # type: ignore
    except ImportError:
        print("ERROR: openai not installed. Run: pip install openai", file=sys.stderr)
        sys.exit(1)

    client = OpenAI(api_key=api_key)

    out_dir = f"/tmp/science_narrator/{run_id}"
    os.makedirs(out_dir, exist_ok=True)

    images: list[dict] = []

    for idx, concept in enumerate(key_concepts):
        term = concept.get("term", f"concept_{idx + 1}")
        definition = concept.get("definition", "")
        prompt = _PROMPT_TEMPLATE.format(concept=term, definition=definition)

        try:
            response = client.images.generate(
                model="dall-e-3",
                prompt=prompt,
                size="1792x1024",
                quality="standard",
                n=1,
            )
            image_url: str = response.data[0].url or ""
        except Exception as exc:
            print(f"ERROR: DALL-E 3 API error for concept '{term}': {exc}", file=sys.stderr)
            sys.exit(1)

        # Download image
        img_filename = f"image_{idx + 1:02d}.png"
        img_path = os.path.join(out_dir, img_filename)

        try:
            import urllib.request
            urllib.request.urlretrieve(image_url, img_path)
        except Exception as exc:
            print(f"ERROR: Failed to download image for '{term}': {exc}", file=sys.stderr)
            sys.exit(1)

        if not os.path.isfile(img_path) or os.path.getsize(img_path) == 0:
            print(f"ERROR: Image file for '{term}' not written to disk.", file=sys.stderr)
            sys.exit(1)

        images.append(
            {
                "asset_id": str(uuid.uuid4()),
                "type": "image",
                "source": "dalle3",
                "generation_prompt": prompt,
                "licence": "openai-tos-commercial",
                "verified": True,
                "created_at": _utcnow(),
                "file_path": img_path,
            }
        )

    result = {"images": images, "run_id": run_id}
    print(json.dumps(result))


if __name__ == "__main__":
    main()
