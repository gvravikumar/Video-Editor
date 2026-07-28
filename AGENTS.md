# AGENTS.md — How to Generate Hook-Based Gameplay Shorts

This project turns raw gameplay video into **hook-first vertical shorts**
(YouTube Shorts / Reels / TikTok) with copy-paste-ready **title, description, and
hashtags**. There are **no local ML models** — *you, the AI agent, are the brain*.
The Flask app does only mechanical work (frame extraction, contact sheets, video
rendering). You watch the gameplay, pick the epic moments, and write the metadata.

Follow this document to reproduce exactly what a human-guided agent already did:
12 videos → 24 shorts, each with a hook overlay, thumbnail, and YouTube-ready
title/description/tags.

---

## 1. Architecture (agent-in-the-loop)

```
Browser ──upload──▶ Flask app ──extract frames──▶ contact sheets
                                    │
                                    ▼
                         job = "awaiting_agent"
                                    │
     YOU (the agent) ◀── view frames / contact sheets
                                    │  pick hook moments + write metadata
                                    ▼
                           plan.json ──▶ app renders 9:16 hook-first
                                         shorts + thumbnails + metadata
```

- **App owns:** `services/frame_extractor.py`, `services/contact_sheet.py`,
  `services/renderer.py` (deterministic, no ML).
- **Contract:** `services/plan_schema.py` (validates your plan),
  `services/job_queue.py` (job lifecycle handoff).
- **You own:** watching frames, choosing moments, writing title/description/tags.

---

## 2. Your role, in one sentence

**Look at the extracted gameplay frames, hand-pick the most hook-worthy epic
moments, and emit a `plan` (JSON) of moments + metadata. The app renders it.**

Never fabricate events. Every moment must be grounded in frames you actually saw.

---

## 3. Workflow — do this every time

### 3a. Interactive (a web job is waiting)

```bash
python3 agent_worker.py list                    # jobs awaiting analysis
python3 agent_worker.py show <job_id>           # job detail + contact-sheet index
# View the contact sheets it lists (frames/<video_id>/sheets/sheet_*.jpg).
# Open individual frames (frames/<video_id>/frame_*.jpg) to confirm key moments.
python3 agent_worker.py submit <job_id> plan.json   # hand your plan back
python3 agent_worker.py wait <job_id> --timeout 900 # (optional) wait for render
```

The app extracts frames, builds **contact sheets** (grids of timestamped frames),
and parks the job as `awaiting_agent`. You **view the sheet images** to scan the
whole match fast — every cell is stamped `MM:SS.ss`, which maps to a real
timestamp in the source video.

### 3b. Batch (analyze many uploaded videos at once)

When there's no live job (e.g. a folder of uploads), build one **overview sheet
per video** (evenly-sampled, timestamped frames), view each, pick moments, then
render directly and register a completed job. See `batch_render.py` for the exact
pattern used to process all uploads. Rough recipe:

1. For each video, sample ~64 frames across its duration into a labeled grid.
2. **View** each grid; note the timestamps of wins/kills/finishes/funny beats.
3. Build a `plan` per video (below), `validate_plan`, then `render_shorts(...)`.
4. `job_queue.create_job(...)` + `mark_completed(job_id, result)` so it shows in
   the web UI and `/gallery`.

---

## 4. Choosing moments (accuracy algorithm)

> 🚨 **MANDATORY:** hook-event selection is governed by **[`HOOK_DETECTION.md`](HOOK_DETECTION.md)**
> — the strict playbook. You MUST read it and follow every rule (Rule 0 vision
> gate, the ground-truth payoff signals, the ≥6 scoring filter, the anti-patterns,
> and the mandatory self-verification) before submitting a plan. The summary below
> is only a pointer; `HOOK_DETECTION.md` is the source of truth and overrides any
> shorter description here.

**Core creed: _See it, prove it, or skip it._** A hook event has a **payoff you
can point to in a specific frame** (kill feed, `VICTORY ROYALE`, `MISSION PASSED`,
`+XP`, KO/combo counter, etc.). No visible payoff → not a hook → do not clip it.
Never fabricate events. If nothing qualifies, return **fewer or zero** shorts
rather than filler.

Signals, strongest first:

- **Result/outcome on screen** — a kill feed, `VICTORY ROYALE` / `#1`, `MISSION
  PASSED`, `YOU PLACED #N`, a KO banner, a scoreboard jump, `+XP` popups.
- **Escalation → payoff** — tension building to a clear result (low HP → clutch,
  many enemies → wipe, chase → catch). This is ideal hook material.
- **Rarity / spectacle** — multikills, 1vX, comebacks, huge combos, trick shots.
- **Phone-readable** — the action reads in a 9:16 centre crop. Skip menus,
  loading screens, idle lobbies.
- **Emotion / humor** — funny deaths, glitches, ragdolls → `FUNNY`.

### Virality score (1–10) — then FILTER

Start at 5, then:
`+2` clear win / decisive kill · `+2` rare/improbable · `+1` obvious build-up→payoff
· `+1` visually clean · `−2` ambiguous or you're inferring · `−4` menu/loading/idle.
**Discard every moment scoring below 6.** Prefer `WINNING`/`CLUTCH`/`FUNNY`.

### Timing rules

- Target ~20–45s for punchy clips, but you **may go up to ~2:59** for a richer
  moment (YouTube still counts a vertical ≤ 3 min as a Short — longer can mean
  more watch time). Set `end_time` at the **payoff**; `start_time` earlier by the
  length you want (the renderer trims/pads between 15s and 179s and puts the last
  ~7s **hook first**).
- `peak_time` = the single most epic instant (used for the thumbnail).
- Avoid overlapping moments; if two overlap, keep the higher score.
- Categories: `WINNING, LOSING, SATISFYING, INTENSE, FUNNY, CLUTCH`.

---

## 5. Metadata rules (title, description, tags) — REQUIRED

Every short ships with copy-paste-ready metadata. **These are generated and
written to disk *while the short is saved*** (in `services/renderer.py`
→ `_render_one` → `build_title` / `build_description` / `format_tags_csv`, written
to `short_XXX.txt` next to the `.mp4`, plus a combined `metadata.txt`). Author the
best content in the plan; the renderer enforces limits and fills gaps.

### Title — YouTube limit **≤ 100 characters**
- Punchy, specific, 1–2 emojis. Describe the actual result.
- Good: `🏆 VICTORY ROYALE! #1 Win in Fortnite Blitz Royale!`
- Good: `💀 Eliminated at #12 — Lost the Sweatiest Point-Blank Brawl!`
- No clickbait you can't back up. `build_title` truncates to 100 with `…` if over.

### Description — YouTube limit **≤ 5000 characters**; write a **detailed story**
- 3–5 sentences telling what happens: the setup, the tension, the payoff. Use
  concrete details you saw (weapon, opponent name from the kill feed, XP, placement).
- End with a **call-to-action** question ("What would you have done?").
- End with a **hashtag line** (space-separated) for discovery.
- `build_description` auto-appends a CTA and hashtag line if you omit them, and
  builds a story from the moment's `reason` if `description` is empty — but you
  should author the full story for the best result.

Example (this is the real quality bar to match):
> WINNER WINNER — took the entire lobby down for the #1 Victory Royale! From the
> drop to the final elimination, everything clicked: clean rotations, smart
> fights, and a last-circle finish that put the crown on my head. There's no
> better feeling in Fortnite than watching that VICTORY ROYALE banner slam onto
> the screen. Drop a 🏆 if you felt this one, and tell me which win to show next!
>
> 👉 Follow for more clips, and drop a comment with your take!
>
> #fortnite #victoryroyale #win #1stplace #battleroyale #shorts

### Tags — comma-separated hashtags
- 10–15 tags. Include the **game**, the **moment/category**, and broad-reach tags.
- Stored/exposed as `tags_csv`, e.g. `#fortnite, #victoryroyale, #win, #1stplace, …`.
- The validator auto-adds category + base tags (`#gaming #shorts #viral #gameplay`),
  so focus on game- and moment-specific ones. `format_tags_csv` de-dupes and
  guarantees exactly one leading `#` per tag.

### `hook_text` — the on-screen overlay
- ≤ ~30 chars, ALL-CAPS, curiosity-driven: `VICTORY ROYALE!`, `1v4 CLUTCH?!`,
  `SO CLOSE...`, `WAIT FOR IT`. Emojis are stripped from the burned-in overlay
  (fonts lack emoji glyphs) but kept in titles/tags.

---

## 6. `plan.json` schema (full example)

```json
{
  "game": "Fortnite",
  "summary": "Blitz Royale drop; several fights and a final-circle win.",
  "moments": [
    {
      "start_time": 228.0,
      "end_time": 258.0,
      "peak_time": 256.0,
      "category": "WINNING",
      "virality_score": 10,
      "hook_text": "VICTORY ROYALE!",
      "reason": "The '#1 VICTORY ROYALE' banner appears after the final elimination.",
      "title": "🏆 VICTORY ROYALE! #1 Win in Fortnite Blitz Royale!",
      "description": "WINNER WINNER — took the whole lobby down... (3-5 sentence story) ... Drop a 🏆 if you felt this one!",
      "tags": ["#fortnite", "#victoryroyale", "#win", "#1stplace", "#battleroyale"]
    }
  ]
}
```

Per moment, only `start_time`, `end_time`, `category` are strictly required — the
rest is defaulted — but **always supply title, description, tags, hook_text,
peak_time** for shorts that are actually good.

---

## 7. What the renderer guarantees (so you don't have to)

`services/renderer.py::render_shorts(video_path, plan, output_dir, smooth=False)`:
- 9:16 (1080×1920) hook-first cut: last ~7s (the climax) first, then the build-up.
- Hook-text overlay on a readable band; thumbnail from `peak_time`.
- **Source-matched output fps** (30–60), CRF-18 H.264, `+faststart`, fades.
- **Metadata generated at save time:** `short_XXX.txt` (TITLE/DESCRIPTION/TAGS)
  written atomically with the `.mp4`, plus a combined `metadata.txt` per video.
- Optional `smooth=True` → motion-interpolate choppy (<48 fps) sources to 60 fps
  (slow, opt-in; per-short).

Outputs per job dir (`shorts/<job_id>/`): `short_NNN_<category>.mp4`,
`thumb_NNN.jpg`, `short_NNN_<category>.txt`, `metadata.txt`, `shorts_manifest.json`.

---

## 8. Results UI

- Main app: `http://127.0.0.1:8000/` (upload + generate + per-video results).
- **Gallery:** `http://127.0.0.1:8000/gallery` — two tabs:
  - **Generated** — every generated short with thumbnail, title, description,
    hashtag chips, hover-preview, copy/download, and an **Upload to YouTube** button.
    Backed by `GET /gallery/data`.
  - **Uploaded** — the archive of shorts already published to YouTube, each with a
    YouTube-style thumbnail + watch link. Backed by `GET /youtube/archive`.

---

## 8b. Direct YouTube upload (YouTube Data API v3)

Shorts can be published straight to YouTube from the gallery. There is **no
separate Shorts API** — a vertical (9:16) video ≤ 3 min is auto-treated as a Short,
which our clips satisfy.

**One-time setup (per machine/account):**
1. [Google Cloud Console](https://console.cloud.google.com/) → new project.
2. Enable **YouTube Data API v3** (APIs & Services → Library).
3. Configure the **OAuth consent screen** (External) and add yourself as a **Test user**.
4. Create an **OAuth client ID** of type **Desktop app**; download the JSON.
5. Save it as **`youtube_client_secret.json`** in the project root (gitignored).
6. `pip install -r requirements.txt` (installs the google-* + crypto libs).
7. In the gallery, click **Connect YouTube** → sign in with Google.

**Security:** the OAuth token is stored via `services/secure_store.py` — the OS
keychain when available, otherwise a `Fernet`-encrypted file whose key is itself
kept in the keychain (or a `0600` key file as a last resort). Tokens are never
logged and never committed. `youtube_client_secret.json` and `state/secrets/` are
gitignored.

**Behavior:**
- Default privacy is **private** (unverified OAuth apps can only upload as private
  until Google verifies them; flip to public/unlisted in YouTube Studio or after
  verification). The UI offers private/unlisted/public.
- Uploads are **idempotent**: each short's `{video_id, url, privacy, uploaded_at}`
  is saved in `job.json`; re-clicking returns the existing link (never double-uploads).
- **Quota:** `videos.insert` costs ~1600 units; the default 10,000/day ≈ 6 uploads/day.
  Request a quota increase for bulk publishing.

**Endpoints:** `GET /youtube/status`, `POST /youtube/connect`,
`POST /youtube/disconnect`, `POST /youtube/upload {job_id,index,privacy}`,
`GET /youtube/archive`.

The app is **fail-safe**: with the libraries or client secret missing, everything
still runs and the UI shows exact setup guidance.

---

## 9. Verification checklist (before you call it done)

- [ ] Every chosen moment is grounded in frames you actually viewed.
- [ ] Each short has a `.mp4`, a `thumb_*.jpg`, and a `short_*.txt` sidecar.
- [ ] Titles ≤ 100 chars; descriptions are 3–5 sentence stories + CTA + hashtags.
- [ ] `tags_csv` renders as comma-separated hashtags (no `##`).
- [ ] Output resolution 1080×1920; fps matches source (60fps stays 60fps).
- [ ] Jobs show as `completed` in `/uploads/list` and appear in `/gallery`.

---

## 10. File map

| Path | Role |
|---|---|
| `HOOK_DETECTION.md` | **strict hook-event playbook — read before selecting any moment** |
| `agent_worker.py` | CLI you drive: `list / show / frames / submit / wait / status` (enforces the quality gate on submit) |
| `batch_render.py` | Batch pattern: analyze many uploads → render + register jobs |
| `refresh_metadata.py` | Rewrite title/description/tags of existing shorts (no re-render) |
| `services/frame_extractor.py` | video → frames (OpenCV) |
| `services/contact_sheet.py` | frames → labeled montage sheets (your triage aid) |
| `services/plan_schema.py` | validates/normalizes your plan (enforces YT limits) |
| `services/renderer.py` | plan → 9:16 hook-first shorts + thumbnails + **metadata at save** |
| `services/job_queue.py` | job lifecycle + agent handoff + per-short YouTube result |
| `services/youtube_uploader.py` | YouTube Data API v3 upload (OAuth, resumable) |
| `services/secure_store.py` | encrypted secret storage (keychain / Fernet file) |
| `.github/skills/gameplay-shorts/SKILL.md` | the skill wrapper (same rules) |
| `templates/gallery.html` | results gallery: Generated + Uploaded tabs, YouTube upload |

---

**Golden rule:** hook them in the first second, ground every moment in what you
actually saw, and ship every short with a ≤100-char title and a story-rich,
CTA-and-hashtag description. That's the job.
