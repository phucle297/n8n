# Contract: Voice Profile Schema

**Branch**: `001-science-narrator`
**Date**: 2026-03-22

The Global voice profile is stored as n8n environment variables and read by
`lib/voice_profile.py` at the start of `generate_voice.py`.

## n8n Environment Variables

| Variable | Type | Required | Default | Description |
|---|---|---|---|---|
| `VOICE_PROVIDER` | enum | No | `gtts` | TTS engine: `gtts` or `openai` |
| `VOICE_LOCALE` | string | No | `en-US` | BCP-47 locale code |
| `VOICE_SPEED` | float | No | `1.0` | Playback speed multiplier (0.5–2.0) |
| `VOICE_PITCH` | string | No | `default` | Pitch hint: `default`, `low`, `high` (gTTS only; ignored by OpenAI TTS) |
| `VOICE_ID` | string | No | `` (empty) | OpenAI TTS voice name (e.g. `nova`, `alloy`, `onyx`); ignored if `VOICE_PROVIDER=gtts` |
| `OPENAI_API_KEY` | string | Conditional | — | Required when `VOICE_PROVIDER=openai` |

## Voice Profile JSON (internal representation)

`lib/voice_profile.py` loads env vars and returns this structure:

```json
{
  "provider": "gtts | openai",
  "locale": "en-US",
  "speed": 1.0,
  "pitch": "default",
  "voice_id": "nova"
}
```

## Validation Rules

- `provider` MUST be `gtts` or `openai`; any other value is a fatal error.
- `speed` MUST be in range [0.5, 2.0]; values outside this range are clamped and
  a warning is logged.
- If `provider=openai` and `OPENAI_API_KEY` is not set, pipeline exits with code 1
  before any API call is made.
- If no env vars are set, the default profile is used and a notice is emitted to the
  run log.

## OpenAI TTS Voice Options

| Voice ID | Characteristic |
|---|---|
| `alloy` | Neutral, balanced |
| `echo` | Clear, measured |
| `fable` | Expressive, storytelling |
| `onyx` | Deep, authoritative |
| `nova` | Warm, engaging (recommended for science narration) |
| `shimmer` | Clear, bright |
