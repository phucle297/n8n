# Design: Expressive Voice & Content-Aware Image Generation

**Date:** 2026-03-23
**Branch:** 001-science-narrator
**Status:** Approved

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

**Package:** `edge-tts` (pip) — wraps Microsoft Edge Neural TTS, free, no API key.

#### `python/lib/voice_profile.py`
- Add `"edge-tts"` to `_VALID_PROVIDERS`
- Change default `provider` from `"gtts"` to `"edge-tts"`
- Default `VOICE_ID` when using edge-tts: `en-US-AriaNeural`

#### `python/generate_voice.py`
Add `_synthesise_edge_tts(narration_text, voice_id, out_path)`:
```python
import asyncio
import edge_tts

async def _run(text, voice, path):
    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(path)

asyncio.run(_run(narration_text, voice_id or "en-US-AriaNeural", out_path))
```
Wire into the `provider == "edge-tts"` branch in `main()`.

**Recommended voices for science narration:**
- `en-US-AriaNeural` — warm, conversational (default)
- `en-US-GuyNeural` — clear, authoritative
- `en-US-JennyNeural` — friendly, engaging

Users override via `VOICE_ID=en-US-GuyNeural` in `.env`.

#### Backwards compatibility
`VOICE_PROVIDER=gtts` and `VOICE_PROVIDER=openai` are unchanged.

---

### Part 2: Content-aware image prompts via `visual_description`

#### `python/generate_script.py` (Stage 2)
Extend `_USER_PROMPT_TEMPLATE` to require a `visual_description` field per key concept:

```
- visual_description: 1–2 sentence cinematic scene description for image generation.
  Describe exactly what to show: subject, action, mood, lighting, style.
  No text or labels in the image. Example: "A glowing double helix rotating slowly
  in a dark void, base pairs highlighted in blue and orange, photorealistic."
```

Updated JSON schema fragment:
```json
"key_concepts": [{
  "term": "...",
  "definition": "...",
  "narration_segment": "...",
  "visual_description": "..."
}]
```

#### `python/generate_images.py` (Stage 4)
- Remove static `_PROMPT_TEMPLATE`
- Use `concept.get("visual_description")` as the image prompt
- Fallback: if `visual_description` is absent (old cached script), construct prompt from `term` + `definition` using the old template (preserves backwards compat)

---

## Files Changed

| File | Change |
|------|--------|
| `python/lib/voice_profile.py` | Add `edge-tts` provider, change default |
| `python/generate_voice.py` | Add `_synthesise_edge_tts()`, wire into main |
| `python/generate_script.py` | Add `visual_description` to prompt + schema |
| `python/generate_images.py` | Use `visual_description` as image prompt |
| `requirements.txt` or `Dockerfile` | Add `edge-tts` dependency |

---

## Data Flow

```
Stage 2 (generate_script.py)
  AI generates key_concepts[].visual_description
        |
        v
Stage 4 (generate_images.py)
  visual_description → image prompt → DALL-E 3 / Imagen
```

```
Stage 3 (generate_voice.py)
  narration_text → edge-tts (en-US-AriaNeural) → narration.mp3
```

---

## Testing

- Run pipeline end-to-end and listen to output MP3 — should sound expressive, not robotic
- Inspect generated images — each should visually match its concept's narrative context
- Verify `VOICE_PROVIDER=gtts` and `VOICE_PROVIDER=openai` still work (no regression)
- Verify fallback image prompt logic works when `visual_description` is absent
