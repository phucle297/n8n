# Quickstart: Science Narrator

**Branch**: `001-science-narrator`
**Date**: 2026-03-22

Get from zero to a running pipeline in under 30 minutes.

---

## Prerequisites

- Ubuntu 22.04+ (or Debian equivalent) — or macOS with Homebrew
- Python 3.11+
- Docker (for n8n)
- An OpenAI API key (required for script generation and DALL·E; optional for TTS)

---

## Step 1: System Dependencies

```bash
# Ubuntu/Debian
sudo apt update
sudo apt install -y ffmpeg imagemagick python3.11 python3.11-venv git

# macOS (Homebrew)
brew install ffmpeg imagemagick python@3.11
```

Verify:
```bash
ffmpeg -version          # must show version
convert --version        # ImageMagick — must show version
python3.11 --version     # must show 3.11.x
```

---

## Step 2: Clone and Set Up Python Environment

```bash
git clone <repo-url>
cd n8n  # or whatever the repo directory is named

cd python/
python3.11 -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate

pip install --upgrade pip
pip install -r requirements.txt
```

Verify:
```bash
python -c "import moviepy; import openai; import gtts; print('OK')"
```

---

## Step 3: Initialise Data Directory

```bash
cd ..  # back to repo root
mkdir -p data output logs
echo '[]' > data/processed_papers.json
```

---

## Step 4: Set Environment Variables

Create a `.env` file in the repo root (do not commit this file):

```bash
# .env
OPENAI_API_KEY=sk-...

# Voice profile (optional — defaults shown)
VOICE_PROVIDER=gtts
VOICE_LOCALE=en-US
VOICE_SPEED=1.0
VOICE_PITCH=default
VOICE_ID=
```

Load them for local testing:
```bash
set -a && source .env && set +a
```

---

## Step 5: Start n8n

```bash
docker run -d \
  --name science-narrator-n8n \
  -p 5678:5678 \
  -v ~/.n8n:/home/node/.n8n \
  --env-file .env \
  n8nio/n8n:latest
```

Open `http://localhost:5678` and create an account.

---

## Step 6: Import the n8n Workflow

1. In n8n UI: **Workflows → Import from File**
2. Select `n8n_workflows/science_narrator.json`
3. Open the imported workflow and verify the Execute Command nodes show the correct
   Python script paths (update if your repo root differs from `/app`).
4. Save and **Activate** the workflow.

---

## Step 7: Run the Pipeline (Manual Test)

In n8n, open the Science Narrator workflow and click **Execute Workflow**.
When prompted for a topic, enter: `gravitational waves`

Expected output in `output/<run_id>/`:
```
output/<run_id>/
├── video_vertical.mp4       # 1080×1920, ~5 min
├── video_horizontal.mp4     # 1920×1080, ~5 min
└── assets-manifest.json     # all assets verified
```

Check the run log:
```bash
cat logs/<run_id>.json | python3 -m json.tool
```

---

## Step 8: Verify Constitution Compliance

```bash
# Check manifest is present and all_verified = true
python3 -c "
import json, sys
m = json.load(open('output/<run_id>/assets-manifest.json'))
assert m['all_verified'], 'FAIL: unverified assets'
assert len(m['video_files']) == 2, 'FAIL: missing format'
print('Constitution check: PASS')
"
```

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `ffmpeg: command not found` | ffmpeg not installed | `apt install ffmpeg` |
| `OSError: no such file: convert` | ImageMagick not installed | `apt install imagemagick` |
| Stage 1 exits 1, "duplicate paper" | Paper already processed | Choose a different topic |
| Stage 2 exits 1, "word count out of range" | GPT response too short/long | Re-run; adjust prompt temperature |
| Stage 3 exits 1, "OPENAI_API_KEY not set" | env var missing | Check `.env` and `docker --env-file` |
| n8n Execute Command node times out | Pipeline > 15 min | Check API response times; increase node timeout |

---

## Updating the Voice Profile

Change voice settings in n8n's environment variable store:
**n8n → Settings → Environment Variables** → update `VOICE_*` fields → restart n8n.

The next pipeline run inherits the new settings automatically.
