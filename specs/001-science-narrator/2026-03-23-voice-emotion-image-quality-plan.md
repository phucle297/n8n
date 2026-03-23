# Expressive Voice & Content-Aware Images — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace robotic gTTS default with expressive edge-tts, and make image prompts content-specific by having the AI generate a cinematic `visual_description` per concept during script generation.

**Architecture:** Two independent changes — (1) new `edge-tts` voice provider wired into the existing provider switch in `generate_voice.py`, defaulting in `voice_profile.py`; (2) `visual_description` field added to the AI prompt in `generate_script.py` Stage 2, consumed in `generate_images.py` Stage 4 as the image prompt with the old template as fallback.

**Tech Stack:** Python 3.11+, `edge-tts>=6.1` (Microsoft Neural TTS, free), pytest, unittest.mock

---

## File Map

| File | Action | What changes |
|------|--------|-------------|
| `python/requirements.txt` | Modify | Add `edge-tts>=6.1` |
| `python/lib/voice_profile.py` | Modify | Add `"edge-tts"` to `_VALID_PROVIDERS`; change default from `"gtts"` to `"edge-tts"`; update module docstring; add SPEED/PITCH warning in `load()` |
| `python/generate_voice.py` | Modify | Add `_run()` async helper and `_synthesise_edge_tts()`; wire `elif provider == "edge-tts":` branch in `main()`; update module docstring |
| `python/tests/unit/test_generate_images.py` | Create | Unit tests for primary path (visual_description used) and fallback path (old template used) |
| `python/generate_images.py` | Modify | Use `concept.get("visual_description")` as primary prompt; fallback to `_PROMPT_TEMPLATE`; fix `_LICENCE_MAP` bugs |
| `python/generate_script.py` | Modify | Add `visual_description` to Requirements bullet list AND JSON example block in `_USER_PROMPT_TEMPLATE`; add warning loop after `json.loads()` |

---

## Task 1: Add edge-tts dependency

**Files:**
- Modify: `python/requirements.txt`

- [ ] **Step 1: Add the package pin**

Open `python/requirements.txt` and add after the `gTTS>=2.5` line:

```
edge-tts>=6.1
```

- [ ] **Step 2: Verify it installs**

```bash
pip install edge-tts>=6.1
python -c "import edge_tts; print(edge_tts.__version__)"
```

Expected: version string `6.x.x` printed, no errors.

- [ ] **Step 3: Commit**

```bash
git add python/requirements.txt
git commit -m "chore: add edge-tts>=6.1 dependency"
```

---

## Task 2: Update voice_profile.py — register edge-tts provider

**Files:**
- Modify: `python/lib/voice_profile.py`

Current state of the file for reference:
- Line 8: module docstring says `provider=gtts, ...`
- Line 28: `_VALID_PROVIDERS = {"gtts", "openai"}`
- Lines 32–38: `_DEFAULTS` dict with `"provider": "gtts"`
- Lines 64–76: provider validation block in `load()`

- [ ] **Step 1: Update module docstring (line 8)**

Change:
```python
    provider=gtts, locale=en-US, speed=1.0, pitch=default, voice_id=""
```
To:
```python
    provider=edge-tts, locale=en-US, speed=1.0, pitch=default, voice_id=""
```

- [ ] **Step 2: Add "edge-tts" to `_VALID_PROVIDERS` (line 28)**

Change:
```python
_VALID_PROVIDERS = {"gtts", "openai"}
```
To:
```python
_VALID_PROVIDERS = {"gtts", "openai", "edge-tts"}
```

**Important:** This must be done BEFORE changing `_DEFAULTS["provider"]`. If the default is changed first and a user has any env var set (e.g. `VOICE_LOCALE=en-GB`) without setting `VOICE_PROVIDER`, the code will hit the `_VALID_PROVIDERS` guard and raise `ConfigError` before this fix is in place.

- [ ] **Step 3: Change the default provider in `_DEFAULTS` (line 34)**

Change:
```python
    "provider": "gtts",
```
To:
```python
    "provider": "edge-tts",
```

- [ ] **Step 4: Add SPEED/PITCH warning in `load()` after the provider guard**

After the existing block (around line 70–76):
```python
    if provider not in _VALID_PROVIDERS:
        raise ConfigError(...)
```

Add immediately after:
```python
    if provider == "edge-tts" and (raw_speed or raw_pitch):
        print(
            "WARNING: VOICE_SPEED and VOICE_PITCH are ignored by edge-tts provider.",
            file=sys.stderr,
        )
```

- [ ] **Step 5: Verify no regressions with a quick sanity check**

```bash
cd /path/to/project
python -c "
import os
os.environ.pop('VOICE_PROVIDER', None)
os.environ.pop('VOICE_LOCALE', None)
os.environ.pop('VOICE_SPEED', None)
os.environ.pop('VOICE_PITCH', None)
os.environ.pop('VOICE_ID', None)
from python.lib.voice_profile import load
p = load()
assert p['provider'] == 'edge-tts', p
print('OK — default is edge-tts:', p)
"
```

Expected: prints `OK — default is edge-tts: {'provider': 'edge-tts', ...}`

- [ ] **Step 6: Commit**

```bash
git add python/lib/voice_profile.py
git commit -m "feat: add edge-tts as default voice provider in voice_profile"
```

---

## Task 3: Add edge-tts synthesis to generate_voice.py

**Files:**
- Modify: `python/generate_voice.py`

Current structure for reference:
- Lines 1–21: module docstring
- Lines 51–61: `_synthesise_gtts()`
- Lines 64–89: `_synthesise_openai()`
- Lines 129–148: synthesis dispatch block in `main()`

- [ ] **Step 1: Update the module docstring**

In the `Environment:` section (around line 13), change:
```
    VOICE_PROVIDER   gtts | openai  (default: gtts)
```
To:
```
    VOICE_PROVIDER   gtts | openai | edge-tts  (default: edge-tts)
                     Note: VOICE_SPEED and VOICE_PITCH are ignored by edge-tts
```

- [ ] **Step 2: Add the async helper and `_synthesise_edge_tts()` function**

Add after `_synthesise_gtts()` and before `_synthesise_openai()` (around line 63):

```python
async def _run_edge_tts(text: str, voice: str, path: str) -> None:
    try:
        import edge_tts  # type: ignore
    except ImportError:
        raise RuntimeError("edge-tts not installed. Run: pip install edge-tts>=6.1")
    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(path)


def _synthesise_edge_tts(narration_text: str, voice_id: str, out_path: str) -> None:
    """Generate audio with edge-tts (Microsoft Neural TTS) and save to out_path."""
    import asyncio
    effective_voice = voice_id if voice_id else "en-US-AriaNeural"
    # asyncio.run() is safe here: generate_voice.py is invoked as a CLI subprocess,
    # never from within an already-running event loop.
    asyncio.run(_run_edge_tts(narration_text, effective_voice, out_path))
```

- [ ] **Step 3: Wire the new branch into `main()`**

In the synthesis dispatch block, the current structure is:
```python
        if provider == "gtts":
            _synthesise_gtts(narration_text, locale, out_path)
            source = "gtts"
            licence = "pipeline-generated"
        elif provider == "openai":
            ...
        else:
            print(f"ERROR: Unknown VOICE_PROVIDER='{provider}'.", file=sys.stderr)
            sys.exit(1)
```

Add the new branch between `gtts` and `openai`:
```python
        if provider == "gtts":
            _synthesise_gtts(narration_text, locale, out_path)
            source = "gtts"
            licence = "pipeline-generated"
        elif provider == "edge-tts":
            _synthesise_edge_tts(narration_text, voice_id, out_path)
            source = "edge-tts"
            licence = "microsoft-edge-tts-tos"
        elif provider == "openai":
            ...
```

- [ ] **Step 4: Smoke-test the new provider**

```bash
python python/generate_voice.py \
  --script '{"script":{"narration_text":"Hello, this is a test of the edge TTS provider."},"run_id":"test-123"}' \
  --run-id test-123
```

Set `VOICE_PROVIDER=edge-tts` (or rely on the new default). Expected: JSON printed to stdout with an `audio.file_path` pointing to a non-empty `.mp3` file. Play it to verify it sounds natural and expressive.

- [ ] **Step 5: Verify gtts and openai branches still work (no regression)**

```bash
VOICE_PROVIDER=gtts python python/generate_voice.py \
  --script '{"script":{"narration_text":"Testing gtts fallback."},"run_id":"gtts-test"}' \
  --run-id gtts-test
```

Expected: exits 0, produces audio file.

- [ ] **Step 6: Commit**

```bash
git add python/generate_voice.py
git commit -m "feat: add edge-tts voice synthesis provider"
```

---

## Task 4: Write unit tests for generate_images.py prompt selection (TDD)

**Files:**
- Create: `python/tests/unit/test_generate_images.py`

Write tests BEFORE modifying `generate_images.py`. They must fail now and pass after Task 5.

- [ ] **Step 1: Read the current generate_images.py loop to understand the interface**

The relevant section (lines 101–134) iterates `key_concepts`, calls `ai.generate_image(prompt, img_path)`, and stores `prompt` as `generation_prompt` in the result. The `ai` object is an `AIProvider` instance.

- [ ] **Step 2: Create the test file**

```python
# python/tests/unit/test_generate_images.py
"""
Unit tests for generate_images.py prompt selection logic.

Tests verify:
  - primary path: visual_description is used directly as the image prompt
  - fallback path: _PROMPT_TEMPLATE is used when visual_description is absent/empty
"""
from unittest.mock import MagicMock, patch
import json
import os
import sys
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../.."))

from python.generate_images import _PROMPT_TEMPLATE, main


def _make_script(concepts: list[dict]) -> str:
    """Build a minimal --script JSON string for generate_images.main()."""
    return json.dumps({
        "run_id": "test-run-001",
        "script": {
            "outline": {
                "key_concepts": concepts
            }
        }
    })


def _run_main(script_json: str, run_id: str = "test-run-001", ai_mock=None):
    """Invoke generate_images.main() with mocked AI and capture the prompt passed to generate_image."""
    captured_prompts = []

    def fake_generate_image(prompt, out_path):
        captured_prompts.append(prompt)
        # Write a dummy file so the existence check passes
        with open(out_path, "wb") as f:
            f.write(b"FAKE")

    mock_provider = MagicMock()
    mock_provider.generate_image.side_effect = fake_generate_image

    with patch("sys.argv", ["generate_images.py", "--script", script_json, "--run-id", run_id]), \
         patch("python.generate_images.get_provider", return_value=mock_provider), \
         patch("python.generate_images.load", return_value={"provider": "openai", "api_key": "test"}), \
         patch("sys.stdout"):
        try:
            main()
        except SystemExit as e:
            if e.code != 0:
                raise

    return captured_prompts


def test_primary_path_uses_visual_description():
    """When visual_description is present, it is passed directly to generate_image."""
    visual_desc = "A glowing double helix rotating in a dark void, photorealistic, 16:9."
    concept = {
        "term": "DNA",
        "definition": "The molecule that carries genetic information.",
        "visual_description": visual_desc,
    }
    prompts = _run_main(_make_script([concept]))
    assert len(prompts) == 1
    assert prompts[0] == visual_desc


def test_fallback_path_uses_prompt_template():
    """When visual_description is absent, _PROMPT_TEMPLATE.format(...) is used."""
    concept = {
        "term": "Entropy",
        "definition": "A measure of disorder in a system.",
        # no visual_description key
    }
    prompts = _run_main(_make_script([concept]))
    assert len(prompts) == 1
    expected = _PROMPT_TEMPLATE.format(
        concept=concept["term"],
        definition=concept["definition"],
    )
    assert prompts[0] == expected


def test_fallback_path_for_empty_visual_description():
    """When visual_description is an empty string, _PROMPT_TEMPLATE is used."""
    concept = {
        "term": "Quasar",
        "definition": "An extremely luminous active galactic nucleus.",
        "visual_description": "",
    }
    prompts = _run_main(_make_script([concept]))
    assert len(prompts) == 1
    expected = _PROMPT_TEMPLATE.format(
        concept=concept["term"],
        definition=concept["definition"],
    )
    assert prompts[0] == expected
```

- [ ] **Step 3: Run tests and confirm they FAIL**

```bash
cd /path/to/project
pytest python/tests/unit/test_generate_images.py -v
```

Expected: all 3 tests FAIL because `generate_images.py` doesn't yet use `visual_description`.

- [ ] **Step 4: Commit the failing tests**

```bash
git add python/tests/unit/test_generate_images.py
git commit -m "test: add failing tests for generate_images prompt selection"
```

---

## Task 5: Update generate_images.py — visual_description + licence fixes

**Files:**
- Modify: `python/generate_images.py`

- [ ] **Step 1: Fix the `_LICENCE_MAP` bugs**

Current (lines 92–94):
```python
    _SOURCE_MAP = {"openai": "dalle3", "gemini": "imagen3"}
    _LICENCE_MAP = {"openai": "openai-tos-commercial", "gemini": "openai-tos-commercial"}
    source = _SOURCE_MAP.get(provider, provider)
    licence = _LICENCE_MAP.get(provider, "openai-tos-commercial")
```

Change to:
```python
    _SOURCE_MAP = {"openai": "dalle3", "gemini": "imagen3"}
    _LICENCE_MAP = {"openai": "openai-tos-commercial", "gemini": "google-tos-commercial"}
    source = _SOURCE_MAP.get(provider, provider)
    licence = _LICENCE_MAP.get(provider, "unknown-tos")
```

- [ ] **Step 2: Update the prompt selection in the loop**

Current (lines 103–104):
```python
        prompt = _PROMPT_TEMPLATE.format(concept=term, definition=definition)
```

Change to:
```python
        visual_description = (concept.get("visual_description") or "").strip()
        prompt = visual_description if visual_description else _PROMPT_TEMPLATE.format(
            concept=term, definition=definition
        )
```

- [ ] **Step 3: Run the tests — they should now PASS**

```bash
pytest python/tests/unit/test_generate_images.py -v
```

Expected: all 3 tests PASS.

- [ ] **Step 4: Commit**

```bash
git add python/generate_images.py
git commit -m "feat: use visual_description as image prompt with template fallback; fix licence map"
```

---

## Task 6: Update generate_script.py — add visual_description to AI prompt

**Files:**
- Modify: `python/generate_script.py`

The `_USER_PROMPT_TEMPLATE` string (lines 40–73) has two representations of the key_concepts schema that must both be updated.

- [ ] **Step 1: Update the Requirements bullet list (around line 51–54)**

Current:
```
- outline.key_concepts: array of 4–6 objects, each with:
    - term: the scientific term
    - definition: plain-language definition (1–2 sentences)
    - narration_segment: 2–4 sentences explaining this concept; define the term on first use; cite "{paper_id}" when making factual claims
```

Change to:
```
- outline.key_concepts: array of 4–6 objects, each with:
    - term: the scientific term
    - definition: plain-language definition (1–2 sentences)
    - narration_segment: 2–4 sentences explaining this concept; define the term on first use; cite "{paper_id}" when making factual claims
    - visual_description: 1–2 sentence cinematic scene description for image generation. Describe exactly what to show: subject, action, mood, lighting, style. No text or labels in the image. Example: "A glowing double helix rotating slowly in a dark void, base pairs highlighted in blue and orange, photorealistic."
```

- [ ] **Step 2: Update the JSON example block (around lines 62–73)**

Current `key_concepts` entry in the JSON example:
```
{{ "term": "...", "definition": "...", "narration_segment": "..." }}
```

Change to:
```
{{ "term": "...", "definition": "...", "narration_segment": "...", "visual_description": "..." }}
```

- [ ] **Step 3: Add the visual_description validation warning loop**

After `gpt_data = json.loads(raw_json)` (line 120) and before the `word_count` / `learning_objective` validations, add:

```python
    # Warn if any concept is missing visual_description (Stage 4 will fall back to template)
    for concept in (gpt_data.get("outline") or {}).get("key_concepts") or []:
        if not (concept.get("visual_description") or "").strip():
            term = concept.get("term", "<unknown>")
            print(
                f"WARNING: concept '{term}' missing visual_description "
                "— image will use fallback prompt.",
                file=sys.stderr,
            )
```

- [ ] **Step 4: Smoke-test the updated prompt**

Run Stage 2 against a real paper (requires `AI_PROVIDER` and matching API key set in env):

```bash
python python/generate_script.py --paper "$(python python/fetch_paper.py --topic 'black holes')"
```

Inspect the output JSON. Each `key_concepts` entry should have a non-empty `visual_description` string.

- [ ] **Step 5: Commit**

```bash
git add python/generate_script.py
git commit -m "feat: add visual_description per concept to AI script generation prompt"
```

---

## Task 7: Run full test suite and end-to-end smoke test

- [ ] **Step 1: Run all unit tests**

```bash
pytest python/tests/ -v
```

Expected: all tests pass, no failures.

- [ ] **Step 2: End-to-end pipeline test**

Trigger a full pipeline run (e.g. via n8n or CLI). After completion:
- Listen to the output MP3 — should sound expressive, not robotic
- Inspect the generated images in `output/<run-id>/` — each image should visually match its concept
- Check `output/<run-id>/assets-manifest.json` — audio `source` should be `"edge-tts"`, image `generation_prompt` should contain the cinematic description

- [ ] **Step 3: Verify SPEED/PITCH warning**

```bash
VOICE_PROVIDER=edge-tts VOICE_SPEED=1.5 python python/generate_voice.py \
  --script '{"script":{"narration_text":"Test."},"run_id":"warn-test"}' \
  --run-id warn-test 2>&1 | grep WARNING
```

Expected: `WARNING: VOICE_SPEED and VOICE_PITCH are ignored by edge-tts provider.`

- [ ] **Step 4: Verify gtts regression**

```bash
VOICE_PROVIDER=gtts python python/generate_voice.py \
  --script '{"script":{"narration_text":"Gtts regression test."},"run_id":"gtts-reg"}' \
  --run-id gtts-reg
echo "Exit code: $?"
```

Expected: exit code 0, audio file produced.

- [ ] **Step 5: Final commit**

```bash
git add -A
git commit -m "chore: verify all tests pass after voice and image quality improvements"
```
