#!/usr/bin/env python3
"""
Refresh metadata for already-rendered shorts: elaborated, story-rich descriptions
and YouTube-limit titles (<=100 chars). Updates each job's stored metadata, the
per-short .txt sidecars, and the combined metadata.txt — WITHOUT re-rendering video.

Mapping is by (filename, category) since each video's two shorts have distinct
categories.
"""
import os, sys, glob, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from services.job_queue import init_job_queue, STATUS_COMPLETED
from services.renderer import format_tags_csv, _write_short_metadata

BASE = os.path.dirname(os.path.abspath(__file__))
jq = init_job_queue(os.path.join(BASE, "jobs"))

CTA = "👉 Follow for more clips, and drop a comment with your take!"

# filename -> { CATEGORY: {title, description, tags} }
ELAB = {
 "bandicam_2026-04-25_13-59-12-605.mp4": {
   "SATISFYING": {
     "title": "🔥 12-Hit Combo Beatdown — Full Bar to Nearly Zero in Brawl of Progress!",
     "description": "Caught my opponent slipping and turned one opening into a full 12-hit combo string that melted their health bar from full to almost nothing. Every link connects clean — no drops, no reset — while the hit counter climbs in the corner and they're stuck in blockstun with nowhere to go. This is the kind of pressure that ends rounds before they even start. Could you have blocked out of this, or would you have eaten the whole string? Tell me your escape plan below.\n\n" + CTA + "\n\n#fightinggame #combo #fgc #anime #gaming #shorts",
     "tags": ["#fightinggame","#combo","#fgc","#anime","#gaming"],
   },
   "WINNING": {
     "title": "💥 Cinematic Super Finish — The Flashiest KO to End the Round!",
     "description": "Down to the wire, I loaded the meter and cashed it all in for the most cinematic super in the game — full screen freeze, camera spin, and a KO that ended the round on the spot. There's nothing like earning the bar the hard way and then spending it on a highlight-reel finish. Watch the timing on the confirm right before the super lands; one frame later and this doesn't connect. Rate this KO 1-10 in the comments!\n\n" + CTA + "\n\n#fightinggame #super #ko #fgc #gaming #shorts",
     "tags": ["#fightinggame","#super","#ko","#fgc","#gaming"],
   },
 },
 "bandicam_2026-04-25_14-06-02-180.mp4": {
   "WINNING": {
     "title": "🏆 Clean Round Victory — Closed It Out in Style!",
     "description": "This round came down to reads, and I won the guessing game at the perfect moment to close it out clean and trigger the victory screen. No wasted resources, no panic — just patient neutral, a confirmed punish, and the KO that sealed it. The best wins are the ones where every decision lines up, and this one felt exactly like that. Would you have played the final exchange the same way? Let me know how you'd have closed it.\n\n" + CTA + "\n\n#fightinggame #win #fgc #anime #gaming #shorts",
     "tags": ["#fightinggame","#win","#fgc","#anime","#gaming"],
   },
   "SATISFYING": {
     "title": "💥 Insane Super Burst Combo — Mid-Combo Meter Dump!",
     "description": "Right in the middle of a combo I burst into a bright blue super and kept the pressure rolling without dropping a single hit. Cancelling straight from the combo into the super is a tight window, and threading it here felt buttery — the screen lights up and the damage just stacks. This is the flashy, satisfying stuff that makes the fighting genre so addictive. Drop a 🔥 if you'd main this character after seeing this!\n\n" + CTA + "\n\n#fightinggame #super #combo #fgc #gaming #shorts",
     "tags": ["#fightinggame","#super","#combo","#fgc","#gaming"],
   },
 },
 "bandicam_2026-04-25_14-44-54-550.mp4": {
   "INTENSE": {
     "title": "😤 So Close — Top 3 Finish in Fortnite Blitz Royale!",
     "description": "Dropped into Blitz Royale, looted up through the storm phases, and fought all the way to the final few players before locking a Top 3 finish. The endgame got sweaty fast — shrinking circle, no room to reset, and everyone swinging for the win. I gave it everything and came up just short of the crown this time. What would you have done differently in that final fight? Coach me in the comments.\n\n" + CTA + "\n\n#fortnite #top3 #blitzroyale #battleroyale #gaming #shorts",
     "tags": ["#fortnite","#top3","#blitzroyale","#battleroyale","#gaming"],
   },
   "WINNING": {
     "title": "🔥 Back-to-Back Top 3 + 10,000 XP in Blitz Royale!",
     "description": "Second match, same result — another Top 3 finish, this time capped off with a fat 10,000 XP reward on the endgame screen. Two deep runs in a row isn't luck; it's rotation, smart fights, and knowing when to third-party and when to hold. The consistency is exactly what climbs the ranks. Think I can turn the next one into a full Victory Royale? Let me know if you want the win compilation!\n\n" + CTA + "\n\n#fortnite #top3 #victory #blitzroyale #battleroyale #shorts",
     "tags": ["#fortnite","#top3","#victory","#blitzroyale","#battleroyale"],
   },
 },
 "bandicam_2026-04-25_14-56-41-717.mp4": {
   "INTENSE": {
     "title": "😳 1v1 Suppressed Pistol Duel — Caught Them in the Open!",
     "description": "Snagged a Suppressed Pistol mid-rotation, spotted an enemy out in the open field, and immediately opened up — the +1,000 XP popup confirms the hits were landing. Open-ground 1v1s are pure nerve: no cover, no builds, just aim and movement deciding who walks away. I had the early advantage and pressed it hard. Would you have pushed this fight or backed off for a better angle? Tell me your play.\n\n" + CTA + "\n\n#fortnite #1v1 #fps #battleroyale #gaming #shorts",
     "tags": ["#fortnite","#1v1","#fps","#battleroyale","#gaming"],
   },
   "LOSING": {
     "title": "💀 Eliminated at #12 — Lost the Sweatiest Point-Blank Brawl!",
     "description": "What started as a clean duel collapsed into a chaotic point-blank scramble, and it ended with the worst four words in the game: eliminated by SOSWEATY63. So close to turning it around — I had shots landing and momentum, but the final exchange went their way and knocked me out at #12. These are the fights that keep you up at night. Rate this brawl 1-10 and tell me exactly what I should've done in that last second!\n\n" + CTA + "\n\n#fortnite #fortnitefail #soclose #battleroyale #gaming #shorts",
     "tags": ["#fortnite","#fortnitefail","#soclose","#battleroyale","#gaming"],
   },
 },
 "bandicam_2026-04-25_15-15-01-069.mp4": {
   "INTENSE": {
     "title": "⚔️ Intense Mid-Game Firefight in Fortnite Blitz Royale!",
     "description": "The mid-game is where Blitz Royale matches are won or lost, and this firefight was a scrap for positioning heading into the endgame. Trading shots, repositioning, and reading the rotation while the storm tightened — every decision here set up the run to the final circle. Momentum is everything at this stage. Clutch or kick? Tell me how you rate the plays.\n\n" + CTA + "\n\n#fortnite #fps #blitzroyale #battleroyale #gaming #shorts",
     "tags": ["#fortnite","#fps","#blitzroyale","#battleroyale","#gaming"],
   },
   "WINNING": {
     "title": "😮‍💨 Agonizing #2 Finish — One Spot Away From the Dub (31K XP)!",
     "description": "This one hurts. Fought all the way to the final duel and landed at #2 with a huge 31,388 XP payout — one single elimination away from the Victory Royale. The endgame was a knife's edge: last two players, shrinking circle, and no margin for error. I did everything right until the very last exchange. Was the runner-up curse real here, or did I misplay the finish? Break it down for me — the redemption run is coming.\n\n" + CTA + "\n\n#fortnite #top2 #soclose #battleroyale #gaming #shorts",
     "tags": ["#fortnite","#top2","#soclose","#battleroyale","#gaming"],
   },
 },
 "bandicam_2026-04-25_15-20-32-839.mp4": {
   "INTENSE": {
     "title": "🔥 Final-Circle Firefight That Set Up the Victory Royale!",
     "description": "This is the fight that decided the whole match — final circle, last players standing, and a firefight with zero room to breathe. Every shot mattered with the crown on the line, and winning this exchange is what opened the door to the dub. The tension in the endgame of Blitz Royale is unmatched. Would you have taken this fight head-on or played the edge of the zone? Let me hear your endgame strategy.\n\n" + CTA + "\n\n#fortnite #fps #endgame #battleroyale #gaming #shorts",
     "tags": ["#fortnite","#fps","#endgame","#battleroyale","#gaming"],
   },
   "WINNING": {
     "title": "🏆 VICTORY ROYALE! #1 Win in Fortnite Blitz Royale!",
     "description": "WINNER WINNER — took the entire lobby down for the #1 Victory Royale! From the drop to the final elimination, everything clicked: clean rotations, smart fights, and a last-circle finish that put the crown on my head. There's no better feeling in Fortnite than watching that VICTORY ROYALE banner slam onto the screen. Drop a 🏆 in the comments if you felt this one, and let me know which win you want to see next!\n\n" + CTA + "\n\n#fortnite #victoryroyale #win #1stplace #battleroyale #shorts",
     "tags": ["#fortnite","#victoryroyale","#win","#1stplace","#battleroyale"],
   },
 },
 "bandicam_2026-04-25_15-25-59-007.mp4": {
   "INTENSE": {
     "title": "⚔️ Blitz Royale Battle — Scrapping Through the Mid-Game!",
     "description": "Loot, rotate, fight — this mid-game battle had all three as I pushed to build a lead heading into the endgame. Close-range trades and quick repositions kept the pressure on while the circle closed in. This is the grind that sets up deep runs. Rate the plays 1-10 and tell me where I could've been more aggressive!\n\n" + CTA + "\n\n#fortnite #fps #blitzroyale #battleroyale #gaming #shorts",
     "tags": ["#fortnite","#fps","#blitzroyale","#battleroyale","#gaming"],
   },
   "LOSING": {
     "title": "😩 Top 4 Finish — So Close to the Dub Before Getting Clipped!",
     "description": "Fought my way into the final four and had the win in sight before ZAIDNEIRAB clipped me right at the death, ending the run at #4. The endgame was brutal — multiple players left, tight rotations, and one bad exchange is all it takes. So close to the crown I could taste it. What would you have done in that final fight to survive? Coach me up in the comments.\n\n" + CTA + "\n\n#fortnite #top4 #soclose #battleroyale #gaming #shorts",
     "tags": ["#fortnite","#top4","#soclose","#battleroyale","#gaming"],
   },
 },
 "bandicam_2026-04-25_15-30-31-023.mp4": {
   "INTENSE": {
     "title": "🔥 The Final Fight That Sealed the Victory Royale!",
     "description": "Everything came down to this last firefight — final players, final circle, and the crown one elimination away. I held my nerve, won the exchange, and set up the finish. This is the moment where Blitz Royale matches are decided, and the pressure is unreal when the dub is on the line. Clutch or kick? Tell me how you'd have played the final push.\n\n" + CTA + "\n\n#fortnite #fps #endgame #battleroyale #gaming #shorts",
     "tags": ["#fortnite","#fps","#endgame","#battleroyale","#gaming"],
   },
   "WINNING": {
     "title": "🏆 Clutch VICTORY ROYALE — Took the Whole Lobby for #1!",
     "description": "Clutched it! Fought through the entire lobby and closed out the final circle for a #1 Victory Royale. This one wasn't handed to me — it took clean aim, smart positioning, and holding my nerve when it mattered most in the endgame. That VICTORY ROYALE banner never gets old. Drop a 🏆 if you felt this clutch, and comment which game you want me to grind next!\n\n" + CTA + "\n\n#fortnite #victoryroyale #win #clutch #battleroyale #shorts",
     "tags": ["#fortnite","#victoryroyale","#win","#clutch","#battleroyale"],
   },
 },
 "bandicam_2026-04-25_15-36-34-073.mp4": {
   "INTENSE": {
     "title": "⚔️ Sword & Gun Skirmish — Up Close and Personal in Fortnite!",
     "description": "This one got personal fast — a close-quarters skirmish mixing melee and gunfire with an enemy who wasn't backing down. Swapping between sword swings and shots in tight spaces is high-risk, high-reward, and it kept both of us on the edge. Pure adrenaline. Would you have committed to the melee or created distance and gunned it out? Tell me your CQC approach!\n\n" + CTA + "\n\n#fortnite #fps #battleroyale #gaming #shorts",
     "tags": ["#fortnite","#fps","#battleroyale","#gaming"],
   },
   "LOSING": {
     "title": "💀 Eliminated at #13 — Got Clipped Mid-Fight!",
     "description": "The run ended at #13 after ITZHIM567 caught me mid-scrap and closed it out. It was a scrappy fight and the exchange just didn't fall my way this time — one misread in a fast trade and the match was over. Not every drop ends in a dub, but every loss is a lesson. Rate the plays and tell me exactly where it went wrong so the next run goes deeper!\n\n" + CTA + "\n\n#fortnite #fortnitefail #battleroyale #gaming #shorts",
     "tags": ["#fortnite","#fortnitefail","#battleroyale","#gaming"],
   },
 },
 "bandicam_2026-04-25_15-39-26-955.mp4": {
   "INTENSE": {
     "title": "⚔️ Close-Quarters Battle in the Fortnite Mid-Game!",
     "description": "Tight, fast, and unforgiving — this close-quarters battle in the mid-game was all about reaction speed and staying calm under pressure. Trading shots at close range with the circle closing means one twitch decides the fight. I pushed for the advantage and kept the run alive. Clutch or kick? Let me know how you rate this exchange!\n\n" + CTA + "\n\n#fortnite #fps #battleroyale #gaming #shorts",
     "tags": ["#fortnite","#fps","#battleroyale","#gaming"],
   },
   "LOSING": {
     "title": "😤 Top 5 Finish — One Fight Away From the Crown!",
     "description": "Grinded all the way to a Top 5 before PKVS-2013 ended the run in the endgame. So close to the dub — final handful of players, tight circle, and everything riding on the last exchanges. Deep runs like this are how you learn the endgame, even when they sting. What's your go-to endgame strategy when it's down to the last five? Drop it below — redemption run loading.\n\n" + CTA + "\n\n#fortnite #top5 #soclose #battleroyale #gaming #shorts",
     "tags": ["#fortnite","#top5","#soclose","#battleroyale","#gaming"],
   },
 },
 "bandicam_2026-04-25_15-43-45-660.mp4": {
   "INTENSE": {
     "title": "🔥 Endgame Firefight Before Another Victory Royale!",
     "description": "The final scraps before the crown — this endgame firefight was the last obstacle between me and the dub. Last players standing, circle collapsing, and every shot decides who takes the win. Holding composure here is what separates a Top 5 from a #1. Would you have pushed or held the high ground? Tell me your endgame read!\n\n" + CTA + "\n\n#fortnite #fps #endgame #battleroyale #gaming #shorts",
     "tags": ["#fortnite","#fps","#endgame","#battleroyale","#gaming"],
   },
   "WINNING": {
     "title": "🏆 Another VICTORY ROYALE! Back in the Winner's Circle!",
     "description": "Another lobby, another #1 Victory Royale! Clean run from drop to finish — smart rotations, disciplined fights, and a final circle closeout that put the crown back on my head. Stacking wins like this is what the grind is all about. Drop a 🏆 if you want the full win compilation, and tell me which game I should chase the next dub in!\n\n" + CTA + "\n\n#fortnite #victoryroyale #win #1stplace #battleroyale #shorts",
     "tags": ["#fortnite","#victoryroyale","#win","#1stplace","#battleroyale"],
   },
 },
 "2026-04-19_18-41-28.mp4": {
   "INTENSE": {
     "title": "💰 GTA 5 Heist Shootout — Guns Out, Alarms Blaring!",
     "description": "The heist went loud. Pushing through a red-lit interior with guns blazing, alarms screaming, and enemies around every corner — this is GTA 5 chaos at its finest. No stealth, no subtlety, just fight your way to the objective and pray the exit is clear. The tension in a loud heist run is unreal. Would you have gone in quiet or kicked the door down like this? Tell me your heist style!\n\n" + CTA + "\n\n#gta #gta5 #heist #gaming #shorts",
     "tags": ["#gta","#gta5","#heist","#gaming"],
   },
   "WINNING": {
     "title": "✅ MISSION PASSED in GTA 5 — Pulled It Off Clean!",
     "description": "Objective complete — that green MISSION PASSED screen is the best reward in GTA 5. After all the driving, shooting, and chaos, seeing it pop up means every risky decision paid off. There's a special satisfaction in wrapping a mission clean and cashing out. Drop a ✅ if you love the classic GTA mission grind, and comment which mission or heist I should run next!\n\n" + CTA + "\n\n#gta #gta5 #missionpassed #gaming #shorts",
     "tags": ["#gta","#gta5","#missionpassed","#gaming"],
   },
 },
}


def _write_combined(shorts_dir, game, summary, shorts):
    combined = []
    if game:
        combined.append(f"GAME: {game}")
    if summary:
        combined.append(f"SUMMARY: {summary}")
    if combined:
        combined += ["", "=" * 60, ""]
    for s in shorts:
        if not s.get("output_path"):
            continue
        m = s["moment"]
        combined += [
            f"SHORT #{s['index'] + 1}  [{m.get('category','INTENSE')} · "
            f"virality {m.get('virality_score',5)}/10 · {s.get('duration',0)}s]",
            f"File: {os.path.basename(s['output_path'])}",
            "", "Title:", m.get("title",""),
            "", "Description:", m.get("description",""),
            "", "Tags:", s["metadata"]["tags_csv"],
            "", "-" * 60, "",
        ]
    with open(os.path.join(shorts_dir, "metadata.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(combined))


def main():
    updated = 0
    for job in jq.list_jobs(statuses=[STATUS_COMPLETED]):
        fname = job.get("filename")
        elab = ELAB.get(fname)
        if not elab:
            continue
        result = job.get("result", {})
        shorts = result.get("shorts", [])
        shorts_dir = None
        for s in shorts:
            if not s.get("output_path"):
                continue
            shorts_dir = os.path.dirname(s["output_path"])
            cat = s["moment"].get("category", "").upper()
            new = elab.get(cat)
            if not new:
                continue
            title = new["title"][:100]  # YouTube title limit
            assert len(title) <= 100
            desc = new["description"][:5000]
            tags = new["tags"]
            tags_csv = format_tags_csv(tags)
            # update moment + metadata in the job result
            s["moment"]["title"] = title
            s["moment"]["description"] = desc
            s["moment"]["tags"] = tags
            s["metadata"] = {
                "title": title, "description": desc,
                "tags": tags, "tags_csv": tags_csv,
                "hook_text": s["metadata"].get("hook_text", ""),
            }
            # rewrite per-short sidecar next to the mp4
            txt_path = os.path.splitext(s["output_path"])[0] + ".txt"
            _write_short_metadata(txt_path, s["moment"], tags_csv)
            updated += 1
            print(f"  [{cat}] {title}  ({len(desc)} chars desc)")
        if shorts_dir:
            _write_combined(shorts_dir, result.get("game",""), result.get("summary",""), shorts)
        jq.update_job(job["job_id"], result=result)
        print(f"Updated {fname}")
    print(f"\nTotal shorts refreshed: {updated}")


if __name__ == "__main__":
    main()
