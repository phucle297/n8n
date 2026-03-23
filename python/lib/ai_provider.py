"""
python/lib/ai_provider.py — AI provider Strategy pattern.

Adding a new provider:
    1. Subclass AIProvider and implement generate_text() + generate_image()
    2. Register it in _REGISTRY with a string key
    3. Add its API key env var to ai_config._KEY_ENV

Public API:
    get_provider(provider: str, api_key: str) -> AIProvider
    AIProvider.generate_text(system_prompt, user_prompt) -> (raw_text, model_name)
    AIProvider.generate_image(prompt, out_path) -> None
"""

from __future__ import annotations

import re
import sys
import urllib.request
from abc import ABC, abstractmethod


# ---------------------------------------------------------------------------
# Abstract strategy
# ---------------------------------------------------------------------------

class AIProvider(ABC):
    """Base strategy. Each concrete class encapsulates one provider's SDK calls."""

    def __init__(self, api_key: str) -> None:
        self.api_key = api_key

    @abstractmethod
    def generate_text(self, system_prompt: str, user_prompt: str) -> tuple[str, str]:
        """
        Generate text from a prompt pair.

        Returns (raw_text, model_name).
        Raises RuntimeError on API failure.
        """

    @abstractmethod
    def generate_image(self, prompt: str, out_path: str) -> None:
        """
        Generate a single image and save it as PNG to out_path.

        Raises RuntimeError on API failure.
        """


# ---------------------------------------------------------------------------
# Concrete strategy: OpenAI
# ---------------------------------------------------------------------------

class OpenAIProvider(AIProvider):
    """
    OpenAI strategy.
        Text  : GPT-4o (gpt-4o-2024-08-06) with JSON mode
        Images: DALL-E 3 (1792×1024)
    """

    def generate_text(self, system_prompt: str, user_prompt: str) -> tuple[str, str]:
        client = self._client()
        response = client.chat.completions.create(
            model="gpt-4o-2024-08-06",
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.7,
        )
        return response.choices[0].message.content or "", response.model

    def generate_image(self, prompt: str, out_path: str) -> None:
        client = self._client()
        response = client.images.generate(
            model="dall-e-3",
            prompt=prompt,
            size="1792x1024",
            quality="standard",
            n=1,
        )
        url = response.data[0].url or ""
        urllib.request.urlretrieve(url, out_path)

    def _client(self):
        try:
            from openai import OpenAI  # type: ignore
        except ImportError:
            print("ERROR: openai not installed. Run: pip install openai", file=sys.stderr)
            raise
        return OpenAI(api_key=self.api_key)


# ---------------------------------------------------------------------------
# Concrete strategy: Gemini
# ---------------------------------------------------------------------------

class GeminiProvider(AIProvider):
    """
    Google Gemini strategy.
        Text  : Gemini 2.0 Flash (gemini-2.5-flash)
        Images: Imagen 3 (imagen-3.0-generate-001)
    """

    _TEXT_MODEL = "gemini-2.5-flash"

    def generate_text(self, system_prompt: str, user_prompt: str) -> tuple[str, str]:
        client = self._client()
        from google.genai import types  # type: ignore
        response = client.models.generate_content(
            model=self._TEXT_MODEL,
            contents=user_prompt,
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
                response_mime_type="application/json",
            ),
        )
        raw = _strip_json_fences(response.text or "")
        return raw, self._TEXT_MODEL

    def generate_image(self, prompt: str, out_path: str) -> None:
        client = self._client()
        from google.genai import types  # type: ignore
        result = client.models.generate_images(
            model="models/imagen-4.0-generate-001",
            prompt=prompt,
            config=types.GenerateImagesConfig(
                number_of_images=1,
                safety_filter_level="block_low_and_above",
                aspect_ratio="16:9",
            ),
        )
        if not result.generated_images:
            raise RuntimeError(f"Imagen returned no images for prompt: {prompt[:80]}")
        image_bytes: bytes = result.generated_images[0].image.image_bytes
        with open(out_path, "wb") as fh:
            fh.write(image_bytes)

    def _client(self):
        try:
            from google import genai  # type: ignore
        except ImportError:
            print(
                "ERROR: google-genai not installed. "
                "Run: pip install google-genai",
                file=sys.stderr,
            )
            raise
        return genai.Client(api_key=self.api_key)


# ---------------------------------------------------------------------------
# Provider registry — add new providers here
# ---------------------------------------------------------------------------

_REGISTRY: dict[str, type[AIProvider]] = {
    "openai": OpenAIProvider,
    "gemini": GeminiProvider,
    # "anthropic": AnthropicProvider,  # example: uncomment when implemented
}


def get_provider(provider: str, api_key: str) -> AIProvider:
    """
    Factory: return the concrete AIProvider for the given provider name.

    Raises ValueError for unknown providers.
    """
    cls = _REGISTRY.get(provider)
    if cls is None:
        raise ValueError(
            f"Unknown AI provider: '{provider}'. "
            f"Registered providers: {sorted(_REGISTRY)}"
        )
    return cls(api_key)


def registered_providers() -> list[str]:
    """Return all provider keys currently in the registry."""
    return sorted(_REGISTRY)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _strip_json_fences(text: str) -> str:
    """Remove ```json ... ``` or ``` ... ``` wrappers if present."""
    text = text.strip()
    match = re.match(r"^```(?:json)?\s*([\s\S]*?)\s*```$", text)
    if match:
        return match.group(1).strip()
    return text
