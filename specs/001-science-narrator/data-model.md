# Data Model: Science Narrator

**Branch**: `001-science-narrator`
**Date**: 2026-03-22

---

## Entities

### Paper

A peer-reviewed article discovered from ArXiv or NASA RSS.

| Field | Type | Notes |
|---|---|---|
| `id` | string | Canonical paper ID, e.g. `arxiv:2401.00001` or `nasa:YYYYMMDD` |
| `title` | string | Full paper title |
| `authors` | string[] | Author name list |
| `published_date` | ISO date | Publication or preprint date |
| `abstract` | string | Full abstract text |
| `source` | enum | `arxiv` \| `nasa_rss` |
| `source_url` | string | Direct URL to paper landing page |
| `licence` | string | e.g. `cc-by-4.0`, `arxiv-non-exclusive` |
| `full_text_available` | boolean | Whether full text was accessible |
| `retrieved_at` | ISO datetime | When the pipeline fetched this paper |

**Validation rules**:
- `id` MUST be unique in `processed_papers.json` before processing begins.
- `abstract` MUST be non-empty; pipeline rejects if blank.
- `licence` MUST be recorded; defaults to `arxiv-non-exclusive` for ArXiv if not
  stated explicitly.

---

### Script

Narration document derived from a Paper.

| Field | Type | Notes |
|---|---|---|
| `paper_id` | string | Foreign key → Paper.id |
| `learning_objective` | string | One sentence; MUST appear in first 30 seconds |
| `outline` | Outline | Structured intro/concepts/conclusion (see below) |
| `narration_text` | string | Full narration; 750–900 words target |
| `word_count` | integer | Auto-computed |
| `estimated_duration_sec` | integer | `word_count / 150 * 60` |
| `citations` | Citation[] | List of inline citations |
| `generated_at` | ISO datetime | When GPT-4o produced this script |
| `model` | string | e.g. `gpt-4o-2024-08-06` |

**Outline sub-entity**:
```json
{
  "intro": "string",
  "key_concepts": [
    { "term": "string", "definition": "string", "narration_segment": "string" }
  ],
  "conclusion": "string"
}
```

**Citation sub-entity**:
```json
{ "paper_id": "string", "claim_excerpt": "string" }
```

**Validation rules**:
- `word_count` MUST be in range [650, 950]; pipeline halts if out of range.
- `learning_objective` MUST be non-empty.
- `citations` MUST contain at least one entry matching the source Paper's `id`.

---

### VoiceProfile

Central narrator voice configuration; one active profile at any time.

| Field | Type | Notes |
|---|---|---|
| `provider` | enum | `gtts` \| `openai` |
| `locale` | string | BCP-47, e.g. `en-US`, `en-GB` |
| `speed` | float | 0.5–2.0; 1.0 = normal |
| `pitch` | string | `default`, `low`, `high` (gTTS limited; OpenAI TTS ignores) |
| `voice_id` | string | OpenAI TTS voice name, e.g. `nova` (ignored for gTTS) |

**Storage**: n8n environment variables:
- `VOICE_PROVIDER`, `VOICE_LOCALE`, `VOICE_SPEED`, `VOICE_PITCH`, `VOICE_ID`

**Default** (used when no env vars set):
```json
{ "provider": "gtts", "locale": "en-US", "speed": 1.0, "pitch": "default", "voice_id": "" }
```

---

### Asset

Any visual or audio element incorporated into a video.

| Field | Type | Notes |
|---|---|---|
| `asset_id` | string | UUID, generated at creation |
| `type` | enum | `image` \| `audio` \| `background_music` |
| `source` | enum | `dalle3` \| `gtts` \| `openai_tts` \| `royalty_free` \| `public_domain` |
| `source_url` | string | URL if fetched; empty if generated |
| `generation_prompt` | string | DALL·E prompt if AI-generated; empty otherwise |
| `licence` | string | e.g. `openai-tos-commercial`, `cc0`, `pexels-licence` |
| `verified` | boolean | True once licence confirmed |
| `created_at` | ISO datetime | Generation or retrieval time |
| `file_path` | string | Temp path during run (cleared after export) |

**Validation rules**:
- `verified` MUST be `true` for every asset before `validate_manifest.py` passes.
- `licence` MUST be non-empty; asset is rejected if licence is unknown.

---

### ProvenanceManifest

One manifest per pipeline run; written to the output directory alongside the video files.

| Field | Type | Notes |
|---|---|---|
| `run_id` | string | UUID |
| `paper_id` | string | Source paper |
| `generated_at` | ISO datetime | Export timestamp |
| `assets` | Asset[] | Complete list of all assets used |
| `all_verified` | boolean | True iff every asset.verified = true |
| `video_files` | VideoFile[] | Paths and metadata for exported videos |

**File path**: `output/<run_id>/assets-manifest.json`

---

### Video

A final composed output file.

| Field | Type | Notes |
|---|---|---|
| `run_id` | string | Parent pipeline run |
| `paper_id` | string | Source paper |
| `format` | enum | `vertical_9_16` \| `horizontal_16_9` |
| `width_px` | integer | 1080 (vertical) or 1920 (horizontal) |
| `height_px` | integer | 1920 (vertical) or 1080 (horizontal) |
| `duration_sec` | float | Actual audio duration |
| `file_path` | string | `output/<run_id>/video_<format>.mp4` |
| `exported_at` | ISO datetime | File write completion time |

---

### PipelineRun

A single end-to-end execution instance.

| Field | Type | Notes |
|---|---|---|
| `run_id` | string | UUID; generated at start |
| `topic` | string | Input topic keyword |
| `paper_id` | string | Resolved paper ID (null until stage 1 completes) |
| `status` | enum | `running` \| `success` \| `failed` |
| `stages` | StageResult[] | Per-stage outcome |
| `started_at` | ISO datetime | |
| `completed_at` | ISO datetime | Null until terminal state |
| `output_dir` | string | `output/<run_id>/` |
| `log_file` | string | `logs/<run_id>.json` |

**StageResult sub-entity**:
```json
{
  "stage": "fetch_paper | generate_script | generate_voice | generate_images | render_video | validate_manifest",
  "status": "success | failed | skipped",
  "duration_sec": 0.0,
  "error": "string or null"
}
```

**File path**: `logs/<run_id>.json`

---

## State Transitions

```
PipelineRun.status:
  running → success   (all 6 stages pass)
  running → failed    (any stage exits non-zero)
```

```
Asset.verified:
  false (default) → true   (validate_manifest.py confirms licence)
  false           → error  (pipeline halts; asset rejected)
```

---

## Deduplication Store

**File**: `data/processed_papers.json`
**Format**: JSON array of paper ID strings.

```json
["arxiv:2401.00001", "arxiv:2312.09876"]
```

Append-only; never delete entries. Checked by `fetch_paper.py` before accepting a paper.
