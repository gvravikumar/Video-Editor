#!/usr/bin/env python3
"""Batch-generate hook shorts for all uploaded gameplay videos (agent-picked moments)."""
import os, sys, uuid, json, traceback
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from services.plan_schema import validate_plan
from services.renderer import render_shorts
from services.job_queue import init_job_queue

BASE = os.path.dirname(os.path.abspath(__file__))
UP = os.path.join(BASE, "uploads")
SHORTS = os.path.join(BASE, "shorts")
jq = init_job_queue(os.path.join(BASE, "jobs"))

# filename -> plan (moments hand-picked by the agent from contact-sheet analysis)
PLANS = {
 "bandicam_2026-04-25_13-59-12-605.mp4": {"game":"Fighting Game","summary":"1v1 anime fighter — big combo strings and a cinematic super finish.","moments":[
   {"start_time":78,"end_time":100,"peak_time":94,"category":"SATISFYING","virality_score":8,"hook_text":"12-HIT COMBO!","reason":"A long combo string builds to a 12-hit counter on screen.","title":"🔥 12-Hit Combo Beatdown!","description":"This combo just kept going and going. Could you have escaped it? Drop a 🔥 if this was clean!","tags":["#fightinggame","#combo","#fgc","#anime"]},
   {"start_time":164,"end_time":179,"peak_time":172,"category":"WINNING","virality_score":9,"hook_text":"CINEMATIC KO!","reason":"A cinematic super move animation lands and ends the round.","title":"💥 Cinematic Super Finish!","description":"Ended the round with the flashiest super in the game. Rate this KO 1-10! Watch till the end.","tags":["#fightinggame","#super","#ko","#fgc"]}]},

 "bandicam_2026-04-25_14-06-02-180.mp4": {"game":"Fighting Game","summary":"Ranked anime fighter — a clean round win and a huge super combo.","moments":[
   {"start_time":145,"end_time":160,"peak_time":158,"category":"WINNING","virality_score":8,"hook_text":"ROUND WON!","reason":"Opponent is KO'd and the victory/battle-pass screen follows.","title":"🏆 Clean Round Victory!","description":"Closed out the round in style. Would you have won this one? Watch till the end!","tags":["#fightinggame","#win","#fgc","#anime"]},
   {"start_time":220,"end_time":236,"peak_time":233,"category":"SATISFYING","virality_score":8,"hook_text":"SUPER BURST!","reason":"A bright blue super move bursts across the screen mid-combo.","title":"💥 Insane Super Combo!","description":"That super burst was too clean. Drop a 🔥 if you'd main this character!","tags":["#fightinggame","#super","#combo","#fgc"]}]},

 "bandicam_2026-04-25_14-44-54-550.mp4": {"game":"Fortnite","summary":"Fortnite Blitz Royale — back-to-back top-3 finishes.","moments":[
   {"start_time":205,"end_time":224,"peak_time":222,"category":"INTENSE","virality_score":7,"hook_text":"TOP 3 FINISH!","reason":"Final moments before placing #3 on the endgame screen.","title":"😤 So Close — Top 3 Finish!","description":"Fought to the very end and locked a top-3. What would you have done differently? 👇","tags":["#fortnite","#top3","#blitzroyale","#battleroyale"]},
   {"start_time":533,"end_time":553,"peak_time":550,"category":"WINNING","virality_score":8,"hook_text":"ANOTHER TOP 3!","reason":"A second top-3 finish with a 10,000 XP reward screen.","title":"🔥 Another Top 3 in Blitz Royale!","description":"Two top-3s in a row and a fat 10K XP. Consistency is key! Follow for more.","tags":["#fortnite","#top3","#victory","#blitzroyale"]}]},

 "bandicam_2026-04-25_14-56-41-717.mp4": {"game":"Fortnite","summary":"A 1v1 firefight that ends in a heartbreak elimination.","moments":[
   {"start_time":27,"end_time":33,"peak_time":32,"category":"INTENSE","virality_score":7,"hook_text":"ENEMY SPOTTED!","reason":"Grabs a suppressed pistol and opens fire on an enemy; +1,000 XP for hits.","title":"😳 1v1 Suppressed Pistol Duel!","description":"Caught this player in the open and opened fire. Would you have pushed? 👀","tags":["#fortnite","#1v1","#fps","#battleroyale"]},
   {"start_time":33,"end_time":38,"peak_time":36.2,"category":"LOSING","virality_score":7,"hook_text":"SO CLOSE...","reason":"The duel collapses into a point-blank brawl and ends 'YOU PLACED #12 - ELIMINATED'.","title":"💀 Eliminated at #12 in the Sweatiest Brawl!","description":"Down to a point-blank scramble and I just barely lost it. Rate the fight 1-10! 😭","tags":["#fortnite","#fortnitefail","#soclose","#battleroyale"]}]},

 "bandicam_2026-04-25_15-15-01-069.mp4": {"game":"Fortnite","summary":"Fortnite Blitz Royale — a runner-up (#2) finish after a tense endgame.","moments":[
   {"start_time":176,"end_time":190,"peak_time":185,"category":"INTENSE","virality_score":6,"hook_text":"FINAL FIGHTS","reason":"Mid-game firefight while pushing toward the endgame.","title":"⚔️ Intense Blitz Royale Firefight!","description":"Scrapping for position in the mid-game. Clutch or kick? 👇","tags":["#fortnite","#fps","#blitzroyale","#battleroyale"]},
   {"start_time":250,"end_time":275,"peak_time":272,"category":"WINNING","virality_score":8,"hook_text":"SO CLOSE — #2!","reason":"Endgame ends with a #2 placement and 31,388 XP.","title":"😮‍💨 Runner-Up! Agonizing #2 Finish","description":"One spot away from the dub. So close it hurts. Follow for the redemption run!","tags":["#fortnite","#top2","#soclose","#battleroyale"]}]},

 "bandicam_2026-04-25_15-20-32-839.mp4": {"game":"Fortnite","summary":"Fortnite Blitz Royale — a full VICTORY ROYALE.","moments":[
   {"start_time":210,"end_time":225,"peak_time":222,"category":"INTENSE","virality_score":7,"hook_text":"FINAL CIRCLE!","reason":"Final-circle firefight right before the win.","title":"🔥 Final-Circle Firefight!","description":"The endgame that set up the dub. Would you have taken this fight? 👇","tags":["#fortnite","#fps","#endgame","#battleroyale"]},
   {"start_time":228,"end_time":258,"peak_time":256,"category":"WINNING","virality_score":10,"hook_text":"VICTORY ROYALE!","reason":"The '#1 VICTORY ROYALE' banner appears — match won.","title":"🏆 VICTORY ROYALE! #1 Win in Blitz Royale","description":"WINNER WINNER! Took the whole lobby down for the #1 dub. Follow for more wins! 🏆","tags":["#fortnite","#victoryroyale","#win","#1stplace"]}]},

 "bandicam_2026-04-25_15-25-59-007.mp4": {"game":"Fortnite","summary":"Fortnite Blitz Royale — a top-4 finish.","moments":[
   {"start_time":118,"end_time":135,"peak_time":128,"category":"INTENSE","virality_score":6,"hook_text":"BLITZ BATTLE!","reason":"Mid-game combat and loot fight.","title":"⚔️ Blitz Royale Battle!","description":"Scrapping through the mid-game. Rate the plays 1-10! 👇","tags":["#fortnite","#fps","#blitzroyale","#battleroyale"]},
   {"start_time":195,"end_time":215,"peak_time":212,"category":"LOSING","virality_score":7,"hook_text":"TOP 4!","reason":"Eliminated placing #4 on the endgame screen.","title":"😩 Top 4 — So Close to the Dub!","description":"Fought to a top-4 before getting clipped. What would you have done? 👇","tags":["#fortnite","#top4","#soclose","#battleroyale"]}]},

 "bandicam_2026-04-25_15-30-31-023.mp4": {"game":"Fortnite","summary":"Fortnite Blitz Royale — a clutch VICTORY ROYALE.","moments":[
   {"start_time":241,"end_time":256,"peak_time":250,"category":"INTENSE","virality_score":7,"hook_text":"FINAL FIGHT!","reason":"The last firefight before the win.","title":"🔥 Final Fight Before the Win!","description":"This is the fight that sealed the victory. Clutch or kick? 👇","tags":["#fortnite","#fps","#endgame","#battleroyale"]},
   {"start_time":270,"end_time":300,"peak_time":298,"category":"WINNING","virality_score":10,"hook_text":"VICTORY ROYALE!","reason":"The '#1 VICTORY ROYALE' banner appears — match won.","title":"🏆 VICTORY ROYALE! Clutch #1 Win","description":"Clutched the whole lobby for the #1 dub! Drop a 🏆 if you felt this one.","tags":["#fortnite","#victoryroyale","#win","#clutch"]}]},

 "bandicam_2026-04-25_15-36-34-073.mp4": {"game":"Fortnite","summary":"Short Fortnite match ending in an early elimination.","moments":[
   {"start_time":44,"end_time":61,"peak_time":57,"category":"INTENSE","virality_score":6,"hook_text":"SKIRMISH!","reason":"Close-quarters sword-and-gun skirmish with an enemy.","title":"⚔️ Sword & Gun Skirmish!","description":"Up close and personal in this one. Would you have swapped weapons? 👇","tags":["#fortnite","#fps","#battleroyale"]},
   {"start_time":90,"end_time":111,"peak_time":108,"category":"LOSING","virality_score":6,"hook_text":"SO CLOSE!","reason":"Eliminated placing #13 after a scrap.","title":"💀 Eliminated at #13","description":"Got clipped mid-fight. Rate the plays and tell me what went wrong! 👇","tags":["#fortnite","#fortnitefail","#battleroyale"]}]},

 "bandicam_2026-04-25_15-39-26-955.mp4": {"game":"Fortnite","summary":"Fortnite match ending in a top-5 finish.","moments":[
   {"start_time":140,"end_time":156,"peak_time":150,"category":"INTENSE","virality_score":6,"hook_text":"CQB FIGHT!","reason":"Close-quarters battle with an enemy player mid-game.","title":"⚔️ Close-Quarters Battle!","description":"Tight fight in the mid-game. Clutch or kick? 👇","tags":["#fortnite","#fps","#battleroyale"]},
   {"start_time":178,"end_time":200,"peak_time":197,"category":"LOSING","virality_score":7,"hook_text":"TOP 5!","reason":"Eliminated placing #5 on the endgame screen.","title":"😤 Top 5 Finish!","description":"So close to the dub — locked a top-5. Follow for the redemption! 👇","tags":["#fortnite","#top5","#soclose","#battleroyale"]}]},

 "bandicam_2026-04-25_15-43-45-660.mp4": {"game":"Fortnite","summary":"Fortnite Blitz Royale — another VICTORY ROYALE.","moments":[
   {"start_time":220,"end_time":235,"peak_time":230,"category":"INTENSE","virality_score":7,"hook_text":"ENDGAME!","reason":"Endgame firefight before the win.","title":"🔥 Endgame Firefight!","description":"The final scraps before the dub. Would you have pushed? 👇","tags":["#fortnite","#fps","#endgame","#battleroyale"]},
   {"start_time":236,"end_time":266,"peak_time":264,"category":"WINNING","virality_score":10,"hook_text":"VICTORY ROYALE!","reason":"The '#1 VICTORY ROYALE' banner appears — match won.","title":"🏆 VICTORY ROYALE! Another #1 Dub","description":"Another lobby, another #1 dub! Follow if you want the win compilation. 🏆","tags":["#fortnite","#victoryroyale","#win","#1stplace"]}]},

 "2026-04-19_18-41-28.mp4": {"game":"GTA V","summary":"GTA V story session — an armed heist and a passed mission.","moments":[
   {"start_time":372,"end_time":417,"peak_time":405,"category":"INTENSE","virality_score":8,"hook_text":"THE HEIST!","reason":"Armed shootout through a red-lit interior during a heist.","title":"💰 GTA Heist Shootout!","description":"Guns out, alarms blaring — this heist got loud. Watch till the end! 🔫","tags":["#gta","#gta5","#heist","#gaming"]},
   {"start_time":1518,"end_time":1548,"peak_time":1546,"category":"WINNING","virality_score":8,"hook_text":"MISSION PASSED!","reason":"The green 'MISSION PASSED' screen appears — objective completed.","title":"✅ Mission Passed in GTA V!","description":"Pulled it off clean — MISSION PASSED. Drop a ✅ if you love GTA missions!","tags":["#gta","#gta5","#missionpassed","#gaming"]}]},
}

def main():
    results = []
    for fname, plan in PLANS.items():
        path = os.path.join(UP, fname)
        if not os.path.exists(path):
            print(f"SKIP missing {fname}"); continue
        job_id = uuid.uuid4().hex
        out_dir = os.path.join(SHORTS, job_id)
        try:
            norm = validate_plan(plan)
            print(f"\n=== {fname}  ({len(norm['moments'])} moments) -> job {job_id[:8]} ===", flush=True)
            shorts = render_shorts(path, norm, out_dir,
                                   progress_callback=lambda c,t,m: print(f"   {m}", flush=True),
                                   smooth=False)
            ok = sum(1 for s in shorts if s.get("output_path"))
            result = {"shorts_dir": job_id, "video_id": job_id, "frame_count": 0,
                      "moment_count": len(norm["moments"]), "short_count": ok,
                      "game": norm.get("game",""), "summary": norm.get("summary",""),
                      "shorts": shorts}
            jq.create_job(job_id, filename=fname, fps=2, video_id=job_id)
            jq.mark_completed(job_id, result)
            results.append((fname, job_id, ok))
            print(f"   DONE {ok}/{len(norm['moments'])} shorts", flush=True)
        except Exception as e:
            print(f"   ERROR {fname}: {e}"); traceback.print_exc()
    print("\n===== SUMMARY =====")
    for fname, job_id, ok in results:
        print(f"  {ok} shorts  job={job_id}  {fname}")
    print(f"Total videos: {len(results)}")

if __name__ == "__main__":
    main()
