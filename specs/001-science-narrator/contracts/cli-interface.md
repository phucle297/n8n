# Contract: CLI Interface (n8n → Python)

**Branch**: `001-science-narrator`
**Date**: 2026-03-22

All Python scripts are invoked by n8n Execute Command nodes. Each script follows the
same protocol:

## General Protocol

- **Input**: CLI arguments and/or environment variables.
- **Output**: A single JSON object written to **stdout** on success.
- **Errors**: Human-readable message written to **stderr**; nothing written to stdout.
- **Exit codes**: `0` = success, `1` = recoverable error (bad input, source unavailable),
  `2` = fatal/unexpected error.
- n8n reads `stdout` as the stage payload and passes it to the next node.

---

## Stage 1: `fetch_paper.py`

**Invocation**:
```bash
python python/fetch_paper.py \
  --topic "black holes" \
  [--source arxiv|nasa|auto]  # default: auto (arxiv first, nasa fallback)
```

**Environment variables read**: none required.

**stdout on success**:
```json
{
  "paper": {
    "id": "arxiv:2401.00001",
    "title": "Rotating Black Holes and Their Properties",
    "authors": ["A. Smith", "B. Jones"],
    "published_date": "2024-01-15",
    "abstract": "...",
    "source": "arxiv",
    "source_url": "https://arxiv.org/abs/2401.00001",
    "licence": "cc-by-4.0",
    "full_text_available": true,
    "retrieved_at": "2026-03-22T10:00:00Z"
  },
  "run_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

**Exit 1 conditions**:
- No paper found for topic.
- Paper ID already in `data/processed_papers.json` (duplicate).
- Abstract is empty or inaccessible.
- Source unreachable (network error).

---

## Stage 2: `generate_script.py`

**Invocation**:
```bash
python python/generate_script.py \
  --paper '<json string from stage 1>'
```

**Environment variables read**:
- `OPENAI_API_KEY` (required)

**stdout on success**:
```json
{
  "script": {
    "paper_id": "arxiv:2401.00001",
    "learning_objective": "By the end of this video, you will understand...",
    "outline": {
      "intro": "...",
      "key_concepts": [
        { "term": "event horizon", "definition": "...", "narration_segment": "..." }
      ],
      "conclusion": "..."
    },
    "narration_text": "...",
    "word_count": 810,
    "estimated_duration_sec": 324,
    "citations": [
      { "paper_id": "arxiv:2401.00001", "claim_excerpt": "..." }
    ],
    "generated_at": "2026-03-22T10:01:30Z",
    "model": "gpt-4o-2024-08-06"
  },
  "run_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

**Exit 1 conditions**:
- `word_count` outside [650, 950].
- `learning_objective` empty.
- No citation for the source paper found.
- OpenAI API error.

---

## Stage 3: `generate_voice.py`

**Invocation**:
```bash
python python/generate_voice.py \
  --script '<json string from stage 2>' \
  --run-id '<uuid>'
```

**Environment variables read**:
- `VOICE_PROVIDER` (default: `gtts`)
- `VOICE_LOCALE` (default: `en-US`)
- `VOICE_SPEED` (default: `1.0`)
- `VOICE_PITCH` (default: `default`)
- `VOICE_ID` (default: empty; used for OpenAI TTS only)
- `OPENAI_API_KEY` (required if `VOICE_PROVIDER=openai`)

**stdout on success**:
```json
{
  "audio": {
    "asset_id": "uuid",
    "type": "audio",
    "source": "gtts",
    "licence": "pipeline-generated",
    "verified": true,
    "created_at": "2026-03-22T10:02:00Z",
    "file_path": "/tmp/science_narrator/<run_id>/narration.mp3",
    "duration_sec": 320.5
  },
  "run_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

**Exit 1 conditions**:
- TTS provider unavailable.
- `VOICE_PROVIDER=openai` but `OPENAI_API_KEY` not set.
- Audio file not produced.

---

## Stage 4: `generate_images.py`

**Invocation**:
```bash
python python/generate_images.py \
  --script '<json string from stage 2>' \
  --run-id '<uuid>'
```

**Environment variables read**:
- `OPENAI_API_KEY` (required)

**stdout on success**:
```json
{
  "images": [
    {
      "asset_id": "uuid",
      "type": "image",
      "source": "dalle3",
      "generation_prompt": "...",
      "licence": "openai-tos-commercial",
      "verified": true,
      "created_at": "2026-03-22T10:03:00Z",
      "file_path": "/tmp/science_narrator/<run_id>/image_01.png"
    }
  ],
  "run_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

**Exit 1 conditions**:
- DALL·E API error or quota exceeded.
- Any image file not written to disk.

---

## Stage 5: `render_video.py`

**Invocation**:
```bash
python python/render_video.py \
  --script '<json string from stage 2>' \
  --audio '<json string from stage 3>' \
  --images '<json string from stage 4>' \
  --run-id '<uuid>'
```

**Environment variables read**: none.

**stdout on success**:
```json
{
  "videos": [
    {
      "run_id": "uuid",
      "paper_id": "arxiv:2401.00001",
      "format": "vertical_9_16",
      "width_px": 1080,
      "height_px": 1920,
      "duration_sec": 320.5,
      "file_path": "/tmp/science_narrator/<run_id>/video_vertical.mp4",
      "exported_at": "2026-03-22T10:08:00Z"
    },
    {
      "run_id": "uuid",
      "paper_id": "arxiv:2401.00001",
      "format": "horizontal_16_9",
      "width_px": 1920,
      "height_px": 1080,
      "duration_sec": 320.5,
      "file_path": "/tmp/science_narrator/<run_id>/video_horizontal.mp4",
      "exported_at": "2026-03-22T10:08:45Z"
    }
  ],
  "run_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

**Exit 1 conditions**:
- ffmpeg or ImageMagick not available.
- Either video file not produced.
- Audio–video duration mismatch > 2 seconds.

---

## Stage 6: `validate_manifest.py`

**Invocation**:
```bash
python python/validate_manifest.py \
  --audio '<json string from stage 3>' \
  --images '<json string from stage 4>' \
  --videos '<json string from stage 5>' \
  --run-id '<uuid>'
```

**Environment variables read**: none.

**stdout on success**:
```json
{
  "manifest": {
    "run_id": "uuid",
    "paper_id": "arxiv:2401.00001",
    "generated_at": "2026-03-22T10:09:00Z",
    "all_verified": true,
    "assets": [ /* all Asset records */ ],
    "video_files": [ /* all Video records */ ]
  },
  "manifest_path": "output/<run_id>/assets-manifest.json",
  "run_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

**Exit 1 conditions**:
- Any asset has `verified: false`.
- Any asset is missing a `licence` value.
- Manifest file cannot be written to `output/<run_id>/`.
- Video files listed in stage 5 output do not exist on disk.
