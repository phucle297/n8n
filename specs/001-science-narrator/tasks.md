---

description: "Task list for Science Narrator pipeline implementation"
---

# Tasks: Science Narrator

**Input**: Design documents from `/specs/001-science-narrator/`
**Prerequisites**: plan.md ✅, spec.md ✅, research.md ✅, data-model.md ✅, contracts/ ✅

**Organization**: Tasks are grouped by user story to enable independent implementation
and testing of each story. No tests generated (not requested in spec).

**User input additions applied**:
- Task 1 (ArXiv fetch) → T013 + T011
- Task 2 (Global TTS utility) → T010 (foundational) + T015 + T026
- Task 3 (MoviePy render with subtitle overlay + looping bg video) → T017 + T020 + T021 + T022
- Task 4 (n8n HTTP nodes for YouTube/Facebook upload) → T035 + T036 (Polish — out of spec scope but user-requested)

## Format: `[ID] [P?] [Story?] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1–US4)
- Paths assume single project layout per plan.md

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and directory layout per plan.md structure decision.

- [X] T001 Create directory structure: `python/lib/`, `python/tests/unit/`, `python/tests/integration/`, `n8n_workflows/`, `data/`, `output/`, `logs/`
- [X] T002 [P] Create `python/requirements.txt` with pinned dependencies: `moviepy==1.0.3`, `openai>=1.0`, `requests>=2.31`, `gTTS>=2.5`, `feedparser>=6.0`, `Pillow>=10.0`
- [X] T003 [P] Create `.gitignore` excluding: `output/`, `logs/`, `python/venv/`, `__pycache__/`, `*.mp4`, `*.mp3`, `*.png` (temp paths), `.env`
- [X] T004 [P] Create `data/processed_papers.json` with initial content `[]` (append-only deduplication store)
- [X] T005 [P] Create `python/lib/__init__.py` and `python/tests/__init__.py` (empty package markers)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Shared library modules that every pipeline stage depends on. All user story
work is blocked until this phase is complete.

**⚠️ CRITICAL**: No user story implementation can begin until this phase is complete.

- [X] T006 Create `python/lib/run_logger.py` — structured JSON logger: init with `run_id`, write `StageResult` dicts (`stage`, `status`, `duration_sec`, `error`), flush to `logs/<run_id>.json` on each stage completion
- [X] T007 [P] Create `python/lib/manifest.py` — `Asset` and `ProvenanceManifest` dataclasses matching data-model.md; `write_manifest(run_id, paper_id, assets, video_files) -> str` writes `output/<run_id>/assets-manifest.json`; approved licence enum: `openai-tos-commercial`, `pipeline-generated`, `cc0`, `cc-by-4.0`, `pexels-licence`, `unsplash-licence`, `pixabay-licence`
- [X] T008 [P] Create `python/lib/dedup_store.py` — `load() -> list[str]`, `is_duplicate(paper_id) -> bool`, `register(paper_id)` (appends to `data/processed_papers.json`); `register` only called after successful export
- [X] T009 [P] Create `python/lib/voice_profile.py` — load `VOICE_PROVIDER`, `VOICE_LOCALE`, `VOICE_SPEED`, `VOICE_PITCH`, `VOICE_ID` from `os.environ`; return `VoiceProfile` dict with documented defaults; emit notice to stderr when defaults are used; validate provider enum (`gtts`|`openai`) and speed range [0.5, 2.0]; detect missing `OPENAI_API_KEY` when `provider=openai` and raise `ConfigError`
- [X] T010 Create `python/lib/arxiv_client.py` — `search(topic: str, max_results: int = 5) -> list[dict]`; queries `https://export.arxiv.org/api/query` with Atom XML response; parses `entry` elements into Paper dicts; returns empty list if HTTP error or no results; includes `licence` field (default `arxiv-non-exclusive`)
- [X] T011 [P] Create `python/lib/nasa_rss_client.py` — `search(topic: str) -> list[dict]`; parses NASA RSS/APOD feed via `feedparser`; maps feed entries to Paper dict shape; returns empty list on parse failure

**Checkpoint**: All shared libraries complete — user story implementation can begin.

---

## Phase 3: User Story 1 - End-to-End Science Video Generation (Priority: P1) 🎯 MVP

**Goal**: A content creator triggers the pipeline with a topic keyword and receives two
video files (9:16 and 16:9) with narration, synced captions, and a provenance manifest,
all without manual intervention.

**Independent Test**: Run `python python/fetch_paper.py --topic "black holes"` and chain
all six stages manually. Confirm `output/<run_id>/` contains `video_vertical.mp4`,
`video_horizontal.mp4`, and `assets-manifest.json` with `all_verified: true`.

### Implementation for User Story 1

- [ ] T012 [US1] Create `python/fetch_paper.py` — CLI: `--topic TEXT`, `--source [arxiv|nasa|auto]` (default `auto`); generates `run_id` (UUID4); calls `arxiv_client.search()` then `nasa_rss_client.search()` as fallback; calls `dedup_store.is_duplicate()`; validates abstract non-empty; writes stdout JSON per cli-interface.md Stage 1 contract; exits 1 with stderr message on all error conditions
- [ ] T013 [US1] Create `python/generate_script.py` — CLI: `--paper JSON`; calls OpenAI GPT-4o with `response_format={"type":"json_object"}`; prompt enforces: learning objective sentence first, define each term on first use, cite arXiv ID per factual claim, 750–900 word narration, structured outline with `intro`/`key_concepts[]`/`conclusion`; validates `word_count` in [650, 950] and `learning_objective` non-empty and `citations` non-empty; writes stdout JSON per Stage 2 contract
- [ ] T014 [US1] Create `python/generate_voice.py` — CLI: `--script JSON`, `--run-id UUID`; loads `VoiceProfile` via `voice_profile.py`; if `provider=gtts`: calls `gTTS(text, lang=locale)`, saves to `/tmp/science_narrator/<run_id>/narration.mp3`; outputs audio `Asset` JSON per Stage 3 contract with `source=gtts`, `licence=pipeline-generated`, `verified=true`
- [ ] T015 [P] [US1] Create `python/generate_images.py` — CLI: `--script JSON`, `--run-id UUID`; iterates `script.outline.key_concepts[]`; for each concept calls `openai.images.generate(model="dall-e-3", prompt=..., size="1792x1024")`; saves PNG to `/tmp/science_narrator/<run_id>/image_NN.png`; builds `images` list of `Asset` dicts with `source=dalle3`, `licence=openai-tos-commercial`, `verified=true`, `generation_prompt` recorded; writes stdout JSON per Stage 4 contract
- [X] T016 [US1] Create `python/render_video.py` — CLI: `--script JSON`, `--audio JSON`, `--images JSON`, `--run-id UUID`, `--background-video PATH` (optional); loads narration MP3 via `AudioFileClip`; distributes images evenly across audio duration via `ImageClip` sequence; generates synced caption `TextClip` per ~10-word narration segment (timed proportionally by word count); overlays arXiv paper ID as bottom-right `TextClip` on all frames; composites into `CompositeVideoClip`; exports 16:9 (1920×1080) to `/tmp/science_narrator/<run_id>/video_horizontal.mp4`; if `--background-video` provided, loop it to audio duration and use as base layer; writes stdout JSON per Stage 5 contract (single format initially; extended to dual-format in US2)
- [ ] T017 [US1] Create `python/validate_manifest.py` — CLI: `--audio JSON`, `--images JSON`, `--videos JSON`, `--run-id UUID`; merges all assets; validates each `asset.licence` against approved enum in `manifest.py`; validates each `asset.verified == true`; calls `manifest.write_manifest()`; validates both video files exist on disk; exits 1 with per-asset stderr detail on any failure; writes stdout JSON per Stage 6 contract
- [ ] T018 [US1] Create `n8n_workflows/science_narrator.json` — n8n workflow with: Manual Trigger → Set node (topic input) → 6 Execute Command nodes (stages 1–6 chained, each reading `stdout` from previous via `$json` reference) → Move Files node (temp → `output/<run_id>/`) → Error node (catches any non-zero exit, logs to stderr); workflow uses `OPENAI_API_KEY` from n8n environment variables

**Checkpoint**: User Story 1 is fully functional. Run quickstart.md Step 7 to validate independently.

---

## Phase 4: User Story 2 - Dual Format Video Output (Priority: P2)

**Goal**: Every pipeline run produces both 9:16 (1080×1920) and 16:9 (1920×1080) video
files in a single invocation, sharing the same narration audio.

**Independent Test**: Inspect `output/<run_id>/` after any run. Both `video_vertical.mp4`
(1080×1920) and `video_horizontal.mp4` (1920×1080) must be present. Verify aspect ratios
via `ffprobe`. Both files must have identical audio duration.

### Implementation for User Story 2

- [X] T019 [US2] Extend `python/render_video.py` to export both formats in one invocation: after 16:9 export, reframe the same `CompositeVideoClip` to 9:16 (1080×1920) using center-crop + pad; export to `/tmp/science_narrator/<run_id>/video_vertical.mp4`; update stdout JSON to return both `Video` entries in `videos` array per updated Stage 5 contract
- [X] T020 [P] [US2] Implement vertical safe-zone caption repositioning in `python/render_video.py`: for 9:16 frame, reposition caption `TextClip` to stay within vertical safe zone (top 80% of frame height); reposition arXiv ID overlay to bottom-center instead of bottom-right; ensure no text is cropped by frame edges
- [ ] T021 [US2] Update `python/validate_manifest.py` to assert exactly two entries in `video_files` (one `vertical_9_16`, one `horizontal_16_9`); exit 1 with descriptive error if either format is missing
- [ ] T022 [US2] Update Stage 5 Execute Command node in `n8n_workflows/science_narrator.json` to parse both file paths from updated `render_video.py` stdout and pass both to Stage 6 `--videos` argument

**Checkpoint**: Both User Story 1 and User Story 2 are independently functional and testable.

---

## Phase 5: User Story 3 - Consistent Narrator Voice Profile (Priority: P3)

**Goal**: The Global voice profile stored as n8n environment variables is automatically
applied to every run. Changing the profile centrally takes effect on the next run without
touching any script.

**Independent Test**: Set `VOICE_PROVIDER=gtts VOICE_SPEED=0.9 VOICE_LOCALE=en-GB` in
n8n env vars. Run pipeline twice for different topics. Both output narration MP3 files
must use en-GB locale at 0.9 speed. Then change `VOICE_LOCALE=en-US`; next run must
reflect the change.

### Implementation for User Story 3

- [ ] T023 [US3] Enhance `python/lib/voice_profile.py` with full startup validation: clamp `speed` to [0.5, 2.0] with `WARNING: speed clamped` logged to stderr; detect `VOICE_PROVIDER=openai` without `OPENAI_API_KEY` and raise `ConfigError` immediately; log `NOTICE: no voice profile configured, using defaults` to stderr when all env vars absent
- [ ] T024 [US3] Add OpenAI TTS provider branch to `python/generate_voice.py`: when `VoiceProfile.provider == "openai"`, call `openai.audio.speech.create(model="tts-1-hd", voice=voice_id, input=narration_text, speed=speed)`; save response to `/tmp/science_narrator/<run_id>/narration.mp3`; output Asset JSON with `source=openai_tts`, `licence=pipeline-generated`, `verified=true`
- [ ] T025 [P] [US3] Add voice profile startup validation call to `python/fetch_paper.py` (first operation before any API call): import and call `voice_profile.load()`; if `ConfigError` raised, write error to stderr and exit 1 immediately
- [ ] T026 [US3] Add sticky-note annotations to each Execute Command node in `n8n_workflows/science_narrator.json` documenting the `VOICE_*` environment variable names, accepted values, and defaults; add a dedicated "Voice Profile Config" note node at the workflow start

**Checkpoint**: Voice profile changes take effect on next run; misconfigured profiles fail fast before any API spend.

---

## Phase 6: User Story 4 - Asset Compliance Verification (Priority: P4)

**Goal**: Every exported video is accompanied by a complete provenance manifest. Any
unverified asset blocks export. The pipeline identifies exactly which asset failed.

**Independent Test**: Manually inject an asset with `licence: "unknown-licence"` into
the images JSON payload passed to `validate_manifest.py`. Confirm it exits 1 with a
stderr message naming the `asset_id` and invalid licence value, and that no
`assets-manifest.json` is written.

### Implementation for User Story 4

- [ ] T027 [US4] Enhance `python/lib/manifest.py` to enforce approved licence enum at `Asset` construction time: raise `ValueError(f"Unknown licence: {licence}")` for any value not in the approved list; `write_manifest()` derives `all_verified` as `all(a.verified for a in assets)` and enforces it equals `True` before writing
- [ ] T028 [US4] Enhance `python/validate_manifest.py` to output per-asset validation failure details to stderr: `COMPLIANCE FAIL: asset_id=<id> type=<type> licence=<value> — not in approved list`; still exits 1; writes a partial manifest marked `all_verified: false` to `output/<run_id>/assets-manifest.json` for debugging
- [ ] T029 [P] [US4] Update `python/lib/dedup_store.py` `register()` call: move invocation to the end of `python/validate_manifest.py` (called only when `all_verified == True` and both video files confirmed on disk); ensures failed runs do not consume a paper ID
- [ ] T030 [US4] Create `python/lib/cleanup.py` — CLI: `--run-id UUID`; removes `/tmp/science_narrator/<run_id>/` and all contents; used by the n8n error node
- [ ] T031 [US4] Add error node Execute Command to `n8n_workflows/science_narrator.json`: on any stage failure, run `python python/lib/cleanup.py --run-id {{run_id}}`; log failure stage and error to `logs/<run_id>.json` via `run_logger.py`

**Checkpoint**: All four user stories are independently functional. Full pipeline from trigger to compliant dual-format export is verified.

---

## Phase N: Polish & Extensions

**Purpose**: Platform upload integration (user-requested extension beyond spec scope),
temp-to-output file move, and end-to-end validation.

- [ ] T032 [P] Add YouTube Data API v3 upload node to `n8n_workflows/science_narrator.json`: HTTP Request node after successful export; `POST https://www.googleapis.com/upload/youtube/v3/videos?uploadType=multipart`; uses YouTube OAuth2 credential; sends 16:9 video file with title from script learning objective and description including arXiv paper ID
- [ ] T033 [P] Add Facebook Graph API video upload node to `n8n_workflows/science_narrator.json`: HTTP Request node running in parallel with T032; `POST https://graph.facebook.com/v18.0/me/videos`; uses Facebook OAuth2 credential; sends vertical 9:16 video with title and description
- [ ] T034 Add output directory move Execute Command node to `n8n_workflows/science_narrator.json`: runs after `validate_manifest.py` succeeds; `mv /tmp/science_narrator/<run_id>/ output/<run_id>/`; runs before T032/T033 upload nodes
- [ ] T035 [P] Final `.gitignore` review: confirm `output/`, `logs/`, `python/venv/`, `**/__pycache__/`, `.env`, `*.mp4`, `*.mp3`, `*.png` (only temp paths) are all excluded; add `n8n_workflows/*.json` to tracked files (explicitly un-ignore)
- [ ] T036 Run quickstart.md end-to-end validation: activate Python venv, start n8n via Docker, import workflow JSON, execute with topic `"gravitational waves"`, confirm `output/<run_id>/` contains `video_vertical.mp4` (1080×1920), `video_horizontal.mp4` (1920×1080), `assets-manifest.json` with `all_verified: true`; verify run completes under 15 minutes

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately
- **Foundational (Phase 2)**: Depends on Phase 1 completion — BLOCKS all user stories
- **User Story 1 (Phase 3)**: Depends on Foundational completion
- **User Story 2 (Phase 4)**: Depends on US1 completion (extends `render_video.py` and `validate_manifest.py`)
- **User Story 3 (Phase 5)**: Depends on Foundational + US1 `generate_voice.py` existing
- **User Story 4 (Phase 6)**: Depends on US1 completion (extends `manifest.py` and `validate_manifest.py`)
- **Polish (Phase N)**: Depends on all user stories complete

### User Story Dependencies

- **US1 (P1)**: No inter-story dependencies — start after Foundational
- **US2 (P2)**: Depends on US1 `render_video.py` and `validate_manifest.py` existing
- **US3 (P3)**: Depends on Foundational `voice_profile.py` + US1 `generate_voice.py` existing; independent of US2
- **US4 (P4)**: Depends on US1 `manifest.py`, `validate_manifest.py`, `dedup_store.py` existing; independent of US2/US3

### Within Each User Story

- Models/libs (Foundational) before entry-point scripts
- `fetch_paper.py` before `generate_script.py` before `generate_voice.py`/`generate_images.py` (stages must execute in order)
- `generate_voice.py` and `generate_images.py` can run in parallel [P] within US1
- `render_video.py` requires both audio and images complete
- `validate_manifest.py` requires `render_video.py` complete
- n8n workflow JSON assembled after all script contracts are finalized

### Parallel Opportunities

```bash
# Phase 2 — Foundational libs (all independent files):
T007 python/lib/manifest.py
T008 python/lib/dedup_store.py
T009 python/lib/voice_profile.py
T011 python/lib/nasa_rss_client.py

# Phase 3 US1 — after T013 generate_script.py is done:
T015 python/generate_images.py   # DALL-E 3 calls
T014 python/generate_voice.py    # TTS call
# Both can run simultaneously; render_video.py waits for both

# Phase N — after all stories complete:
T032 YouTube upload node
T033 Facebook upload node
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational — BLOCKS everything
3. Complete Phase 3: User Story 1 (T012–T018)
4. **STOP and VALIDATE**: Run quickstart.md Step 7 manually (topic: "gravitational waves")
5. Confirm two MP4 files + manifest produced under 15 minutes

### Incremental Delivery

1. Setup + Foundational → shared lib ready
2. US1 → end-to-end pipeline working (16:9 only initially acceptable for MVP)
3. US2 → dual format confirmed, both platforms covered
4. US3 → voice branding locked in
5. US4 → compliance gate hardened for production
6. Polish → upload automation live

---

## Notes

- `[P]` tasks operate on different files with no blocking dependencies — safe to parallelize
- `[Story]` labels enable each phase to be implemented and tested independently
- `render_video.py` is the most complex task; implement 16:9 first (T016), validate, then add 9:16 (T019)
- YouTube/Facebook upload nodes (T032, T033) require manual OAuth credential setup in n8n UI — document this in quickstart.md before closing
- `data/processed_papers.json` is committed to the repo; never delete entries from it
- Avoid running `generate_images.py` and `generate_voice.py` in separate pipeline re-runs — both must complete in the same run for the manifest to be consistent
