"""
python/lib/ai_provider.py — Unified AI provider abstraction.

Supports OpenAI and Gemini for text generation and image generation.
Provider SDKs are imported lazily so missing packages only fail when
the relevant branch is actually executed.

Public API:
    generate_text(system_prompt, user_prompt, provider, api_key) -> str
    generate_image(prompt, provider, api_key, out_path) -> None
"""

import json
import re
import sys
import urllib.request


# ---------------------------------------------------------------------------
# Text generation
# ---------------------------------------------------------------------------

def generate_text(
    system_prompt: str,
    user_prompt: str,
    provider: str,
    api_key: str,
) -> tuple[str, str]:
    """
    Generate text using the configured provider.

    Returns (raw_text, model_name).
    Raises RuntimeError on API failure.
    """
    if provider == "openai":
        return _text_openai(system_prompt, user_prompt, api_key)
    if provider == "gemini":
        return _text_gemini(system_prompt, user_prompt, api_key)
    raise ValueError(f"Unknown AI provider: '{provider}'")


def _text_openai(system_prompt: str, user_prompt: str, api_key: str) -> tuple[str, str]:
    try:
        from openai import OpenAI  # type: ignore
    except ImportError:
        print("ERROR: openai not installed. Run: pip install openai", file=sys.stderr)
        raise

    client = OpenAI(api_key=api_key)
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


def _text_gemini(system_prompt: str, user_prompt: str, api_key: str) -> tuple[str, str]:
    try:
        import google.generativeai as genai  # type: ignore
    except ImportError:
        print(
            "ERROR: google-generativeai not installed. Run: pip install google-generativeai",
            file=sys.stderr,
        )
        raise

    genai.configure(api_key=api_key)
    model_name = "gemini-1.5-pro"
    model = genai.GenerativeModel(
        model_name=model_name,
        system_instruction=system_prompt,
    )

    # Gemini doesn't have a response_format flag — instruct via prompt
    full_prompt = user_prompt + "\n\nRespond with ONLY a raw JSON object. No markdown fences."

    response = model.generate_content(full_prompt)
    raw = response.text or ""

    # Strip any accidental markdown fences Gemini may add
    raw = _strip_json_fences(raw)

    return raw, model_name


def _strip_json_fences(text: str) -> str:
    """Remove ```json ... ``` or ``` ... ``` wrappers if present."""
    text = text.strip()
    match = re.match(r"^```(?:json)?\s*([\s\S]*?)\s*```$", text)
    if match:
        return match.group(1).strip()
    return text


# ---------------------------------------------------------------------------
# Image generation
# ---------------------------------------------------------------------------

def generate_image(
    prompt: str,
    provider: str,
    api_key: str,
    out_path: str,
) -> None:
    """
    Generate a single image and save it as a PNG to out_path.
    Raises RuntimeError on API failure.
    """
    if provider == "openai":
        _image_openai(prompt, api_key, out_path)
    elif provider == "gemini":
        _image_gemini(prompt, api_key, out_path)
    else:
        raise ValueError(f"Unknown AI provider: '{provider}'")


def _image_openai(prompt: str, api_key: str, out_path: str) -> None:
    try:
        from openai import OpenAI  # type: ignore
    except ImportError:
        print("ERROR: openai not installed. Run: pip install openai", file=sys.stderr)
        raise

    client = OpenAI(api_key=api_key)
    response = client.images.generate(
        model="dall-e-3",
        prompt=prompt,
        size="1792x1024",
        quality="standard",
        n=1,
    )
    image_url = response.data[0].url or ""
    urllib.request.urlretrieve(image_url, out_path)


def _image_gemini(prompt: str, api_key: str, out_path: str) -> None:
    try:
        import google.generativeai as genai  # type: ignore
    except ImportError:
        print(
            "ERROR: google-generativeai not installed. Run: pip install google-generativeai",
            file=sys.stderr,
        )
        raise

    genai.configure(api_key=api_key)
    imagen = genai.ImageGenerationModel("imagen-3.0-generate-001")
    result = imagen.generate_images(
        prompt=prompt,
        number_of_images=1,
        safety_filter_level="block_only_high",
        aspect_ratio="16:9",
    )
    if not result.images:
        raise RuntimeError(f"Imagen returned no images for prompt: {prompt[:80]}")

    image_bytes: bytes = result.images[0].image.image_bytes
    with open(out_path, "wb") as fh:
        fh.write(image_bytes)
