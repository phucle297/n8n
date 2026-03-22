"""
python/lib/voice_profile.py — Global voice profile loader.

Reads VOICE_PROVIDER, VOICE_LOCALE, VOICE_SPEED, VOICE_PITCH, VOICE_ID
from environment variables and returns a validated VoiceProfile dict.

Defaults (used when no env vars are set):
    provider=gtts, locale=en-US, speed=1.0, pitch=default, voice_id=""
"""

import os
import sys
from typing import TypedDict


class ConfigError(Exception):
    """Raised when the voice profile configuration is invalid."""


class VoiceProfile(TypedDict):
    provider: str
    locale: str
    speed: float
    pitch: str
    voice_id: str


_VALID_PROVIDERS = {"gtts", "openai"}
_SPEED_MIN = 0.5
_SPEED_MAX = 2.0

_DEFAULTS: VoiceProfile = {
    "provider": "gtts",
    "locale": "en-US",
    "speed": 1.0,
    "pitch": "default",
    "voice_id": "",
}


def load() -> VoiceProfile:
    """
    Load and validate the voice profile from environment variables.

    Emits notices to stderr when defaults are applied.
    Raises ConfigError for fatal configuration problems (e.g. openai
    provider without OPENAI_API_KEY).
    """
    raw_provider = os.environ.get("VOICE_PROVIDER", "").strip()
    raw_locale = os.environ.get("VOICE_LOCALE", "").strip()
    raw_speed = os.environ.get("VOICE_SPEED", "").strip()
    raw_pitch = os.environ.get("VOICE_PITCH", "").strip()
    raw_voice_id = os.environ.get("VOICE_ID", "").strip()

    all_absent = not any([raw_provider, raw_locale, raw_speed, raw_pitch, raw_voice_id])
    if all_absent:
        print(
            "NOTICE: no voice profile configured, using defaults "
            f"({_DEFAULTS})",
            file=sys.stderr,
        )
        return dict(_DEFAULTS)  # type: ignore[return-value]

    # --- provider ---
    provider = raw_provider if raw_provider else _DEFAULTS["provider"]
    if provider not in _VALID_PROVIDERS:
        raise ConfigError(
            f"VOICE_PROVIDER='{provider}' is not valid. "
            f"Choose from: {sorted(_VALID_PROVIDERS)}"
        )

    # --- OpenAI API key check ---
    if provider == "openai" and not os.environ.get("OPENAI_API_KEY", "").strip():
        raise ConfigError(
            "VOICE_PROVIDER=openai requires OPENAI_API_KEY to be set."
        )

    # --- locale ---
    locale = raw_locale if raw_locale else _DEFAULTS["locale"]

    # --- speed ---
    if raw_speed:
        try:
            speed = float(raw_speed)
        except ValueError:
            raise ConfigError(f"VOICE_SPEED='{raw_speed}' is not a valid float.")
        if not (_SPEED_MIN <= speed <= _SPEED_MAX):
            clamped = max(_SPEED_MIN, min(_SPEED_MAX, speed))
            print(
                f"WARNING: VOICE_SPEED={speed} out of range [{_SPEED_MIN}, {_SPEED_MAX}]; "
                f"clamped to {clamped}.",
                file=sys.stderr,
            )
            speed = clamped
    else:
        speed = _DEFAULTS["speed"]

    # --- pitch ---
    pitch = raw_pitch if raw_pitch else _DEFAULTS["pitch"]

    # --- voice_id ---
    voice_id = raw_voice_id if raw_voice_id else _DEFAULTS["voice_id"]

    return VoiceProfile(
        provider=provider,
        locale=locale,
        speed=speed,
        pitch=pitch,
        voice_id=voice_id,
    )
