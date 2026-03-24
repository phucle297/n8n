"""
Stage 3: generate_voice.py — Voice Generation

Synthesises narration audio from the script narration_text using
gTTS (default) or OpenAI TTS (when VOICE_PROVIDER=openai).

Usage:
    python python/generate_voice.py --script '<json>' --run-id '<uuid>'

Environment:
    VOICE_PROVIDER   gtts | openai | edge-tts  (default: edge-tts)
                     Note: VOICE_SPEED and VOICE_PITCH are ignored by edge-tts
    VOICE_LOCALE     BCP-47         (default: en-US)
    VOICE_SPEED      0.5–2.0        (default: 1.0; gTTS ignores this)
    VOICE_PITCH      default|low|high (default: default; ignored by OpenAI TTS)
    VOICE_ID         TTS voice ID   (default: ""; openai: voice name; edge-tts: BCP-47 neural voice e.g. en-US-GuyNeural)
    OPENAI_API_KEY   required when VOICE_PROVIDER=openai

stdout on success: JSON per cli-interface.md Stage 3 contract
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

from python.lib.voice_profile import ConfigError, load as load_voice_profile


def _utcnow() -> str:
    return datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _audio_duration(path: str) -> float:
    """Return duration in seconds using moviepy (already a dependency)."""
    try:
        from moviepy.editor import AudioFileClip  # type: ignore
        clip = AudioFileClip(path)
        dur = clip.duration
        clip.close()
        return float(dur)
    except Exception:
        return 0.0


def _synthesise_gtts(narration_text: str, locale: str, out_path: str) -> None:
    """Generate audio with gTTS and save to out_path."""
    try:
        from gtts import gTTS  # type: ignore
    except ImportError:
        print("ERROR: gTTS not installed. Run: pip install gTTS", file=sys.stderr)
        sys.exit(1)

    lang = locale.split("-")[0]  # gTTS uses 2-letter lang codes
    tts = gTTS(text=narration_text, lang=lang)
    tts.save(out_path)


async def _run_edge_tts(text: str, voice: str, path: str) -> None:
    try:
        import edge_tts  # type: ignore
    except ImportError:
        raise RuntimeError("edge-tts not installed. Run: pip install edge-tts>=6.1")
    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(path)


def _synthesise_edge_tts(narration_text: str, voice_id: str, out_path: str) -> None:
    """Generate audio with edge-tts (Microsoft Neural TTS) and save to out_path."""
    import asyncio
    effective_voice = voice_id if voice_id else "en-US-AriaNeural"
    # asyncio.run() is safe here: generate_voice.py is invoked as a CLI subprocess,
    # never from within an already-running event loop.
    asyncio.run(_run_edge_tts(narration_text, effective_voice, out_path))


def _synthesise_openai(
    narration_text: str,
    voice_id: str,
    speed: float,
    out_path: str,
    api_key: str,
) -> None:
    """Generate audio with OpenAI TTS and save to out_path."""
    try:
        from openai import OpenAI  # type: ignore
    except ImportError:
        print("ERROR: openai not installed. Run: pip install openai", file=sys.stderr)
        sys.exit(1)

    effective_voice = voice_id if voice_id else "alloy"
    # Speed clamping: OpenAI TTS accepts 0.25–4.0; pipeline allows 0.5–2.0
    effective_speed = max(0.5, min(2.0, speed))

    client = OpenAI(api_key=api_key)
    response = client.audio.speech.create(
        model="tts-1-hd",
        voice=effective_voice,  # type: ignore[arg-type]
        input=narration_text,
        speed=effective_speed,
    )
    response.stream_to_file(out_path)


def main() -> None:
    parser = argparse.ArgumentParser(description="Stage 3: generate narration audio")
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

    narration_text: str = (script.get("narration_text") or "").strip()
    if not narration_text:
        print("ERROR: Script has empty narration_text.", file=sys.stderr)
        sys.exit(1)

    # --- Voice profile ---
    try:
        profile = load_voice_profile()
    except ConfigError as exc:
        print(f"ERROR: Voice profile error: {exc}", file=sys.stderr)
        sys.exit(1)

    provider = profile["provider"]
    locale = profile["locale"]
    speed = profile["speed"]
    voice_id = profile["voice_id"]

    # --- Output path ---
    out_dir = f"/tmp/science_narrator/{run_id}"
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "narration.mp3")

    # --- Synthesise ---
    try:
        if provider == "gtts":
            _synthesise_gtts(narration_text, locale, out_path)
            source = "gtts"
            licence = "pipeline-generated"
        elif provider == "edge-tts":
            _synthesise_edge_tts(narration_text, voice_id, out_path)
            source = "edge-tts"
            licence = "microsoft-edge-tts-tos"
        elif provider == "openai":
            api_key = os.environ.get("OPENAI_API_KEY", "").strip()
            if not api_key:
                print("ERROR: OPENAI_API_KEY not set (required for openai TTS).", file=sys.stderr)
                sys.exit(1)
            _synthesise_openai(narration_text, voice_id, speed, out_path, api_key)
            source = "openai_tts"
            licence = "openai-tos-commercial"
        else:
            print(f"ERROR: Unknown VOICE_PROVIDER='{provider}'.", file=sys.stderr)
            sys.exit(1)
    except Exception as exc:
        print(f"ERROR: TTS synthesis failed: {exc}", file=sys.stderr)
        sys.exit(1)

    if not os.path.isfile(out_path) or os.path.getsize(out_path) == 0:
        print("ERROR: Audio file was not produced or is empty.", file=sys.stderr)
        sys.exit(1)

    duration_sec = _audio_duration(out_path)

    result = {
        "audio": {
            "asset_id": str(uuid.uuid4()),
            "type": "audio",
            "source": source,
            "licence": licence,
            "verified": True,
            "created_at": _utcnow(),
            "file_path": out_path,
            "duration_sec": round(duration_sec, 3),
        },
        "run_id": run_id,
    }
    print(json.dumps(result))


if __name__ == "__main__":
    main()
