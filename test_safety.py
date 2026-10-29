"""Checks for password reset, account page, OTP before adding people, rate limits and email notifications.
Run: python test_safety.py"""
import io, json, os, re, subprocess, sys, tempfile, time
os.environ["DATA_DIR"] = tempfile.mkdtemp()
for k in ("GROQ_API_KEY", "SMTP_HOST"):
    os.environ.pop(k, None)
os.environ.update(BREVO_API_KEY="k", MAIL_FROM="noreply@brandguard.in", MAIL_SYNC="1", PUBLIC_URL="https://bg.example")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import main
import mailer
import accounts as ACC
import ratelimit as RL
import realestate as RE
from fastapi.testclient import TestClient

fails = []
OUT = []
mailer._brevo = lambda to, subject, text: (OUT.append((to, subject, text)) or (True, ""))


def check(name, cond, extra=""):
    print(("PASS " if cond else "FAIL ") + name + (f"  [{extra}]" if extra and not cond else ""))
    if not cond:
        fails.append(name)


def last_to(addr):
    return [m for m in OUT if m[0] == addr]


wav = os.path.join(os.environ["DATA_DIR"], "t.mp4")
subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i", "sine=frequency=440:duration=1", "-c:a", "aac", wav], capture_output=True)
SCRIPT = {"t": "Welcome to Zippy Hatchback VXi at 7.1 lakh"}
main.transcribe = lambda w, l, g: [{"start": 0.0, "end": 1.0, "text": SCRIPT["t"], "conf": 0.95}]
main.OCR.read_screen = lambda *a, **k: None

with TestClient(main.app) as a:
    # role label fix for the demo freelancer
    a.get("/enter/admin")
    team = a.get("/admin/team").text
    check("demo freelancer is shown as Freelancer", re.search(r"Priya Freelance \(Freelancer\)</td><td[^>]*>[^<]*</td><td[^>]*>Freelancer", team) is not None)
    a.get("/logout")

    # ---------- sign up a real company
    a.post("/signup", data={"company": "Zippy", "name": "Meera", "email": "meera@zippy.in", "password": "a-long-password-1", "industry": "ecommerce"})
    bid = main.q("SELECT id FROM brands WHERE name='Zippy'")[0]["id"]
    a.post("/admin/sample")
    car = [p["id"] for p in RE.brand_projects(bid) if p["official_name"] == "Zippy Hatchback"][0]

    # ---------- OTP before adding people
    page = a.get("/admin/team").text
    check("adding people asks for an emailed code first", "Email me a code" in page and 'action="/admin/team/invite"' not in page)
    r = a.post("/admin/team/invite", data={"email": "dev@dealer.in", "kind": "partner", "all_projects": "1"}, follow_redirects=False)
    check("an invite without the code is refused", r.headers["location"].startswith("/admin/team") and not main.q("SELECT 1 FROM invites WHERE email='dev@dealer.in'"))
    a.post("/admin/otp/send", data={"purpose": "invite", "back": "/admin/team"})
    code = re.search(r"\b(\d{6})\b", last_to("meera@zippy.in")[-1][1]).group(1)
    r = a.post("/admin/otp/send", data={"purpose": "invite", "back": "/admin/team"})
    check("a new code cannot be asked for within a minute", "seconds" in r.text)
    r = a.post("/admin/otp/verify", data={"code": "000000" if code != "000000" else "111111"})
    check("a wrong code is refused", "wrong or has expired" in r.text)
    r = a.post("/admin/otp/verify", data={"code": code})
    check("the right code unlocks invites", "Confirmed" in r.text and 'action="/admin/team/invite"' in a.get("/admin/team").text)
    r = a.post("/admin/team/invite", data={"email": "dev@dealer.in", "kind": "partner", "all_projects": "1"})
    check("after the code, the invite is created and emailed", "Invite emailed to dev@dealer.in" in r.text and last_to("dev@dealer.in"))
    check("a used code cannot be used again", not ACC.check_otp(main.q("SELECT id FROM users WHERE email='meera@zippy.in'")[0]["id"], "invite", code))

    # bulk: a fresh code every time
    csv = "Email,Name,Role,Access\nann@x.in,Ann,Agency,All\n".encode()
    loc = a.post("/admin/team/bulk", files={"file": ("p.csv", csv, "text/csv")}, follow_redirects=False).headers["location"]
    iid = loc.rsplit("/", 1)[-1]
    check("bulk preview asks for a code", "Email me a code" in a.get(loc).text and 'name="code"' in a.get(loc).text)
    a.post(loc + "/send", data={"code": "123456"})
    check("bulk send without the right code creates nothing", not main.q("SELECT 1 FROM invites WHERE email='ann@x.in'"))
    a.post("/admin/otp/send", data={"purpose": f"bulk:{iid}", "back": loc})
    bcode = re.search(r"\b(\d{6})\b", last_to("meera@zippy.in")[-1][1]).group(1)
    res = a.post(loc + "/send", data={"code": bcode}).text
    check("bulk send with its own fresh code works", "Emailed" in res and main.q("SELECT 1 FROM invites WHERE email='ann@x.in'"))

    # ---------- the dealer joins; notifications
    tok = re.search(r"/invite/([\w-]+)", last_to("dev@dealer.in")[-1][2]).group(1)
    p = TestClient(main.app)
    p.post(f"/invite/{tok}", data={"name": "Dev", "password": "dealer-strong-pass"})
    OUT.clear()
    SCRIPT["t"] = "Zippy Hatchback VXi at 7.1 lakh with 12% cashback"
    r = p.post("/upload", data={"brand_id": str(bid), "language": "en", "project_id": ""},
               files={"file": ("ad.mp4", open(wav, "rb"), "video/mp4")}, follow_redirects=False)
    sid = int(r.headers["location"].rsplit("/", 1)[-1])
    st = main.q("SELECT status FROM submissions WHERE id=?", (sid,))[0]["status"]
    check("the creator is emailed the result with a link", last_to("dev@dealer.in") and f"/s/{sid}" in last_to("dev@dealer.in")[-1][2], st)
    check("the builder is emailed when a person must check", st != "SUPERVISION" or last_to("meera@zippy.in"))
    a.post(f"/decide/{sid}", data={"decision": "reject", "note": "Cashback is not approved."}) if st == "SUPERVISION" else None
    if st == "SUPERVISION":
        check("the creator is emailed the reviewer's decision and note", "Cashback is not approved" in last_to("dev@dealer.in")[-1][2])
    p.get("/account")
    p.post("/account/notify", data={})
    n = len(last_to("dev@dealer.in"))
    p.post("/upload", data={"brand_id": str(bid), "language": "en", "project_id": ""}, files={"file": ("ad2.mp4", open(wav, "rb"), "video/mp4")})
    check("notifications can be switched off", len(last_to("dev@dealer.in")) == n)

    # ---------- upload rate limit
    main.UPLOADS_PER_HOUR = 2
    r = p.post("/upload", data={"brand_id": str(bid), "language": "en", "project_id": ""}, files={"file": ("ad3.mp4", open(wav, "rb"), "video/mp4")})
    check("uploads over the hourly limit are refused with a clear message", "files an hour" in r.text)
    main.UPLOADS_PER_HOUR = 20

    # ---------- password reset
    b = TestClient(main.app)
    OUT.clear()
    r = b.post("/forgot", data={"email": "dev@dealer.in"})
    check("reset request shows the same message for everyone", "If an account with that email exists" in r.text)
    link = re.search(r"https://bg\.example(/reset/[\w-]+)", last_to("dev@dealer.in")[-1][2]).group(1)
    r = b.post("/forgot", data={"email": "nobody@nowhere.in"})
    check("an unknown email gets the same message and no email", "If an account with that email exists" in r.text and not last_to("nobody@nowhere.in"))
    b.post("/forgot", data={"email": "dev@dealer.in"})
    check("a second request inside the cool-down sends nothing", len(last_to("dev@dealer.in")) == 1)
    r = b.post(link, data={"password": "brand-new-pass-1", "confirm": "different-pass-1"})
    check("the two new passwords must match", "different" in r.text)
    r = b.post(link, data={"password": "short", "confirm": "short"})
    check("a weak new password is refused", "at least" in r.text)
    r = b.post(link, data={"password": "brand-new-pass-1", "confirm": "brand-new-pass-1"}, follow_redirects=False)
    check("a good new password is saved and signs the person in", r.status_code == 303 and "/s/" not in r.headers["location"])
    check("the reset link works only once", "not valid any more" in b.get(link).text)
    check("other signed-in sessions are ended", p.get("/account", follow_redirects=False).status_code == 303)
    check("the old password no longer works", main.ACC.authenticate("dev@dealer.in", "dealer-strong-pass", "1.1.1.1") is None)
    check("the new password works", main.ACC.authenticate("dev@dealer.in", "brand-new-pass-1", "1.1.1.1") is not None)
    check("a confirmation email is sent after a change", any("was changed" in m[1] for m in last_to("dev@dealer.in")))
    check("demo accounts cannot be reset", ACC.request_reset("admin@demo.test", 10)[0] is None)

    # cool-down setting
    r = a.post("/admin/security", data={"reset_cooldown_min": "0"})
    check("cool-down must be 1 to 1440 minutes", "between 1 and 1440" in r.text)
    a.post("/admin/security", data={"reset_cooldown_min": "45"})
    dev = main.q("SELECT * FROM users WHERE email='dev@dealer.in'")[0]
    check("the company's cool-down applies to its people", main.reset_cooldown_for(dev) == 45)
    check("the Team page shows the cool-down setting", "Password reset cool-down" in a.get("/admin/team").text)

    # change password on the account page
    c2 = TestClient(main.app)
    c2.post("/login", data={"email": "dev@dealer.in", "password": "brand-new-pass-1"})
    r = c2.post("/account/password", data={"current": "wrong-password-x", "new": "another-pass-22"})
    check("changing the password needs the current one", "current password is wrong" in r.text)
    r = c2.post("/account/password", data={"current": "brand-new-pass-1", "new": "another-pass-22"})
    check("password can be changed and the person stays signed in", "Password changed" in r.text and c2.get("/account").status_code == 200)

    # ---------- signup rate limit
    RL.reset()
    s = TestClient(main.app)
    codes = [s.post("/signup", data={"company": f"Spam {i}", "name": "X", "email": f"s{i}@spam.in", "password": "a-long-password-1"}).text
             for i in range(6)]
    check("more than 5 new companies an hour from one network are refused", "Too many new companies" in codes[-1])
    RL.reset()
    for i in range(11):
        r = s.post("/forgot", data={"email": f"x{i}@y.in"})
    check("reset requests are limited per network", "Too many requests" in r.text)

print("\n%d failed" % len(fails) if fails else "\nALL PASSED")
sys.exit(1 if fails else 0)
