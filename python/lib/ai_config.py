"""
python/lib/ai_config.py — AI provider configuration loader.

Reads AI_PROVIDER from the environment and returns the matching API key.

Supported providers:
    openai  — reads OPENAI_API_KEY
    gemini  — reads GEMINI_API_KEY

Usage:
    from lib.ai_config import load as load_ai_config, ConfigError
    cfg = load_ai_config()   # {"provider": "gemini", "api_key": "..."}
"""

import os
import sys
from typing import TypedDict

from python.lib.voice_profile import ConfigError  # reuse existing ConfigError

# Maps provider name → its API key environment variable.
# When a new provider is added to ai_provider._REGISTRY, add its key here too.
_KEY_ENV: dict[str, str] = {
    "openai": "OPENAI_API_KEY",
    "gemini": "GEMINI_API_KEY",
    # "anthropic": "ANTHROPIC_API_KEY",
}


class AIConfig(TypedDict):
    provider: str
    api_key: str


def load() -> AIConfig:
    """
    Load and validate the AI provider configuration.

    Raises ConfigError if the provider is unknown or the API key is missing.
    Emits a notice to stderr when the default provider is used.
    """
    provider = os.environ.get("AI_PROVIDER", "").strip().lower()

    if not provider:
        provider = "openai"
        print(
            "NOTICE: AI_PROVIDER not set, defaulting to 'openai'.",
            file=sys.stderr,
        )

    if provider not in _KEY_ENV:
        raise ConfigError(
            f"AI_PROVIDER='{provider}' is not supported. "
            f"Choose from: {sorted(_KEY_ENV)}"
        )

    key_env = _KEY_ENV[provider]
    api_key = os.environ.get(key_env, "").strip()

    if not api_key:
        raise ConfigError(
            f"AI_PROVIDER={provider} requires {key_env} to be set."
        )

    return AIConfig(provider=provider, api_key=api_key)
