# Implementation Plan: Science Narrator

**Branch**: `001-science-narrator` | **Date**: 2026-03-22 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/001-science-narrator/spec.md`

## Summary

Automate end-to-end production of short science education videos by orchestrating a
six-stage pipeline in n8n: fetch a physics/science paper (ArXiv API or NASA RSS) →
generate a 4–6 minute narration script (OpenAI GPT-4o) → synthesise narration audio
(gTTS or OpenAI TTS) → generate visuals (OpenAI DALL·E 3) → compose and export dual-
format video (Python + MoviePy) → validate asset provenance and export. The Global voice
profile is stored as n8n environment variables and injected into every run. All asset
provenance is recorded in a machine-readable manifest; the pipeline fails loudly if any
compliance gate is not cleared.

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**:
- n8n (self-hosted, Execute Command node enabled)
- Python: `moviepy>=1.0.3`, `openai>=1.0`, `requests>=2.31`, `gTTS>=2.5`,
  `feedparser>=6.0` (NASA RSS), `Pillow>=10.0`
**Storage**: Local filesystem — temp assets per run, output videos, JSON run logs,
`data/processed_papers.json` (deduplication), `assets-manifest.json` per video
**Testing**: pytest
**Target Platform**: Linux server (Ubuntu 22.04+), n8n self-hosted via Docker or npm
**Project Type**: Automation pipeline — Python CLI scripts invoked by n8n Execute
Command nodes
**Performance Goals**: Full pipeline run (fetch → dual-format export) in under 15 minutes
**Constraints**: Zero partial outputs on failure; every asset must pass licence
verification before export; pipeline must emit structured JSON logs at each stage
**Scale/Scope**: Single operator (one content creator), one video per pipeline run,
single-threaded

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Gate | Status | Notes |
|---|---|---|---|
| I. Scientific Accuracy | Every factual claim MUST trace to a verifiable paper ID | ✅ PASS | ArXiv ID / NASA article ID embedded in video metadata and on-screen citation; script generation prompt enforces citation per claim |
| I. Scientific Accuracy | Pipeline rejects content that cannot be sourced | ✅ PASS | `fetch_paper.py` exits non-zero if no accessible abstract is returned; n8n error node halts workflow |
| II. Educational Value | Learning objective stated within first 30 seconds | ✅ PASS | Script generation prompt includes mandatory opening-section template with learning objective |
| II. Educational Value | Structured outline (intro → key concepts → conclusion) before any asset generation | ✅ PASS | `generate_script.py` produces structured JSON outline; asset generation stages gate on its presence |
| II. Educational Value | Jargon defined on first use | ✅ PASS | Script generation prompt instructs GPT-4o to define each technical term inline |
| III. Copyright Compliance | All assets AI-generated or royalty-free with provenance logged | ✅ PASS | DALL·E 3 for images; gTTS/OpenAI TTS for audio; `manifest.py` records every asset |
| III. Copyright Compliance | Manifest present and verified before export | ✅ PASS | `validate_manifest.py` runs as stage 6 gate; non-zero exit if any asset unverified |
| III. Copyright Compliance | ArXiv figures only if licence permits | ✅ PASS | No raw ArXiv figures used; all visuals are freshly AI-generated |

**Verdict**: All gates pass. Phase 0 research approved.

## Project Structure

### Documentation (this feature)

```text
specs/001-science-narrator/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
│   ├── cli-interface.md
│   ├── manifest-schema.md
│   └── voice-profile-schema.md
└── tasks.md             # Phase 2 output (/speckit.tasks)
```

### Source Code (repository root)

```text
n8n_workflows/
└── science_narrator.json        # Exported n8n workflow (importable)

python/
├── requirements.txt
├── fetch_paper.py               # Stage 1 — Source Data
├── generate_script.py           # Stage 2 — Script Generation
├── generate_voice.py            # Stage 3 — Voice Generation
├── generate_images.py           # Stage 4 — Image Generation
├── render_video.py              # Stage 5 — MoviePy Render (both formats)
├── validate_manifest.py         # Stage 6 — Compliance Validation Gate
├── lib/
│   ├── arxiv_client.py          # ArXiv API wrapper
│   ├── nasa_rss_client.py       # NASA RSS feed parser
│   ├── manifest.py              # Provenance manifest read/write
│   ├── voice_profile.py         # Global voice profile loader
│   └── dedup_store.py           # Processed-paper ID registry
└── tests/
    ├── unit/
    └── integration/

data/
└── processed_papers.json        # Deduplication store (committed, append-only)

output/                          # Generated videos — gitignored
logs/                            # Structured JSON run logs — gitignored
```

**Structure Decision**: Single-project layout. Python scripts are invoked as CLI tools
by n8n Execute Command nodes; no web server or database is required. The `lib/` package
contains shared utilities. The `n8n_workflows/` directory holds the importable workflow
JSON for reproducible deployment.

## Complexity Tracking

> No constitution violations requiring justification.

---

## Phase 0: Research

*See [research.md](./research.md) for full findings and decisions.*

### Resolved Decisions

| Topic | Decision | Rationale |
|---|---|---|
| Primary paper source | ArXiv API | Structured JSON responses, stable paper IDs, CC-licensed abstracts |
| Secondary source | NASA RSS (APOD / news) | Supplements ArXiv for applied/space science topics |
| Script generation | OpenAI GPT-4o via `openai` SDK | Best instruction-following for structured script with citations |
| TTS (default) | gTTS | Zero cost, no API key, sufficient for prototype |
| TTS (premium) | OpenAI TTS (`tts-1-hd`, voice selectable) | Higher naturalness; selected by Global voice profile flag |
| Image generation | OpenAI DALL·E 3 | Permissive output licence; 1024×1024 native, upscalable |
| Video composition | MoviePy 1.0.3 | Mature, Python-native, no system GUI dependency |
| Deduplication | `data/processed_papers.json` (JSON list of IDs) | No DB dependency; append-only; trivially auditable |
| n8n invocation | Execute Command node | Supports arbitrary shell commands; stdout/stderr captured |
| Output formats | 9:16 at 1080×1920 px; 16:9 at 1920×1080 px | Platform spec for TikTok/Shorts and YouTube |
| Run logging | Structured JSON to `logs/YYYY-MM-DD_HHMMSS.json` | Machine-readable; one file per run |
