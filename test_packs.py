"""Checks for industry starter packs. Run: python test_packs.py"""
import json, os, subprocess, sys, tempfile
os.environ["DATA_DIR"] = tempfile.mkdtemp()
os.environ.pop("GROQ_API_KEY", None)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import main
import packs
import engine
from fastapi.testclient import TestClient

fails = []


def check(name, cond, extra=""):
    print(("PASS " if cond else "FAIL ") + name + (f"  [{extra}]" if extra and not cond else ""))
    if not cond:
        fails.append(name)


def flagged(reg, text):
    r = engine.review([{"start": 0, "end": 1, "text": text, "conf": 0.95}], reg, 0.65, check_prices=False)
    return [f["evidence"] for f in r["findings"] if f["type"] == "BANNED_PHRASE"]


# pack content and matching
reg = {}
packs.apply(reg, ["tech"])
check("general pack is always included", "100% safe" in reg["banned_phrases"])
check("industry pack is included", "unhackable" in reg["banned_phrases"])
check("other industries are not mixed in", "guaranteed cure" not in reg["banned_phrases"])
n = len(reg["banned_phrases"])
check("applying twice adds nothing", sum(packs.apply(reg, ["tech"]).values()) == 0 and len(reg["banned_phrases"]) == n)
check("a real claim is flagged", flagged(reg, "Our platform is 100% secure and unhackable") != [])
check("ordinary words are not flagged ('secure', 'insecure', 'procure')",
      flagged({"banned_phrases": ["cure"]}, "We secure your data and procure parts, nothing insecure") == [])
check("whole word still matches", flagged({"banned_phrases": ["cure"]}, "This is a cure for everything") == ["cure"])
check("phrases with a percent sign match", flagged({"banned_phrases": ["100% safe"]}, "It is 100% safe, trust us") == ["100% safe"])
check("Hindi/Marathi phrases match", flagged({"banned_phrases": ["पैसे दुप्पट"]}, "तुमचे पैसे दुप्पट होतील") == ["पैसे दुप्पट"])
check("everyday sentences are not flagged by any pack",
      all(flagged({"banned_phrases": sum((p["banned"] for p in list(packs.PACKS.values()) + [packs.GENERAL]), [])},
                  t) == [] for t in ["Welcome to our store, we are open daily", "Our team will call you back today",
                                     "The new model has a better camera and a longer battery", "Book a free site visit this weekend",
                                     "Fresh vegetables delivered to your door", "Apply online in five minutes"]))
check("every pack has a label and phrases", all(p["label"] and p["banned"] for p in packs.PACKS.values()))
check("no pack lists a phrase twice", all(len(p["banned"]) == len({x.lower() for x in p["banned"]}) for p in packs.PACKS.values()))

with TestClient(main.app) as c:
    check("signup page asks for the industry", "Your industry" in c.get("/signup").text and "Technology and software" in c.get("/signup").text)
    c.post("/signup", data={"company": "Acme Pharma", "name": "Asha", "email": "asha@acme.test",
                            "password": "a-long-password-1", "industry": "pharma"})
    brand = main.q("SELECT * FROM brands WHERE name='Acme Pharma'")[0]
    r = json.loads(brand["registry"])
    check("new company starts with the general and pharma rules", "no side effects" in r["banned_phrases"] and "miracle" in r["banned_phrases"])
    check("rules page shows them, editable", "no side effects" in c.get("/admin/rules").text and "Starter rules by industry" in c.get("/admin/rules").text)
    c.post("/admin/rules/pack", data={"pack": "food"})
    r2 = json.loads(main.q("SELECT registry FROM brands WHERE id=?", (brand["id"],))[0]["registry"])
    check("adding another pack merges it", "boosts immunity" in r2["banned_phrases"] and "no side effects" in r2["banned_phrases"])
    before = len(r2["banned_phrases"])
    c.post("/admin/rules/pack", data={"pack": "food"})
    r3 = json.loads(main.q("SELECT registry FROM brands WHERE id=?", (brand["id"],))[0]["registry"])
    check("adding the same pack again changes nothing", len(r3["banned_phrases"]) == before)
    c.post("/admin/rules/pack", data={"pack": "not-a-pack"})
    check("unknown pack is ignored", len(json.loads(main.q("SELECT registry FROM brands WHERE id=?", (brand["id"],))[0]["registry"])["banned_phrases"]) == before)
    c.post("/admin/rules/remove", data={"field": "banned_phrases", "value": "miracle"})
    r4 = json.loads(main.q("SELECT registry FROM brands WHERE id=?", (brand["id"],))[0]["registry"])
    check("a pack phrase can be removed by the company", "miracle" not in r4["banned_phrases"])
    c.get("/logout")
    c.post("/signup", data={"company": "Other Co", "name": "O", "email": "o@other.test", "password": "a-long-password-1", "industry": "bogus"})
    r5 = json.loads(main.q("SELECT registry FROM brands WHERE name='Other Co'")[0]["registry"])
    check("a made-up industry falls back to the general rules", "100% safe" in r5["banned_phrases"] and "no side effects" not in r5["banned_phrases"])

print("\n%d failed" % len(fails) if fails else "\nALL PASSED")
sys.exit(1 if fails else 0)
