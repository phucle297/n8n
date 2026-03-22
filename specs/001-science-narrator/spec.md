# Feature Specification: Science Narrator

**Feature Branch**: `001-science-narrator`
**Created**: 2026-03-22
**Status**: Draft
**Input**: User description: "Create a functional specification for the Science Narrator
app. Source: ArXiv API or NASA RSS feeds for physics/science papers. Logic: Python script
to summarize papers into a 5-minute engaging script. Voice: Use a consistent Global voice
profile stored in n8n variables. Output: Vertical video (9:16) for TikTok/Shorts and
Horizontal (16:9) for YouTube."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - End-to-End Science Video Generation (Priority: P1)

A content creator triggers the Science Narrator pipeline for a physics or science topic.
The system automatically discovers a recent, relevant paper from a vetted academic source,
summarises it into an engaging narrator script (targeting approximately 5 minutes of
spoken content), assembles a complete video with narration and visuals, and delivers
ready-to-publish output in both vertical and horizontal formats — with no manual editing
required.

**Why this priority**: This is the entire value proposition of the app. Without a working
end-to-end pipeline, no other story can be demonstrated or tested independently.

**Independent Test**: Trigger the pipeline with a topic keyword (e.g., "black holes").
Verify that two video files are produced (9:16 and 16:9), the narration runs approximately
4–6 minutes, and the output folder contains a provenance manifest listing every asset used.

**Acceptance Scenarios**:

1. **Given** a topic keyword is provided and a matching recent paper is available,
   **When** the pipeline runs to completion,
   **Then** two video files are produced (one 9:16, one 16:9), each containing synced
   narration, visuals, and captions, with total narration duration between 4 and 6 minutes.

2. **Given** the pipeline has completed successfully,
   **When** the output folder is inspected,
   **Then** an asset provenance manifest is present listing every visual and audio asset,
   its licence type, and its source.

3. **Given** no matching paper is found for the requested topic,
   **When** the pipeline runs,
   **Then** the pipeline halts with a clear error message and produces no partial output.

---

### User Story 2 - Dual Format Video Output (Priority: P2)

A content creator needs the same science narrative delivered in two aspect ratios in a
single pipeline run — vertical (9:16) for TikTok and YouTube Shorts, and horizontal
(16:9) for standard YouTube uploads — so they can publish to both platforms without
re-running the pipeline or re-editing.

**Why this priority**: The dual-format requirement is a hard distribution constraint.
A single-format output forces the creator to run the pipeline twice or manually reformat,
doubling cost and effort.

**Independent Test**: Run the pipeline for any topic. Confirm the output directory
contains exactly two video files with correct aspect ratios (verifiable via metadata
inspection), both with identical narration audio and equivalent visual content adapted
to each frame.

**Acceptance Scenarios**:

1. **Given** a pipeline run completes successfully,
   **When** the output files are inspected,
   **Then** one file has a 9:16 aspect ratio and one has a 16:9 aspect ratio, and both
   share the same narration audio track.

2. **Given** a 9:16 video,
   **When** visual layout is reviewed,
   **Then** all text, captions, and key visuals are fully visible without cropping within
   the vertical frame.

3. **Given** a 16:9 video,
   **When** visual layout is reviewed,
   **Then** all text, captions, and key visuals are fully visible without letterboxing
   or pillarboxing within the horizontal frame.

---

### User Story 3 - Consistent Narrator Voice Profile (Priority: P3)

A content creator configures a "Global" narrator voice profile — defining accent, speed,
pitch, and other vocal characteristics — and stores it centrally so that every video
produced by the pipeline automatically uses that same voice without requiring per-run
configuration.

**Why this priority**: Voice consistency is the brand identity of the channel. Inconsistent
narration across videos undermines audience recognition and trust. This story can be
independently verified once audio generation works, without needing dual-format output.

**Independent Test**: Configure the Global voice profile. Run the pipeline twice for
different topics. Confirm both output videos use the same audible vocal characteristics
(accent, speed, style) and that the profile can be changed centrally and takes effect on
the next run without touching individual pipeline configurations.

**Acceptance Scenarios**:

1. **Given** a Global voice profile is configured and saved centrally,
   **When** the pipeline runs,
   **Then** the narration audio uses the voice characteristics defined in that profile
   without any additional per-run voice setting.

2. **Given** the Global voice profile is updated (e.g., speed changed),
   **When** the next pipeline run completes,
   **Then** the narration reflects the new settings, and no previous run's output is altered.

3. **Given** no Global voice profile has been configured,
   **When** the pipeline runs,
   **Then** the pipeline uses a documented default voice configuration and logs a notice
   that no custom profile was found.

---

### User Story 4 - Asset Compliance Verification (Priority: P4)

Before a video is published, a content creator (or an automated gate) can verify that
every asset used in the video is copyright-compliant — either AI-generated, royalty-free,
or public domain — by reviewing the provenance manifest produced alongside the video.

**Why this priority**: Without auditability, the creator cannot confidently publish.
This story depends on Story 1 producing a manifest, making it a lower-priority extension
of the core flow.

**Independent Test**: Produce a video via Story 1. Open the provenance manifest and verify
it lists every asset (images, audio, background) with a licence category. Confirm that any
asset without a verified licence causes the pipeline to halt before export.

**Acceptance Scenarios**:

1. **Given** a completed pipeline run,
   **When** the provenance manifest is opened,
   **Then** every visual and audio asset is listed with: source identifier, licence type,
   and retrieval or generation date.

2. **Given** an asset whose licence cannot be verified during a pipeline run,
   **When** the validation gate runs,
   **Then** the pipeline halts before producing any output file, and the error identifies
   the specific unverified asset.

3. **Given** all assets are verified as compliant,
   **When** the validation gate runs,
   **Then** the pipeline proceeds to export and the manifest is marked as fully verified.

---

### Edge Cases

- What happens when the discovered paper is behind a paywall or returns no accessible
  abstract? The pipeline must detect this and attempt an alternative source or halt
  gracefully with a clear message.
- What happens when the generated script exceeds 6 minutes or falls below 3 minutes of
  narration? The pipeline must flag the duration anomaly and halt for creator review.
- What happens when the Global voice profile references a voice configuration that is no
  longer available? The pipeline must detect this at startup and halt with a clear
  configuration error before incurring any generation costs.
- What happens when one format (e.g., 9:16) renders successfully but the other fails
  mid-composition? No partial output should be exported; both files must succeed or
  neither is produced.
- What happens when the same paper is discovered on two consecutive runs? The pipeline
  must detect the duplicate via paper ID and skip or notify the creator rather than
  producing an identical video.
- What happens when the academic source is unreachable (network error or rate limit)?
  The pipeline must halt with a descriptive error and not attempt to generate content
  from an empty or incomplete source response.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST automatically discover a recent, relevant science or physics
  paper from a vetted academic publication source based on a topic keyword or category
  input.
- **FR-002**: The system MUST transform the discovered paper's content into a narration
  script targeting a spoken duration of 4–6 minutes.
- **FR-003**: The narration script MUST open with a clearly stated learning objective
  that is communicated within the first 30 seconds of the resulting video.
- **FR-004**: Technical terms introduced in the narration MUST be defined on first use,
  either in spoken narration or as on-screen text overlays.
- **FR-005**: The system MUST generate narration audio using the centrally stored Global
  voice profile for every pipeline run.
- **FR-006**: The system MUST allow the Global voice profile to be configured and stored
  centrally; all subsequent runs MUST inherit those settings automatically without
  per-run configuration.
- **FR-007**: The system MUST produce a 9:16 (vertical) video suitable for TikTok and
  YouTube Shorts as part of every successful pipeline run.
- **FR-008**: The system MUST produce a 16:9 (horizontal) video suitable for standard
  YouTube uploads as part of every successful pipeline run.
- **FR-009**: Both format outputs MUST share the same narration audio track and equivalent
  visual content, each laid out appropriately for its respective frame dimensions.
- **FR-010**: The system MUST include synced captions in both output videos.
- **FR-011**: The system MUST produce a machine-readable provenance manifest alongside
  every video, listing each asset's source identifier, licence type, and retrieval or
  generation date.
- **FR-012**: The system MUST halt and produce no output files if any asset's licence
  cannot be verified as compliant prior to video export.
- **FR-013**: The system MUST embed or display the source paper's identifier within the
  video (on-screen citation or embedded metadata) so every factual claim can be traced
  to its origin.
- **FR-014**: The system MUST detect papers already processed in prior runs (via paper ID)
  and skip re-processing, notifying the creator instead of producing a duplicate video.
- **FR-015**: The system MUST emit a structured run log for every pipeline execution
  capturing the outcome and duration of each processing stage.
- **FR-016**: The system MUST halt with a descriptive error at any stage failure and
  produce no partial output files.

### Key Entities

- **Paper**: A peer-reviewed scientific article discovered from an academic source.
  Attributes: unique identifier, title, authors, publication date, abstract, full-text
  availability, source licence.
- **Script**: A narration document derived from a Paper. Attributes: learning objective,
  structured outline (intro → key concepts → conclusion), narration text, estimated
  spoken duration, citation references.
- **Voice Profile**: A centrally stored configuration defining narrator voice
  characteristics (locale/accent, speed, pitch, style). One active "Global" profile
  is in effect at any time.
- **Asset**: Any visual (image, diagram, background) or audio (SFX, music) element
  incorporated into a video. Attributes: asset ID, type, source URL or generation prompt,
  licence category, retrieval or generation date, verification status.
- **Provenance Manifest**: A structured record produced per pipeline run listing all
  Assets used and their compliance status.
- **Video**: A final composed output file. Attributes: aspect ratio (9:16 or 16:9),
  duration, narration audio, captions, source paper identifier, export timestamp.
- **Pipeline Run**: A single end-to-end execution instance. Attributes: topic trigger,
  paper discovered, run status, per-stage outcomes, output file paths, manifest path.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A complete pipeline run — from topic trigger to two exported video files —
  completes without manual intervention in under 15 minutes.
- **SC-002**: 100% of exported videos include a fully populated provenance manifest;
  no video is exported without one.
- **SC-003**: 100% of exported videos contain narration within the 4–6 minute target
  duration window.
- **SC-004**: Both format outputs (9:16 and 16:9) are produced in every successful run;
  a partial-format export is treated as a pipeline failure.
- **SC-005**: 100% of pipeline runs use the centrally configured Global voice profile;
  no run silently falls back to an undocumented default without logging a notice.
- **SC-006**: When a paper cannot be sourced or an asset licence cannot be verified,
  the pipeline halts with a descriptive error in 100% of such cases — no silent partial
  outputs.
- **SC-007**: Duplicate paper detection prevents re-processing of any previously produced
  paper in 100% of detected cases, with a creator notification each time.
- **SC-008**: A content creator with no prior configuration can trigger the pipeline and
  receive two compliant, ready-to-publish videos on their first run using documented
  default settings.

## Assumptions

- A topic keyword or category is sufficient to identify a relevant paper; selection of
  a specific paper by URL or DOI is out of scope for this feature.
- "Ready to publish" means files are exported locally; upload to TikTok, YouTube, or
  any distribution platform is out of scope.
- The Global voice profile is a single shared profile; per-video voice overrides are
  out of scope.
- Background music is optional and not required for the initial implementation; the
  pipeline must support narration-only audio as a valid complete output.
- Captions are auto-generated from the narration script; manual caption editing is
  out of scope.
- Videos are in standard web-compatible container formats (e.g., MP4); codec selection
  is an implementation detail.
