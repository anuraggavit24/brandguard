"""Checks for the setup checklist, the guided tour and invites to all projects. Run: python test_onboarding.py"""
import json, os, re, sys, tempfile
os.environ["DATA_DIR"] = tempfile.mkdtemp()
os.environ.pop("GROQ_API_KEY", None)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import main
import realestate as RE
from fastapi.testclient import TestClient

fails = []


def check(name, cond, extra=""):
    print(("PASS " if cond else "FAIL ") + name + (f"  [{extra}]" if extra and not cond else ""))
    if not cond:
        fails.append(name)


with TestClient(main.app) as a:
    a.post("/signup", data={"company": "Fresh Co", "name": "Nina", "email": "n@f.test", "password": "a-long-password-1", "industry": "tech"})
    home = a.get("/").text
    check("a new company sees the setup checklist", "Get started: 0 of 4 done" in home and "Invite your team" in home)
    check("the tour is on every page and starts by itself for a new user", 'id="tour-data"' in home and 'data-auto="1"' in home
          and "Take the tour" in home)
    steps = json.loads(re.search(r'<script type="application/json" id="tour-data"[^>]*>(.*?)</script>', home, re.S).group(1).replace("<\\/", "</"))
    check("builder tour covers rules, products, team, access, queue, disputes, lessons",
          [s["href"] for s in steps if s["href"]] == ["/", "/admin/rules", "/admin/projects", "/admin/team", "/admin/access", "/queue",
                                                       "/disputes", "/admin/learned", "/approvals"])
    check("a product company's tour says products, not projects", any(s["title"] == "Products and Facts" for s in steps))
    check("every tour step points at a real menu item", all(f'href="{s["href"]}"' in home for s in steps if s["href"]))
    a.get("/admin/rules")
    check("opening Brand Rules ticks the first step", "Get started: 1 of 4 done" in a.get("/").text)

    # invite before any product exists: the old dead end
    r = a.post("/admin/team/invite", data={"email": "dealer@f.test", "kind": "partner", "all_projects": "1"})
    check("an invite works with no products yet ('all products, including later')", "/invite/" in r.text, r.text[-300:])
    tok = re.search(r"/invite/([\w-]+)", r.text).group(1)
    check("the team page offers 'All products, including ones you add later'", "including ones you add later" in a.get("/admin/team").text)
    r = a.post("/admin/team/invite", data={"email": "nobody@f.test", "kind": "partner"})
    check("an invite with nothing chosen explains what to do", "All projects" in r.text or "at least one" in r.text)
    p = TestClient(main.app)
    p.post(f"/invite/{tok}", data={"name": "Dev Dealer", "password": "dealer-strong-pass"})
    dealer = main.q("SELECT id FROM users WHERE email='dealer@f.test'")[0]["id"]
    bid = main.q("SELECT id FROM brands WHERE name='Fresh Co'")[0]["id"]
    a.post("/admin/projects/add", data={"official_name": "Cloud Router X1", "aliases": ""})
    later = [x["id"] for x in RE.brand_projects(bid) if x["official_name"] == "Cloud Router X1"][0]
    check("a product added later is given to an 'all products' partner automatically", RE.can_use_project(dealer, later))
    a.post(f"/admin/projects/{later}/unit", data={"category": "product", "label": "Standard", "price": "4999", "source": "Price list"})
    check("inviting and adding products ticks those steps", "Get started: 3 of 4 done" in a.get("/").text, re.search(r"Get started: \d of 4", a.get("/").text).group(0))
    a.post("/admin/onboarding/hide")
    check("the checklist can be hidden", "Get started" not in a.get("/").text)

    ptour = p.get("/").text
    psteps = json.loads(re.search(r'id="tour-data"[^>]*>(.*?)</script>', ptour, re.S).group(1).replace("<\\/", "</"))
    check("the partner gets their own tour", [s["href"] for s in psteps if s["href"]][:3] == ["/", "/submit", "/bulk"])

print("\n%d failed" % len(fails) if fails else "\nALL PASSED")
sys.exit(1 if fails else 0)
