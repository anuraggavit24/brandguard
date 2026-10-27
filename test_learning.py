"""Checks for the lessons learner. Run: python test_learning.py"""
import os, subprocess, sys, tempfile
os.environ["DATA_DIR"] = tempfile.mkdtemp()
os.environ.pop("GROQ_API_KEY", None)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import main
import learning as LRN
from fastapi.testclient import TestClient

wav = os.path.join(os.environ["DATA_DIR"], "t.mp4")
subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i", "sine=frequency=440:duration=3", "-f", "lavfi", "-i",
                "color=c=navy:s=320x240:d=3", "-shortest", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", wav],
               capture_output=True)
SCRIPT = {"t": ""}
main.transcribe = lambda w, l, g: [{"start": float(i), "end": float(i) + 1, "text": t, "conf": 0.95}
                                   for i, t in enumerate(SCRIPT["t"].split("||"))] if SCRIPT["t"] else []
fails = []


def check(name, cond, extra=""):
    print(("PASS " if cond else "FAIL ") + name + (f"  [{extra}]" if extra and not cond else ""))
    if not cond:
        fails.append(name)


def submit(c, text):
    SCRIPT["t"] = text
    r = c.post("/upload", data={"brand_id": "1", "language": "en", "project_id": ""},
               files={"file": ("t.mp4", open(wav, "rb"), "video/mp4")}, follow_redirects=False)
    sid = int(r.headers["location"].rsplit("/", 1)[-1])
    row = main.q("SELECT * FROM submissions WHERE id=?", (sid,))[0]
    return sid, row["status"], main.rep_of(row)


def types(rep):
    return [f["type"] for f in rep["findings"]]


GOOD = "Welcome to Demo Heights Wakad||Our 2 BHK is 1.3 crore||We never give guaranteed returns on any flat"
BAD = "Welcome to Demo Heights Wakad||Our 2 BHK is 1.3 crore||Guaranteed returns, price will double in two years"
NEW = "Welcome to Demo Heights Wakad||Our 2 BHK is 1.3 crore||Customers often ask about guaranteed returns from this flat"

with TestClient(main.app) as c:
    c.get("/enter/partner")
    sid1, st, rep = submit(c, GOOD)
    check("1: negated sentence is wrongly rejected before any lesson", st == "REJECTED" and "BANNED_PHRASE" in types(rep), f"{st} {types(rep)}")
    c.post(f"/dispute/{sid1}", data={"note": "I said we do NOT offer guaranteed returns. It is a disclaimer.", "said": ""})
    check("2: dispute raised", main.q("SELECT status FROM submissions WHERE id=?", (sid1,))[0]["status"] == "DISPUTED")
    # before-state for replay
    c.get("/logout"); c.get("/enter/admin")
    c.post(f"/decide/{sid1}", data={"decision": "approve", "note": "Negated sentence, the phrase is a disclaimer. Not a claim."})
    ls = LRN.list_lessons(1)
    check("3: a lesson was written", len(ls) >= 1 and ls[0]["trigger"] == "guaranteed returns", str([dict(x) for x in ls]))
    check("3: lesson is active and has a cue", bool(ls) and ls[0]["active"] == 1 and "NOT" in ls[0]["cue"].split(), str([dict(x) for x in ls]))
    check("3: lesson page loads", c.get("/admin/learned").status_code == 200)

    c.get("/logout"); c.get("/enter/partner")
    sid2, st, rep = submit(c, GOOD)
    check("4: same wording now passes by precedent", st == "AUTO_APPROVED" and "BANNED_PHRASE" not in types(rep), f"{st} {types(rep)}")
    check("4: report says which decision it relied on", bool(rep.get("cleared")) and rep["cleared"][0]["source_sub"] == sid1)
    check("4: report page shows the cleared card", "Cleared by earlier builder decisions" in c.get(f"/s/{sid2}").text)
    check("4: usage is recorded", LRN.stats(1)["cleared"] >= 1)

    sid3, st, rep = submit(c, BAD)
    check("5: a real violation is still rejected", st == "REJECTED" and "BANNED_PHRASE" in types(rep), f"{st} {types(rep)}")
    sid4, st, rep = submit(c, NEW)
    check("6: a different context is still flagged (no negation)", "BANNED_PHRASE" in types(rep) and not rep.get("cleared"), f"{st} {types(rep)}")
    sid5, st, rep = submit(c, "Welcome to Demo Heights Wakad||Our 2 BHK is 1.3 crore||We never give guaranteed returns||Guaranteed returns are certain for you")
    check("7: one clean and one real use in the same video is still flagged", "BANNED_PHRASE" in types(rep), f"{st} {types(rep)}")

    c.get("/logout"); c.get("/enter/admin")
    lid = LRN.list_lessons(1)[0]["id"]
    c.post("/admin/learned/toggle", data={"lesson_id": str(lid), "on": "0"})
    c.get("/logout"); c.get("/enter/partner")
    sid6, st, rep = submit(c, GOOD)
    check("8: switching the lesson off restores the rejection", st == "REJECTED" and "BANNED_PHRASE" in types(rep), f"{st}")

    # prices are never learned
    sid7, st, rep = submit(c, "Welcome to Demo Heights Wakad||Our 2 BHK is only 1.9 crore")
    c.post(f"/dispute/{sid7}", data={"note": "I think the price is right", "said": "1.3 crore"})
    c.get("/logout"); c.get("/enter/admin")
    before = len(LRN.list_lessons(1))
    c.post(f"/decide/{sid7}", data={"decision": "approve", "note": "Allowed this one by hand."})
    check("9: a price dispute creates no lesson", len(LRN.list_lessons(1)) == before)

    # AI says it was a real claim -> saved switched off
    LRN.summarise = lambda *a: {"summary": "Builder allowed a real claim.", "why": "x", "category": "other",
                                "is_wording_mistake": False, "cue_words": ["not"]}
    c.get("/logout"); c.get("/enter/partner")
    sid8, st, rep = submit(c, "Welcome to Demo Heights Wakad||Our 2 BHK is 1.3 crore||This is the best in city for families")
    c.post(f"/dispute/{sid8}", data={"note": "Fine by me", "said": ""})
    c.get("/logout"); c.get("/enter/admin")
    c.post(f"/decide/{sid8}", data={"decision": "approve", "note": "Allowed once for this client."})
    row = [x for x in LRN.list_lessons(1) if x["trigger"] == "best in city"]
    check("10: AI judged 'real claim' -> lesson saved OFF, needs a builder", row and row[0]["active"] == 0 and row[0]["pending_reason"], str([dict(x) for x in row]))

    # isolation between companies
    check("11: lessons are per company", LRN.list_lessons(2) == [])
    # helpers
    check("12: cue words must exist in the sentence", LRN.clean_cue(["invented", "not"], ["NOT"], ["flat"]) == ["NOT"])

print("\n%d failed" % len(fails) if fails else "\nALL PASSED")
sys.exit(1 if fails else 0)
