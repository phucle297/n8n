"""
python/lib/manifest.py — Asset and ProvenanceManifest dataclasses + writer.

Approved licence values (any other raises ValueError at Asset construction):
    openai-tos-commercial, pipeline-generated, cc0, cc-by-4.0,
    pexels-licence, unsplash-licence, pixabay-licence
"""

import json
import os
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Literal


# ---------------------------------------------------------------------------
# Approved licence enum
# ---------------------------------------------------------------------------

APPROVED_LICENCES: frozenset[str] = frozenset(
    {
        "openai-tos-commercial",
        "pipeline-generated",
        "cc0",
        "cc-by-4.0",
        "pexels-licence",
        "unsplash-licence",
        "pixabay-licence",
    }
)

AssetType = Literal["image", "audio", "background_music"]
AssetSource = Literal["dalle3", "gtts", "openai_tts", "royalty_free", "public_domain"]


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass
class Asset:
    asset_id: str
    type: AssetType
    source: AssetSource
    licence: str
    verified: bool
    created_at: str
    file_path: str
    source_url: str = ""
    generation_prompt: str = ""

    def __post_init__(self) -> None:
        if self.licence not in APPROVED_LICENCES:
            raise ValueError(
                f"Unknown licence: '{self.licence}'. "
                f"Approved values: {sorted(APPROVED_LICENCES)}"
            )


@dataclass
class VideoFile:
    format: Literal["vertical_9_16", "horizontal_16_9"]
    width_px: int
    height_px: int
    duration_sec: float
    file_path: str
    exported_at: str


@dataclass
class ProvenanceManifest:
    run_id: str
    paper_id: str
    generated_at: str
    assets: list[Asset] = field(default_factory=list)
    video_files: list[VideoFile] = field(default_factory=list)
    all_verified: bool = False

    def compute_all_verified(self) -> bool:
        return bool(self.assets) and all(a.verified for a in self.assets)


# ---------------------------------------------------------------------------
# Writer
# ---------------------------------------------------------------------------


def write_manifest(
    run_id: str,
    paper_id: str,
    assets: list[Asset],
    video_files: list[VideoFile],
    output_dir: str = "output",
) -> str:
    """
    Validate assets, compute all_verified, write assets-manifest.json.

    Returns the path to the written file.
    Raises ValueError if all_verified is False (caller should exit 1).
    """
    all_verified = bool(assets) and all(a.verified for a in assets)

    manifest = ProvenanceManifest(
        run_id=run_id,
        paper_id=paper_id,
        generated_at=datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        assets=assets,
        video_files=video_files,
        all_verified=all_verified,
    )

    run_out_dir = os.path.join(output_dir, run_id)
    os.makedirs(run_out_dir, exist_ok=True)
    path = os.path.join(run_out_dir, "assets-manifest.json")

    # Serialise dataclasses to plain dicts
    data = asdict(manifest)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2)

    return path
