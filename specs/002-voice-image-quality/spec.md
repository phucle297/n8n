# Design: Expressive Voice & Content-Aware Image Generation

**Date:** 2026-03-23
**Branch:** 001-science-narrator
**Status:** Draft

---

## Problem

1. **Voice is flat** — default `gTTS` provider produces robotic, monotone audio with no emotional variation. OpenAI TTS is used without any tonal guidance.
2. **Images are generic** — the image prompt template uses only `term` + `definition`, ignoring the paper's content. All images have the same style directive regardless of what concept is being illustrated.

---

## Goals

- Voice output sounds like an engaged, expressive science narrator (not a text reader)
- Each image is a content-specific, visually distinct illustration matching the concept's narrative context
- Changes are free (no new paid APIs)
- No breaking changes to existing `VOICE_PROVIDER=openai` or `VOICE_PROVIDER=gtts` configs

---

## Non-Goals

- Adding ElevenLabs, Gemini TTS, or other paid/new providers
- Changing the video rendering pipeline (Stage 5)
- Altering the narration text structure

---

## Design

### Part 1: edge-tts voice provider

**Package:** `edge-tts>=6.1` (pip) — wraps Microsoft Edge Neural TTS, free, no API key. The `Communicate.save()` async API was stabilized in 6.x; versions below 6.1 have incompatible interfaces.

#### `python/lib/voice_profile.py`
- Add `"edge-tts"` to `_VALID_PROVIDERS` **before** changing `_DEFAULTS["provider"]` — these two changes are required together and must be applied in this order; if only `_DEFAULTS` is changed, a user who sets any other env var (e.g. `VOICE_LOCALE=en-GB`) without setting `VOICE_PROVIDER` will hit the `_VALID_PROVIDERS` guard and get a `ConfigError` at runtime
- Change default `provider` from `"gtts"` to `"edge-tts"`
- `_DEFAULTS["voice_id"]` stays as `""` intentionally — the `"en-US-AriaNeural"` fallback lives inside `_synthesise_edge_tts`, not in the profile, avoiding two sources of truth
- Update module-level docstring to reflect the new default: `provider=edge-tts` (was `provider=gtts`)
- Inside `load()`, after the provider is resolved (i.e. after the `if provider not in _VALID_PROVIDERS` check), add:
  ```python
  if provider == "edge-tts" and (raw_speed or raw_pitch):
      print("WARNING: VOICE_SPEED and VOICE_PITCH are ignored by edge-tts provider.", file=sys.stderr)
  ```
  This mirrors the existing OpenAI API-key check pattern in the same function.

#### `python/generate_voice.py`
- Update module docstring: add `edge-tts` to the `VOICE_PROVIDER` list, note that `VOICE_SPEED` and `VOICE_PITCH` are ignored by this provider
- Add `_synthesise_edge_tts(narration_text, voice_id, out_path)`:

```python
import asyncio
import edge_tts

async def _run(text: str, voice: str, path: str) -> None:
    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(path)

def _synthesise_edge_tts(narration_text: str, voice_id: str, out_path: str) -> None:
    effective_voice = voice_id if voice_id else "en-US-AriaNeural"
    # asyncio.run() is safe here: generate_voice.py is invoked as a CLI subprocess,
    # never from within an already-running event loop.
    asyncio.run(_run(narration_text, effective_voice, out_path))
```

Wire into `main()` as a new `elif provider == "edge-tts":` branch, setting:
```python
source = "edge-tts"
licence = "microsoft-edge-tts-tos"
```

**Recommended voices for science narration (set via `VOICE_ID` env var):**
- `en-US-AriaNeural` — warm, conversational (default)
- `en-US-GuyNeural` — clear, authoritative
- `en-US-JennyNeural` — friendly, engaging

#### Backwards compatibility
`VOICE_PROVIDER=gtts` and `VOICE_PROVIDER=openai` are unchanged.

---

### Part 2: Content-aware image prompts via `visual_description`

#### `python/generate_script.py` (Stage 2)

Extend `_USER_PROMPT_TEMPLATE` in **two places**:

**1. Requirements bullet list** — add to the `key_concepts` item description:
```
    - visual_description: 1–2 sentence cinematic scene description for image generation.
      Describe exactly what to show: subject, action, mood, lighting, style.
      No text or labels. Example: "A glowing double helix rotating slowly in a dark void,
      base pairs highlighted in blue and orange, photorealistic."
```

**2. JSON example block** — add `"visual_description": "..."` to each key_concepts entry in the `Return this exact JSON structure:` section.

Both locations must be updated or the AI will see a contradiction.

**Validation:** Immediately after `gpt_data = json.loads(raw_json)` succeeds, iterate `gpt_data.get("outline", {}).get("key_concepts", [])` and emit a warning to stderr for any entry with a missing or empty `visual_description`:
```
WARNING: concept '{term}' missing visual_description — image will use fallback prompt.
```
Do not exit; Stage 4 handles the fallback gracefully. Place this loop before the `script` dict is assembled at the bottom of `main()`.

#### `python/generate_images.py` (Stage 4)

- **Retain** `_PROMPT_TEMPLATE` — it is used as the fallback when `visual_description` is absent
- Use `concept.get("visual_description")` as the primary image prompt; fall back to `_PROMPT_TEMPLATE.format(...)` when absent or empty
- The `generation_prompt` field in the output JSON will now contain the AI-generated cinematic description for new runs. Stage 5 (`render_video.py`) only reads `file_path` from the image asset — it does not parse `generation_prompt` — so this change is safe
- **Fix pre-existing bugs in licence values:**
  - `_LICENCE_MAP` at line 92: `"gemini": "openai-tos-commercial"` → `"gemini": "google-tos-commercial"`
  - `_LICENCE_MAP.get(provider, "openai-tos-commercial")` default at line 94: change to `"unknown-tos"` so unknown providers don't claim OpenAI licence terms

---

## Files Changed

| File | Change |
|------|--------|
| `python/lib/voice_profile.py` | Add `edge-tts` to `_VALID_PROVIDERS`; change default; update docstring; add SPEED/PITCH warning |
| `python/generate_voice.py` | Add `_synthesise_edge_tts()`; wire into `main()`; update docstring |
| `python/generate_script.py` | Add `visual_description` to both prompt locations; add per-concept warning |
| `python/generate_images.py` | Use `visual_description` as primary prompt; retain `_PROMPT_TEMPLATE` as fallback |
| `requirements.txt` | Add `edge-tts>=6.1` |
| `python/tests/unit/test_generate_images.py` | New: fallback + primary path tests for image prompt selection |

---

## Data Flow

```
Stage 2 (generate_script.py)
  AI generates key_concepts[].visual_description
        |
        v
Stage 4 (generate_images.py)
  visual_description (or fallback template) → image prompt → DALL-E 3 / Imagen
```

```
Stage 3 (generate_voice.py)
  narration_text → edge-tts (en-US-AriaNeural) → narration.mp3
```

---

## Testing

**Automated (pytest):**
- File: `python/tests/unit/test_generate_images.py`
- **Fallback path test:** mock `ai.generate_image`, pass a concept dict with no `visual_description`, assert the string passed to `generate_image` equals `_PROMPT_TEMPLATE.format(concept=term, definition=definition)`
- **Primary path test:** mock `ai.generate_image`, pass a concept dict with a non-empty `visual_description`, assert the string passed to `generate_image` equals the `visual_description` value directly

**Manual:**
- Run pipeline end-to-end and listen to output MP3 — should sound expressive, not robotic
- Inspect generated images — each should visually match its concept's narrative context
- Verify `VOICE_PROVIDER=gtts` and `VOICE_PROVIDER=openai` still work (no regression)
- Verify `VOICE_SPEED` + `VOICE_PROVIDER=edge-tts` emits the expected WARNING to stderr
