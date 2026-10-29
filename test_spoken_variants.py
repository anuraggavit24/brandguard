"""Regression for a real Marathi clip (Clip5): every claim must be checked, whatever spelling speech-to-text used.
Run: python test_spoken_variants.py"""
import json, os, sys, tempfile
os.environ["DATA_DIR"] = tempfile.mkdtemp()
os.environ.pop("GROQ_API_KEY", None)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import main
import phon
import amounts
import realestate as RE
from fastapi.testclient import TestClient

fails = []


def check(name, cond, extra=""):
    print(("PASS " if cond else "FAIL ") + name + (f"  [{extra}]" if extra and not cond else ""))
    if not cond:
        fails.append(name)


check("spellings share a skeleton: possession", phon.skel("पझेशन") == phon.skel("पोजेशन") == phon.skel("पजेशन"))
check("spellings share a skeleton: bathroom", phon.skel("बाथरूम") == phon.skel("बात्रुम") == phon.skel("बाथरुम"))
check("spellings share a skeleton: December", phon.skel("डिसेंबर") == phon.skel("डेसेंबर"))
check("English and Marathi place name match by sound", phon.latin_skel("Wakad") == phon.latin_skel("वाकड"))
check("misheard lakh is read as lakh", amounts.extract_amounts("5 लाक रुपई") == [{"value": 500000, "spoken": "5 लाक रुपई"}])
check("लाकूड (wood) is not a lakh", amounts.extract_amounts("5 लाकूड") == [])
check("लोक (people) is not a lakh", amounts.extract_amounts("5 लोक आले") == [])
check("Devanagari text keeps its vowel signs when folded", "बुकिंग" in RE._fold("आनी तुम्ही बुकिंग अमाउंट"))

CLIP5 = ["Hello Punekar, Demo Hights, हे अपला प्रोजेक्ट नवीन लॉंच होता है, इथे तुमाला साधारान 2 BHK फ्लाट, हे एक कोटी 30 लाखा परेंता भिटेल,",
         "आनी तुम्ही बुकिंग अमाउंट ही मिनिमम 5 लाक रुपई हाइट्स, वाकड ब्रिच इतुन 12 मिनिट बाई कार हाइट्स, जर तुम्ही 3 BHK बुकिंग करता हॅंस असल, तो तुम्हाला 1 कवर्ड पार्किंग फ्री हाइट्स, पोजेशन तुम्हाला डेसेंबर 2028 मदे भे",
         "बात्रुम दुमाला दोन दिले जाती"]

with TestClient(main.app) as c:
    u = main.q("SELECT * FROM users WHERE id=2")[0]
    reg = json.loads(main.q("SELECT registry FROM brands WHERE id=1")[0]["registry"])
    pid = [p["id"] for p in RE.brand_projects(1) if p["official_name"] == "Demo Heights"][0]

    def run(lines):
        segs = [{"start": float(i * 10), "end": float(i * 10 + 5), "text": t, "conf": 0.9} for i, t in enumerate(lines)]
        rep = main.analyze(u, 1, segs, "", reg, hint_pid=pid)
        return rep, {c_["kind"]: c_["verdict"] for c_ in rep["claims"]}

    rep, got = run(CLIP5)
    want = {"price", "booking", "possession", "offer", "distance", "bathrooms"}
    check("Clip5: all six claims are found", set(got) == want, str(got))
    check("Clip5: all six are verified and the clip passes", all(v == "VERIFIED" for v in got.values()) and rep["verdict"].startswith("PASS"), str(got))
    for name, lines, kind in [
        ("wrong booking amount", ["Demo Heights मध्ये बुकिंग अमाउंट फक्त 3 लाक रुपई"], "booking"),
        ("earlier possession date", ["Demo Heights पोजेशन तुम्हाला डेसेंबर 2027 मदे"], "possession"),
        ("shorter travel time", ["Demo Heights वाकड ब्रिच इतुन 5 मिनिट बाई कार"], "distance"),
        ("wrong bathroom count", ["Demo Heights 2 BHK बात्रुम तुम्हाला तीन मिळतील"], "bathrooms")]:
        rep, got = run(lines)
        check(f"misspelled but wrong claim is caught: {name}", got.get(kind) == "VIOLATION", str(got))

# a video whose speech is fine but whose on-screen text makes investment promises (OCR misread MONEY as MENEY)
check("near match: one misread letter", main.near_banned("INVEST TODAY - WATCH YOUR MENEY GROW", ["watch your money grow"]) == ["watch your money grow"])
check("near match: an exact phrase is left to the exact check", main.near_banned("watch your money grow", ["watch your money grow"]) == [])
check("near match: different words are not matched", main.near_banned("watch our homes grow", ["watch your money grow"]) == [])
check("near match: short words must be exact", main.near_banned("no hidden charge", ["no hidden charges"]) == ["no hidden charges"]
      and main.near_banned("to hidden charges", ["no hidden charges"]) == [])
with TestClient(main.app) as c:
    reg = json.loads(main.q("SELECT registry FROM brands WHERE id=1")[0]["registry"])
    check("demo company starts with the industry starter rules", "double your earnings" in reg["banned_phrases"] and len(reg["banned_phrases"]) > 100)
    segs = [{"start": 0.0, "end": 3.0, "text": "Welcome to Demo Heights in Wakad, Pune. A 2 BHK at 1.3 crore.", "conf": 0.9}]
    screen = {"lines": [{"start": 1.0, "end": 1.5, "text": l, "raw": l, "conf": 0.95} for l in
                        ["DEMO HEIGHTS", "PRICE: 1.3 cr", "INVEST TODAY - WATCH YOUR MENEY GROW", "DOUBLE YOUR EARNINGS IN THE NEXT :"]],
              "frames": 10, "total": 10, "partial": False}
    rep = main.analyze(u, 1, segs, "", reg, hint_pid=pid, screen=screen)
    ty = [(f["type"], f["status"]) for f in rep["findings"]]
    check("on-screen 'double your earnings' is a violation", ("BANNED_PHRASE", "FLAG") in ty, str(ty))
    check("on-screen misread 'watch your meney grow' goes to a person", ("BANNED_PHRASE_LIKELY", "SUPERVISION") in ty, str(ty))
    check("the video is rejected, not approved", rep["verdict"].startswith("REJECT"), rep["verdict"])
    check("a commission rate is caught even without the exact confidential phrase",
          main.confidential_figures("Channel partners get 2% commission on every booking", ["dealer commission"]) != [])
    check("Marathi spelling of commission with a rate is caught", main.confidential_figures("तुम्हाला 2 टक्के कमिशन मिळेल", ["dealer commission"]) != [])
    check("the word alone, with no figure, is not flagged", main.confidential_figures("ask us about our commission policy", ["dealer commission"]) == [])
    rep2 = main.analyze(u, 1, [{"start": 0.0, "end": 3.0, "text": "Demo Heights in Wakad, 2 BHK at 1.3 crore, and partners get 2% commission", "conf": 0.9}],
                        "", reg, hint_pid=pid)
    check("a spoken commission rate needs a person", ("CONFIDENTIAL_LIKELY", "SUPERVISION") in [(f["type"], f["status"]) for f in rep2["findings"]]
          and not rep2["verdict"].startswith("PASS"), rep2["verdict"])
    import ai_review as AIR
    units = AIR.units_from(rep["inputs"])
    check("the AI reviewer reads on-screen text as well as speech", any(x["src"] == "screen" and "EARNINGS" in x["text"] for x in units)
          and any(x["src"] == "audio" for x in units))

print("\n%d failed" % len(fails) if fails else "\nALL PASSED")
sys.exit(1 if fails else 0)
