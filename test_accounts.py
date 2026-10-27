"""Checks for sign-up, login and invites. Run: python test_accounts.py"""
import os, re, sys, tempfile
os.environ["DATA_DIR"] = tempfile.mkdtemp()
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import main
import accounts as ACC
import realestate as RE
from fastapi.testclient import TestClient

fails = []


def check(name, cond, extra=""):
    print(("PASS " if cond else "FAIL ") + name + (f"  [{extra}]" if extra and not cond else ""))
    if not cond:
        fails.append(name)


def client():
    return TestClient(main.app)


with client() as c:
    check("home offers sign-up and sign-in", "/signup" in c.get("/").text and "/login" in c.get("/").text)
    r = c.post("/signup", data={"company": "Acme Homes", "name": "Asha", "email": "asha@acme.test", "password": "short"})
    check("weak password rejected", "at least 10" in r.text and not main.q("SELECT 1 FROM users WHERE email='asha@acme.test'"))
    r = c.post("/signup", data={"company": "Acme Homes", "name": "Asha", "email": "bad-email", "password": "a-long-password-1"})
    check("bad email rejected", "valid email" in r.text)
    r = c.post("/signup", data={"company": "Acme Homes", "name": "Asha", "email": "asha@acme.test", "password": "a-long-password-1"},
               follow_redirects=False)
    check("company created and signed in", r.status_code == 303 and main.q("SELECT 1 FROM brands WHERE name='Acme Homes'"))
    u = main.q("SELECT * FROM users WHERE email='asha@acme.test'")[0]
    check("password is hashed, not stored", u["pw_hash"].startswith("scrypt$") and "a-long-password-1" not in u["pw_hash"])
    check("owner is builder of the new company", u["role"] == "admin" and u["brand_id"] > 2)
    BID = u["brand_id"]
    check("dashboard opens for a company with no projects", c.get("/").status_code == 200)
    check("team page opens", c.get("/admin/team").status_code == 200)
    r = c.post("/signup", data={"company": "Other", "name": "X", "email": "ASHA@acme.test", "password": "a-long-password-1"})
    check("duplicate email (any case) rejected", "already exists" in r.text)

    # a project to invite people to
    pid = RE.add_project(BID, "Acme Towers", "", "", "", "", [], "test")
    # isolation: other company's project
    other = RE.brand_projects(1)[0]["id"]

    r = c.post("/admin/team/invite", data={"email": "ravi@partner.test", "kind": "partner"}, follow_redirects=False)
    check("partner invite needs a project", not main.q("SELECT 1 FROM invites WHERE email='ravi@partner.test'"))
    r = c.post("/admin/team/invite", data={"email": "ravi@partner.test", "kind": "partner", "project_id": [str(pid), str(other)]})
    inv = main.q("SELECT * FROM invites WHERE email='ravi@partner.test'")[0]
    check("invite only keeps projects of this company", __import__("json").loads(inv["project_ids"]) == [pid], inv["project_ids"])
    page_html = r.text          # the POST redirects to the team page, which shows the link once
    m = re.search(r'/invite/([\w-]+)', page_html)
    check("invite link shown once", bool(m))
    tok = m.group(1)
    check("link not shown a second time", "/invite/" not in c.get("/admin/team").text)
    check("token stored hashed", tok not in inv["token_hash"] and len(inv["token_hash"]) == 64)

with client() as p:
    check("invite page opens", p.get(f"/invite/{tok}").status_code == 200 and "Acme Homes" in p.get(f"/invite/{tok}").text)
    check("garbage link is refused", "not valid" in p.get("/invite/not-a-real-token").text)
    r = p.post(f"/invite/{tok}", data={"name": "Ravi", "password": "x"})
    check("invite rejects weak password", "at least 10" in r.text)
    r = p.post(f"/invite/{tok}", data={"name": "Ravi", "password": "ravi-strong-pass-1"}, follow_redirects=False)
    check("invite accepted", r.status_code == 303)
    ru = main.q("SELECT * FROM users WHERE email='ravi@partner.test'")[0]
    check("partner is a submitter, not a builder", ru["role"] == "submitter" and ru["brand_id"] is None)
    check("partner got only the invited project", [x["id"] for x in RE.authorized_projects(ru["id"], BID)] == [pid])
    check("partner cannot open admin pages", p.get("/admin/team", follow_redirects=False).status_code == 303)
    check("partner can open the submit page", p.get("/submit").status_code == 200)
    check("invite link is single use", "not valid" in client().get(f"/invite/{tok}").text)

with client() as c2:
    r = c2.post("/login", data={"email": "ravi@partner.test", "password": "wrong"})
    check("wrong password refused", "Wrong email or password" in r.text)
    r = c2.post("/login", data={"email": "nobody@x.test", "password": "wrong"})
    check("unknown email gives the same message", "Wrong email or password" in r.text)
    r = c2.post("/login", data={"email": "ravi@partner.test", "password": "ravi-strong-pass-1"}, follow_redirects=False)
    check("correct login works", r.status_code == 303 and c2.get("/").status_code == 200)
    r = client().post("/login", data={"email": "admin@demo.test", "password": ""})
    check("demo accounts cannot password-login", "Wrong email or password" in r.text)

# throttle
with client() as c3:
    for _ in range(5):
        c3.post("/login", data={"email": "ravi@partner.test", "password": "bad"})
    r = c3.post("/login", data={"email": "ravi@partner.test", "password": "ravi-strong-pass-1"})
    check("login locked after repeated failures", "Too many" in r.text)
ACC._fails.clear()

# remove member ends access at once; expired and cancelled invites
with client() as a:
    a.post("/login", data={"email": "asha@acme.test", "password": "a-long-password-1"})
    a.post("/admin/team/remove", data={"user_id": str(ru["id"])})
    check("removing a member ends project access at once", RE.authorized_projects(ru["id"], BID) == [])
    a.post("/admin/team/invite", data={"email": "late@x.test", "kind": "freelancer", "project_id": str(pid)})
    i2 = main.q("SELECT * FROM invites WHERE email='late@x.test'")[0]
    a.post("/admin/team/revoke", data={"invite_id": str(i2["id"])})
    check("cancelled invite is dead", ACC.get_invite("anything") is None and
          main.q("SELECT revoked_at FROM invites WHERE id=?", (i2["id"],))[0]["revoked_at"] is not None)
    tok3 = ACC.create_invite(BID, "old@x.test", "freelancer", [pid], "t")
    main.ex("UPDATE invites SET expires_at='2000-01-01 00:00:00' WHERE email='old@x.test'")
    check("expired invite is dead", ACC.get_invite(tok3) is None)

# a manager invite
with client() as a:
    a.post("/login", data={"email": "asha@acme.test", "password": "a-long-password-1"})
    t = re.search(r'/invite/([\w-]+)', a.post("/admin/team/invite", data={"email": "boss@acme.test", "kind": "manager"}).text).group(1)
with client() as m:
    m.post(f"/invite/{t}", data={"name": "Boss", "password": "boss-strong-pass-1"})
    bu = main.q("SELECT * FROM users WHERE email='boss@acme.test'")[0]
    check("manager invite makes a builder of the same company", bu["role"] == "admin" and bu["brand_id"] == BID)
    check("manager sees only their own company", m.get("/admin/team").status_code == 200)

# another company is isolated
with client() as z:
    z.post("/signup", data={"company": "Zed Estates", "name": "Zed", "email": "zed@zed.test", "password": "zed-strong-pass-1"})
    zb = main.q("SELECT brand_id FROM users WHERE email='zed@zed.test'")[0]["brand_id"]
    check("second company is separate", zb != BID and RE.brand_projects(zb) == [])
    check("team page does not list other companies' people", "asha@acme.test" not in z.get("/admin/team").text)

check("demo mode still works", client().get("/enter/admin", follow_redirects=False).status_code == 303)
print("\n%d failed" % len(fails) if fails else "\nALL PASSED")
sys.exit(1 if fails else 0)
