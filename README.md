# VideoStudio AI — Gameplay Hook-Based Shorts Generator

Turn raw gameplay footage into **hook-based vertical shorts** (YouTube Shorts /
Reels / TikTok) — automatically. Upload a gameplay video, and the **Copilot AI
agent** watches it, hand-picks the most hook-worthy epic moments, writes the
titles/descriptions/hashtags, and the app renders 9:16 hook-first shorts with
thumbnails.

> **No local ML models. No GPU. No downloads.** The old BLIP + TinyLlama pipeline
> has been replaced by an **agent-in-the-loop** design: the AI reasoning is done
> by the Copilot agent itself (via the bundled `gameplay-shorts` skill), and the
> web app only does the deterministic work (frame extraction + video rendering).

## How it works

```
Browser --upload--> Flask app --extract frames--> contact sheets
                                    |
                                    v
                         job = "awaiting_agent"
                                    |
       Copilot agent (gameplay-shorts skill) <-- views frames/sheets
                                    |  picks epic moments + writes metadata
                                    v
                           plan.json  -->  Flask app renders
                                             9:16 hook-first shorts
                                             + thumbnails  -->  Browser
```

1. **Web app (`app.py`)** — upload UI, extracts frames (OpenCV), builds labeled
   contact sheets, parks a **job**, then deterministically renders shorts from the
   agent's plan (MoviePy/FFmpeg). Contains **zero** machine learning.
2. **The agent (Copilot)** — driven by the `gameplay-shorts` skill, visually
   analyzes the frames, selects the most hook-worthy moments using a scoring
   algorithm, and writes a **plan** (moments + hook text + titles + tags).
3. **The contract** — `services/plan_schema.py` validates the plan;
   `services/job_queue.py` manages the handoff; `services/renderer.py` renders.

### The hook-first formula (why shorts go viral)

```
[0 - 7s]   RESULT / CLIMAX  <- shown FIRST (+ optional on-screen hook text)
[~0.3s]    quick transition
[7s - end] BUILD-UP          <- the gameplay that led to the climax
```

Viewers see the payoff immediately -> curiosity -> watch to the end -> algorithm
boost.

## Project structure

```
Video-Editor/
├── app.py                     # Flask app: upload, frames, job queue, rendering
├── agent_worker.py            # CLI the agent uses to fetch jobs + submit plans
├── requirements.txt           # Lightweight deps (no torch/transformers)
│
├── services/
│   ├── frame_extractor.py     # video -> frames (OpenCV)          [deterministic]
│   ├── contact_sheet.py       # frames -> labeled montage sheets  [agent aid]
│   ├── job_queue.py           # job lifecycle + agent handoff     [contract]
│   ├── plan_schema.py         # validates the agent's plan        [contract]
│   ├── renderer.py            # plan -> 9:16 hook-first shorts     [deterministic]
│   └── state_manager.py       # persistent state for the manual editor
│
├── .github/skills/gameplay-shorts/SKILL.md   # the agent's brain / algorithm
│
├── templates/index.html       # Web UI
├── static/                    # CSS + JS frontend
└── uploads/ frames/ shorts/ jobs/            # runtime data (auto-created)
```

## Requirements

- **Python** 3.8+ (tested on 3.13)
- **FFmpeg** on your PATH (`brew install ffmpeg` / `apt install ffmpeg`)
- **Copilot CLI / agent** to perform the analysis (this repo ships the skill)
- A few hundred MB of disk for frames/shorts — **no multi-GB model downloads**

## Quick start

```bash
# macOS/Linux
./start.sh
# Windows
start.bat
```

Or manually:

```bash
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
python app.py            # http://127.0.0.1:8000
```

## Using it

1. **Upload** a gameplay video (MP4/MOV/MKV/AVI/WebM, up to 2 GB) and click
   **Generate AI Shorts** (pick a frame-extraction FPS — 2 is a good default).
2. The app extracts frames and shows **"Waiting for the AI agent..."**.
3. In your Copilot session, ask the agent to **generate the shorts** (the
   `gameplay-shorts` skill triggers automatically). The agent will:
   ```bash
   python3 agent_worker.py list            # find the pending job
   python3 agent_worker.py show <job_id>   # get the contact sheets
   # ...the agent views the frames, picks moments, writes plan.json...
   python3 agent_worker.py submit <job_id> plan.json
   ```
4. The app renders the shorts + thumbnails; the web UI shows them (sorted by
   virality), each with title, description, hashtags, and a download button.

### Manual editor (no AI)

Still available: upload -> set start/end -> optional 2x speed -> **Process Video**.

## The moment-selection algorithm

Lives in `.github/skills/gameplay-shorts/SKILL.md`. What the agent looks for and
how it scores (1-10):

- **Result/outcome visible** (kill, VICTORY banner, scoreboard jump) -> strongest.
- **Escalation** (tension -> clear payoff) -> great hook material.
- **Rarity/spectacle** (multikills, 1vX, comebacks, huge plays).
- **Phone-readable** in a 9:16 center crop; skip menus/loading/lobbies.
- **Emotion/humor** (funny deaths, glitches) -> FUNNY category.

Every moment must be **grounded in frames the agent actually viewed** — no
hallucinated events. Categories: WINNING, LOSING, SATISFYING, INTENSE, FUNNY,
CLUTCH.

## Output quality & smoothness

Shorts are rendered for maximum smoothness and quality:

- **Source-matched framerate** — output fps matches the source, clamped to
  30–60. Smooth 60 fps gameplay stays 60 fps (no more juddery 30 fps downsample).
- **CRF-18 H.264** (`yuv420p`, `+faststart`) — near-visually-lossless and
  universally playable; starts streaming before it's fully downloaded.
- **Fades** — subtle video + audio fade in/out so cuts don't pop.
- **Readable hook text** — bold gold overlay on a semi-transparent band.

> **Choppy low-FPS captures?** If your recording was made below ~48 fps (many
> Bandicam captures are 10–17 fps), the choppiness is baked into the source —
> higher output fps alone can't fix it. Enable **“Smooth choppy footage”** to
> motion-interpolate each short up to 60 fps (`services/motion_interpolation.py`).
> It's **opt-in and slow** (CPU optical flow), applied per-short so cost is
> bounded by short length. Best fix is to record at 60 fps in the first place.

## Configuration

- Render sizing / hook length / output fps — `services/renderer.py`
  (`TARGET_WIDTH/HEIGHT`, `HOOK_DURATION`, `MIN/MAX_SHORT_DURATION`,
  `MIN/MAX_OUTPUT_FPS`).
- Motion-interpolation settings — `services/motion_interpolation.py`.
- Plan validation / categories / default tags — `services/plan_schema.py`.
- Agent behavior / scoring / metadata style — the skill `SKILL.md`.
- Upload limit — `app.config['MAX_CONTENT_LENGTH']` in `app.py`.

## Publish to YouTube (optional)

Publish shorts straight from the **gallery** via the YouTube Data API v3
(a vertical clip ≤ 3 min is auto-treated as a Short).

**One-time setup:**
1. [Google Cloud Console](https://console.cloud.google.com/) → new project → enable **YouTube Data API v3**.
2. Configure the **OAuth consent screen** (External; add yourself as a Test user).
3. Create an **OAuth client ID** → type **Desktop app** → download the JSON.
4. Save it as `youtube_client_secret.json` in the project root (gitignored).
5. `pip install -r requirements.txt`, then click **Connect YouTube** in the gallery and sign in.

- Each short has an **Upload to YouTube** button; uploaded shorts show a watch
  link and appear in the **Uploaded** tab. Uploads are idempotent (no duplicates).
- Default privacy is **private** (recommended until your OAuth app is verified).
- The login token is stored **encrypted** (OS keychain, or a Fernet-encrypted file
  with the key in the keychain) — never committed, never logged.
- Quota note: ~1600 units per upload; the default 10,000/day ≈ 6 uploads/day.

## Privacy

All video processing is local. Videos never leave your machine except when *you*
explicitly upload a short to your own YouTube account. Analysis is performed by
your Copilot agent session; there are no external model downloads.

## License

Uses Flask (BSD-3), MoviePy (MIT), OpenCV (Apache-2.0), Pillow (HPND).

---

**Made for gamers and content creators — hook them in the first second.**
