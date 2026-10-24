#!/usr/bin/env python3
"""BrandGuard web app (Round 2) - link ingestion, caption check, stricter auto-approval."""

import hashlib
import html
import json
import math
import os
import secrets
import sqlite3
import subprocess
import uuid
from collections import Counter
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

import requests
from fastapi import FastAPI, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from starlette.middleware.sessions import SessionMiddleware

from engine import (LAKH, UNITS, classify_price, extract_prices, fmt_money, fmt_time,
                    norm, review)

# short spelling seen in captions and titles, for example "Rs 90L"
UNITS.setdefault("l", LAKH)

DATA_DIR = Path(os.environ.get("DATA_DIR", "data"))
UPLOAD_DIR = DATA_DIR / "uploads"
DB_PATH = DATA_DIR / "brandguard.db"
GROQ_KEY = os.environ.get("GROQ_API_KEY", "")
MODE = os.environ.get("TRANSCRIBE_MODE", "groq")  # groq | local
LINKS_ENABLED = os.environ.get("LINKS_ENABLED", "1") == "1"
MAX_MB = 60
MAX_SECONDS = 180
THRESHOLD = 0.65
ALLOWED = {".mp4", ".mov", ".mkv", ".webm", ".m4a", ".mp3", ".wav", ".aac", ".ogg"}
LINK_HOSTS = ("youtube.com", "youtu.be", "instagram.com", "facebook.com", "fb.watch")
DEMO = {"admin": 1, "partner": 2, "freelancer": 3}
ROLE_LABEL = {"admin": "Builder / Brand Manager", "submitter": "Submitter"}

# comparative and urgency claims that need supporting evidence
UNSUPPORTED = [
    "distress", "below market", "market se kam", "lowest price", "best price", "cheapest",
    "last few", "only few", "few units left", "limited units", "limited period", "hurry",
    "से कम प्राइस", "से कम कीमत", "मार्केट से कम", "सबसे कम", "सबसे सस्ता", "सिर्फ आज", "आखिरी मौका",
]

app = FastAPI(title="BrandGuard")
app.add_middleware(SessionMiddleware,
                   secret_key=os.environ.get("SECRET_KEY", "dev-only-change-me"),
                   max_age=3 * 86400)

e = html.escape


# ------------------------------------------------------------------ database
def q(sql, args=()):
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    try:
        return con.execute(sql, args).fetchall()
    finally:
        con.close()


def ex(sql, args=()):
    con = sqlite3.connect(DB_PATH)
    try:
        cur = con.execute(sql, args)
        con.commit()
        return cur.lastrowid
    finally:
        con.close()


REG1 = {
    "brand": "Demo Developer", "project": "Demo Heights", "rera": "P00000000000",
    "configs": [{"name": "2 BHK", "price": 13000000}, {"name": "3 BHK", "price": 19000000}],
    "possession": "December 2028",
    "banned_phrases": ["guaranteed returns", "best in city", "price will double",
                       "100% safe", "no hidden charges"],
    "confidential": ["dealer commission", "internal discount", "unreleased project", "margin slab"],
    "allowed_contacts": ["9999999999"],
    "glossary": ["Demo Heights", "RERA", "BHK", "possession", "crore", "lakh",
                 "दीड कोटी", "सव्वा कोटी", "साडे तीन कोटी", "डेढ़ करोड़", "कोटी", "ताबा"],
}
REG2 = {
    "brand": "Sample Builders", "project": "Sample Residency", "rera": "P11111111111",
    "configs": [{"name": "1 BHK", "price": 6500000}, {"name": "2 BHK", "price": 9500000}],
    "possession": "June 2029",
    "banned_phrases": ["guaranteed returns", "price will double", "only today"],
    "confidential": ["dealer commission", "internal discount"],
    "allowed_contacts": ["8888888888"],
    "glossary": ["Sample Residency", "RERA", "BHK", "crore", "lakh", "कोटी", "लाख"],
}


def init_db():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB_PATH)
    con.executescript("""
    CREATE TABLE IF NOT EXISTS brands (id INTEGER PRIMARY KEY, name TEXT, registry TEXT);
    CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, name TEXT, email TEXT, role TEXT, brand_id INTEGER);
    CREATE TABLE IF NOT EXISTS memberships (user_id INTEGER, brand_id INTEGER);
    CREATE TABLE IF NOT EXISTS submissions (
        id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, brand_id INTEGER, filename TEXT,
        sha256 TEXT, language TEXT, status TEXT, verdict TEXT, report TEXT, created_at TEXT,
        approval_id TEXT, decision_note TEXT, dispute_note TEXT);
    CREATE TABLE IF NOT EXISTS audit (
        id INTEGER PRIMARY KEY AUTOINCREMENT, sub_id INTEGER, at TEXT, actor TEXT, action TEXT, note TEXT);
    """)
    try:
        con.execute("ALTER TABLE submissions ADD COLUMN source_url TEXT")
    except sqlite3.OperationalError:
        pass
    if con.execute("SELECT COUNT(*) FROM brands").fetchone()[0] == 0:
        con.execute("INSERT INTO brands VALUES (1, ?, ?)", ("Demo Developer", json.dumps(REG1, ensure_ascii=False)))
        con.execute("INSERT INTO brands VALUES (2, ?, ?)", ("Sample Builders", json.dumps(REG2, ensure_ascii=False)))
        con.execute("INSERT INTO users VALUES (1, 'Builder Admin', 'admin@demo.test', 'admin', 1)")
        con.execute("INSERT INTO users VALUES (2, 'Rahul Realty (Channel Partner)', 'partner@demo.test', 'submitter', NULL)")
        con.execute("INSERT INTO users VALUES (3, 'Priya Freelance (Freelancer)', 'freelancer@demo.test', 'submitter', NULL)")
        con.execute("INSERT INTO memberships VALUES (2, 1)")
        con.execute("INSERT INTO memberships VALUES (3, 1)")
        con.execute("INSERT INTO memberships VALUES (3, 2)")
    con.commit()
    con.close()


init_db()


def log(sid, actor, action, note=""):
    ex("INSERT INTO audit (sub_id, at, actor, action, note) VALUES (?,?,?,?,?)",
       (sid, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), actor, action, note))


def me(request):
    uid = request.session.get("uid")
    if not uid:
        return None
    rows = q("SELECT * FROM users WHERE id=?", (uid,))
    return rows[0] if rows else None


def get_sub(sid):
    rows = q("""SELECT s.*, u.name AS uname, b.name AS bname FROM submissions s
                JOIN users u ON u.id=s.user_id JOIN brands b ON b.id=s.brand_id WHERE s.id=?""", (sid,))
    return rows[0] if rows else None


def can_view(u, s):
    return (u["role"] == "admin" and s["brand_id"] == u["brand_id"]) or s["user_id"] == u["id"]


def new_approval_id():
    return f"BG-{datetime.now().year}-{secrets.token_hex(3).upper()}"


# ---------------------------------------------------------------------- pages
CSS = """
*{box-sizing:border-box}body{margin:0;font-family:system-ui,Segoe UI,Arial,sans-serif;background:#f4f6f9;color:#1c2330}
header{background:#12233d;color:#fff;padding:12px 20px;display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px}
header nav{font-size:14px}header nav a{color:#9fd0ff;margin-left:14px;text-decoration:none}header nav span{opacity:.8}
main{max-width:980px;margin:20px auto;padding:0 16px}
.card{background:#fff;border:1px solid #dde3ec;border-radius:10px;padding:16px;margin-bottom:16px}
h1,h2,h3{margin:0 0 10px}
table{width:100%;border-collapse:collapse;font-size:14px}
th,td{text-align:left;padding:8px;border-bottom:1px solid #eef1f6;vertical-align:top}
.chip{display:inline-block;padding:2px 10px;border-radius:12px;font-size:12px;font-weight:600;background:#e8edf5}
.ok{background:#d9f4e3;color:#136b36}.bad{background:#fde0e0;color:#a31616}.warn{background:#fff0cc;color:#8a5a00}
.counts span{margin-right:10px}
button,.btn{background:#1f5fbf;color:#fff;border:0;border-radius:8px;padding:10px 16px;font-size:15px;cursor:pointer;text-decoration:none;display:inline-block;margin:2px 4px 2px 0}
button.alt,.btn.alt{background:#5a6678}button.danger{background:#b32a2a}
input,select,textarea{width:100%;padding:9px;border:1px solid #c5ceda;border-radius:8px;font-size:15px;font-family:inherit;margin:4px 0 12px}
label{font-size:13px;font-weight:600}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:12px}
.mono{font-family:Consolas,monospace;font-size:12px;word-break:break-all}
.muted{color:#5a6678;font-size:13px}
"""


def page(title, body, user=None):
    nav = ""
    if user:
        nav = (f'<span>{e(user["name"])} ({e(ROLE_LABEL[user["role"]])})</span>'
               '<a href="/">Home</a><a href="/verify">Verify a file</a><a href="/logout">Log out</a>')
    return HTMLResponse(
        "<!doctype html><html lang='en'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width,initial-scale=1'>"
        f"<title>{e(title)} - BrandGuard</title><style>{CSS}</style></head><body>"
        f"<header><b>BrandGuard</b><nav>{nav}</nav></header><main>{body}</main></body></html>")


def err_page(u, msg):
    return page("Could not review",
                f"<div class='card'><h2>Could not review this</h2><p>{e(msg)}</p>"
                "<a class='btn' href='/'>Back</a></div>", u)


def chip(status):
    cls = {"AUTO_APPROVED": "ok", "APPROVED": "ok", "REJECTED": "bad", "BLOCKED": "bad",
           "REJECTED_FINAL": "bad", "SUPERVISION": "warn", "DISPUTED": "warn",
           "FLAG": "bad", "PASS": "ok"}.get(status, "")
    return f'<span class="chip {cls}">{e(status.replace("_", " ").title())}</span>'


def sub_table(rows, show_user=True):
    if not rows:
        return '<p class="muted">Nothing here yet.</p>'
    out = ["<table><tr><th>#</th><th>File</th>"]
    out.append("<th>Submitted by</th>" if show_user else "")
    out.append("<th>Company</th><th>Status</th><th>Verdict</th><th>When</th></tr>")
    for r in rows:
        who = f'<td>{e(r["uname"])}</td>' if show_user else ""
        out.append(f'<tr><td><a href="/s/{r["id"]}">{r["id"]}</a></td><td>{e(r["filename"] or "")}</td>{who}'
                   f'<td>{e(r["bname"])}</td><td>{chip(r["status"])}</td>'
                   f'<td>{e(r["verdict"] or "")}</td><td class="muted">{e(r["created_at"])}</td></tr>')
    out.append("</table>")
    return "".join(out)


SUB_SQL = """SELECT s.*, u.name AS uname, b.name AS bname FROM submissions s
             JOIN users u ON u.id=s.user_id JOIN brands b ON b.id=s.brand_id """


# --------------------------------------------------------------------- landing
@app.get("/health")
def health():
    return {"ok": True}


@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    u = me(request)
    if not u:
        body = """
        <div class="card"><h1>BrandGuard</h1>
        <p>Pre-publication review for promotional content. A creator uploads a reel, the system listens to the
        audio, checks every claim against the brand's approved facts, and routes anything risky or uncertain
        to a human. Nothing is approved without a recorded decision.</p>
        <p class="muted">Demo mode: choose a role below to enter. No sign-up needed.</p></div>
        <div class="grid">
          <div class="card"><h3>Builder / Brand Manager</h3>
            <p class="muted">Set the brand rules, review flagged and disputed items, approve or reject.</p>
            <a class="btn" href="/enter/admin">Enter as Builder</a></div>
          <div class="card"><h3>Channel Partner</h3>
            <p class="muted">Upload a reel (or paste a link) for one company and see the result.</p>
            <a class="btn" href="/enter/partner">Enter as Partner</a></div>
          <div class="card"><h3>Freelancer</h3>
            <p class="muted">Works with two companies under one login.</p>
            <a class="btn" href="/enter/freelancer">Enter as Freelancer</a></div>
        </div>"""
        return page("Welcome", body)
    return admin_dash(u) if u["role"] == "admin" else submitter_dash(u)


@app.get("/enter/{key}")
def enter(request: Request, key: str):
    uid = DEMO.get(key)
    if uid:
        request.session["uid"] = uid
    return RedirectResponse("/", 303)


@app.get("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/", 303)


# ------------------------------------------------------------ submitter views
def submitter_dash(u):
    brands = q("SELECT b.* FROM brands b JOIN memberships m ON m.brand_id=b.id WHERE m.user_id=?", (u["id"],))
    opts = "".join(f'<option value="{b["id"]}">{e(b["name"])}</option>' for b in brands)
    mine = q(SUB_SQL + "WHERE s.user_id=? ORDER BY s.id DESC", (u["id"],))
    langs = ('<option value="mr">Marathi</option><option value="hi">Hindi</option>'
             '<option value="en">English</option><option value="auto">Auto-detect</option>')
    busy = "var b=this.querySelector('button');b.disabled=true;b.textContent='Reviewing... this can take 10-40 seconds';"
    if LINKS_ENABLED:
        link_card = f"""
    <div class="card"><h2>Or check a link</h2>
    <p class="muted">Paste a public YouTube Shorts, Instagram reel or Facebook reel link. This is a live-content
    check of something already posted. Both the audio and the post's title and description are reviewed.
    Private posts and some platform links cannot be fetched automatically; if that happens, download the
    video and upload the file above.</p>
    <form method="post" action="/upload_link" onsubmit="{busy}">
      <label>Company</label><select name="brand_id">{opts}</select>
      <label>Spoken language</label><select name="language">{langs}</select>
      <label>Link</label><input type="url" name="url" placeholder="https://www.youtube.com/shorts/..." required>
      <button type="submit">Fetch and review</button>
    </form></div>"""
    else:
        link_card = """
    <div class="card"><h2>Check a posted link</h2>
    <p class="muted">BrandGuard can fetch a public YouTube, Instagram or Facebook reel from its link and review it,
    including the post's title and description. This hosted demo runs on a shared cloud server, which these
    platforms block from automated downloads, so link checking is switched off here. It works in the local
    build, and production would use each platform's official API with the account owner's consent.
    To check a posted reel on this demo, download it and upload the file above.</p></div>"""
    body = f"""
    <div class="card"><h2>Upload a reel</h2>
    <form method="post" action="/upload" enctype="multipart/form-data" onsubmit="{busy}">
      <label>Company</label><select name="brand_id">{opts}</select>
      <label>Spoken language</label><select name="language">{langs}</select>
      <label>Video or audio file (up to {MAX_MB} MB, first {MAX_SECONDS // 60} minutes are reviewed)</label>
      <input type="file" name="file" accept="video/*,audio/*" required>
      <button type="submit">Submit for review</button>
    </form></div>
    {link_card}
    <div class="card"><h2>My submissions</h2>{sub_table(mine, show_user=False)}</div>"""
    return page("Dashboard", body, u)


def save_upload(up: UploadFile):
    ext = Path(up.filename or "").suffix.lower()
    if ext not in ALLOWED:
        raise ValueError("Unsupported file type. Please upload a video or audio file (mp4, mov, m4a, wav...).")
    dst = UPLOAD_DIR / (uuid.uuid4().hex + ext)
    h = hashlib.sha256()
    size = 0
    too_big = False
    with open(dst, "wb") as f:
        while True:
            chunk = up.file.read(1024 * 1024)
            if not chunk:
                break
            size += len(chunk)
            if size > MAX_MB * 1024 * 1024:
                too_big = True
                break
            h.update(chunk)
            f.write(chunk)
    if too_big:
        dst.unlink(missing_ok=True)
        raise ValueError(f"File is larger than {MAX_MB} MB.")
    return dst, h.hexdigest()


def host_ok(url: str) -> bool:
    try:
        p = urlparse(url.strip())
    except Exception:
        return False
    if p.scheme not in ("http", "https") or not p.hostname:
        return False
    h = p.hostname.lower()
    return any(h == d or h.endswith("." + d) for d in LINK_HOSTS)


def fetch_link(url: str):
    """Download one public video from an allowed host. Returns (path, sha256, title, description)."""
    import yt_dlp
    from yt_dlp.utils import DownloadError

    fail = ("Could not fetch this link. The post may be private, removed, or blocked for automated "
            "access. Please download the video and upload the file instead.")
    stem = uuid.uuid4().hex
    opts = {
        "outtmpl": str(UPLOAD_DIR / (stem + ".%(ext)s")),
        "format": "bv*[height<=480]+ba[format_note*=original]/bv*[height<=480]+ba/b[height<=480]/b",
        "merge_output_format": "mp4",
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "socket_timeout": 20,
        "retries": 1,
        "max_filesize": MAX_MB * 1024 * 1024,
        "match_filter": yt_dlp.utils.match_filter_func("duration <=? 300"),
    }
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url.strip(), download=True)
    except DownloadError:
        raise RuntimeError(fail)
    except Exception:
        raise RuntimeError(fail)
    if not info:
        raise RuntimeError("This video is longer than 5 minutes or larger than the size limit, "
                           "so it was not fetched. Please upload a shorter file.")
    files = [f for f in UPLOAD_DIR.glob(stem + ".*") if f.suffix.lower() in ALLOWED]
    if not files:
        raise RuntimeError(fail)
    path = files[0]
    if path.stat().st_size > MAX_MB * 1024 * 1024:
        path.unlink(missing_ok=True)
        raise RuntimeError(f"The video is larger than {MAX_MB} MB.")
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    title = (info.get("title") or "Linked video").strip()[:200]
    desc = (info.get("description") or "").strip()[:1500]
    return path, h.hexdigest(), title, desc


def extract_audio(src: Path, dst: Path):
    cmd = ["ffmpeg", "-y", "-i", str(src), "-vn", "-ac", "1", "-ar", "16000",
           "-t", str(MAX_SECONDS), str(dst)]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
    if r.returncode != 0 or not dst.exists() or dst.stat().st_size < 1000:
        raise RuntimeError("Could not read audio from this file. Check that it has sound and try again.")


def transcribe_groq(wav: Path, lang: str, glossary):
    if not GROQ_KEY:
        raise RuntimeError("The speech service key is not configured on the server.")
    data = {"model": "whisper-large-v3", "response_format": "verbose_json", "temperature": "0"}
    if glossary:
        data["prompt"] = ", ".join(glossary)[:400]
    if lang in ("mr", "hi", "en"):
        data["language"] = lang
    with open(wav, "rb") as f:
        r = requests.post("https://api.groq.com/openai/v1/audio/transcriptions",
                          headers={"Authorization": f"Bearer {GROQ_KEY}"},
                          files={"file": ("audio.wav", f)}, data=data, timeout=120)
    if r.status_code != 200:
        raise RuntimeError(f"The speech service returned an error ({r.status_code}). Please try again.")
    j = r.json()
    segs = [{"start": round(s["start"], 2), "end": round(s["end"], 2), "text": s["text"].strip(),
             "conf": round(math.exp(s.get("avg_logprob", -1.0)), 3)} for s in j.get("segments", [])]
    if not segs and (j.get("text") or "").strip():
        segs = [{"start": 0, "end": 0, "text": j["text"].strip(), "conf": 0.5}]
    return segs


def transcribe(wav: Path, lang: str, glossary):
    if MODE == "local":
        from engine import transcribe as local_transcribe
        segs, _ = local_transcribe(wav, os.environ.get("LOCAL_MODEL", "medium"),
                                   lang if lang in ("mr", "hi", "en") else None, glossary, "auto", "auto")
        return segs
    return transcribe_groq(wav, lang, glossary)


def finalize(rep):
    """Recount findings and set the verdict from the final list."""
    fl = [f for f in rep["findings"] if f["status"] == "FLAG"]
    su = [f for f in rep["findings"] if f["status"] == "SUPERVISION"]
    rep["flags"], rep["supervision"] = len(fl), len(su)
    if any(f["severity"] == "CRITICAL" for f in rep["findings"]):
        rep["verdict"] = "BLOCKED - confidential data"
    elif fl:
        rep["verdict"] = "REJECT - fix and resubmit"
    elif su:
        rep["verdict"] = "SUPERVISION - manager check needed"
    else:
        rep["verdict"] = "PASS - auto-clear candidate"


def make_finding(status, severity, ftype, t, evidence, why, fix, conf=None, source="audio"):
    return {"status": status, "severity": severity, "type": ftype, "time": t, "evidence": evidence,
            "explanation": why, "suggestion": fix, "confidence": conf, "source": source}


def process_file(src: Path, reg: dict, lang: str, caption: str = "") -> dict:
    wav = src.parent / (src.stem + "_16k.wav")
    try:
        extract_audio(src, wav)
        segs = transcribe(wav, lang, reg.get("glossary"))
    finally:
        wav.unlink(missing_ok=True)

    rep = review(segs, reg, THRESHOLD)
    prices = [(c["name"], c["price"]) for c in reg["configs"]]
    claims, passed = [], 0

    for s in segs:
        for p in extract_prices(s["text"]):
            if p["value"] <= 0:
                continue
            st, _t, _w, name, ref = classify_price(p["value"], prices, s["conf"], THRESHOLD)
            passed += 1 if st == "PASS" else 0
            claims.append({"heard": fmt_money(p["value"]), "config": name, "approved": fmt_money(ref),
                           "status": st, "time": s["start"], "source": "audio"})

    # title / description of a linked post: same rules, typed text so confidence is full
    if caption.strip():
        cap = review([{"start": 0, "end": 0, "text": caption, "conf": 1.0}], reg, THRESHOLD)
        for f in cap["findings"]:
            f["source"] = "caption"
            rep["findings"].append(f)
        for p in extract_prices(caption):
            if p["value"] <= 0:
                continue
            st, _t, _w, name, ref = classify_price(p["value"], prices, 1.0, THRESHOLD)
            passed += 1 if st == "PASS" else 0
            claims.append({"heard": fmt_money(p["value"]), "config": name, "approved": fmt_money(ref),
                           "status": st, "time": 0, "source": "caption"})

    # comparative / urgency claims need evidence
    sources = [(s["text"], s["start"], "audio") for s in segs]
    if caption.strip():
        sources.append((caption, 0, "caption"))
    seen = set()
    for text, t, srcname in sources:
        low = norm(text).lower()
        for w in UNSUPPORTED:
            if w in low and (w, srcname) not in seen:
                seen.add((w, srcname))
                rep["findings"].append(make_finding(
                    "SUPERVISION", "MEDIUM", "UNSUPPORTED_CLAIM", t, w,
                    f'"{w}" is a comparative or urgency claim that needs supporting evidence.',
                    "Add proof from the approved facts or offers, or remove the claim.", None, srcname))

    rep["claims"], rep["passed"] = claims, passed

    if not segs:
        rep["findings"].append(make_finding(
            "SUPERVISION", "MEDIUM", "NO_SPEECH_DETECTED", 0, "-",
            "No speech could be detected in this file.", "A human should check the file."))
    elif passed == 0 and not any(f["status"] == "FLAG" for f in rep["findings"]):
        rep["findings"].append(make_finding(
            "SUPERVISION", "LOW", "NO_VERIFIABLE_CLAIM", 0, "-",
            "Nothing in this content could be matched against the approved facts, so nothing was verified.",
            "A person should confirm that no price or fact needs checking."))

    finalize(rep)
    return rep


def allowed_brand(u, brand_id):
    return bool(q("SELECT 1 FROM memberships WHERE user_id=? AND brand_id=?", (u["id"], brand_id)))


def run_review(u, brand_id, path, sha, filename, language, source_url=None, caption=""):
    brand = q("SELECT * FROM brands WHERE id=?", (brand_id,))[0]
    reg = json.loads(brand["registry"])
    try:
        rep = process_file(path, reg, language, caption)
    except Exception as ex_:
        msg = str(ex_) if isinstance(ex_, (ValueError, RuntimeError)) else "Something went wrong while reviewing this file."
        return err_page(u, msg)

    approval = None
    if rep["verdict"].startswith("BLOCKED"):
        status = "BLOCKED"
    elif rep["flags"]:
        status = "REJECTED"
    elif rep["supervision"]:
        status = "SUPERVISION"
    else:
        status, approval = "AUTO_APPROVED", new_approval_id()

    sid = ex("""INSERT INTO submissions (user_id, brand_id, filename, sha256, language, status, verdict, report,
                created_at, approval_id, source_url) VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
             (u["id"], brand_id, filename, sha, language, status, rep["verdict"],
              json.dumps(rep, ensure_ascii=False), datetime.now().strftime("%Y-%m-%d %H:%M"),
              approval, source_url))
    how = "SUBMITTED_LINK" if source_url else "SUBMITTED"
    log(sid, u["name"], how, f"{filename} for {brand['name']}")
    log(sid, "BrandGuard engine", "AUTO_REVIEW",
        f"{rep['verdict']} ({rep['flags']} flags, {rep['supervision']} supervision)")
    if approval:
        log(sid, "BrandGuard engine", "AUTO_APPROVED", approval)
    return RedirectResponse(f"/s/{sid}", 303)


@app.post("/upload")
def upload(request: Request, brand_id: int = Form(...), language: str = Form("auto"),
           file: UploadFile = File(...)):
    u = me(request)
    if not u or u["role"] != "submitter":
        return RedirectResponse("/", 303)
    if not allowed_brand(u, brand_id):
        return err_page(u, "You are not linked to that company.")
    try:
        path, sha = save_upload(file)
    except Exception as ex_:
        return err_page(u, str(ex_) if isinstance(ex_, (ValueError, RuntimeError)) else "Upload failed.")
    return run_review(u, brand_id, path, sha, file.filename, language)


@app.post("/upload_link")
def upload_link(request: Request, brand_id: int = Form(...), language: str = Form("auto"),
                url: str = Form(...)):
    u = me(request)
    if not u or u["role"] != "submitter":
        return RedirectResponse("/", 303)
    if not allowed_brand(u, brand_id):
        return err_page(u, "You are not linked to that company.")
    url = url.strip()
    if not host_ok(url):
        return err_page(u, "Please paste a link from YouTube, Instagram or Facebook.")
    try:
        path, sha, title, desc = fetch_link(url)
    except Exception as ex_:
        return err_page(u, str(ex_) if isinstance(ex_, (ValueError, RuntimeError)) else "Could not fetch this link.")
    caption = (title + "\n" + desc).strip()
    return run_review(u, brand_id, path, sha, title[:80], language, source_url=url, caption=caption)


# ------------------------------------------------------------- result / review
@app.get("/s/{sid}", response_class=HTMLResponse)
def view_submission(request: Request, sid: int):
    u = me(request)
    if not u:
        return RedirectResponse("/", 303)
    s = get_sub(sid)
    if not s or not can_view(u, s):
        return page("Not found", "<div class='card'><p>Submission not found.</p></div>", u)
    rep = json.loads(s["report"] or "{}")

    items = []
    for c in rep.get("claims", []):
        when = "in the title or caption" if c.get("source") == "caption" else f'at {fmt_time(c["time"])}'
        items.append(f'<li>{e(c["heard"])} for {e(c["config"])} {when} '
                     f'(approved {e(c["approved"])}) {chip(c["status"])}</li>')
    claims = f"<ul>{''.join(items)}</ul>" if items else '<p class="muted">No price claims were detected.</p>'

    src = ""
    if s["source_url"]:
        src = (f'<p class="muted">Fetched from a link: {e(s["source_url"])}<br>'
               'The platform\'s copy can differ from the original file, so the file-hash check does not apply '
               'to link submissions.</p>')

    summary = f"""
    <div class="card"><h2>Summary card</h2>
    <p><b>{e(s["bname"])}</b> &middot; {e(s["uname"])} &middot; {e(s["filename"] or "")} &middot; language: {e(s["language"])}</p>
    {src}
    <p><b>Claims heard</b></p>{claims}
    <p><b>Verdict:</b> {e(s["verdict"] or "")} &nbsp; {chip(s["status"])}</p>
    <p class="counts"><span class="chip bad">{rep.get("flags", 0)} flags</span>
    <span class="chip warn">{rep.get("supervision", 0)} supervision</span>
    <span class="chip ok">{rep.get("passed", 0)} passed</span></p>"""
    if s["approval_id"]:
        summary += (f'<p><b>Approval ID:</b> {e(s["approval_id"])}<br>'
                    f'<span class="muted">File hash (SHA-256):</span> <span class="mono">{e(s["sha256"])}</span></p>')
    summary += "</div>"

    rows = []
    for f in rep.get("findings", []):
        conf = f' (confidence {f["confidence"]})' if f.get("confidence") is not None else ""
        when = "Title / caption" if f.get("source") == "caption" else fmt_time(f["time"])
        rows.append(f'<tr><td>{chip(f["status"])}<br><span class="muted">{e(f["severity"])}</span></td>'
                    f'<td>{e(when)}</td><td><b>{e(f["type"])}</b>{e(conf)}<br>'
                    f'Heard: {e(str(f["evidence"]))}<br>{e(f["explanation"])}<br>'
                    f'<i>Suggested fix:</i> {e(f["suggestion"])}</td></tr>')
    findings = ('<div class="card"><h2>Findings</h2><table><tr><th>Status</th><th>Time</th><th>Detail</th></tr>'
                + "".join(rows) + "</table></div>") if rows else \
        '<div class="card"><h2>Findings</h2><p>No issues found.</p></div>'

    tr = "".join(f'<tr><td>{fmt_time(t["start"])}</td><td>{e(t["text"])}</td><td class="muted">{t["conf"]}</td></tr>'
                 for t in rep.get("transcript", []))
    transcript = (f'<div class="card"><h2>Transcript</h2><p class="muted">Sensitive terms are redacted.</p>'
                  f'<table><tr><th>Time</th><th>Text</th><th>Confidence</th></tr>{tr}</table></div>')

    actions = ""
    if u["role"] == "submitter" and s["user_id"] == u["id"] and s["status"] in ("REJECTED", "BLOCKED"):
        actions = f"""<div class="card"><h2>What would you like to do?</h2>
        <p>Fix the issues and <a href="/">upload again</a>, or dispute if you believe the finding is wrong.</p>
        <form method="post" action="/dispute/{sid}">
        <label>Why is the finding wrong? (mention the time in the video if you can)</label>
        <textarea name="note" rows="3" required></textarea>
        <button class="alt" type="submit">Dispute this decision</button></form></div>"""
    if u["role"] == "admin" and s["brand_id"] == u["brand_id"] and s["status"] in ("SUPERVISION", "DISPUTED"):
        dispute = ""
        yes, no = "Approve", "Reject"
        if s["status"] == "DISPUTED":
            dispute = f'<p><b>Creator\'s explanation:</b> {e(s["dispute_note"] or "")}</p>'
            yes, no = "Overturn (approve)", "Uphold rejection"
        actions = f"""<div class="card"><h2>Your decision</h2>{dispute}
        <form method="post" action="/decide/{sid}"><label>Note (optional)</label>
        <textarea name="note" rows="2"></textarea>
        <button name="decision" value="approve" type="submit">{yes}</button>
        <button class="danger" name="decision" value="reject" type="submit">{no}</button></form></div>"""
    if s["decision_note"]:
        actions += f'<div class="card"><b>Manager note:</b> {e(s["decision_note"])}</div>'

    au = "".join(f'<tr><td class="muted">{e(a["at"])}</td><td>{e(a["actor"])}</td><td>{e(a["action"])}</td>'
                 f'<td>{e(a["note"] or "")}</td></tr>'
                 for a in q("SELECT * FROM audit WHERE sub_id=? ORDER BY id", (sid,)))
    audit = f'<div class="card"><h2>Audit trail</h2><table>{au}</table></div>'

    return page(f"Submission {sid}", summary + actions + findings + transcript + audit, u)


@app.post("/dispute/{sid}")
def dispute(request: Request, sid: int, note: str = Form("")):
    u, s = me(request), get_sub(sid)
    if u and s and s["user_id"] == u["id"] and s["status"] in ("REJECTED", "BLOCKED") and note.strip():
        ex("UPDATE submissions SET status='DISPUTED', dispute_note=? WHERE id=?", (note.strip()[:1000], sid))
        log(sid, u["name"], "DISPUTE_RAISED", note.strip()[:300])
    return RedirectResponse(f"/s/{sid}", 303)


@app.post("/decide/{sid}")
def decide(request: Request, sid: int, decision: str = Form(...), note: str = Form("")):
    u, s = me(request), get_sub(sid)
    if (u and s and u["role"] == "admin" and s["brand_id"] == u["brand_id"]
            and s["status"] in ("SUPERVISION", "DISPUTED")):
        was_dispute = s["status"] == "DISPUTED"
        if decision == "approve":
            status, approval = "APPROVED", new_approval_id()
            action = "DISPUTE_OVERTURNED" if was_dispute else "APPROVED"
        else:
            status, approval = "REJECTED_FINAL", None
            action = "DISPUTE_UPHELD" if was_dispute else "REJECTED"
        ex("UPDATE submissions SET status=?, approval_id=?, decision_note=? WHERE id=?",
           (status, approval, note.strip()[:1000], sid))
        log(sid, u["name"], action, (approval or "") + (" " + note.strip()[:300] if note.strip() else ""))
    return RedirectResponse(f"/s/{sid}", 303)


# ---------------------------------------------------------------- admin views
def admin_dash(u):
    bid = u["brand_id"]
    brand = q("SELECT * FROM brands WHERE id=?", (bid,))[0]
    allrows = q(SUB_SQL + "WHERE s.brand_id=? ORDER BY s.id DESC", (bid,))
    queue = [r for r in allrows if r["status"] in ("SUPERVISION", "DISPUTED")]
    n = Counter(r["status"] for r in allrows)

    types = Counter()
    for r in allrows:
        try:
            for f in json.loads(r["report"] or "{}").get("findings", []):
                types[f["type"]] += 1
        except Exception:
            pass
    ov = q("""SELECT a.action, COUNT(*) AS c FROM audit a JOIN submissions s ON s.id=a.sub_id
              WHERE s.brand_id=? AND a.action IN ('DISPUTE_OVERTURNED','DISPUTE_UPHELD') GROUP BY a.action""", (bid,))
    ovd = {r["action"]: r["c"] for r in ov}
    common = "".join(f"<li>{e(k)}: {v}</li>" for k, v in types.most_common(5)) or "<li>No findings yet.</li>"

    body = f"""
    <div class="card"><h2>{e(brand["name"])}</h2>
    <p class="counts"><span class="chip">{len(allrows)} submissions</span>
    <span class="chip warn">{len(queue)} need your decision</span>
    <span class="chip ok">{n["APPROVED"] + n["AUTO_APPROVED"]} approved</span>
    <span class="chip bad">{n["REJECTED"] + n["BLOCKED"] + n["REJECTED_FINAL"]} rejected</span></p>
    <a class="btn" href="/admin/setup">Brand rules and fact registry</a></div>
    <div class="card"><h2>Needs your decision</h2>{sub_table(queue)}</div>
    <div class="card"><h2>Insights</h2>
    <p><b>Most common findings</b></p><ul>{common}</ul>
    <p>Disputes overturned: {ovd.get("DISPUTE_OVERTURNED", 0)} &middot; upheld: {ovd.get("DISPUTE_UPHELD", 0)}</p>
    <p class="muted">Findings that creators successfully dispute point to guidelines that may need clearer wording.</p></div>
    <div class="card"><h2>All submissions</h2>{sub_table(allrows)}</div>"""
    return page("Dashboard", body, u)


def lines(s):
    return [x.strip() for x in (s or "").splitlines() if x.strip()]


def parse_price(s):
    s = s.strip()
    try:
        return int(float(s.replace(",", "")))
    except ValueError:
        pass
    found = extract_prices(s)
    return found[0]["value"] if found else None


@app.get("/admin/setup", response_class=HTMLResponse)
def setup_form(request: Request, msg: str = ""):
    u = me(request)
    if not u or u["role"] != "admin":
        return RedirectResponse("/", 303)
    reg = json.loads(q("SELECT registry FROM brands WHERE id=?", (u["brand_id"],))[0]["registry"])
    cfg = "\n".join(f'{c["name"]} = {c["price"]}' for c in reg["configs"])
    body = f"""
    <div class="card"><h2>Brand rules and fact registry</h2>
    <p class="muted">These are the core rules every submission is checked against. Prices are in rupees
    (for example 13000000, or write 1.3 Cr).</p>
    {f'<p><b>{e(msg)}</b></p>' if msg else ''}
    <form method="post" action="/admin/setup">
      <label>Brand name</label><input name="brand" value="{e(reg.get('brand', ''))}">
      <label>Project name</label><input name="project" value="{e(reg.get('project', ''))}">
      <label>RERA number</label><input name="rera" value="{e(reg.get('rera', ''))}">
      <label>Possession date</label><input name="possession" value="{e(reg.get('possession', ''))}">
      <label>Configurations and approved prices (one per line, like: 2 BHK = 13000000)</label>
      <textarea name="configs" rows="4">{e(cfg)}</textarea>
      <label>Banned claims (one per line)</label>
      <textarea name="banned" rows="4">{e(chr(10).join(reg.get('banned_phrases', [])))}</textarea>
      <label>Confidential terms that must never appear (one per line)</label>
      <textarea name="confidential" rows="4">{e(chr(10).join(reg.get('confidential', [])))}</textarea>
      <label>Approved contact numbers (one per line)</label>
      <textarea name="contacts" rows="2">{e(chr(10).join(reg.get('allowed_contacts', [])))}</textarea>
      <label>Glossary: project names, places, key terms (one per line)</label>
      <textarea name="glossary" rows="4">{e(chr(10).join(reg.get('glossary', [])))}</textarea>
      <button type="submit">Save rules</button> <a class="btn alt" href="/">Back</a>
    </form></div>"""
    return page("Brand rules", body, u)


@app.post("/admin/setup")
def setup_save(request: Request, brand: str = Form(""), project: str = Form(""), rera: str = Form(""),
               possession: str = Form(""), configs: str = Form(""), banned: str = Form(""),
               confidential: str = Form(""), contacts: str = Form(""), glossary: str = Form("")):
    u = me(request)
    if not u or u["role"] != "admin":
        return RedirectResponse("/", 303)
    cfgs = []
    for ln in lines(configs):
        if "=" not in ln:
            return RedirectResponse(f"/admin/setup?msg=Could+not+read+line:+{ln[:30]}", 303)
        name, price = ln.split("=", 1)
        val = parse_price(price)
        if not name.strip() or not val or val <= 0:
            return RedirectResponse(f"/admin/setup?msg=Could+not+read+the+price+on+line:+{ln[:30]}", 303)
        cfgs.append({"name": name.strip(), "price": val})
    if not cfgs:
        return RedirectResponse("/admin/setup?msg=Add+at+least+one+configuration+with+a+price", 303)
    reg = {"brand": brand.strip(), "project": project.strip(), "rera": rera.strip(),
           "possession": possession.strip(), "configs": cfgs, "banned_phrases": lines(banned),
           "confidential": lines(confidential), "allowed_contacts": lines(contacts),
           "glossary": lines(glossary)}
    ex("UPDATE brands SET name=?, registry=? WHERE id=?",
       (brand.strip() or "Brand", json.dumps(reg, ensure_ascii=False), u["brand_id"]))
    return RedirectResponse("/admin/setup?msg=Saved.+New+submissions+use+these+rules.", 303)


# -------------------------------------------------------- tamper check (hash)
@app.get("/verify", response_class=HTMLResponse)
def verify_form(request: Request):
    u = me(request)
    if not u:
        return RedirectResponse("/", 303)
    body = """<div class="card"><h2>Verify a file against its approval</h2>
    <p class="muted">Upload the file you are about to post. If it is identical to an approved submission,
    you will see the approval ID. If anything was edited after approval, it will not match.</p>
    <form method="post" action="/verify" enctype="multipart/form-data">
    <input type="file" name="file" required><button type="submit">Check file</button></form></div>"""
    return page("Verify a file", body, u)


@app.post("/verify", response_class=HTMLResponse)
def verify_check(request: Request, file: UploadFile = File(...)):
    u = me(request)
    if not u:
        return RedirectResponse("/", 303)
    h, size = hashlib.sha256(), 0
    while True:
        chunk = file.file.read(1024 * 1024)
        if not chunk:
            break
        size += len(chunk)
        if size > MAX_MB * 1024 * 1024:
            return page("Verify", "<div class='card'><p>File is too large to check.</p></div>", u)
        h.update(chunk)
    digest = h.hexdigest()
    rows = q("SELECT id, approval_id FROM submissions WHERE sha256=? AND approval_id IS NOT NULL AND source_url IS NULL",
             (digest,))
    if rows:
        result = (f'<p class="chip ok">Match</p><p>This file is identical to approved submission '
                  f'<a href="/s/{rows[0]["id"]}">#{rows[0]["id"]}</a> (approval ID {e(rows[0]["approval_id"])}).</p>')
    else:
        result = ('<p class="chip bad">No match</p><p>This file does not match any approved submission. '
                  'It may have been edited after approval, or it was never approved.</p>')
    return page("Verify a file", f'<div class="card"><h2>Result</h2>{result}'
                f'<p class="mono">{digest}</p><a class="btn" href="/verify">Check another file</a></div>', u)