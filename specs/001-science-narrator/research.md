# Research: Science Narrator

**Branch**: `001-science-narrator`
**Date**: 2026-03-22
**Status**: Complete — all NEEDS CLARIFICATION resolved

---

## 1. Paper Sourcing

### Decision: ArXiv API (primary) + NASA RSS (secondary)

**Rationale**:
- ArXiv provides a clean REST API (`https://export.arxiv.org/api/query`) returning
  Atom XML. Each entry has a stable `id` (arXiv ID), title, authors, abstract, and
  a declared licence (most are CC BY 4.0 or arXiv non-exclusive licence permitting
  quotation of abstracts).
- NASA RSS feeds (e.g., APOD, NASA Breaking News) supplement ArXiv for applied/space
  science topics that may not have a preprint. Parsed with `feedparser`.
- Both sources return content usable under their stated licences; neither requires
  payment or authentication for read access.

**Alternatives considered**:
- PubMed Central: Biomedical focus; out of scope for physics/space science.
- Semantic Scholar API: Good but adds an extra dependency; ArXiv covers the target
  domain adequately.
- Direct web scraping: Avoided — fragile, potentially violates ToS.

**Failure mode**: If ArXiv returns HTTP 4xx/5xx or an empty result set for a query,
`fetch_paper.py` exits with code 1 and a JSON error payload; n8n error node halts
the workflow.

---

## 2. Script Generation

### Decision: OpenAI GPT-4o via `openai` Python SDK

**Rationale**:
- GPT-4o has the best instruction-following for structured generation tasks (JSON mode
  available), enabling reliable output of the required outline schema.
- The prompt instructs the model to:
  1. Open with a learning objective sentence.
  2. Define every technical term on first use.
  3. Cite the arXiv ID for every factual claim.
  4. Stay within a 750–900 word count (≈ 4–6 minutes at 150 wpm average TTS speed).
  5. Close with a 2-sentence summary.
- JSON mode (`response_format={"type": "json_object"}`) ensures the outline and
  narration text are returned in a parseable structure.

**Alternatives considered**:
- Local LLM (Ollama + Mistral): Lower quality instruction-following; risk of hallucination
  increases without strong RLHF; rejected for accuracy principle compliance.
- Claude API: Compatible alternative; swappable if OpenAI key unavailable.

**Word count → duration mapping**:
- Target: 750–900 words → 4.5–6 min at 150 wpm (conservative TTS pace).
- Pipeline enforces: if `len(script.split()) < 650` → flag too short; if `> 950` →
  flag too long; halt for review.

---

## 3. Text-to-Speech

### Decision: gTTS (default) / OpenAI TTS (premium, selected via voice profile)

**Rationale**:
- **gTTS**: Free, no API key, wraps Google Translate TTS. Produces MP3. Suitable for
  prototyping and cost-free operation. Voice characteristics are fixed per locale.
- **OpenAI TTS** (`tts-1-hd`): Higher naturalness, selectable voice (`alloy`, `echo`,
  `fable`, `onyx`, `nova`, `shimmer`). Billed per character. Selected when the Global
  voice profile sets `provider: openai`.
- The Global voice profile determines which provider is active; the pipeline reads this
  at startup from n8n environment variables.

**Failure mode**: If TTS API call fails (network error, quota exceeded), `generate_voice.py`
exits non-zero; no audio file is produced; workflow halts.

**Audio spec**: MP3, 44.1 kHz equivalent (gTTS default); OpenAI TTS produces MP3 at
24 kHz natively (upsampled to 44.1 kHz by MoviePy during composition).

---

## 4. Image Generation

### Decision: OpenAI DALL·E 3

**Rationale**:
- DALL·E 3 output is licensed for commercial use under OpenAI's Terms of Service
  (as of 2024); generated images are owned by the user and are fully copyright-compliant
  for the pipeline's purposes.
- Native resolution: 1024×1024, 1024×1792 (portrait), 1792×1024 (landscape) — both
  formats needed. Pillow is used to pad/crop to exact output dimensions.
- `generate_images.py` requests one image per key concept in the script outline
  (typically 4–6 images per video).

**Alternatives considered**:
- Stable Diffusion (self-hosted): Requires GPU; adds infrastructure complexity; licence
  of model outputs varies by checkpoint — rejected for compliance simplicity.
- Unsplash API (royalty-free stock): No AI generation cost, but subject to availability
  per topic — used as fallback only when DALL·E quota is exhausted.

**Manifest entry**: Each image logged with `{"type": "image", "source": "dalle3",
"prompt": "<prompt>", "licence": "openai-tos-commercial", "generated_at": "<ISO timestamp>"}`.

---

## 5. Video Composition

### Decision: MoviePy 1.0.3 (Python)

**Rationale**:
- Pure Python, no system GUI required. Works headlessly on a Linux server.
- Supports image sequences, audio tracks, text overlays, and clip concatenation.
- Outputs MP4 (H.264 via `ffmpeg` backend, which MoviePy bundles or uses from system).
- `render_video.py` produces both formats in one invocation:
  1. Load narration audio → derive total duration.
  2. Distribute images evenly across duration (each displayed for `total_dur / n_images` seconds).
  3. Overlay captions (timed to narration text segments).
  4. Compose 16:9 clip → export.
  5. Reframe same content to 9:16 (crop + pad) → export.

**Caption strategy**: Script text is split into ~10-word segments; each segment is timed
proportionally to its word count relative to total word count × total audio duration.
MoviePy `TextClip` renders each segment. Requires `ImageMagick` on the server.

**ffmpeg dependency**: Must be installed system-wide (`apt install ffmpeg`). MoviePy
detects it automatically.

---

## 6. n8n Orchestration

### Decision: Execute Command node for all Python stages

**Rationale**:
- n8n's Execute Command node runs arbitrary shell commands and captures stdout/stderr.
- Each Python script writes its output as a JSON payload to stdout; n8n parses this
  with a subsequent Set or Code node and passes fields to the next stage.
- Environment variables (API keys, voice profile settings) are injected via n8n's
  environment variable store — no secrets in workflow JSON.

**n8n workflow topology**:
```
[Manual/Schedule Trigger]
       ↓
[Set: topic keyword]
       ↓
[Execute Command: python fetch_paper.py --topic "{{topic}}"]
       ↓
[Execute Command: python generate_script.py --paper "{{paper_json}}"]
       ↓
[Execute Command: python generate_voice.py --script "{{script_json}}"]
       ↓
[Execute Command: python generate_images.py --outline "{{outline_json}}"]
       ↓
[Execute Command: python render_video.py --assets "{{assets_json}}"]
       ↓
[Execute Command: python validate_manifest.py --run-id "{{run_id}}"]
       ↓
[Move files to output/; log success]
  ↗ Error node (any stage) → log failure, clean temp dir
```

**Voice profile injection**: n8n stores voice profile fields as environment variables
(`VOICE_PROVIDER`, `VOICE_LOCALE`, `VOICE_SPEED`, `VOICE_PITCH`, `VOICE_ID`). Each
Python script reads these via `os.environ` through `lib/voice_profile.py`.

---

## 7. Deduplication

### Decision: `data/processed_papers.json` — append-only JSON list

**Rationale**:
- Simplest possible implementation; no database dependency.
- Format: `["arxiv:2401.00001", "arxiv:2312.09876", ...]`
- `dedup_store.py` reads the file on startup, checks the candidate paper ID, adds it
  on successful export.
- File is committed to the repository for auditability; it is the canonical record of
  all papers ever processed.

**Concurrency**: Single-threaded pipeline; no locking needed.

---

## 8. Environment Setup

### Python Virtual Environment

```bash
cd python/
python3.11 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

**requirements.txt**:
```
moviepy==1.0.3
openai>=1.0
requests>=2.31
gTTS>=2.5
feedparser>=6.0
Pillow>=10.0
pytest>=8.0
```

**System dependencies** (Ubuntu 22.04+):
```bash
apt install -y ffmpeg imagemagick python3.11 python3.11-venv
```

### n8n Setup

- Self-hosted n8n (Docker recommended):
  ```bash
  docker run -d --name n8n -p 5678:5678 \
    -v ~/.n8n:/home/node/.n8n \
    -e EXECUTIONS_PROCESS=main \
    n8nio/n8n
  ```
- Execute Command node requires `N8N_RUNNERS_ENABLED=true` (n8n ≥ 1.0) or the
  default `executions.process=main` setting in older versions.
- Import `n8n_workflows/science_narrator.json` via n8n UI → Workflows → Import.

---

## 9. Output Specifications

| Format | Dimensions | Aspect Ratio | Platform |
|---|---|---|---|
| Vertical | 1080 × 1920 px | 9:16 | TikTok, YouTube Shorts |
| Horizontal | 1920 × 1080 px | 16:9 | YouTube standard |
| Codec | H.264 (libx264) | — | Both |
| Audio | AAC, 44.1 kHz, stereo | — | Both |
| Frame rate | 24 fps | — | Both |
| Container | MP4 | — | Both |
