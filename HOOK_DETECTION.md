# HOOK_DETECTION.md — The Strict Playbook for Finding Hook Events

> **READ THIS BEFORE PICKING ANY MOMENT.** This is the single source of truth for
> identifying hook-worthy gameplay events. If you cannot follow these rules, DO NOT
> produce a plan — the whole project depends on getting *this* right. A short built
> on a weak moment is a failure, no matter how good the rendering is.

---

## RULE 0 — You must be able to SEE the footage (hard gate)

You are the vision brain. You **must visually inspect the extracted frames /
contact sheets** before selecting anything.

- ✅ REQUIRED: open and actually look at `frames/<video_id>/sheets/sheet_*.jpg`
  (every cell is stamped `MM:SS.ss`) and zoom into individual
  `frames/<video_id>/frame_*.jpg` around any candidate.
- ❌ FORBIDDEN: guessing timestamps, inventing events, or picking "middle of the
  video" without looking. If you have no vision capability, **STOP** and tell the
  user this task needs a multimodal agent or a vision API — do not fake a plan.

**Self-check before continuing:** "Have I viewed frames covering 100% of the
video's duration?" If no → keep viewing.

---

## What a "hook event" IS (the only things worth clipping)

A hook event is a moment with a **visible, unambiguous payoff** that makes a
viewer think *"wait — what just happened?"* in the first second. It has three
parts you must be able to point to in the frames:

1. **Setup** — context that creates stakes (low HP, many enemies, a race to a spot).
2. **Escalation** — tension rising toward a result.
3. **PAYOFF** — a concrete, on-screen outcome (see the ground-truth list below).

If you cannot identify the **PAYOFF frame**, it is **NOT a hook event.** Skip it.

---

## GROUND-TRUTH payoff signals (highest confidence — prefer these)

On-screen text/UI is near-proof. Actively hunt for these in the frames:

- **Win/Result banners:** `VICTORY ROYALE`, `#1`, `YOU PLACED #N`, `WINNER`,
  `MISSION PASSED`, `VICTORY`, `DEFEAT`, `GAME OVER`, `MATCH COMPLETE`.
- **Elimination / kill feed:** `ELIMINATED BY…`, `KNOCKED`, kill counters ticking
  up, "+1 elim", multi-kill callouts (`DOUBLE/TRIPLE KILL`, `ACE`).
- **Score/number jumps:** `+1,000 XP`, `+300`, combo counters (`12 HITS`),
  scoreboard flips, level-up.
- **Special effects tied to an outcome:** super/ultimate KO animations, finishing
  moves, a downed enemy, an explosion that kills.

A moment anchored to any of these = strong candidate. **Read the small HUD text
in the frames — that is where the truth is.**

---

## SECONDARY signals (use when no banner, needs 2+ together)

Only clip these if **at least two** co-occur and you can see a clear result:

- Sudden burst of muzzle flash / tracers followed by an enemy dropping.
- Rapid camera/scene change (chase → catch, fall → survive).
- A visible enemy player at close range in a 1v1, then they vanish (kill) — confirm
  with the kill feed frame.
- Big physics/spectacle: huge explosion, ragdoll, vehicle launch, trick shot landing.

If it's only motion/color with **no result you can point to → DO NOT clip it.**

---

## Per-game cheat sheet (where the payoff shows up)

| Game type | Look for (payoff) | Hook text ideas |
|---|---|---|
| Battle Royale (Fortnite/PUBG/Warzone/Apex) | `VICTORY ROYALE`/`#1`/`YOU PLACED #N`, kill feed, "eliminated", crown | `VICTORY ROYALE!`, `1v3 CLUTCH?!`, `SO CLOSE #2` |
| Hero/Arena FPS (Valorant/CS/OW) | Kill banners, `ACE`, clutch (1vX), spike/round win, MVP | `1v4 ACE?!`, `CLUTCH OR KICK` |
| Fighting (SF/Tekken/anime) | Combo counter, `K.O.`, super/ultra cinematic, `WINS` | `12-HIT COMBO!`, `PERFECT KO` |
| MOBA (LoL/Dota) | Multi-kill banners (`DOUBLE/TRIPLE/PENTA`), tower/objective, `VICTORY` | `PENTAKILL?!`, `BARON STEAL` |
| Sandbox/Story (GTA/RDR) | `MISSION PASSED`, wanted-level chase, heist, cutscene beat | `MISSION PASSED!`, `THE HEIST` |
| Racing/Sports | Finish line `1st`, last-lap overtake, goal/score | `LAST-LAP WIN!`, `BUZZER BEATER` |
| Roguelike/Survival | Boss death, run record, near-death survival | `BOSS DOWN!`, `1 HP SURVIVAL` |

If you can't identify the game, describe the **visible result** literally and pick
a neutral category (`INTENSE`/`WINNING`/`LOSING`).

---

## The scoring gate (assign `virality_score`, then FILTER)

Start at **5**, adjust:

| Signal | Δ |
|---|---|
| Clear WIN / decisive KILL / clutch visible on screen | **+2** |
| Rare / improbable (multikill, 1vX, comeback, huge play) | **+2** |
| Obvious build-up → payoff arc (great hook material) | **+1** |
| Clean & phone-readable (subject centered, uncluttered) | **+1** |
| Ambiguous, cluttered, or you're INFERRING the result | **−2** |
| Menu / loading / lobby / idle / walking with nothing happening | **−4** |

**HARD FILTER:** after scoring, **discard every moment below 6.** If a video
yields zero moments ≥ 6, it's fine to return **fewer shorts (even zero)** — never
pad the plan with filler. Quality over quantity, always.

Order the final list by score, highest first.

---

## ANTI-PATTERNS — do NOT clip these (instant reject)

- ❌ Menus, loading screens, lobbies, character-select, inventory, map screens.
- ❌ Walking/looting/rotating with no fight and no result.
- ❌ "Something *might* be happening" — if you're guessing, it's a no.
- ❌ A fight with **no visible outcome** (you can't tell who won).
- ❌ Duplicated/overlapping windows of the same event (keep the single best one).
- ❌ Fabricated details in the description (a kill count, opponent name, or XP you
  did not actually see in a frame). Ground every claim in a viewed frame.

---

## TIMING rules (so the render hooks correctly)

- `end_time` = the exact **payoff** moment (the banner/kill/KO frame).
- `peak_time` = the single most epic instant (used for the thumbnail) — usually
  at or just before `end_time`.
- `start_time` = earlier by the length you want. Default 25–40s; you MAY go up to
  **~2:59** for a rich sequence (still a valid YouTube Short, more watch time).
- The renderer puts the **last ~7s (the payoff) FIRST** as the hook, then the
  build-up. So always make sure the payoff sits at the END of your window.
- Never overlap two moments; if they overlap, keep the higher score.

---

## MANDATORY self-verification (do this before submitting the plan)

For **each** moment, you must be able to answer YES to all of these. If any is
NO, fix or drop the moment:

1. Did I **see** the payoff in a specific frame? (name the timestamp)
2. Is the payoff one of the ground-truth signals, or ≥2 secondary signals?
3. Is `virality_score` ≥ 6 after honest scoring?
4. Is `end_time` on the payoff, with `start_time` giving a coherent build-up?
5. Does every sentence of my description match something visible? (no fabrication)
6. Is the title ≤ 100 chars and specific to the actual result?

Then, across the whole plan:
- 7. No two moments overlap in time.
- 8. Moments are sorted by `virality_score` (desc).
- 9. If nothing scored ≥ 6, I returned an empty/short list rather than filler.

**Only after all boxes are checked do you call `agent_worker.py submit`.**

---

## One-line creed

> **See it, prove it, or skip it.** A hook event has a payoff you can point to in
> a frame. No payoff, no clip. This rule is what makes the entire pipeline worth
> running.
