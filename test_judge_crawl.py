"""What a judge will do: open every page as every kind of user, send empty and garbage forms, wrong ids, broken
files, the same action twice, and script tags in every text box. Nothing may crash (HTTP 500), hang, or show
unescaped script. Run: python test_judge_crawl.py"""
import io, json, os, re, sys, tempfile, time
os.environ["DATA_DIR"] = tempfile.mkdtemp()
for k in ("GROQ_API_KEY", "BREVO_API_KEY", "MAIL_FROM", "SMTP_HOST"):
    os.environ.pop(k, None)
os.environ["UPLOADS_PER_HOUR"] = "100000"
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import main
import ratelimit as RL
import realestate as RE
from fastapi.testclient import TestClient

main.UPLOADS_PER_HOUR = 100000
main.transcribe = lambda w, l, g: [{"start": 0.0, "end": 1.0, "text": "Welcome to Demo Heights, 2 BHK at 1.3 crore", "conf": 0.95}]
main.OCR.read_screen = lambda *a, **k: None
fails, crashes = [], []
XSS = '<script>alert("x")</script>'


def check(name, cond, extra=""):
    print(("PASS " if cond else "FAIL ") + name + (f"  [{extra}]" if extra and not cond else ""))
    if not cond:
        fails.append(name)


ROUTES = re.findall(r'@app\.(get|post)\("([^"]+)"', open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "main.py")).read())
SKIP = {"/logout", "/enter/{key}"}
BAD_IDS = ["0", "999999", "-1", "abc", "1" * 30]
GARBAGE = ["", " ", "x" * 5000, XSS, "०१२३ मराठी ✓ 😀", "' OR 1=1 --", "../../etc/passwd", "null", "-5", "1e309"]


def call(c, method, path, **kw):
    t0 = time.time()
    try:
        r = c.request(method, path, follow_redirects=False, **kw)
        code = r.status_code
    except Exception as ex_:
        code, r = 599, None
        crashes.append(f"{method.upper()} {path}: {type(ex_).__name__}: {str(ex_)[:120]}")
    dt = time.time() - t0
    if code >= 500:
        crashes.append(f"{method.upper()} {path} -> {code}")
    if dt > 15:
        crashes.append(f"{method.upper()} {path} took {dt:.0f}s")
    return r


def fill(path, ids):
    for k, v in ids.items():
        path = path.replace("{" + k + "}", str(v))
    return path


def crawl(c, who, ids):
    for method, path in ROUTES:
        if path in SKIP:
            continue
        variants = [fill(path, ids)]
        if "{" in path:
            for bad in BAD_IDS:
                variants.append(re.sub(r"\{[^}]+\}", bad, path))
        for p in variants:
            if method == "get":
                r = call(c, "get", p)
                if r is not None and r.status_code == 200 and "text/html" in r.headers.get("content-type", ""):
                    if XSS in r.text:
                        crashes.append(f"unescaped script on GET {p} as {who}")
            else:
                for g in GARBAGE:
                    data = {k: g for k in ("email", "name", "password", "company", "value", "note", "decision", "field", "text",
                                           "url", "brand_id", "project_id", "language", "kind", "code", "def_id", "label", "ftype",
                                           "unit", "aliases", "direction", "source", "valid_to", "valid_from", "key", "unit_type_id",
                                           "fact_id", "user_id", "invite_id", "grant_id", "pack", "palette", "min_contrast",
                                           "min_text_pct", "reset_cooldown_min", "purpose", "back", "variant", "row", "minutes",
                                           "place", "alias", "rera_no", "category", "price", "id", "lesson_id", "scope", "said",
                                           "current", "new", "confirm", "notify", "title", "all_projects", "official_name")}
                    call(c, "post", p, data=data)
                call(c, "post", p, files={"file": ("x.mp4", b"\x00\x01garbage", "video/mp4")}, data={"brand_id": str(ids.get("brand", 1))})
                call(c, "post", p, files={"file": ("x.xlsx", b"PK\x03\x04broken", "application/octet-stream")})
                call(c, "post", p, files={"files": ("x.png", b"not an image", "image/png")}, data={"brand_id": str(ids.get("brand", 1))})


with TestClient(main.app, raise_server_exceptions=False) as anon:
    # ---------- set up: demo partner submits; a real general company with sample data
    p = TestClient(main.app, raise_server_exceptions=False)
    p.get("/enter/partner")
    r = p.post("/upload_text", data={"brand_id": "1", "text": "Demo Heights 2 BHK at 1.3 crore with guaranteed returns " + XSS,
                                     "title": XSS}, follow_redirects=False)
    sid = int(r.headers["location"].rsplit("/", 1)[-1]) if r.status_code == 303 and "/s/" in r.headers.get("location", "") else 1
    check("paste copy creates a submission", r.status_code == 303 and "/s/" in r.headers.get("location", ""),
          f"{r.status_code} " + re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", (re.search(r'<main id="main">(.*?)</main>', r.text, re.S) or re.search(r"(.*)", r.text[:400], re.S)).group(1)))[:400])
    a = TestClient(main.app, raise_server_exceptions=False)
    a.get("/enter/admin")
    pid = RE.brand_projects(1)[0]["id"]
    ids = {"sid": sid, "pid": pid, "iid": 1, "batch_id": 1, "token": "x" * 20, "key": "clip1", "i": 0, "brand": 1}

    # ---------- the same action twice
    p.post(f"/dispute/{sid}", data={"note": "please check", "said": ""})
    p.post(f"/dispute/{sid}", data={"note": "please check", "said": ""})
    r1 = a.post(f"/decide/{sid}", data={"decision": "approve", "note": "ok"}, follow_redirects=False)
    r2 = a.post(f"/decide/{sid}", data={"decision": "reject", "note": "changed my mind"}, follow_redirects=False)
    st = main.q("SELECT status FROM submissions WHERE id=?", (sid,))[0]["status"]
    check("a decision cannot be made twice (the second click changes nothing)", st in ("APPROVED", "REJECTED_FINAL")
          and len(main.q("SELECT 1 FROM audit WHERE sub_id=? AND action IN ('APPROVED','REJECTED','DISPUTE_OVERTURNED','DISPUTE_UPHELD')", (sid,))) <= 1, st)
    a.post("/admin/sample"); a.post("/admin/sample")
    names = [x["official_name"] for x in RE.brand_projects(1)]
    check("loading sample data twice does not duplicate projects", len(names) == len(set(names)), str(names))

    # ---------- crawl as everyone
    for who, c in (("visitor", anon), ("demo builder", a), ("demo partner", p)):
        RL.reset()
        crawl(c, who, ids)
    f = TestClient(main.app, raise_server_exceptions=False)
    f.get("/enter/freelancer")
    crawl(f, "demo freelancer", ids)
    RL.reset()
    g = TestClient(main.app, raise_server_exceptions=False)
    g.post("/signup", data={"company": "Judge Co " + XSS, "name": XSS, "email": "judge@judge.in", "password": "a-long-password-1",
                            "industry": "tech"})
    g.post("/admin/sample")
    gid = main.q("SELECT id FROM brands WHERE name LIKE 'Judge Co%'")[0]["id"]
    gp = RE.brand_projects(gid)[0]["id"]
    crawl(g, "new company builder", dict(ids, pid=gp, brand=gid))

    # ---------- refresh-after-post and pages with nothing in them
    RL.reset()
    e = TestClient(main.app, raise_server_exceptions=False)
    e.post("/signup", data={"company": "Empty Co", "name": "E", "email": "e@empty.in", "password": "a-long-password-1"})
    for path in ("/", "/queue", "/reviews", "/disputes", "/approvals", "/audit", "/admin/insights", "/admin/projects",
                 "/admin/learned", "/admin/learned/replay", "/admin/access", "/admin/team", "/admin/fact-types", "/admin/rules"):
        r = call(e, "get", path)
        check(f"empty company: {path} opens", r is not None and r.status_code == 200, str(r.status_code if r else "-"))

    # ---------- script tags are never executed
    for path in ("/", f"/s/{sid}", "/reviews", "/audit", "/admin/team", "/admin/rules", "/admin/insights"):
        for c in (a, g):
            r = call(c, "get", path)
            if r is not None and r.status_code == 200 and XSS in r.text:
                crashes.append(f"unescaped script on {path}")

check("no page crashes, hangs or shows unescaped script, for any user and any input", not crashes,
      "\n  " + "\n  ".join(sorted(set(crashes))[:60]))
print("\n%d failed" % len(fails) if fails else "\nALL PASSED")
sys.exit(1 if fails else 0)
