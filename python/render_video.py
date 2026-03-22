"""
Stage 5: render_video.py — Science Narrator Pipeline

Composite narration audio, images, and word-level subtitles into two video
formats (16:9 horizontal and 9:16 vertical) using MoviePy 1.0.3.

Usage:
    python python/render_video.py \
        --script '<json>' \
        --audio '<json>' \
        --images '<json>' \
        --run-id '<uuid>' \
        [--background-video PATH]
"""

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_json_arg(name: str, value: str) -> dict:
    """Parse a JSON CLI argument; exit 1 on failure."""
    try:
        return json.loads(value)
    except json.JSONDecodeError as exc:
        print(f"ERROR: --{name} is not valid JSON: {exc}", file=sys.stderr)
        sys.exit(1)


def _check_ffmpeg() -> None:
    """Exit 1 if ffmpeg is not available."""
    try:
        subprocess.run(
            ["ffmpeg", "-version"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=True,
        )
    except (FileNotFoundError, subprocess.CalledProcessError):
        print("ERROR: ffmpeg is not available on PATH.", file=sys.stderr)
        sys.exit(1)


def _check_imagemagick() -> None:
    """Exit 1 if ImageMagick (required by MoviePy TextClip) is not available."""
    try:
        from moviepy.editor import TextClip  # noqa: F401 (side-effect import)
        TextClip.list("font")
    except OSError as exc:
        print(f"ERROR: ImageMagick is not available (required for TextClip): {exc}", file=sys.stderr)
        sys.exit(1)


def _assert_file_exists(path: str, label: str) -> None:
    if not os.path.isfile(path):
        print(f"ERROR: {label} file not found: {path}", file=sys.stderr)
        sys.exit(1)


def _utcnow() -> str:
    return datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------------------
# Subtitle helpers
# ---------------------------------------------------------------------------

def _chunk_text(text: str, chunk_size: int = 10) -> list[str]:
    """Split text into chunks of ~chunk_size words."""
    words = text.split()
    chunks = []
    for i in range(0, len(words), chunk_size):
        chunks.append(" ".join(words[i : i + chunk_size]))
    return chunks


def _build_caption_clips(narration_text: str, audio_duration: float, width: int, height: int, y_fraction: float):
    """
    Build a list of TextClip objects positioned as word-level subtitles.

    y_fraction: fraction of height for vertical positioning of the caption
                (e.g. 0.83 for 16:9, 0.75 for 9:16).
    """
    from moviepy.editor import TextClip

    chunks = _chunk_text(narration_text, chunk_size=10)
    n_chunks = len(chunks)
    if n_chunks == 0:
        return []

    segment_duration = audio_duration / n_chunks
    caption_y = int(y_fraction * height)

    clips = []
    for idx, chunk in enumerate(chunks):
        start_t = idx / n_chunks * audio_duration
        clip = (
            TextClip(
                chunk,
                fontsize=40,
                color="white",
                stroke_color="black",
                stroke_width=2,
                method="caption",
                size=(int(width * 0.9), None),
            )
            .set_start(start_t)
            .set_duration(segment_duration)
            .set_position(("center", caption_y))
        )
        clips.append(clip)

    return clips


def _build_watermark_clip(paper_id: str, duration: float, width: int, height: int, position):
    """Build a semi-transparent arXiv paper-ID watermark TextClip."""
    from moviepy.editor import TextClip

    clip = (
        TextClip(
            paper_id,
            fontsize=24,
            color="white",
            stroke_color="black",
            stroke_width=1,
        )
        .set_opacity(0.6)
        .set_duration(duration)
        .set_position(position)
    )
    return clip


# ---------------------------------------------------------------------------
# Composite builder
# ---------------------------------------------------------------------------

def _build_composite(
    *,
    audio_clip,
    image_paths: list[str],
    narration_text: str,
    paper_id: str,
    width: int,
    height: int,
    caption_y_fraction: float,
    watermark_position,
    background_video_path: str | None,
):
    """Build and return a CompositeVideoClip ready for export."""
    from moviepy.editor import (
        AudioFileClip,  # noqa: F401
        ColorClip,
        CompositeVideoClip,
        ImageClip,
        VideoFileClip,
    )

    audio_duration = audio_clip.duration

    # --- Base layer ---
    if background_video_path:
        base = (
            VideoFileClip(background_video_path)
            .loop(duration=audio_duration)
            .resize((width, height))
        )
    else:
        base = ColorClip(size=(width, height), color=(0, 0, 0), duration=audio_duration)

    # --- Image clips distributed evenly ---
    n_images = len(image_paths)
    image_duration = audio_duration / max(n_images, 1)
    image_clips = []
    for idx, img_path in enumerate(image_paths):
        start_t = idx * image_duration
        # Scale image to fit frame while preserving aspect ratio
        img_clip = (
            ImageClip(img_path)
            .resize(height=height)
            .set_start(start_t)
            .set_duration(image_duration)
            .set_position("center")
        )
        # If image is wider than frame, resize to width instead
        if img_clip.size[0] > width:
            img_clip = (
                ImageClip(img_path)
                .resize(width=width)
                .set_start(start_t)
                .set_duration(image_duration)
                .set_position("center")
            )
        image_clips.append(img_clip)

    # --- Captions ---
    caption_clips = _build_caption_clips(
        narration_text=narration_text,
        audio_duration=audio_duration,
        width=width,
        height=height,
        y_fraction=caption_y_fraction,
    )

    # --- Watermark ---
    watermark = _build_watermark_clip(
        paper_id=paper_id,
        duration=audio_duration,
        width=width,
        height=height,
        position=watermark_position,
    )

    # --- Composite ---
    composite = CompositeVideoClip(
        [base, *image_clips, *caption_clips, watermark],
        size=(width, height),
    ).set_audio(audio_clip)

    return composite


# ---------------------------------------------------------------------------
# Vertical format (9:16) derived from horizontal composite
# ---------------------------------------------------------------------------

def _build_vertical_composite(
    *,
    audio_clip,
    image_paths: list[str],
    narration_text: str,
    paper_id: str,
    background_video_path: str | None,
):
    """
    Build the 9:16 (1080×1920) vertical composite.

    Strategy: rebuild from scratch at vertical dimensions so that captions
    and watermark are correctly positioned for the taller frame.
    Images are center-cropped to 1080 wide then padded/stretched to 1920.
    """
    from moviepy.editor import (
        ColorClip,
        CompositeVideoClip,
        ImageClip,
        VideoFileClip,
    )

    V_WIDTH = 1080
    V_HEIGHT = 1920
    audio_duration = audio_clip.duration

    # --- Base layer ---
    if background_video_path:
        base_raw = VideoFileClip(background_video_path).loop(duration=audio_duration)
        # Crop centre to 9:16 aspect from original 16:9
        bw, bh = base_raw.size
        target_w = int(bh * 9 / 16)
        x1 = max((bw - target_w) // 2, 0)
        x2 = x1 + target_w
        base = base_raw.crop(x1=x1, x2=x2, y1=0, y2=bh).resize((V_WIDTH, V_HEIGHT))
    else:
        base = ColorClip(size=(V_WIDTH, V_HEIGHT), color=(0, 0, 0), duration=audio_duration)

    # --- Image clips ---
    n_images = len(image_paths)
    image_duration = audio_duration / max(n_images, 1)
    image_clips = []
    for idx, img_path in enumerate(image_paths):
        start_t = idx * image_duration
        img_clip = (
            ImageClip(img_path)
            .resize(width=V_WIDTH)
            .set_start(start_t)
            .set_duration(image_duration)
            .set_position("center")
        )
        image_clips.append(img_clip)

    # --- Captions: positioned at top 80% (y <= 0.8 * V_HEIGHT = 1536) ---
    caption_clips = _build_caption_clips(
        narration_text=narration_text,
        audio_duration=audio_duration,
        width=V_WIDTH,
        height=V_HEIGHT,
        y_fraction=0.75,  # well within top 80%
    )

    # --- Watermark: bottom-center for vertical ---
    watermark = _build_watermark_clip(
        paper_id=paper_id,
        duration=audio_duration,
        width=V_WIDTH,
        height=V_HEIGHT,
        position=("center", V_HEIGHT - 60),
    )

    composite = CompositeVideoClip(
        [base, *image_clips, *caption_clips, watermark],
        size=(V_WIDTH, V_HEIGHT),
    ).set_audio(audio_clip)

    return composite


# ---------------------------------------------------------------------------
# Duration validation
# ---------------------------------------------------------------------------

def _validate_duration(video_path: str, expected_duration: float) -> None:
    from moviepy.editor import VideoFileClip

    try:
        vc = VideoFileClip(video_path)
        actual = vc.duration
        vc.close()
    except Exception as exc:
        print(f"ERROR: Could not read exported video {video_path}: {exc}", file=sys.stderr)
        sys.exit(1)

    if abs(actual - expected_duration) > 2.0:
        print(
            f"ERROR: Audio-video duration mismatch in {video_path}: "
            f"expected ~{expected_duration:.2f}s, got {actual:.2f}s "
            f"(diff={abs(actual - expected_duration):.2f}s > 2s).",
            file=sys.stderr,
        )
        sys.exit(1)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Stage 5: render video for Science Narrator pipeline")
    parser.add_argument("--script", required=True, help="JSON string from generate_script.py")
    parser.add_argument("--audio", required=True, help="JSON string from generate_voice.py")
    parser.add_argument("--images", required=True, help="JSON string from generate_images.py")
    parser.add_argument("--run-id", required=True, help="Pipeline run UUID")
    parser.add_argument("--background-video", default=None, help="Optional path to background video file")
    args = parser.parse_args()

    # --- Parse JSON inputs ---
    script_data = _parse_json_arg("script", args.script)
    audio_data = _parse_json_arg("audio", args.audio)
    images_data = _parse_json_arg("images", args.images)

    run_id: str = args.run_id

    # --- Extract fields ---
    try:
        script_info = script_data["script"]
        paper_id: str = script_info["paper_id"]
        narration_text: str = script_info["narration_text"]
    except KeyError as exc:
        print(f"ERROR: Missing expected key in --script JSON: {exc}", file=sys.stderr)
        sys.exit(1)

    try:
        audio_info = audio_data["audio"]
        audio_path: str = audio_info["file_path"]
        audio_duration_meta: float = float(audio_info["duration_sec"])
    except KeyError as exc:
        print(f"ERROR: Missing expected key in --audio JSON: {exc}", file=sys.stderr)
        sys.exit(1)

    try:
        image_list = images_data["images"]
        image_paths: list[str] = [img["file_path"] for img in image_list]
    except KeyError as exc:
        print(f"ERROR: Missing expected key in --images JSON: {exc}", file=sys.stderr)
        sys.exit(1)

    if not image_paths:
        print("ERROR: --images JSON contains no image entries.", file=sys.stderr)
        sys.exit(1)

    # --- Validate input files exist ---
    _assert_file_exists(audio_path, "audio")
    for ip in image_paths:
        _assert_file_exists(ip, f"image ({ip})")
    if args.background_video:
        _assert_file_exists(args.background_video, "background-video")

    # --- System checks ---
    _check_ffmpeg()
    _check_imagemagick()

    # --- Output directory ---
    out_dir = f"/tmp/science_narrator/{run_id}"
    os.makedirs(out_dir, exist_ok=True)

    horizontal_path = os.path.join(out_dir, "video_horizontal.mp4")
    vertical_path = os.path.join(out_dir, "video_vertical.mp4")

    # --- Load audio ---
    from moviepy.editor import AudioFileClip

    audio_clip = AudioFileClip(audio_path)
    audio_duration: float = audio_clip.duration

    # -----------------------------------------------------------------------
    # 16:9 Horizontal (1920×1080)
    # -----------------------------------------------------------------------
    H_WIDTH = 1920
    H_HEIGHT = 1080

    h_composite = _build_composite(
        audio_clip=audio_clip,
        image_paths=image_paths,
        narration_text=narration_text,
        paper_id=paper_id,
        width=H_WIDTH,
        height=H_HEIGHT,
        caption_y_fraction=0.83,
        watermark_position=(H_WIDTH - 300, H_HEIGHT - 40),
        background_video_path=args.background_video,
    )

    h_composite.write_videofile(
        horizontal_path,
        fps=24,
        codec="libx264",
        audio_codec="aac",
        logger=None,
    )
    h_composite.close()

    if not os.path.isfile(horizontal_path):
        print(f"ERROR: Horizontal video was not produced at {horizontal_path}", file=sys.stderr)
        sys.exit(1)

    _validate_duration(horizontal_path, audio_duration)
    exported_at_h = _utcnow()

    # -----------------------------------------------------------------------
    # 9:16 Vertical (1080×1920)
    # -----------------------------------------------------------------------

    # Re-open audio clip (previous one may be consumed)
    audio_clip_v = AudioFileClip(audio_path)

    v_composite = _build_vertical_composite(
        audio_clip=audio_clip_v,
        image_paths=image_paths,
        narration_text=narration_text,
        paper_id=paper_id,
        background_video_path=args.background_video,
    )

    v_composite.write_videofile(
        vertical_path,
        fps=24,
        codec="libx264",
        audio_codec="aac",
        logger=None,
    )
    v_composite.close()

    if not os.path.isfile(vertical_path):
        print(f"ERROR: Vertical video was not produced at {vertical_path}", file=sys.stderr)
        sys.exit(1)

    _validate_duration(vertical_path, audio_duration)
    exported_at_v = _utcnow()

    # -----------------------------------------------------------------------
    # stdout result
    # -----------------------------------------------------------------------
    result = {
        "videos": [
            {
                "run_id": run_id,
                "paper_id": paper_id,
                "format": "horizontal_16_9",
                "width_px": H_WIDTH,
                "height_px": H_HEIGHT,
                "duration_sec": audio_duration,
                "file_path": horizontal_path,
                "exported_at": exported_at_h,
            },
            {
                "run_id": run_id,
                "paper_id": paper_id,
                "format": "vertical_9_16",
                "width_px": 1080,
                "height_px": 1920,
                "duration_sec": audio_duration,
                "file_path": vertical_path,
                "exported_at": exported_at_v,
            },
        ],
        "run_id": run_id,
    }

    print(json.dumps(result))


if __name__ == "__main__":
    main()
