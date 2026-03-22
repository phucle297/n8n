"""
Stage 6: validate_manifest.py — Asset Compliance Validation Gate

Validates all assets for licence compliance, verifies video files exist,
writes the provenance manifest, and registers the paper ID in the dedup store.

Usage:
    python python/validate_manifest.py \
        --audio '<json from stage 3>' \
        --images '<json from stage 4>' \
        --videos '<json from stage 5>' \
        --run-id '<uuid>'

stdout on success: JSON per cli-interface.md Stage 6 contract
stderr on failure: per-asset compliance detail
exit 0 = success, 1 = error
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from python.lib import dedup_store
from python.lib.manifest import (
    APPROVED_LICENCES,
    Asset,
    VideoFile,
    write_manifest,
)


def _utcnow() -> str:
    return datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse(name: str, value: str) -> dict | list:
    try:
        return json.loads(value)
    except json.JSONDecodeError as exc:
        print(f"ERROR: --{name} is not valid JSON: {exc}", file=sys.stderr)
        sys.exit(1)


def _build_asset(raw: dict) -> Asset:
    return Asset(
        asset_id=raw["asset_id"],
        type=raw["type"],
        source=raw["source"],
        licence=raw.get("licence", ""),
        verified=bool(raw.get("verified", False)),
        created_at=raw.get("created_at", _utcnow()),
        file_path=raw.get("file_path", ""),
        source_url=raw.get("source_url", ""),
        generation_prompt=raw.get("generation_prompt", ""),
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Stage 6: validate asset compliance")
    parser.add_argument("--audio", required=True, help="JSON from generate_voice.py")
    parser.add_argument("--images", required=True, help="JSON from generate_images.py")
    parser.add_argument("--videos", required=True, help="JSON from render_video.py")
    parser.add_argument("--run-id", required=True, help="Pipeline run UUID")
    args = parser.parse_args()

    run_id = args.run_id

    audio_data = _parse("audio", args.audio)
    images_data = _parse("images", args.images)
    videos_data = _parse("videos", args.videos)

    # --- Collect raw asset dicts ---
    raw_assets: list[dict] = []

    audio_raw = audio_data.get("audio", {})  # type: ignore[union-attr]
    if audio_raw:
        raw_assets.append(audio_raw)

    for img in images_data.get("images", []):  # type: ignore[union-attr]
        raw_assets.append(img)

    video_entries: list[dict] = videos_data.get("videos", [])  # type: ignore[union-attr]

    # --- US2: assert exactly two video entries ---
    formats_present = {v.get("format") for v in video_entries}
    required_formats = {"vertical_9_16", "horizontal_16_9"}
    if formats_present != required_formats:
        missing = required_formats - formats_present
        print(
            f"ERROR: Expected two video formats {required_formats}; "
            f"missing: {missing}",
            file=sys.stderr,
        )
        sys.exit(1)

    # --- Verify video files exist on disk ---
    for v in video_entries:
        vpath = v.get("file_path", "")
        if not os.path.isfile(vpath):
            print(
                f"ERROR: Video file not found on disk: {vpath}",
                file=sys.stderr,
            )
            sys.exit(1)

    # --- Validate assets ---
    compliance_failures: list[str] = []
    validated_assets: list[Asset] = []

    for raw in raw_assets:
        asset_id = raw.get("asset_id", "<unknown>")
        asset_type = raw.get("type", "")
        licence = raw.get("licence", "")
        verified = bool(raw.get("verified", False))

        # Licence check
        if licence not in APPROVED_LICENCES:
            msg = (
                f"COMPLIANCE FAIL: asset_id={asset_id} type={asset_type} "
                f"licence={licence!r} — not in approved list"
            )
            print(msg, file=sys.stderr)
            compliance_failures.append(msg)
            continue

        # Verified check
        if not verified:
            msg = (
                f"COMPLIANCE FAIL: asset_id={asset_id} type={asset_type} "
                f"licence={licence!r} — verified=false"
            )
            print(msg, file=sys.stderr)
            compliance_failures.append(msg)
            continue

        try:
            asset = _build_asset(raw)
        except ValueError as exc:
            msg = f"COMPLIANCE FAIL: asset_id={asset_id} — {exc}"
            print(msg, file=sys.stderr)
            compliance_failures.append(msg)
            continue

        validated_assets.append(asset)

    # --- Build VideoFile list ---
    video_files = [
        VideoFile(
            format=v["format"],
            width_px=v["width_px"],
            height_px=v["height_px"],
            duration_sec=v["duration_sec"],
            file_path=v["file_path"],
            exported_at=v.get("exported_at", _utcnow()),
        )
        for v in video_entries
    ]

    # Determine paper_id from audio or images
    paper_id: str = ""
    for v in video_entries:
        paper_id = v.get("paper_id", "")
        if paper_id:
            break

    # --- Write partial manifest on failure (for debugging) ---
    if compliance_failures:
        out_dir = os.path.join("output", run_id)
        os.makedirs(out_dir, exist_ok=True)
        partial = {
            "run_id": run_id,
            "paper_id": paper_id,
            "generated_at": _utcnow(),
            "all_verified": False,
            "compliance_failures": compliance_failures,
        }
        with open(os.path.join(out_dir, "assets-manifest.json"), "w") as fh:
            json.dump(partial, fh, indent=2)
        print(
            f"ERROR: {len(compliance_failures)} compliance failure(s). "
            "See stderr for details. Partial manifest written.",
            file=sys.stderr,
        )
        sys.exit(1)

    # --- Write full manifest ---
    try:
        manifest_path = write_manifest(
            run_id=run_id,
            paper_id=paper_id,
            assets=validated_assets,
            video_files=video_files,
        )
    except Exception as exc:
        print(f"ERROR: Failed to write manifest: {exc}", file=sys.stderr)
        sys.exit(1)

    # --- Register paper ID in dedup store (only on full success) ---
    if paper_id:
        dedup_store.register(paper_id)

    result = {
        "manifest": {
            "run_id": run_id,
            "paper_id": paper_id,
            "generated_at": _utcnow(),
            "all_verified": True,
            "assets": [
                {
                    "asset_id": a.asset_id,
                    "type": a.type,
                    "source": a.source,
                    "licence": a.licence,
                    "verified": a.verified,
                }
                for a in validated_assets
            ],
            "video_files": [
                {
                    "format": vf.format,
                    "width_px": vf.width_px,
                    "height_px": vf.height_px,
                    "duration_sec": vf.duration_sec,
                    "file_path": vf.file_path,
                }
                for vf in video_files
            ],
        },
        "manifest_path": manifest_path,
        "run_id": run_id,
    }
    print(json.dumps(result))


if __name__ == "__main__":
    main()
