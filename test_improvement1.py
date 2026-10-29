"""Checks for wording/tone rules, suggested rewrites, speech clarity and the replay. Run: python test_improvement1.py"""
import json, os, subprocess, sys, tempfile
os.environ["DATA_DIR"] = tempfile.mkdtemp()
os.environ.pop("GROQ_API_KEY", None)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import main
import learning as LRN
import rewrite as RW
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


def submit(c, text, conf=0.95):
    SCRIPT["t"], SCRIPT["conf"] = text, conf
    r = c.post("/upload", data={"brand_id": "1", "language": "en", "project_id": ""},
               files={"file": ("t.mp4", open(wav, "rb"), "video/mp4")}, follow_redirects=False)
    sid = int(r.headers["location"].rsplit("/", 1)[-1])
    row = main.q("SELECT * FROM submissions WHERE id=?", (sid,))[0]
    return sid, row["status"], main.rep_of(row)


def types(rep):
    return [f["type"] for f in rep["findings"]]


BASE = "Welcome to Demo Heights Wakad||Our 2 BHK is 1.3 crore"

with TestClient(main.app) as c:
    c.get("/enter/admin")
    c.post("/admin/rules/add", data={"field": "terminology", "value": "cheap => affordable"})
    c.post("/admin/rules/add", data={"field": "avoid_tone", "value": "super duper"})
    check("rules page lists the new rule kinds", "Preferred wording" in c.get("/admin/rules").text)
    c.get("/logout"); c.get("/enter/partner")

    sid, st, rep = submit(c, BASE + "||This is a cheap flat in a super duper location")
    check("terminology note does not block approval", st == "AUTO_APPROVED", f"{st} {types(rep)}")
    check("terminology and tone are noted", "TERMINOLOGY" in types(rep) and "TONE" in types(rep), str(types(rep)))
    check("notes are advice only", all(f["status"] == "NOTE" for f in rep["findings"] if f["type"] in ("TERMINOLOGY", "TONE")))
    sid2, st2, rep2 = submit(c, BASE + "||cheap||cheap||cheap flat")
    check("repeated advice is shown once", types(rep2).count("TERMINOLOGY") == 1, str(types(rep2)))
    page = c.get(f"/s/{sid}").text
    check("report shows suggestion section and button", "Wording and tone suggestions" in page and "Suggest compliant wording" in page)

    i = [f["i"] for f in rep["findings"] if f["type"] == "TERMINOLOGY"][0]
    c.post(f"/suggest/{sid}/{i}")
    page = c.get(f"/s/{sid}").text
    check("rule-based rewrite replaces the word", "This is a affordable flat" in page or "affordable flat" in page)
    n = len(main.q("SELECT 1 FROM audit WHERE action='REWRITE_SUGGESTED'"))
    c.post(f"/suggest/{sid}/{i}")
    check("a suggestion is created once", len(main.q("SELECT 1 FROM audit WHERE action='REWRITE_SUGGESTED'")) == n)

    # AI rewrite guards (model is mocked)
    reg = {"banned_phrases": ["guaranteed returns"], "confidential": ["margin slab"]}
    orig = "We offer guaranteed returns on this 2 BHK for 1.3 crore"
    check("safe rewrite accepted", RW.check_rewrite(orig, "This 2 BHK is priced at 1.3 crore", reg) == "")
    check("rewrite still containing a banned phrase is rejected", "restricted" in RW.check_rewrite(orig, "Guaranteed returns on 1.3 crore", reg))
    check("rewrite with a new price is rejected", "price" in RW.check_rewrite(orig, "This 2 BHK is only 90 lakh", reg))
    check("rewrite with a new percentage is rejected", "percentage" in RW.check_rewrite(orig, "Get 20% off this 2 BHK for 1.3 crore", reg))
    check("unchanged rewrite is rejected", RW.check_rewrite(orig, orig, reg) == "unchanged")
    check("confidential term in rewrite is rejected", "restricted" in RW.check_rewrite(orig, "see our margin slab", reg))
    text, err = RW.ai_rewrite(orig, "guaranteed returns", "banned", reg)
    check("no AI key means a clear message, no crash", text is None and "not set up" in err)

    # voices: unclear speech never auto-approves
    sid3, st3, rep3 = submit(c, BASE, conf=0.3)
    check("very unclear speech goes to a person", st3 == "SUPERVISION" and "SPEECH_UNCLEAR" in types(rep3), f"{st3} {types(rep3)}")
    check("voice stats are stored", rep3.get("voice", {}).get("avg") == 0.3)
    sid4, st4, rep4 = submit(c, BASE, conf=0.85)
    check("normal speech is unaffected", st4 == "AUTO_APPROVED" and "SPEECH_UNCLEAR" not in types(rep4), f"{st4}")

    # replay: one overturned wording dispute and one upheld real violation
    sidA, stA, repA = submit(c, "Welcome to Demo Heights Wakad||Our 2 BHK is 1.3 crore||We never give guaranteed returns")
    sidB, stB, repB = submit(c, "Welcome to Demo Heights Wakad||Our 2 BHK is 1.3 crore||Guaranteed returns, price will double")
    check("replay setup: both rejected", stA == "REJECTED" and stB == "REJECTED")
    c.post(f"/dispute/{sidA}", data={"note": "I said never. It is a disclaimer.", "said": ""})
    c.post(f"/dispute/{sidB}", data={"note": "Please look again", "said": ""})
    c.get("/logout"); c.get("/enter/admin")
    c.post(f"/decide/{sidB}", data={"decision": "reject", "note": "Real claim, upheld."})
    r0 = main.replay(1)
    check("replay before any lesson: nothing clears", r0["cleared"] == 0)
    c.post(f"/decide/{sidA}", data={"decision": "approve", "note": "Negated sentence, a disclaimer, not a claim."})
    r1 = main.replay(1)
    check("replay after the lesson: the overturned dispute clears", r1["cleared"] == 1 and r1["overturned"] == 1, str(r1))
    check("replay: the upheld real violation is never wrongly cleared", r1["upheld"] == 1 and r1["wrongly_cleared"] == 0, str(r1))
    check("replay page opens", c.get("/admin/learned/replay").status_code == 200 and "Replay" in c.get("/admin/learned/replay").text)
    check("replay changes nothing in the database",
          main.q("SELECT status FROM submissions WHERE id=?", (sidB,))[0]["status"] == "REJECTED_FINAL")
    check("lessons page shows AI status and replay link", "Replay disputed videos" in c.get("/admin/learned").text)

# the real request/response path, with the network mocked
import requests as _rq


class _Resp:
    status_code, headers = 200, {}
    def __init__(self, content): self._c = content
    def raise_for_status(self): pass
    def json(self): return {"choices": [{"message": {"content": self._c}}]}


os.environ["GROQ_API_KEY"] = "test-key"
_orig_post = _rq.post
_rq.post = lambda *a, **k: _Resp(json.dumps({"rewrite": "This 2 BHK is priced at 1.3 crore"}))
t, e_ = RW.ai_rewrite("We offer guaranteed returns on this 2 BHK for 1.3 crore", "guaranteed returns", "banned", {"banned_phrases": ["guaranteed returns"]})
check("AI rewrite path works with a valid answer", t == "This 2 BHK is priced at 1.3 crore" and e_ is None, str((t, e_)))
_rq.post = lambda *a, **k: _Resp(json.dumps({"rewrite": "Guaranteed returns on this 2 BHK"}))
t, e_ = RW.ai_rewrite("We offer guaranteed returns on this 2 BHK", "guaranteed returns", "banned", {"banned_phrases": ["guaranteed returns"]})
check("AI answer that breaks the rules is discarded", t is None and "discarded" in e_, str((t, e_)))
_rq.post = lambda *a, **k: _Resp("not json at all")
t, e_ = RW.ai_rewrite("x y z", "x", "banned", {})
check("garbled AI answer does not crash", t is None and e_)
_rq.post = lambda *a, **k: _Resp(json.dumps({"summary": "Negated sentence", "why": "not a claim", "category": "negation",
                                            "is_wording_mistake": True, "cue_words": ["never", "invented"]}))
ai = LRN.summarise("BANNED_PHRASE", "guaranteed returns", "We never give guaranteed returns", "I said never", "ok")
check("lesson summary parses the model's JSON", ai and ai["is_wording_mistake"] is True and ai["category"] == "negation", str(ai))
check("invented cue words are dropped", LRN.clean_cue(ai["cue_words"], ["NOT"], ["NOT", "give"]) == ["NOT"])
_rq.post = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("network down"))
check("network failure gives no summary, no crash", LRN.summarise("BANNED_PHRASE", "x", "x y", "a", "b") is None)
_rq.post = _orig_post
os.environ.pop("GROQ_API_KEY", None)

print("\n%d failed" % len(fails) if fails else "\nALL PASSED")
sys.exit(1 if fails else 0)
