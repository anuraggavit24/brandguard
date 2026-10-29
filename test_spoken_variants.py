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

print("\n%d failed" % len(fails) if fails else "\nALL PASSED")
sys.exit(1 if fails else 0)
