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


def _run_main(script_json: str, run_id: str = "test-run-001"):
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
         patch("python.generate_images.load_ai_config", return_value={"provider": "openai", "api_key": "test"}), \
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
