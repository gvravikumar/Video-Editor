---
name: gameplay-shorts
description: >-
  Turn raw gameplay footage into hook-based vertical shorts. USE WHEN the user
  asks to generate shorts/reels/clips from a gameplay video, mentions a pending
  "AI shorts" job from the Video-Editor web app, or points at an uploaded
  gameplay file. The AGENT is the analysis brain (no local ML models): it visually
  reviews extracted frames/contact sheets, hand-picks the most hook-worthy epic
  moments, writes titles/descriptions/hashtags, and hands a plan back to the app,
  which deterministically renders 9:16 hook-first shorts + thumbnails.
---

# Gameplay Shorts (agent-in-the-loop)

You are the AI brain of a gameplay shorts generator. The Flask web app in this
repo (`app.py`) does the mechanical work (frame extraction, contact sheets,
video rendering). **You** do the intelligence: watch the gameplay frames, decide
which moments will hook viewers, and write the metadata. There are **no local ML
models** — accuracy comes from your own multimodal reasoning plus the structured
algorithm below.

## The contract

- The app extracts frames and parks a **job** as `awaiting_agent`.
- You inspect frames + contact sheets, then submit a **plan** (list of moments).
- The app validates the plan (`services/plan_schema.py`) and renders the shorts.

Talk to the job queue with the CLI (works from anywhere in the repo):

```bash
python3 agent_worker.py list                 # jobs waiting for you (JSON)
python3 agent_worker.py show <job_id>         # job detail + contact-sheet index
python3 agent_worker.py frames <job_id> --stride 5   # frame files + timestamps
python3 agent_worker.py submit <job_id> plan.json    # submit your plan ('-' = stdin)
python3 agent_worker.py wait <job_id> --timeout 900  # block until render done
```

## Workflow (do this every time)

> 🚨 **STEP 0 — MANDATORY:** open and follow **`HOOK_DETECTION.md`** in the project
> root. It is the strict, authoritative playbook for finding hook events (vision
> gate, ground-truth payoff signals, the ≥6 score filter, anti-patterns, and a
> mandatory self-verification checklist). Do **not** pick any moment or submit a
> plan without satisfying every rule in it. If you cannot view images, STOP —
> this task requires a multimodal agent.

1. **Find the job.** Run `python3 agent_worker.py list`. If a specific `job_id`
   was given, use it. Note `frames_dir`, `frame_count`, and `duration`.

2. **Get the contact sheets.** Run `show <job_id>`. The `sheets` object lists
   montage images under `<frames_dir>/sheets/sheet_XXX.jpg`, each cell stamped
   with its timestamp (`MM:SS.ss`). **View these sheet images** to scan the whole
   match fast. Every cell maps to a real timestamp in the source video.

3. **Scan for epic moments.** Read the sheets in order and look for hook-worthy
   beats (see the algorithm below). For anything promising, open the individual
   full-resolution frames around that time (use `frames <job_id> --stride 1` or
   just open `<frames_dir>/frame_XXXXXX.jpg`) to confirm what actually happens.

4. **Pick + rank moments.** Choose the strongest moments (typically 5–15,
   depending on length). For each, determine:
   - `start_time` — where the build-up should start (seconds).
   - `end_time` — the climax/result timestamp (the payoff), in seconds.
   - `peak_time` — the single most epic instant (used for the thumbnail).
   - `category` — one of WINNING, LOSING, SATISFYING, INTENSE, FUNNY, CLUTCH.
   - `virality_score` — 1–10 (see scoring below).
   - `hook_text` — a punchy ≤30-char on-screen overlay ("1v4 CLUTCH?!").
   - `reason` — one line grounding it in what you actually saw (no hallucination).
   - `title`, `description`, `tags` — platform-ready metadata.

5. **Write plan.json** (schema below) and submit it:
   ```bash
   python3 agent_worker.py submit <job_id> plan.json
   ```

6. **Confirm.** Optionally `wait <job_id>` until rendering finishes, then tell the
   user how many shorts were produced (they appear in the web UI).

## Moment-selection algorithm (accuracy)

> **Authoritative source: `HOOK_DETECTION.md`.** The rules below are a summary; if
> anything conflicts, `HOOK_DETECTION.md` wins. **Core creed: _See it, prove it,
> or skip it_** — a hook event has a visible payoff you can point to in a specific
> frame. No payoff → not a hook → do not clip. If nothing qualifies, return fewer
> or zero shorts (never filler). **Discard any moment scoring below 6.**

Judge each candidate window on these signals and keep only genuine highlights:

- **Result/outcome visible** — a kill, victory/defeat banner, "VICTORY", scoreboard
  jump, boss down, round win. Strongest hook signal → high score.
- **Escalation** — the frames show tension building to a clear payoff (chase →
  catch, low HP → clutch, many enemies → wipe). Hook-first structure thrives here.
- **Rarity / spectacle** — multikills, improbable survivals, huge explosions, trick
  shots, comebacks. The more "no way!" the better.
- **Readability at a glance** — the action is clear in a 9:16 center crop and would
  read on a phone. Skip cluttered menus, loading screens, idle lobbies.
- **Emotion / humor** — funny deaths, glitches, ragdolls, fails → FUNNY category.

**Virality score (1–10):**
- Start at 5.
- +2 if a clear WIN or decisive KILL/clutch is on screen.
- +2 if it's rare/improbable (multikill, 1vX, comeback, huge play).
- +1 if the build-up→payoff arc is obvious (great hook material).
- +1 if visually clean and phone-readable.
- −2 if ambiguous, cluttered, or you're inferring rather than seeing it.
- Cap at 10. Prefer WINNING/CLUTCH/FUNNY for shareability. **Never invent events
  you can't see in the frames.**

**Timing rules:**
- Aim for shorts ~20–45s for snappy clips, but you **may extend up to ~2:59**
  when a moment deserves it — YouTube treats a vertical ≤ 3 min as a Short, and
  longer clips can earn more watch time. Set `end_time` at the payoff, `start_time`
  earlier by the desired length (the app trims/pads between 15s and 179s and puts
  the last ~7s hook FIRST).
- `peak_time` should be the exact most-epic frame (used for the thumbnail).
- Avoid overlapping moments; if two candidates overlap, keep the higher score.

## Writing hooks & metadata (retention + CTR)

Metadata is generated and written to disk **while each short is saved**
(`services/renderer.py`), so author the best content in the plan — the renderer
enforces YouTube limits and fills any gaps.

- `hook_text`: ALL-CAPS, ≤30 chars, creates curiosity — "WAIT FOR IT",
  "1v4 CLUTCH?!", "HOW DID THIS MISS?", "LAST SECOND WIN". Rendered on the hook.
  (Emojis are stripped from the burned-in overlay but kept in title/tags.)
- `title`: **≤ 100 chars (YouTube limit)**, 1–2 emojis, specific to what happens —
  "🏆 VICTORY ROYALE! #1 Win in Fortnite Blitz Royale!". No clickbait you can't back up.
- `description`: **write a detailed 3–5 sentence STORY** (≤ 5000 chars) — the setup,
  the tension, and the payoff, using concrete details you saw (weapon, opponent
  name from the kill feed, XP, placement). End with a **call-to-action** question
  and a **hashtag line**. If you leave it short, the renderer auto-adds a CTA and
  hashtags, but author the full story for the best result.
- `tags`: 10–15 hashtags. Include the game if identifiable (logo/HUD), the
  category, and broad-reach tags (#gaming #shorts #viral). The validator adds
  category/base tags automatically; focus on game- and moment-specific ones.
  Exposed as comma-separated `tags_csv` (e.g. `#fortnite, #clutch, #win`).
- `game`: your best guess from the HUD/art style (e.g. "Valorant", "Fortnite",
  "Call of Duty"). Leave "" if unsure.

Example description quality bar:
> WINNER WINNER — took the entire lobby down for the #1 Victory Royale! Clean
> rotations, smart fights, and a last-circle finish sealed the crown. Drop a 🏆 if
> you felt this one, and tell me which win to show next!
>
> 👉 Follow for more clips, and drop a comment with your take!
>
> #fortnite #victoryroyale #win #1stplace #battleroyale #shorts

## plan.json schema

```json
{
  "game": "Valorant",
  "summary": "Ranked match; several clutches and a close final round.",
  "moments": [
    {
      "start_time": 812.0,
      "end_time": 840.0,
      "peak_time": 838.5,
      "category": "CLUTCH",
      "virality_score": 9,
      "hook_text": "1v4 CLUTCH?!",
      "reason": "Player is last alive vs 4, wins the round with a final headshot; kill feed + round-win banner visible.",
      "title": "🔥 INSANE 1v4 Clutch to Win the Round!",
      "description": "Down to the last player, this clutch is unreal. Would you have won it? Watch till the end!",
      "tags": ["#valorant", "#clutch", "#1v4", "#ace", "#fps"]
    }
  ]
}
```

Only `start_time`, `end_time`, and `category` are strictly required per moment —
the rest is defaulted if missing — but supply everything for the best shorts.

## Notes & guardrails

- **Ground every moment in frames you actually viewed.** If you can't see the
  payoff, lower the score or drop it. No fabricated events.
- The app reuses extracted frames per video, so re-runs are fast.
- If `list` shows no jobs, the user probably hasn't clicked **Generate AI Shorts**
  in the web app yet, or the frames are still extracting — check `status <job_id>`.
- If you're pointed at a bare video file instead of a job, tell the user to start
  it from the web app (upload → Generate AI Shorts) so frames get extracted first.
