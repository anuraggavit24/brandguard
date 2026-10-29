"""Checks for the AI reviewer (model mocked). Run: python test_ai_review.py"""
import json, os, subprocess, sys, tempfile
os.environ["DATA_DIR"] = tempfile.mkdtemp()
os.environ.pop("GROQ_API_KEY", None)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import main
import ai_review as AIR
from fastapi.testclient import TestClient

wav = os.path.join(os.environ["DATA_DIR"], "t.mp4")
subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i", "sine=frequency=440:duration=3", "-f", "lavfi", "-i",
                "color=c=navy:s=320x240:d=3", "-shortest", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", wav],
               capture_output=True)
SCRIPT = {"t": "", "conf": 0.95}
main.transcribe = lambda w, l, g: [{"start": float(i), "end": float(i) + 1, "text": t, "conf": SCRIPT["conf"]}
                                   for i, t in enumerate(SCRIPT["t"].split("||"))] if SCRIPT["t"] else []
fails = []


def check(name, cond, extra=""):
    print(("PASS " if cond else "FAIL ") + name + (f"  [{extra}]" if extra and not cond else ""))
    if not cond:
        fails.append(name)


REG = {"banned_phrases": ["risk free", "guaranteed returns"], "terminology": [], "avoid_tone": [], "confidential": ["margin slab"]}
UNITS = [{"src": "audio", "time": 1.0, "text": "Your money is totally safe with us, nothing can go wrong", "conf": 0.95},
         {"src": "audio", "time": 2.0, "text": "Our 2 BHK is priced at 1.3 crore", "conf": 0.5},
         {"src": "audio", "time": 3.0, "text": "This is a risk free offer", "conf": 0.95}]


def con(**kw):
    d = {"line": 0, "quote": "Your money is totally safe with us", "category": "paraphrase", "matches_banned": "risk free",
         "reason": "Promises no risk.", "alternative": "Talk to us about how we protect your booking"}
    d.update(kw)
    return d


def run(concerns, units=UNITS, reg=REG):
    return AIR.verify({"summary": "A sales pitch.", "tone_consistent": True, "concerns": concerns}, units, reg)


# ---------------- verification of model output
r = run([con()])
check("a real paraphrase is kept", len(r["concerns"]) == 1 and r["concerns"][0]["matches"] == "risk free")
check("a safe alternative is kept", r["concerns"][0]["alternative"].startswith("Talk to us"))
check("an invented quote is dropped", run([con(quote="We promise a flat in the sky")])["concerns"] == [])
check("quote matching ignores case and punctuation", len(run([con(quote="your MONEY is totally safe, with us")])["concerns"]) == 1)
check("paraphrase naming a phrase that is not the company's banned list is dropped", run([con(matches_banned="no worries")])["concerns"] == [])
check("exact banned phrase is left to the engine", run([con(quote="This is a risk free offer", matches_banned="risk free")])["concerns"] == [])
check("alternative with a banned phrase is dropped but the concern stays",
      run([con(alternative="It is risk free for you")])["concerns"][0]["alternative"] == "")
check("alternative with a new price is dropped", run([con(alternative="Pay only 90 lakh for it")])["concerns"][0]["alternative"] == "")
check("unknown category is dropped", run([con(category="vibes")])["concerns"] == [])
check("duplicate concern is shown once", len(run([con(), con()])["concerns"]) == 1)
check("low-confidence note only for lines the recogniser was unsure about",
      len(run([con(category="low_confidence", quote="Our 2 BHK is priced at 1.3 crore", matches_banned="")])["concerns"]) == 1
      and run([con(category="low_confidence", quote="Your money is totally safe with us", matches_banned="")])["concerns"] == [])
check("garbage model output gives an empty result", AIR.verify("nonsense", UNITS, REG)["concerns"] == [])
check("at most 8 concerns", len(run([con(category="tone", quote=f"word{i}", matches_banned="") for i in range(20)],
                                   units=[{"src": "audio", "time": 0, "text": " ".join(f"word{i}" for i in range(20)), "conf": 1}])["concerns"]) <= 8)

# ---------------- cache, caps, failures
CALLS = []
REPLY = {"summary": "Pitch", "tone_consistent": True, "concerns": [con()]}


def fake(system, user):
    CALLS.append(user)
    if "confidential" in user or "margin slab" in user:
        raise AssertionError("confidential term sent to the model")
    return json.dumps(REPLY)


AIR.call_model = fake
res, st = AIR.get_or_run(1, UNITS, REG)
check("first review calls the model", st == "fresh" and len(CALLS) == 1 and res["concerns"])
res2, st2 = AIR.get_or_run(1, UNITS, REG)
check("identical content makes no second AI call", st2 == "cached" and len(CALLS) == 1)
res3, st3 = AIR.get_or_run(2, UNITS, REG)
check("another company is reviewed on its own rules", st3 == "fresh" and len(CALLS) == 2)
reg2 = dict(REG, banned_phrases=REG["banned_phrases"] + ["sure thing"])
_, st4 = AIR.get_or_run(1, UNITS, reg2)
check("changed rules make the old review stale", st4 == "fresh" and len(CALLS) == 3)
AIR.DAILY_CAP = 0
_, st5 = AIR.get_or_run(1, UNITS[:1], REG)
check("daily cap stops new calls", st5 == "capped" and len(CALLS) == 3)
AIR.DAILY_CAP = 200


def boom(system, user):
    raise RuntimeError("down")


AIR.call_model = boom
_, st6 = AIR.get_or_run(1, UNITS[:2], REG)
check("a failing model returns 'error' and does not raise", st6 == "error")
check("a failure is not cached", AIR._rows("SELECT 1 FROM ai_reviews WHERE key=?", (AIR.cache_key(1, UNITS[:2], REG),)) == [])

# ---------------- end to end
CALLS.clear()
AIR.call_model = fake
BASE = "Welcome to Demo Heights Wakad||Our 2 BHK is 1.3 crore"


def submit(c, text, conf=0.95):
    SCRIPT["t"], SCRIPT["conf"] = text, conf
    r = c.post("/upload", data={"brand_id": "1", "language": "en", "project_id": ""},
               files={"file": ("t.mp4", open(wav, "rb"), "video/mp4")}, follow_redirects=False)
    sid = int(r.headers["location"].rsplit("/", 1)[-1])
    row = main.q("SELECT * FROM submissions WHERE id=?", (sid,))[0]
    return sid, row["status"], main.rep_of(row)


with TestClient(main.app) as c:
    c.get("/enter/admin")
    c.post("/admin/rules/add", data={"field": "banned_phrases", "value": "risk free"})
    c.get("/logout"); c.get("/enter/partner")
    REPLY["concerns"] = [con(quote="your money is totally safe", line=2), {
        "line": 2, "quote": "totally safe", "category": "tone", "matches_banned": "", "reason": "Pushy", "alternative": ""}]
    text = BASE + "||Your money is totally safe with us"
    sid, st, rep = submit(c, text)
    types = [f["type"] for f in rep["findings"]]
    check("paraphrase becomes a human-check finding, not a rejection", "BANNED_PARAPHRASE" in types and st == "SUPERVISION", f"{st} {types}")
    check("advice findings are notes", all(f["status"] == "NOTE" for f in rep["findings"] if f["type"] == "AI_TONE"))
    check("AI review summary is stored", rep["ai_review"]["state"] == "fresh" and rep["ai_review"]["summary"] == "Pitch")
    n = len(CALLS)
    sid2, st2, rep2 = submit(c, text)
    check("the same content again makes no new AI call", len(CALLS) == n and rep2["ai_review"]["state"] == "cached")
    check("submitter sees the AI card but no decision buttons", "AI review" in c.get(f"/s/{sid}").text and "add to banned phrases" not in c.get(f"/s/{sid}").text)

    c.get("/logout"); c.get("/enter/admin")
    page = c.get(f"/s/{sid}").text
    check("builder sees the decision buttons", "add to banned phrases" in page and "harmless: dismiss" in page)
    i = [f["i"] for f in rep["findings"] if f["type"] == "BANNED_PARAPHRASE"][0]
    c.post(f"/ai/{sid}/{i}/dismiss")
    row = main.q("SELECT * FROM submissions WHERE id=?", (sid,))[0]
    rep_d = main.rep_of(row)
    check("dismissal clears the open count but never auto-approves", rep_d["supervision"] == 0 and row["status"] == "SUPERVISION", f"{row['status']} {rep_d['supervision']}")
    c.get("/logout"); c.get("/enter/partner")
    sid3, st3, rep3 = submit(c, text)
    check("a dismissed wording is not raised again for this company", "BANNED_PARAPHRASE" not in [f["type"] for f in rep3["findings"]])

    REPLY["concerns"] = [con(quote="nothing can go wrong", line=2)]
    sid4, st4, rep4 = submit(c, BASE + "||Nothing can go wrong with this")
    i4 = [f["i"] for f in rep4["findings"] if f["type"] == "BANNED_PARAPHRASE"][0]
    c.get("/logout"); c.get("/enter/admin")
    c.post(f"/ai/{sid4}/{i4}/ban")
    c.get("/logout"); c.get("/enter/partner")
    check("confirming adds the wording to banned phrases", "nothing can go wrong" in [x.lower() for x in json.loads(main.q("SELECT registry FROM brands WHERE id=1")[0]["registry"])["banned_phrases"]])
    sid5, st5, rep5 = submit(c, BASE + "||Nothing can go wrong with this")
    check("after confirming, the engine itself flags the wording", st5 == "REJECTED" and "BANNED_PHRASE" in [f["type"] for f in rep5["findings"]], f"{st5}")
    c.get("/logout"); c.get("/enter/partner")
    check("a submitter cannot make the decision", c.post(f"/ai/{sid4}/{i4}/dismiss", follow_redirects=False).status_code == 303
          and not main.rep_of(main.q("SELECT * FROM submissions WHERE id=?", (sid4,))[0])["findings"][i4].get("dismissed"))

    # no key / no model: everything still works
    AIR.call_model = AIR._real_call_model
    sid6, st6, rep6 = submit(c, BASE + "||A brand new line of text")
    check("without an AI key the rules engine still decides", rep6["ai_review"]["state"] == "off" and st6 in ("AUTO_APPROVED", "SUPERVISION"))
    check("the page explains the AI review was not available", "AI review is not set up" in c.get(f"/s/{sid6}").text)

print("\n%d failed" % len(fails) if fails else "\nALL PASSED")
sys.exit(1 if fails else 0)
