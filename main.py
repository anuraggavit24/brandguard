#!/usr/bin/env python3
"""BrandGuard web app (Round 2) - link ingestion, caption check, stricter auto-approval."""

import hashlib
import html
import json
import math
import os
import re
import secrets
import sqlite3
import subprocess
import uuid
from collections import Counter
from datetime import datetime
from pathlib import Path
from urllib.parse import quote, urlparse

import requests
from fastapi import FastAPI, File, Form, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from starlette.middleware.sessions import SessionMiddleware

import learning as LRN
import ocr as OCR
import realestate as RE
import ui
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
ROLE_LABEL = {"admin": "Builder / Brand Manager", "submitter": "Creator / Partner"}

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
    try:
        con.execute("ALTER TABLE audit ADD COLUMN brand_id INTEGER")
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
RE.setup(DB_PATH)
RE.seed_if_empty()
LRN.setup(DB_PATH)


def log(sid, actor, action, note="", brand_id=None):
    ex("INSERT INTO audit (sub_id, at, actor, action, note, brand_id) VALUES (?,?,?,?,?,?)",
       (sid, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), actor, action, note, brand_id))


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
LANG_LABEL = {"mr": "Marathi", "hi": "Hindi", "en": "English", "auto": "Auto-detect"}
QUEUE_STATUSES = ("SUPERVISION", "DISPUTED")
APPROVED_STATUSES = ("APPROVED", "AUTO_APPROVED")
REJECTED_STATUSES = ("REJECTED", "BLOCKED", "REJECTED_FINAL")
PAGE_SIZE = 15

SUB_SQL = """SELECT s.*, u.name AS uname, b.name AS bname FROM submissions s
             JOIN users u ON u.id=s.user_id JOIN brands b ON b.id=s.brand_id """


def user_brands(u):
    return q("SELECT b.* FROM brands b JOIN memberships m ON m.brand_id=b.id WHERE m.user_id=? ORDER BY b.id",
             (u["id"],))


def current_company(request, u):
    """The company a submitter is working in. Always one of their own memberships."""
    ids = [b["id"] for b in user_brands(u)]
    if not ids:
        return None
    cid = request.session.get("company") if request is not None else None
    return cid if cid in ids else ids[0]


def page(title, body, user=None, active="", crumbs=None, request=None):
    if not user:
        return HTMLResponse(ui.landing(body))
    flash = request.session.pop("flash", "") if request is not None else ""
    company, queue_n = None, 0
    if user["role"] == "submitter":
        company = (current_company(request, user), [(b["id"], b["name"]) for b in user_brands(user)])
    else:
        queue_n = q("SELECT COUNT(*) AS c FROM submissions WHERE brand_id=? AND status IN ('SUPERVISION','DISPUTED')",
                    (user["brand_id"],))[0]["c"]
    demo = [(k, lbl, DEMO[k] == user["id"]) for k, lbl in
            (("admin", "Builder"), ("partner", "Channel Partner"), ("freelancer", "Freelancer"))]
    return HTMLResponse(ui.shell(title, body, user, ROLE_LABEL[user["role"]], active, crumbs,
                                 queue_n, company, flash, demo))


def err_page(u, msg, request=None):
    back = "/submit" if u["role"] == "submitter" else "/"
    body = (ui.page_header("Could not complete this request")
            + ui.alert(e(msg), "bad", "Something went wrong.")
            + f'<p style="margin-top:20px"><a class="btn" href="{back}">Go back</a></p>')
    return page("Could not complete", body, u, "", [("Error", None)], request)


def rep_of(row):
    try:
        return json.loads(row["report"] or "{}")
    except (TypeError, ValueError):
        return {}


def risk_badge(rep):
    order = ["LOW", "MEDIUM", "HIGH", "CRITICAL"]
    sev = [f.get("severity", "LOW") for f in rep.get("findings", [])]
    if not sev:
        return ui.badge("No findings", "ok", "check-circle")
    top = max(sev, key=lambda s: order.index(s) if s in order else 0)
    tone = {"CRITICAL": "bad", "HIGH": "bad", "MEDIUM": "warn"}.get(top, "neutral")
    return ui.badge(f"{top.title()} risk", tone, "alert" if tone != "neutral" else "info")


def sub_table(rows, show_user=True, label="Submissions", review_label="Review"):
    if not rows:
        return ui.empty("Nothing here yet", "Submissions will appear here as soon as they are made.")
    heads = ["Submission"] + (["Creator"] if show_user else []) + ["Company", "Submitted", "Findings", "Status", "Action"]
    out = []
    for r in rows:
        rep = rep_of(r)
        link = f' {ui.icon("link", 14)}' if r["source_url"] else ""
        fname = e(r["filename"] or "Untitled")
        cells = [f'<a href="/s/{r["id"]}"><b>#{r["id"]}</b></a>{link}<span class="trunc" title="{fname}">{fname}</span>']
        if show_user:
            cells.append(e(r["uname"]))
        n = f'{rep.get("flags", 0)} violation(s), {rep.get("supervision", 0)} to check'
        cells += [e(r["bname"]), f'<span class="muted">{e(r["created_at"])}</span>',
                  f'{risk_badge(rep)}<br><span class="muted">{n}</span>', ui.chip(r["status"]),
                  f'<a class="btn sm {"" if r["status"] in QUEUE_STATUSES and show_user else "secondary"}" '
                  f'href="/s/{r["id"]}" aria-label="{review_label if (r["status"] in QUEUE_STATUSES and show_user) else "View"} submission {r["id"]}">'
                  f'{review_label if (r["status"] in QUEUE_STATUSES and show_user) else "View"}</a>']
        out.append(cells)
    return ui.table(heads, out, label)


# --------------------------------------------------------------------- landing
@app.get("/health")
def health():
    return {"ok": True}


@app.get("/ocr-status")
def ocr_status():
    import shutil
    return {"ocr_available": OCR.available(), "tesseract": OCR.TESSERACT,
            "ffmpeg": shutil.which("ffmpeg"), "ffprobe": shutil.which("ffprobe"),
            "fps": OCR.OCR_FPS, "budget": OCR.OCR_BUDGET}


@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    u = me(request)
    if not u:
        def role(key, ic, title, text, btn):
            return (f'<div class="card role-card"><span class="ic-lg">{ui.icon(ic, 22)}</span><h2>{title}</h2>'
                    f'<p class="muted">{text}</p><a class="btn" href="/enter/{key}">{btn}{ui.icon("arrow-right", 16)}</a></div>')
        body = f"""
        <div style="margin-bottom:28px"><h1>Review reels before they go live</h1>
        <p class="page-desc">BrandGuard listens to a marketing reel in Marathi, Hindi or English, checks every price
        and claim against the brand's approved facts, and sends anything uncertain to a person. Nothing is approved
        without a recorded decision.</p></div>
        <p class="sec-title">Choose a demo role to enter</p>
        <div class="cols-3">
          {role("admin", "shield", "Builder / Brand Manager",
                "Set brand rules and approved facts, review flagged and disputed items, then approve or reject.",
                "Enter as Builder")}
          {role("partner", "upload", "Channel Partner",
                "Submit a reel or paste a link for one company and see the result.", "Enter as Partner")}
          {role("freelancer", "building", "Freelancer",
                "Works with two companies under one login and switches between them.", "Enter as Freelancer")}
        </div>
        <p style="margin-top:20px"><a class="btn secondary" href="/test-audio">Judges: download test audio</a></p>
        <p class="muted" style="margin-top:12px">This is a demo. No sign-up is needed and the roles are not real accounts.</p>"""
        return page("Welcome", body)
    return admin_dash(request, u) if u["role"] == "admin" else submitter_dash(request, u)


@app.get("/enter/{key}")
def enter(request: Request, key: str):
    uid = DEMO.get(key)
    if uid:
        request.session["uid"] = uid
        request.session.pop("company", None)
    return RedirectResponse("/", 303)


@app.get("/company")
def switch_company(request: Request, id: int = 0):
    u = me(request)
    if u and u["role"] == "submitter" and id in [b["id"] for b in user_brands(u)]:
        request.session["company"] = id
    ref = urlparse(request.headers.get("referer", "")).path
    return RedirectResponse(ref if ref.startswith("/") and not ref.startswith("//") and not ref.startswith("/s/") else "/", 303)


@app.get("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/", 303)


# ------------------------------------------------------------ submitter views
def submitter_dash(request, u):
    cid = current_company(request, u)
    brand = q("SELECT name FROM brands WHERE id=?", (cid,))
    cname = brand[0]["name"] if brand else "your company"
    mine = q(SUB_SQL + "WHERE s.user_id=? AND s.brand_id=? ORDER BY s.id DESC", (u["id"], cid))
    n = Counter(r["status"] for r in mine)
    approved = sum(n[s] for s in APPROVED_STATUSES)
    rejected = sum(n[s] for s in REJECTED_STATUSES)
    in_review = n["SUPERVISION"] + n["DISPUTED"] + n["NEEDS_CONFIRMATION"]
    first = u["name"].split(" (")[0].split()[0]
    multi = len(user_brands(u)) > 1

    welcome = f"""<section class="card welcome" aria-labelledby="wl"><div class="card-head"><h2 id="wl">Welcome, {e(first)}</h2>
      <button type="button" class="btn secondary sm" data-dismiss="creator">Dismiss</button></div>
      <p>Submit a reel and BrandGuard checks it against {e(cname)}'s approved prices and rules before it is published.
      Uncertain cases are sent to a person, so you always get a clear answer.</p>
      <ol class="steps"><li>Submit content</li><li>Analyze content</li><li>Review findings</li><li>Resolve issues</li><li>Receive a decision</li></ol></section>"""
    attn = ""
    if n["REJECTED"] + n["BLOCKED"]:
        attn = ui.alert(f'{n["REJECTED"] + n["BLOCKED"]} submission(s) were rejected. Open them to see what to fix. '
                        'You can resubmit a corrected file, or dispute the decision if you think it is wrong.',
                        "warn", "Needs your attention.")
    scope = (f'<p class="muted">Showing activity for <b>{e(cname)}</b>. Use the company switcher at the top to change.</p>'
             if multi else "")
    body = (ui.page_header("My Dashboard", f"Your reel submissions for {e(cname)}.",
                           f'<a class="btn" href="/submit">{ui.icon("upload", 16)}Submit a Reel</a>')
            + '<div class="stack">' + welcome + attn + scope
            + '<div class="stats">'
            + ui.stat("Submissions", len(mine), "", "/reviews")
            + ui.stat("In review", in_review, "Waiting for a person", "/reviews?status=supervision", "warn")
            + ui.stat("Approved", approved, "", "/reviews?status=approved", "ok")
            + ui.stat("Rejected", rejected, "Fix and resubmit, or dispute", "/reviews?status=rejected", "bad")
            + '</div>'
            + ui.card("Recent submissions",
                      sub_table(mine[:5], show_user=False, label="Recent submissions") if mine else
                      ui.empty("No submissions yet", f"Submit your first reel for {e(cname)} to get started.",
                               '<a class="btn" href="/submit">Submit a Reel</a>'),
                      actions='<a href="/reviews">View all</a>' if len(mine) > 5 else "")
            + '</div>')
    return page("My Dashboard", body, u, "overview", [], request)


@app.get("/submit", response_class=HTMLResponse)
def submit_form(request: Request):
    u = me(request)
    if not u or u["role"] != "submitter":
        return RedirectResponse("/", 303)
    brands = user_brands(u)
    cid = current_company(request, u)
    opts = "".join(f'<option value="{b["id"]}"{" selected" if b["id"] == cid else ""}>{e(b["name"])}</option>'
                   for b in brands)
    langs = "".join(f'<option value="{k}">{v}</option>' for k, v in
                    (("mr", "Marathi"), ("hi", "Hindi"), ("en", "English"), ("auto", "Auto-detect")))
    projs = RE.authorized_projects(u["id"], cid)
    popts = '<option value="">Detect automatically (recommended)</option>' + "".join(
        f'<option value="{p["id"]}">{e(p["official_name"])}{" - " + e(p["city"]) if p["city"] else ""}</option>' for p in projs)
    company = (f'<label for="brand_id">Company</label><select id="brand_id" name="brand_id">{opts}</select>'
               f'<label for="project_id">Project <span class="muted">(optional)</span></label>'
               f'<select id="project_id" name="project_id">{popts}</select>'
               f'<p class="hint">BrandGuard finds the project from what is said and written. You only need to choose one if '
               f'you want to be explicit. You can only pick projects you have been given access to'
               f'{"" if projs else ". You have none for this company yet, so ask the company to grant access"}.</p>')
    lang = (f'<label for="language">Spoken language</label><select id="language" name="language">{langs}</select>'
            '<p class="hint">Choose the language spoken in the reel. If unsure, pick Auto-detect.</p>')
    exts = ",".join(sorted(ALLOWED))
    file_form = f"""
    <form method="post" action="/upload" enctype="multipart/form-data" data-lock>
      <div class="dropzone" id="dropzone">{ui.icon("upload", 32)}
        <p><b>Drag a video or audio file here</b></p>
        <p class="muted">Accepted: {", ".join(x.lstrip(".") for x in sorted(ALLOWED))}. Up to {MAX_MB} MB.
        The first {MAX_SECONDS // 60} minutes are reviewed.</p>
        <label class="btn secondary" for="file">Browse files</label>
        <input id="file" type="file" name="file" required data-max="{MAX_MB * 1024 * 1024}" data-ext="{exts}"
               accept="video/*,audio/*" aria-describedby="file-err"></div>
      <div class="picked" id="picked">{ui.icon("file", 18)}<b id="picked-name"></b><span class="sp"></span>
        <button type="button" class="btn secondary sm" id="remove-file">Remove</button></div>
      <p class="req" id="file-err" role="alert" hidden></p>
      {company}{lang}
      <p data-busy hidden class="muted" role="status">Reviewing. This can take 10 to 40 seconds. Please keep this page open.</p>
      <button id="submit-file" class="btn" type="submit" data-busy-label="Reviewing...">Submit for Compliance Review</button>
    </form>"""
    if LINKS_ENABLED:
        link_form = f"""
    {ui.alert("Link submission is supported on a laptop or desktop. On a phone, download the video and upload the file instead.", "info")}
    <form method="post" action="/upload_link" data-lock style="margin-top:16px">
      <label for="url">Link to a public reel</label>
      <input id="url" type="url" name="url" required placeholder="https://www.youtube.com/shorts/..." aria-describedby="url-h">
      <p class="hint" id="url-h">YouTube Shorts, Instagram reels and Facebook reels. Both the audio and the post's title and
      description are reviewed. Private posts cannot be fetched.</p>
      {company}{lang}
      <p data-busy hidden class="muted" role="status">Fetching and reviewing. This can take up to a minute. Please keep this page open.</p>
      <button class="btn" type="submit" data-busy-label="Fetching...">Fetch and Submit for Compliance Review</button>
    </form>"""
    else:
        link_form = ui.alert(
            "Link checking is switched off on this hosted demo, because YouTube, Instagram and Facebook block automated "
            "downloads from shared cloud servers. It works in the local build on a laptop or desktop. To check a posted reel "
            "here, download it and use <b>Upload a file</b>.", "warn", "Links are unavailable here.")
    body = (ui.page_header("Submit a Reel for Review",
                           "BrandGuard listens to the reel, checks every price and claim against the brand's approved facts "
                           "and shows you the result. Anything uncertain goes to a person for a decision.")
            + '<div class="cols"><div>'
            + ui.card("", f"""
              <div class="method" role="tablist" aria-label="Submission method">
                <button type="button" class="btn" role="tab" id="tab-file" aria-selected="true" aria-controls="panel-file">{ui.icon("upload", 16)}Upload a file</button>
                <button type="button" class="btn" role="tab" id="tab-link" aria-selected="false" aria-controls="panel-link">{ui.icon("link", 16)}Paste a link</button></div>
              <div id="panel-file" role="tabpanel" aria-labelledby="tab-file">{file_form}</div>
              <div id="panel-link" role="tabpanel" aria-labelledby="tab-link" hidden>{link_form}</div>""")
            + '</div><div>'
            + ui.card("What happens next", """<ol class="muted" style="padding-left:20px;margin:0">
              <li>The audio is transcribed and checked, usually in 10 to 40 seconds.</li>
              <li>You see one of: auto-approved, rejected, or sent to a person.</li>
              <li>If rejected, fix the reel and resubmit, or dispute the finding.</li>
              <li>Nothing is approved just because it uploaded.</li></ol>""")
            + '</div></div>')
    return page("Submit a Reel", body, u, "submit", [("Submit a Reel", None)], request)


@app.get("/help", response_class=HTMLResponse)
def help_page(request: Request):
    u = me(request)
    if not u:
        return RedirectResponse("/", 303)
    legend = [[ui.chip(k), t] for k, t in (
        ("AUTO_APPROVED", "Every price matched the approved facts and nothing needed a person. An approval ID was issued."),
        ("SUPERVISION", "BrandGuard was not sure (for example, unclear audio or a possible lakh/crore mix-up). A builder will decide."),
        ("REJECTED", "A claim breaks the brand rules, such as a wrong price or a banned phrase. Fix and resubmit, or dispute."),
        ("BLOCKED", "Confidential company information was mentioned. Remove it before resubmitting."),
        ("DISPUTED", "You disagreed with a rejection. A builder will uphold or overturn it."),
        ("APPROVED", "A builder approved this after review."),
        ("REJECTED_FINAL", "A builder upheld the rejection after review."))]
    body = (ui.page_header("Help and Guidelines", "How reviews work and what each status means.")
            + '<div class="stack">'
            + ui.card("What BrandGuard checks", """<ul class="muted" style="margin:0;padding-left:20px">
              <li>Prices spoken or written, compared with the approved price list (including forms like "dedh crore" or "sava crore").</li>
              <li>Banned claims and confidential company terms.</li>
              <li>Phone numbers and emails that are not on the approved contact list.</li>
              <li>Comparative or urgency claims that need evidence, such as "lowest price" or "limited units".</li>
              <li>For linked posts, the title and description as well as the audio.</li></ul>""")
            + ui.card("What each status means", ui.table(["Status", "Meaning"], legend, "Status meanings"))
            + ui.card("Not yet available", """<p class="muted" style="margin:0">Reading on-screen text, comparing spoken and
              written prices, poster review, RERA and possession-date verification and email sign-in are planned. They are not
              part of reviews today.</p>""")
            + '</div>')
    return page("Help and Guidelines", body, u, "help", [("Help and Guidelines", None)], request)


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


def redact(text, reg):
    out = text or ""
    for w in reg.get("confidential", []):
        if w.strip():
            out = re.sub(re.escape(norm(w)), "[REDACTED]", out, flags=re.I)
    return out


def glossary_for(reg, brand_id, user_id):
    terms = list(reg.get("glossary", []))
    for p in RE.authorized_projects(user_id, brand_id):
        terms += RE.names_of(p)
    seen, out = set(), []
    for t in terms:
        if t and t.lower() not in seen:
            seen.add(t.lower())
            out.append(t)
    return out


def transcribe_file(src: Path, lang: str, glossary):
    wav = src.parent / (src.stem + "_16k.wav")
    try:
        extract_audio(src, wav)
        return transcribe(wav, lang, glossary)
    finally:
        wav.unlink(missing_ok=True)

        

def analyze(u, brand_id, segs, caption, reg, hint_pid=None, confirmed=None, is_link=False, screen=None):
    """Rules plus project-aware claim checks. Never approves anything it could not fully check."""
    rep = review(segs, reg, THRESHOLD, check_prices=False)
    caption_parts = RE._split_caption(caption) if caption.strip() else []
    if caption.strip():
        cap = review([{"start": 0, "end": 0, "text": caption, "conf": 1.0}], reg, THRESHOLD, check_prices=False)
        for f in cap["findings"]:
            f["source"] = "caption"
            rep["findings"].append(f)

    screen_lines = list((screen or {}).get("lines", []))
    if screen_lines:  # banned phrases and confidential terms drawn on screen
        scr = review([{"start": l["start"], "end": l["end"], "text": l["text"], "conf": l["conf"]} for l in screen_lines],
                     reg, THRESHOLD, check_prices=False)
        for f in scr["findings"]:
            f["source"] = "screen"
            rep["findings"].append(f)
    sources = [(s["text"], s["start"], "audio") for s in segs]
    sources += [(l["text"], l["start"], "screen") for l in screen_lines]
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

    authorised = RE.authorized_projects(u["id"], brand_id)
    all_p = RE.brand_projects(brand_id)
    texts = [("audio", i, s["text"]) for i, s in enumerate(segs)] + [("caption", i, c) for i, c in enumerate(caption_parts)]
    texts += [("screen", i, l["text"]) for i, l in enumerate(screen_lines)]
    if confirmed:
        idres = {"state": "CONFIRMED", "project_ids": list(confirmed), "evidence": {}, "out_of_scope": [],
                 "segments": {}, "note": "Project confirmed by the submitter."}
    else:
        idres = RE.identify(texts, authorised, all_p, hint_pid)
    state = idres["state"]
    names = {p["id"]: p["official_name"] for p in all_p}
    rep["identity"] = {"state": state, "project_ids": idres["project_ids"], "note": idres["note"],
                       "evidence": {str(k): v for k, v in idres["evidence"].items()},
                       "names": {str(k): names.get(k, "?") for k in set(idres["project_ids"]) | set(idres["out_of_scope"])}}
    rep["project_ids"] = list(idres["project_ids"])
    rep["inputs"] = {"segments": [{"start": s["start"], "end": s.get("end", s["start"]), "text": redact(s["text"], reg),
                                   "conf": s.get("conf", 1.0)} for s in segs],
                     "caption": redact(caption, reg),
                     "screen": [{"start": l["start"], "end": l["end"], "text": redact(l["text"], reg),
                                 "raw": redact(l.get("raw", l["text"]), reg), "conf": l["conf"]} for l in screen_lines]}
    if screen is not None:
        rep["screen_meta"] = {"frames": screen.get("frames", 0), "total": screen.get("total", 0), "partial": bool(screen.get("partial"))}
    rep["policy"] = RE.POLICY_VERSION
    rep["claims"], rep["facts_used"] = [], []
    rep["needs_confirmation"] = state in ("LIKELY", "AMBIGUOUS", "NOT_FOUND", "CONFLICT") and bool(segs or caption.strip())
    rep["candidates"] = [p["id"] for p in authorised] if state in ("NOT_FOUND",) else list(idres["project_ids"])

    checks = [("Project identification", "done" if not rep["needs_confirmation"] else "pending",
               idres["note"] or "Project identified from the content.")]
    if state == "NOT_AUTHORIZED":
        rep["findings"].append(make_finding(
            "SUPERVISION", "HIGH", "UNAUTHORIZED_PROJECT", 0,
            ", ".join(names.get(p, "?") for p in idres["out_of_scope"]),
            "The content seems to promote a project this account has not been given access to.",
            "Remove that project, or ask the company to grant access."))
    elif state == "SELECTED":
        rep["findings"].append(make_finding(
            "SUPERVISION", "LOW", "IDENTITY_WEAK", 0, names.get(idres["project_ids"][0], ""),
            "The content never names the project, so the project could only be taken from your selection.",
            "A person should confirm this reel is about the selected project."))
    if idres["out_of_scope"] and state not in ("NOT_AUTHORIZED",):
        rep["findings"].append(make_finding(
            "SUPERVISION", "HIGH", "UNAUTHORIZED_PROJECT", 0, ", ".join(names.get(p, "?") for p in idres["out_of_scope"]),
            "The content also mentions a project this account has not been given access to.",
            "Remove that project, or ask the company to grant access."))

    if not rep["needs_confirmation"] and idres["project_ids"]:
        by_proj, unassigned = RE.assign_segments(segs, caption_parts, idres, all_p, screen_lines)
        claims, used = RE.validate(by_proj, all_p, THRESHOLD)
        rep["claims"], rep["facts_used"] = claims, used
        for c in claims:
            if c["verdict"] == RE.VIOLATION and c["kind"] in ("price", "booking"):
                prec = LRN.precedent(brand_id, c)
                if prec:
                    said = f" The creator had said {fmt_money(prec['said_value'])}." if prec["said_value"] else ""
                    c["verdict"] = RE.REVIEW
                    c["reason"] += (f" A similar reading was overturned by a builder before "
                                    f"(submission #{prec['sub_id']}).{said}")
                    c["fix"] = "A manager should listen to this moment and confirm."
                    c["precedent"] = prec["sub_id"]
            if c["verdict"] != RE.VERIFIED:
                rep["findings"].append(RE.claim_to_finding(c))
        for src_, t_, conf_, text_ in unassigned:
            if extract_prices(text_) or RE.AREA_RE.search(norm(text_)):
                rep["findings"].append(make_finding(
                    "SUPERVISION", "MEDIUM", "PROJECT_UNCERTAIN", t_, text_[:80],
                    "A price or area was mentioned, but it could not be linked to one project.",
                    "A person should check which project this refers to.", conf_, src_))

    rep["passed"] = sum(1 for c in rep["claims"] if c["verdict"] == RE.VERIFIED)
    speech = bool(segs)
    checks.append(("Spoken claims", "done" if speech else "incomplete",
                   "Speech transcribed and checked." if speech else "No speech could be detected, so spoken claims were not checked."))
    if is_link:
        has_cap = bool(caption.strip())
        checks.append(("Post title and description", "done" if has_cap else "incomplete",
                       "Checked." if has_cap else "No title or description was available."))
    checks.append(("Project facts (price, area, bathrooms, possession, RERA, offers, distance)",
                   "done" if not rep["needs_confirmation"] and idres["project_ids"] else "pending",
                   "Checked against the approved facts of the identified project."
                   if idres["project_ids"] and not rep["needs_confirmation"] else "Waiting for the project to be confirmed."))
    if screen is None:
        checks.append(("On-screen text", "not_available",
                       "Not analysed. This file has no video, or on-screen reading was off or unavailable."))
    elif screen.get("partial"):
        checks.append(("On-screen text", "incomplete",
                       f"Only {screen['frames']} of {screen['total']} frames were read in the time allowed."))
        rep["findings"].append(make_finding(
            "SUPERVISION", "MEDIUM", "SCREEN_PARTIAL", 0, f"{screen['frames']}/{screen['total']} frames",
            "Not every frame could be read in the time allowed, so some on-screen text may not have been checked.",
            "A person should watch the rest of the video."))
    else:
        checks.append(("On-screen text", "done",
                       f"{screen.get('frames', 0)} frames read (2 per second plus every scene change); "
                       f"{len(screen_lines)} distinct text lines found."))
    spoken_p = {p["value"] for s in segs for p in extract_prices(s["text"])}
    shown_p = {p["value"] for l in screen_lines for p in extract_prices(l["text"])}
    if spoken_p and shown_p and not (spoken_p & shown_p):
        rep["findings"].append(make_finding(
            "SUPERVISION", "HIGH", "VOICE_SCREEN_MISMATCH", 0,
            "voice: " + ", ".join(fmt_money(v) for v in sorted(spoken_p)) + " / screen: " + ", ".join(fmt_money(v) for v in sorted(shown_p)),
            "The price spoken in the video is different from the price shown on screen.",
            "Make the voice and the on-screen price the same, and match the approved price."))
    checks.append(("Voice versus screen", "done" if (spoken_p and shown_p) else "incomplete",
                   "Spoken and on-screen prices compared." if (spoken_p and shown_p)
                   else "Needs both a spoken price and an on-screen price to compare."))
    checks.append(("RERA authoritative verification", "not_available",
                   "Not available. A RERA number is only compared with the BrandGuard registry unless an administrator has recorded an official check."))
    rep["checks"] = checks

    if not segs:
        rep["findings"].append(make_finding(
            "SUPERVISION", "MEDIUM", "NO_SPEECH_DETECTED", 0, "-",
            "No speech could be detected in this file.", "A human should check the file."))
    elif (not rep["needs_confirmation"] and rep["passed"] == 0
          and not any(f["status"] == "FLAG" for f in rep["findings"])
          and not any(f["type"] == "NO_VERIFIABLE_CLAIM" for f in rep["findings"])):
        rep["findings"].append(make_finding(
            "SUPERVISION", "LOW", "NO_VERIFIABLE_CLAIM", 0, "-",
            "Nothing in this content could be matched against approved facts, so nothing was verified.",
            "A person should confirm that no price or fact needs checking."))
    finalize(rep)
    if rep["needs_confirmation"] and not any(f["severity"] == "CRITICAL" for f in rep["findings"]):
        rep["verdict"] = "CONFIRM - project needs confirming"
    return rep


def status_of(rep):
    """Turn a finished report into a status. Approval needs certain identity, a verified claim and no open issue."""
    if rep["verdict"].startswith("BLOCKED"):
        return "BLOCKED"
    if rep.get("needs_confirmation"):
        return "NEEDS_CONFIRMATION"
    if rep["flags"]:
        return "REJECTED"
    if rep["supervision"]:
        return "SUPERVISION"
    ident = rep.get("identity", {}).get("state")
    if ident in ("MATCHED", "MULTIPLE", "CONFIRMED") and rep.get("passed", 0) >= 1:
        return "AUTO_APPROVED"
    return "SUPERVISION"


def allowed_brand(u, brand_id):
    return bool(q("SELECT 1 FROM memberships WHERE user_id=? AND brand_id=?", (u["id"], brand_id)))


def store_projects(sid, rep, actor):
    ex("DELETE FROM submission_projects WHERE sub_id=?", (sid,))
    for pid in rep.get("project_ids", []):
        ex("INSERT INTO submission_projects (sub_id, project_id, identity_state, evidence, confirmed_by) VALUES (?,?,?,?,?)",
           (sid, pid, rep.get("identity", {}).get("state"),
            rep.get("identity", {}).get("evidence", {}).get(str(pid), ""),
            actor if rep.get("identity", {}).get("state") == "CONFIRMED" else None))


def run_review(u, brand_id, path, sha, filename, language, source_url=None, caption="", hint_pid=None):
    brand = q("SELECT * FROM brands WHERE id=?", (brand_id,))[0]
    reg = json.loads(brand["registry"])
    if not RE.authorized_projects(u["id"], brand_id):
        return err_page(u, f"You have not been given access to any {brand['name']} project yet. "
                           "Ask the company to grant you access, then submit again.")
    if hint_pid and not RE.can_use_project(u["id"], hint_pid):
        return err_page(u, "You do not have access to that project.")
    try:
        segs = transcribe_file(path, language, glossary_for(reg, brand_id, u["id"]))
        screen = None if source_url else OCR.read_screen(path, MAX_SECONDS)
        rep = analyze(u, brand_id, segs, caption, reg, hint_pid, is_link=bool(source_url), screen=screen)
    except Exception as ex_:
        msg = str(ex_) if isinstance(ex_, (ValueError, RuntimeError)) else "Something went wrong while reviewing this file."
        return err_page(u, msg)

    dup = q("SELECT id FROM submissions WHERE sha256=? AND brand_id=? ORDER BY id LIMIT 1", (sha, brand_id))
    if dup:
        rep["duplicate_of"] = dup[0]["id"]
    status = status_of(rep)
    approval = new_approval_id() if status == "AUTO_APPROVED" else None
    sid = ex("""INSERT INTO submissions (user_id, brand_id, filename, sha256, language, status, verdict, report,
                created_at, approval_id, source_url) VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
             (u["id"], brand_id, filename, sha, language, status, rep["verdict"],
              json.dumps(rep, ensure_ascii=False), datetime.now().strftime("%Y-%m-%d %H:%M"),
              approval, source_url))
    store_projects(sid, rep, u["name"])
    how = "SUBMITTED_LINK" if source_url else "SUBMITTED"
    log(sid, u["name"], how, f"{filename} for {brand['name']}", brand_id)
    log(sid, "BrandGuard engine", "AUTO_REVIEW",
        f"{rep['verdict']} ({rep['flags']} flags, {rep['supervision']} to check). Identity: {rep['identity']['state']}", brand_id)
    if dup:
        log(sid, "BrandGuard engine", "DUPLICATE_FOUND", f"Identical file already submitted as #{dup[0]['id']}", brand_id)
    if approval:
        log(sid, "BrandGuard engine", "AUTO_APPROVED", f"{approval} (policy {RE.POLICY_VERSION})", brand_id)
    return RedirectResponse(f"/s/{sid}", 303)


@app.post("/confirm/{sid}")
async def confirm_project(request: Request, sid: int):
    u = me(request)
    s = get_sub(sid)
    if not u or u["role"] != "submitter" or not s or s["user_id"] != u["id"]:
        return RedirectResponse("/", 303)
    if s["status"] != "NEEDS_CONFIRMATION":
        return RedirectResponse(f"/s/{sid}", 303)
    form = await request.form()
    ids = []
    for v in form.getlist("project_id"):
        if str(v).isdigit():
            ids.append(int(v))
    ids = list(dict.fromkeys(ids))
    if not ids:
        request.session["flash"] = "Choose at least one project to continue."
        return RedirectResponse(f"/s/{sid}", 303)
    for pid in ids:  # backend check, whatever the form sent
        if not RE.can_use_project(u["id"], pid) or RE.get_project(pid)["brand_id"] != s["brand_id"]:
            return err_page(u, "You do not have access to one of those projects.")
    old = rep_of(s)
    reg = json.loads(q("SELECT registry FROM brands WHERE id=?", (s["brand_id"],))[0]["registry"])
    segs = old.get("inputs", {}).get("segments", [])
    caption = old.get("inputs", {}).get("caption", "")
    scr_old = old.get("inputs", {}).get("screen")
    screen = None
    if scr_old is not None and old.get("screen_meta"):
        screen = {"lines": [{"start": l["start"], "end": l["end"], "text": l["text"], "raw": l.get("raw", l["text"]),
                             "conf": l["conf"]} for l in scr_old], **old["screen_meta"]}
    rep = analyze(u, s["brand_id"], segs, caption, reg, confirmed=ids, is_link=bool(s["source_url"]), screen=screen)
    if old.get("duplicate_of"):
        rep["duplicate_of"] = old["duplicate_of"]
    status = status_of(rep)
    approval = new_approval_id() if status == "AUTO_APPROVED" else None
    ex("UPDATE submissions SET status=?, verdict=?, report=?, approval_id=? WHERE id=?",
       (status, rep["verdict"], json.dumps(rep, ensure_ascii=False), approval, sid))
    store_projects(sid, rep, u["name"])
    names = ", ".join(RE.get_project(i)["official_name"] for i in ids)
    log(sid, u["name"], "PROJECT_CONFIRMED", f"Confirmed project: {names}", s["brand_id"])
    log(sid, "BrandGuard engine", "AUTO_REVIEW", f"{rep['verdict']} ({rep['flags']} flags, {rep['supervision']} to check)", s["brand_id"])
    if approval:
        log(sid, "BrandGuard engine", "AUTO_APPROVED", f"{approval} (policy {RE.POLICY_VERSION})", s["brand_id"])
    return RedirectResponse(f"/s/{sid}", 303)


@app.post("/upload")
def upload(request: Request, brand_id: int = Form(...), language: str = Form("auto"),
           project_id: str = Form(""), file: UploadFile = File(...)):
    u = me(request)
    if not u or u["role"] != "submitter":
        return RedirectResponse("/", 303)
    if not allowed_brand(u, brand_id):
        return err_page(u, "You are not linked to that company.")
    try:
        path, sha = save_upload(file)
    except Exception as ex_:
        return err_page(u, str(ex_) if isinstance(ex_, (ValueError, RuntimeError)) else "Upload failed.")
    return run_review(u, brand_id, path, sha, file.filename, language,
                      hint_pid=int(project_id) if project_id.isdigit() else None)


@app.post("/upload_link")
def upload_link(request: Request, brand_id: int = Form(...), language: str = Form("auto"),
                url: str = Form(...), project_id: str = Form("")):
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
    return run_review(u, brand_id, path, sha, title[:80], language, source_url=url, caption=caption,
                      hint_pid=int(project_id) if project_id.isdigit() else None)


# ------------------------------------------------------------- result / review
TYPE_LABEL = {
    "PRICE_MISMATCH": "Price does not match the approved price",
    "PRICE_UNIT_CHECK": "Possible unit or transcription error",
    "PRICE_LOW_CONFIDENCE": "Price heard with low confidence",
    "PRICE_NOT_IN_REGISTRY": "Price is not close to any approved price",
    "UNCLEAR_AMOUNT": "Amount could not be read",
    "BANNED_PHRASE": "Banned phrase used",
    "CONFIDENTIAL_DATA": "Confidential information mentioned",
    "UNKNOWN_CONTACT": "Contact detail not on the approved list",
    "UNSUPPORTED_CLAIM": "Claim needs supporting evidence",
    "NO_SPEECH_DETECTED": "No speech detected",
    "NO_VERIFIABLE_CLAIM": "Nothing could be verified",
    "AREA_CHECK": "Area does not match the approved area",
    "BATHROOMS_CHECK": "Bathroom count does not match",
    "POSSESSION_CHECK": "Possession claim needs attention",
    "RERA_CHECK": "RERA number needs attention",
    "OFFER_CHECK": "Offer claim needs attention",
    "DISTANCE_CHECK": "Distance claim does not match",
    "BOOKING_CHECK": "Booking amount does not match",
    "UNAUTHORIZED_PROJECT": "Project this account cannot promote",
    "PROJECT_UNCERTAIN": "Could not link a claim to one project",
    "IDENTITY_WEAK": "Project not named in the content",
}
for _k in ("AREA", "BATHROOMS", "POSSESSION", "RERA", "OFFER", "DISTANCE", "BOOKING", "PRICE"):
    TYPE_LABEL[_k + "_UNVERIFIABLE"] = "No approved fact to compare with (not a confirmed error)"
UNCERTAIN = {"PRICE_UNIT_CHECK", "PRICE_LOW_CONFIDENCE", "UNCLEAR_AMOUNT", "PRICE_NOT_IN_REGISTRY"}
SECTIONS = [
    ("Price verification", lambda t: t.startswith("PRICE_") and not t.endswith("_UNVERIFIABLE") or t == "UNCLEAR_AMOUNT"),
    ("Property facts (area, bathrooms, possession, RERA, offers, distance)",
     lambda t: t.endswith("_CHECK") and not t.startswith("PRICE_") or t.endswith("_UNVERIFIABLE")),
    ("Project and permission", lambda t: t in ("UNAUTHORIZED_PROJECT", "PROJECT_UNCERTAIN", "IDENTITY_WEAK")),
    ("Restricted or banned language", lambda t: t == "BANNED_PHRASE"),
    ("Confidential information", lambda t: t == "CONFIDENTIAL_DATA"),
    ("Contact information", lambda t: t == "UNKNOWN_CONTACT"),
    ("Claims requiring evidence", lambda t: t == "UNSUPPORTED_CLAIM"),
]
ACTION_LABEL = {
    "SUBMITTED": "Submission received", "SUBMITTED_LINK": "Link submission received",
    "AUTO_REVIEW": "Analysis completed", "AUTO_APPROVED": "Auto-approved", "APPROVED": "Approved by reviewer",
    "REJECTED": "Rejected by reviewer", "DISPUTE_RAISED": "Dispute raised",
    "DISPUTE_OVERTURNED": "Dispute resolved: decision overturned", "DISPUTE_UPHELD": "Dispute resolved: decision upheld",
    "RULE_ADDED": "Brand rule added", "RULE_CHANGED": "Brand rule changed", "RULE_REMOVED": "Brand rule removed",
    "FACTS_UPDATED": "Brand details updated", "PROJECT_CONFIRMED": "Project confirmed by submitter",
    "DUPLICATE_FOUND": "Identical file found", "PROJECT_ADDED": "Project added", "PROJECT_EDITED": "Project details changed",
    "FACT_SET": "Approved fact saved", "FACT_ENDED": "Approved fact withdrawn", "ACCESS_GRANTED": "Project access granted",
    "ACCESS_REVOKED": "Project access revoked", "UNIT_ADDED": "Property type added", "RERA_RECORDED": "RERA check recorded",
    "PRICE_SAVED": "Approved price saved", "PRICE_REMOVED": "Approved price removed",
    "RULES_IMPORTED": "Brand rules imported from document",
    "CASE_REMEMBERED": "Dispute remembered for next time",
}
DECISION_TEXT = {
    "AUTO_APPROVED": ("ok", "check-circle", "Every price matched the approved facts and nothing needed a person to check."),
    "APPROVED": ("ok", "check-circle", "A reviewer looked at this submission and approved it."),
    "REJECTED": ("bad", "x-circle", "One or more claims break the brand rules. Fix the issues below and resubmit, or dispute the decision if you think it is wrong."),
    "BLOCKED": ("bad", "x-circle", "Confidential company information was mentioned, so this cannot be approved. Remove it and resubmit."),
    "REJECTED_FINAL": ("bad", "x-circle", "A reviewer looked at this submission and upheld the rejection."),
    "NEEDS_CONFIRMATION": ("warn", "search", "BrandGuard is not certain which project this reel is about, so it did not check prices against a guess. Choose the project below to continue."),
    "SUPERVISION": ("warn", "alert", "BrandGuard could not be sure about some parts of this reel, so a person must check it. This is not a confirmed violation."),
    "DISPUTED": ("warn", "scale", "The creator disagreed with the rejection. A reviewer must uphold or overturn it."),
}


def finding_html(f):
    tone = {"FLAG": "bad", "SUPERVISION": "warn"}.get(f["status"], "ok")
    kind = f["type"]
    label = TYPE_LABEL.get(kind, kind.replace("_", " ").title())
    cap = f.get("source") == "caption"
    where = ("Post title or description" if cap else f'On screen at {fmt_time(f["time"])}' if f.get("source") == "screen"
             else f'Spoken at {fmt_time(f["time"])}')
    status_chip = ui.badge("Needs a human check" if f["status"] == "SUPERVISION" else "Violation",
                           tone, "alert" if tone == "warn" else "x-circle")
    conf = ""
    if f.get("confidence") is not None and not cap:
        conf = f' <span class="muted">Recognition confidence {round(float(f["confidence"]) * 100)}%</span>'
    note = ""
    if kind in UNCERTAIN:
        note = ('<dt>Note</dt><dd>This is an uncertainty, not a confirmed violation. The amount may have been misheard or '
                'a unit (lakh or crore) may be wrong, so a person should listen to this moment.</dd>')
    return (f'<div class="finding {tone}"><div class="finding-top">{status_chip}<b>{e(label)}</b>{conf}</div>'
            f'<dl><dt>Where</dt><dd>{e(where)}</dd>'
            f'<dt>Detected</dt><dd>{e(str(f["evidence"]))}</dd>'
            f'<dt>Why it matters</dt><dd>{e(f["explanation"])}</dd>{note}'
            f'<dt>What to do</dt><dd>{e(f["suggestion"])}</dd></dl></div>')


VERDICT_BADGE = {
    "VERIFIED": ("Verified", "ok", "check-circle"), "VIOLATION": ("Violation", "bad", "x-circle"),
    "UNVERIFIABLE": ("Cannot verify", "warn", "alert"), "REVIEW": ("Person must review", "warn", "alert"),
    "INCOMPLETE": ("Incomplete", "warn", "alert"), "NA": ("Not applicable", "neutral", "info"),
}
KIND_LABEL = {"price": "Price", "booking": "Booking amount", "area": "Area", "bathrooms": "Bathrooms",
              "possession": "Possession", "rera": "RERA", "offer": "Offer", "distance": "Distance"}
IDENT_TEXT = {
    "MATCHED": ("ok", "Project identified from the content."), "CONFIRMED": ("ok", "Project confirmed by the submitter."),
    "MULTIPLE": ("info", "Several projects are mentioned. Each claim was checked against its own project."),
    "LIKELY": ("warn", "Likely match, but not certain."), "AMBIGUOUS": ("warn", "The name fits more than one project."),
    "NOT_FOUND": ("warn", "No project could be identified from the content."),
    "CONFLICT": ("warn", "The selected project differs from the project in the content."),
    "SELECTED": ("warn", "The content does not name the project. Only your selection was used."),
    "NOT_AUTHORIZED": ("bad", "The content promotes a project this account cannot use."),
}


def claims_table(claims):
    rows = []
    for c in claims:
        b = VERDICT_BADGE.get(c["verdict"], VERDICT_BADGE["REVIEW"])
        when = ("Caption" if c.get("source") == "caption" else
                f'{fmt_time(c.get("time") or 0)} (screen)' if c.get("source") == "screen" else fmt_time(c.get("time") or 0))
        off = e(str(c.get("official") or "-"))
        if c.get("fact_version"):
            off += f'<br><span class="muted">{e(c["fact_version"])}</span>'
        if c.get("source_title"):
            off += f'<br><span class="muted">Source: {e(c["source_title"])}</span>'
        why = e(c.get("reason") or "")
        if c.get("level") == "registry_match":
            why += " " + ui.badge("Registry match only", "warn", "info")
        elif c.get("level") == "authoritative":
            why += " " + ui.badge("Confirmed with official register", "ok", "check")
        rows.append([e(when), e(KIND_LABEL.get(c["kind"], c["kind"])), e(c.get("project") or "-"),
                     e(str(c.get("heard") or "")), off, ui.badge(b[0], b[1], b[2]), why])
    return ui.table(["Where", "Claim", "Project", "Said", "Approved value", "Result", "Why"], rows, "Claim checks")


def identity_card(rep):
    idn = rep.get("identity")
    if not idn:
        return ""
    tone, text = IDENT_TEXT.get(idn["state"], ("info", ""))
    names = idn.get("names", {})
    plist = ", ".join(names.get(str(i), "?") for i in idn.get("project_ids", []))
    inner = f"<p>{e(text)} {e(idn.get('note') or '')}</p>"
    if plist:
        inner += f"<p><b>Project:</b> {e(plist)}</p>"
    ev = [f"{e(names.get(k, 'Project'))}: {e(v)}" for k, v in idn.get("evidence", {}).items() if v]
    if ev:
        inner += '<p class="muted">Evidence: ' + "; ".join(ev) + "</p>"
    return ui.card("Project identification", inner)


def checks_card(rep):
    chk = rep.get("checks")
    if not chk:
        return ""
    lab = {"done": ("Done", "ok", "check-circle"), "pending": ("Waiting", "warn", "clock"),
           "incomplete": ("Incomplete", "warn", "alert"), "not_available": ("Not performed", "neutral", "info")}
    rows = [[e(n), ui.badge(*lab.get(st, lab["pending"])), e(note)] for n, st, note in chk]
    return ui.card("What was and was not checked", ui.table(["Check", "State", "Detail"], rows, "Checks performed"),
                   f"Policy version {e(rep.get('policy', ''))}. A check that was not performed is never counted as passed.")


def timeline_html(rows):
    if not rows:
        return ui.empty("No events recorded")
    items = "".join(f'<li><span class="when">{e(a["at"])}</span><span><b>{e(ACTION_LABEL.get(a["action"], a["action"]))}</b>'
                    f' <span class="muted">by {e(a["actor"])}</span>'
                    f'{"<br>" + e(a["note"]) if a["note"] else ""}</span></li>' for a in rows)
    return f'<ul class="timeline">{items}</ul>'

    

@app.get("/s/{sid}", response_class=HTMLResponse)
def view_submission(request: Request, sid: int):
    u = me(request)
    if not u:
        return RedirectResponse("/", 303)
    s = get_sub(sid)
    if not s or not can_view(u, s):
        return page("Not found", ui.page_header("Submission not found")
                    + ui.card("", ui.empty("We could not find that submission",
                                           "It may not exist, or you may not have access to it.",
                                           '<a class="btn" href="/">Back to dashboard</a>')),
                    u, "", [("Not found", None)], request)
    rep = rep_of(s)
    admin = u["role"] == "admin"
    tone, ic, why = DECISION_TEXT.get(s["status"], ("neutral", "info", ""))
    findings = rep.get("findings", [])

    # ---- decision summary
    counts = (f'{ui.badge(str(rep.get("flags", 0)) + " violation(s)", "bad", "x-circle")} '
              f'{ui.badge(str(rep.get("supervision", 0)) + " to check", "warn", "alert")} '
              f'{ui.badge(str(rep.get("passed", 0)) + " claim(s) verified", "ok", "check-circle")}')
    approval = ""
    if s["approval_id"]:
        approval = (f'<dl class="kv" style="margin-top:14px"><dt>Approval ID</dt><dd><b>{e(s["approval_id"])}</b></dd>'
                    f'<dt>File hash (SHA-256)</dt><dd class="mono">{e(s["sha256"])}</dd></dl>')
    summary = ui.card("", f'<div class="verdict {tone}">{ui.icon(ic, 26)}<div><h2>{e(ui.STATUS.get(s["status"], (s["status"],))[0])}</h2>'
                      f'<p>{e(why)}</p><p style="margin-top:10px">{counts}</p></div></div>{approval}')

    # ---- actions
    actions, dialogs = "", ""
    said_val = (s["dispute_said"] or "") if "dispute_said" in s.keys() else ""
    if not admin and s["user_id"] == u["id"] and s["status"] in ("REJECTED", "BLOCKED"):
        actions = ui.card("What would you like to do?",
                          f'<p class="muted">Fix the issues and <a href="/submit">submit a corrected reel</a>, or dispute the '
                          f'decision if you believe a finding is wrong.</p>'
                          f'<button type="button" class="btn secondary" data-dialog="dlg-dispute">{ui.icon("scale", 16)}Raise a dispute</button>')
        dialogs = (
            f'<dialog id="dlg-dispute" class="dlg" aria-labelledby="dlg-dispute-t">'
            f'<form method="post" action="/dispute/{sid}" data-lock>'
            f'<h2 id="dlg-dispute-t">Raise a dispute</h2>'
            f'<p class="muted">Explain why the finding is wrong. Mention the time in the reel if you can. A builder will review it.</p>'
            f'<label for="dsp-said">What did you actually say? <span class="muted">(optional, helps the builder check quickly)</span></label>'
            f'<input id="dsp-said" name="said" maxlength="80" placeholder="Example: 1 crore 30 lakh">'
            f'<label for="dsp-note">Why is the finding wrong? <span class="req">(required)</span></label>'
            f'<textarea id="dsp-note" name="note" rows="3" maxlength="1000" required></textarea>'
            f'<div class="dlg-actions"><button type="button" class="btn secondary" data-close>Cancel</button>'
            f'<button type="submit" class="btn primary">Submit dispute</button></div></form></dialog>')
    elif not admin and s["status"] == "DISPUTED":
        you_said = f'<p><b>You said:</b> {e(said_val)}</p>' if said_val else ""
        actions = ui.card("Your dispute", f'<p>{e(s["dispute_note"] or "")}</p>{you_said}'
                          '<p class="muted">Waiting for a builder to review it. You will see the outcome here.</p>')
    if admin and s["brand_id"] == u["brand_id"] and s["status"] in QUEUE_STATUSES:
        disputed = s["status"] == "DISPUTED"
        ctx = ""
        if disputed:
            ctx = f'<p><b>Creator\'s explanation:</b> {e(s["dispute_note"] or "")}</p>'
            if said_val:
                ctx += f'<p><b>What the creator says they said:</b> {e(said_val)}</p>'
            ctx += ('<p class="muted">If you overturn this on a price or booking claim, BrandGuard remembers the case. '
                    'The next time the same reading appears, it asks a person to check instead of rejecting. '
                    'It never approves on its own, and you can switch a remembered case off under Learned Cases.</p>')
        yes, no = ("Overturn decision", "Uphold rejection") if disputed else ("Approve", "Reject")
        actions = ui.card("Your decision", ctx + '<p class="muted">Review the findings, then record a decision. '
                          'It is saved to the audit trail.</p>'
                          f'<div class="form-actions"><button type="button" class="btn success" data-dialog="dlg-approve">{ui.icon("check", 16)}{yes}</button>'
                          f'<button type="button" class="btn danger" data-dialog="dlg-reject">{ui.icon("x", 16)}{no}</button></div>')
        dialogs = (ui.confirm_dialog("dlg-approve", f"{yes}?",
                                     "This approves the content and issues an approval ID." if not disputed else
                                     "This approves the content and issues an approval ID. The creator's dispute is resolved in their favour.",
                                     f"/decide/{sid}", yes, "success", ("note", "Note", False), {"decision": "approve"})
                   + ui.confirm_dialog("dlg-reject", f"{no}?",
                                       "This is a final decision for this submission." if not disputed else
                                       "The original rejection stands and the dispute is closed.",
                                       f"/decide/{sid}", no, "danger", ("note", "Reason for the creator", True),
                                       {"decision": "reject"}))
    if s["decision_note"]:
        actions += ui.card("Reviewer note", f'<p style="margin:0">{e(s["decision_note"])}</p>')

    # ---- left column: details + transcript
    lang = s["language"] if s["language"] in ("mr", "hi", "en") else ""
    src = ""
    if s["source_url"]:
        src = (f'<dt>Source link</dt><dd><a href="{e(s["source_url"])}" target="_blank" rel="noopener noreferrer">'
               f'{e(s["source_url"])}</a></dd>')
    details = ui.card("Submission details", f"""<dl class="kv"><dt>Reel</dt><dd>{e(s["filename"] or "Untitled")}</dd>
      <dt>Company</dt><dd>{e(s["bname"])}</dd><dt>Submitted by</dt><dd>{e(s["uname"])}</dd>
      <dt>Submitted</dt><dd>{e(s["created_at"])}</dd><dt>Spoken language</dt><dd>{e(LANG_LABEL.get(s["language"], s["language"] or ""))}</dd>{src}</dl>"""
                      + (ui.alert("This was fetched from a link. The platform's copy can differ from the original file, so the "
                                  "file-hash check does not apply to link submissions.", "info") if s["source_url"] else ""))
    tr = rep.get("transcript", [])
    if tr:
        rows = "".join(
            f'<div class="tr-row{" low" if t["conf"] < THRESHOLD else ""}"><time>{fmt_time(t["start"])}</time>'
            f'<span{f" lang={lang}" if lang else ""}>{e(t["text"])}</span>'
            f'<span class="muted conf">{round(t["conf"] * 100)}%{" (low)" if t["conf"] < THRESHOLD else ""}</span></div>'
            for t in tr)
        transcript = ui.card("Transcript and recognition confidence",
                             f'<p class="muted">Confidential terms are redacted. Highlighted lines had low recognition '
                             f'confidence and may contain mistakes.</p>{rows}')
    else:
        transcript = ui.card("Transcript and recognition confidence", ui.empty("No transcript available"))
    scr_lines = rep.get("inputs", {}).get("screen") or []
    meta = rep.get("screen_meta")
    if meta is not None:
        if scr_lines:
            srows = "".join(
                f'<div class="tr-row"><time>{fmt_time(l["start"])}</time><span>{e(l.get("raw") or l["text"])}</span>'
                f'<span class="muted conf">{round(l["conf"] * 100)}%</span></div>' for l in scr_lines)
        else:
            srows = ui.empty("No text was found on screen")
        transcript += ui.card("Text read from the screen",
                              f'<p class="muted">{meta["frames"]} frames read (2 per second plus every scene change). '
                              f'Each line is shown once, at the first time it appeared.</p>{srows}')

    # ---- right column: grouped findings
    parts, clean = [], []
    used = set()
    claims = rep.get("claims", [])
    for title, test in SECTIONS:
        fs = [f for f in findings if test(f["type"])]
        used.update(id(f) for f in fs)
        inner = ""
        if title == "Price verification" and claims and "verdict" in claims[0]:
            pass
        elif title == "Price verification" and claims:
            crow = []
            for c in claims:
                when = "Caption" if c.get("source") == "caption" else fmt_time(c["time"])
                crow.append([e(when), e(c["heard"]), e(c["config"]), e(c["approved"]),
                             {"PASS": ui.badge("Matches", "ok", "check-circle"), "FLAG": ui.badge("Mismatch", "bad", "x-circle")}.get(
                                 c["status"], ui.badge("Needs check", "warn", "alert"))])
            inner += ui.table(["Time", "Detected", "Compared with", "Approved", "Result"], crow, "Price claims")
            inner += '<p></p>'
        inner += "".join(finding_html(f) for f in fs)
        if inner:
            parts.append(f'<h3 class="sec-title">{e(title)}</h3>{inner}')
        else:
            clean.append(title.lower())
    other = [f for f in findings if id(f) not in used]
    if other:
        parts.append('<h3 class="sec-title">Other checks</h3>' + "".join(finding_html(f) for f in other))
    if not findings and not claims:
        parts.append(ui.empty("No issues found", "Nothing in this reel broke a rule."))
    if clean and (findings or claims):
        parts.append(f'<p class="muted" style="margin-top:12px">{ui.icon("check-circle", 14)} No issues found in: {", ".join(clean)}.</p>')
    if s["source_url"]:
        cf = [f for f in findings if f.get("source") == "caption"]
        parts.append('<h3 class="sec-title">Link metadata</h3><p class="muted">'
                     + (f'{len(cf)} finding(s) came from the post title or description (marked above).' if cf
                        else "The post title and description were checked and had no findings.") + "</p>")
    findings_card = ui.card("Compliance findings", "".join(parts))
    new_claims = [c for c in claims if "verdict" in c]
    claims_card = (ui.card("Claim-by-claim checks", claims_table(new_claims),
                           "Every claim found in the content, what it was compared with, and the result.") if new_claims else "")
    extra = identity_card(rep) + checks_card(rep)
    notes = ""
    if rep.get("duplicate_of") and rep["duplicate_of"] != sid:
        notes += ui.alert(f'An identical file was already submitted as #{rep["duplicate_of"]}.', "info", "Duplicate file.")
    if s["approval_id"]:
        rs, why_ = RE.reuse_status(sid, rep, s["user_id"], s["brand_id"])
        if rs == "OK":
            notes += ui.alert("Facts used for this approval are still current and the creator still has access. "
                              "This is a check at this moment, not a permanent guarantee.", "ok", "Reuse check: no change found.")
        else:
            notes += ui.alert("; ".join(why_) + ". The original approval is unchanged, but this content should be re-checked before it is used again.",
                              "warn", "Re-check needed before reuse.")
    confirm = ""
    if not admin and s["user_id"] == u["id"] and s["status"] == "NEEDS_CONFIRMATION":
        cands = [RE.get_project(i) for i in rep.get("candidates", [])]
        auth = RE.authorized_projects(u["id"], s["brand_id"])
        opts_ = {p["id"]: p for p in auth}
        for c_ in cands:
            if c_ and c_["id"] not in opts_ and False:
                pass
        pool = [p for p in auth] if not cands or any(c_ is None for c_ in cands) else [opts_[c_["id"]] for c_ in cands if c_ and c_["id"] in opts_]
        if not pool:
            pool = auth
        boxes = "".join(f'<label class="check"><input type="checkbox" name="project_id" value="{p["id"]}"> '
                        f'{e(p["official_name"])}{" (" + e(p["city"]) + ")" if p["city"] else ""}</label>' for p in pool)
        confirm = ui.card("Which project is this reel about?",
                          f'<form method="post" action="/confirm/{sid}" data-lock><p class="muted">Tick every project the reel promotes. '
                          f'Prices and facts are then checked against those projects only.</p>{boxes}'
                          f'<p></p><button class="btn" type="submit">Confirm and continue</button></form>')

    au = q("SELECT * FROM audit WHERE sub_id=? ORDER BY id", (sid,))
    audit = ui.card("History", timeline_html(au))

    crumbs = [("Review Queue" if admin else "My Submissions", "/queue" if admin else "/reviews"), (f"Submission #{sid}", None)]
    body = (ui.page_header(f"Submission #{sid}", e(s["filename"] or ""), '<a class="btn secondary" href="/reviews">Back to list</a>')
            + '<div class="stack">' + summary + notes + confirm + actions + '<div class="cols"><div class="stack">' + details + extra + transcript
            + '</div><div class="stack">' + claims_card + findings_card + audit + '</div></div></div>' + dialogs)
    return page(f"Submission {sid}", body, u, "queue" if admin and s["status"] in QUEUE_STATUSES else "reviews", crumbs, request)


@app.post("/dispute/{sid}")
def dispute(request: Request, sid: int, note: str = Form(""), said: str = Form("")):
    u, s = me(request), get_sub(sid)
    if u and s and s["user_id"] == u["id"] and s["status"] in ("REJECTED", "BLOCKED") and note.strip():
        ex("UPDATE submissions SET status='DISPUTED', dispute_note=?, dispute_said=? WHERE id=?",
           (note.strip()[:1000], said.strip()[:80], sid))
        detail = note.strip()[:300]
        if said.strip():
            detail += f" (creator says they said: {said.strip()[:80]})"
        log(sid, u["name"], "DISPUTE_RAISED", detail)
        request.session["flash"] = "Dispute sent to the builder."
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
        if was_dispute and decision == "approve":
            try:
                n = LRN.record_overturn(get_sub(sid), rep_of(s), note.strip()[:300])
                if n:
                    log(sid, "BrandGuard engine", "CASE_REMEMBERED",
                        f"{n} reading(s) from this dispute will be sent to a person next time, not rejected.")
            except Exception:
                pass  # learning must never block a decision
        request.session["flash"] = "Decision recorded: " + ui.STATUS[status][0] + "."
    return RedirectResponse(f"/s/{sid}", 303)

    

# ------------------------------------------------------------------ list views
TABS = {
    "all": ("All", None), "supervision": ("Supervision Required", ("SUPERVISION",)),
    "disputed": ("Disputed", ("DISPUTED",)), "approved": ("Approved", APPROVED_STATUSES),
    "rejected": ("Rejected", REJECTED_STATUSES),
}


def scope_sql(request, u):
    if u["role"] == "admin":
        return "s.brand_id=?", [u["brand_id"]]
    return "s.user_id=? AND s.brand_id=?", [u["id"], current_company(request, u)]


def list_view(request, mode):
    u = me(request)
    if not u or (mode == "queue" and u["role"] != "admin"):
        return RedirectResponse("/", 303)
    admin = u["role"] == "admin"
    tab_keys = ("all", "supervision", "disputed") if mode == "queue" else tuple(TABS)
    st = request.query_params.get("status", "all")
    st = st if st in tab_keys else "all"
    term = request.query_params.get("q", "").strip()[:80]
    try:
        pg = max(1, int(request.query_params.get("page", "1")))
    except ValueError:
        pg = 1
    where, args = scope_sql(request, u)
    if mode == "queue":
        where += " AND s.status IN ('SUPERVISION','DISPUTED')"
    counts = Counter({r["status"]: r["c"] for r in q(
        f"SELECT s.status, COUNT(*) AS c FROM submissions s WHERE {where} GROUP BY s.status", tuple(args))})

    def tab_count(k):
        sts = TABS[k][1]
        return sum(counts.values()) if sts is None else sum(counts[x] for x in sts)

    w2, a2 = where, list(args)
    if TABS[st][1]:
        w2 += " AND s.status IN (%s)" % ",".join("?" * len(TABS[st][1]))
        a2 += list(TABS[st][1])
    if term:
        w2 += " AND (s.filename LIKE ? OR u.name LIKE ? OR s.approval_id LIKE ? OR CAST(s.id AS TEXT)=?)"
        a2 += [f"%{term}%", f"%{term}%", f"%{term}%", term.lstrip("#")]
    total = q(f"SELECT COUNT(*) AS c FROM submissions s JOIN users u ON u.id=s.user_id WHERE {w2}", tuple(a2))[0]["c"]
    pages = max(1, math.ceil(total / PAGE_SIZE))
    pg = min(pg, pages)
    rows = q(SUB_SQL + f"WHERE {w2} ORDER BY s.id DESC LIMIT {PAGE_SIZE} OFFSET {(pg - 1) * PAGE_SIZE}", tuple(a2))

    base = "/queue" if mode == "queue" else "/reviews"
    tabs = "".join(
        f'<a href="{base}?status={k}{"&q=" + quote(term) if term else ""}"{" aria-current=true" if k == st else ""}>'
        f'{e(TABS[k][0])} ({tab_count(k)})</a>' for k in tab_keys)
    toolbar = (f'<div class="toolbar"><nav class="tabs" aria-label="Filter by status">{tabs}</nav></div>'
               f'<div class="toolbar"><form method="get" action="{base}" role="search"><input type="hidden" name="status" value="{st}">'
               f'<label for="q" class="sr-only" style="position:absolute;left:-9999px">Search submissions</label>'
               f'<input id="q" type="search" name="q" value="{e(term)}" placeholder="Search by file, creator or approval ID">'
               f'<button class="btn secondary" type="submit">{ui.icon("search", 16)}Search</button></form></div>')
    if rows:
        listing = sub_table(rows, show_user=admin, label="Submissions") + ui.pager(
            f"{base}?status={st}" + (f"&q={quote(term)}" if term else ""), pg, pages)
    elif term or st != "all":
        listing = ui.empty("No matching submissions", "Try a different filter or search term.",
                           f'<a class="btn secondary" href="{base}">Clear filters</a>')
    else:
        listing = ui.empty("Nothing waiting for you" if mode == "queue" else "No submissions yet",
                           "New items that need a decision will appear here." if mode == "queue" else
                           "Submit a reel to see its review here.",
                           '' if admin else '<a class="btn" href="/submit">Submit a Reel</a>')
    if mode == "queue":
        head = ui.page_header("Review Queue", f"{sum(counts.values())} submission(s) need a decision. Open one to see the evidence and decide.")
        crumbs, active = [("Review Queue", None)], "queue"
    else:
        head = ui.page_header("All Reviews" if admin else "My Submissions",
                              "Every submission and its current status." if admin else "Every reel you have submitted for the selected company.",
                              "" if admin else '<a class="btn" href="/submit">Submit a Reel</a>')
        crumbs, active = [("All Reviews" if admin else "My Submissions", None)], "reviews"
    return page(("Review Queue" if mode == "queue" else "Reviews"), head + ui.card("", toolbar + listing), u, active, crumbs, request)


@app.get("/queue", response_class=HTMLResponse)
def queue_page(request: Request):
    return list_view(request, "queue")


@app.get("/reviews", response_class=HTMLResponse)
def reviews_page(request: Request):
    return list_view(request, "reviews")


# --------------------------------------------------------------------- disputes
@app.get("/disputes", response_class=HTMLResponse)
def disputes_page(request: Request):
    u = me(request)
    if not u:
        return RedirectResponse("/", 303)
    admin = u["role"] == "admin"
    where, args = scope_sql(request, u)
    rows = q(SUB_SQL + f"WHERE {where} AND s.id IN (SELECT sub_id FROM audit WHERE action='DISPUTE_RAISED') ORDER BY s.id DESC",
             tuple(args))
    open_rows = [r for r in rows if r["status"] == "DISPUTED"]
    done = [r for r in rows if r["status"] != "DISPUTED"]

    def tbl(rs, resolved):
        if not rs:
            return ui.empty("No resolved disputes" if resolved else "No open disputes",
                            "Disputes appear here after a creator challenges a rejection." if admin else
                            "If a rejection looks wrong, open the submission and choose Raise a dispute.")
        heads = ["Submission"] + (["Creator"] if admin else []) + ["Explanation", "Outcome" if resolved else "Status", "Action"]
        out = []
        for r in rs:
            outcome = ({"APPROVED": ui.badge("Decision overturned", "ok", "check-circle"),
                        "REJECTED_FINAL": ui.badge("Decision upheld", "bad", "x-circle")}.get(r["status"], ui.chip(r["status"]))
                       if resolved else ui.chip(r["status"]))
            lbl = "Resolve" if admin and not resolved else "View"
            out.append([f'<a href="/s/{r["id"]}"><b>#{r["id"]}</b></a><span class="trunc">{e(r["filename"] or "")}</span>']
                       + ([e(r["uname"])] if admin else [])
                       + [f'<span class="trunc" style="max-width:340px" title="{e(r["dispute_note"] or "")}">{e(r["dispute_note"] or "")}</span>',
                          outcome, f'<a class="btn sm" href="/s/{r["id"]}" aria-label="{lbl} dispute for submission {r["id"]}">{lbl}</a>'])
        return ui.table(heads, out, "Disputes")
    body = (ui.page_header("Disputes", "A creator can dispute a rejection. A builder then upholds the rejection or overturns it. "
                           "Every resolution is recorded in the audit trail.")
            + '<div class="stack">' + ui.card(f"Open ({len(open_rows)})", tbl(open_rows, False))
            + ui.card(f"Resolved ({len(done)})", tbl(done, True)) + '</div>')
    return page("Disputes", body, u, "disputes", [("Disputes", None)], request)


# ------------------------------------------------------------------- approvals
@app.get("/approvals", response_class=HTMLResponse)
def approvals_page(request: Request):
    u = me(request)
    if not u:
        return RedirectResponse("/", 303)
    admin = u["role"] == "admin"
    where, args = scope_sql(request, u)
    term = request.query_params.get("q", "").strip()[:60]
    w2, a2 = where + " AND s.approval_id IS NOT NULL", list(args)
    if term:
        w2 += " AND (s.approval_id LIKE ? OR s.filename LIKE ?)"
        a2 += [f"%{term}%", f"%{term}%"]
    rows = q(f"""SELECT s.*, u.name AS uname, b.name AS bname,
                 (SELECT MAX(at) FROM audit a WHERE a.sub_id=s.id AND a.action IN ('AUTO_APPROVED','APPROVED','DISPUTE_OVERTURNED')) AS approved_at
                 FROM submissions s JOIN users u ON u.id=s.user_id JOIN brands b ON b.id=s.brand_id
                 WHERE {w2} ORDER BY s.id DESC LIMIT 200""", tuple(a2))
    search = (f'<div class="toolbar"><form method="get" action="/approvals" role="search">'
              f'<label for="q" style="position:absolute;left:-9999px">Search approval records</label>'
              f'<input id="q" type="search" name="q" value="{e(term)}" placeholder="Search by approval ID or file">'
              f'<button class="btn secondary" type="submit">{ui.icon("search", 16)}Search</button></form></div>')
    if rows:
        out = []
        for r in rows:
            h = r["sha256"] or ""
            verif = (ui.badge("Not applicable (link)", "neutral", "link") if r["source_url"]
                     else ui.badge("Verifiable by file", "ok", "file-check"))
            out.append([f'<b>{e(r["approval_id"])}</b>', f'<a href="/s/{r["id"]}">#{r["id"]}</a><span class="trunc">{e(r["filename"] or "")}</span>',
                        e(r["bname"]), f'<span class="muted">{e(r["approved_at"] or r["created_at"])}</span>',
                        f'<span class="mono" title="{e(h)}">{e(h[:12])}…</span>' if h else "-", verif])
        listing = ui.table(["Approval ID", "Submission", "Company", "Approved", "SHA-256", "Verification"], out, "Approval records")
    else:
        listing = ui.empty("No approval records yet", "An approval ID is issued when a submission is auto-approved or a reviewer approves it.")
    body = (ui.page_header("Approval Records", "Each approved file has an approval ID and a SHA-256 fingerprint. "
                           "You can check a file against these records on the Verify a File page.",
                           '<a class="btn secondary" href="/verify">Verify a File</a>')
            + ui.card("", search + listing))
    return page("Approval Records", body, u, "approvals", [("Approval Records", None)], request)


# ----------------------------------------------------------------------- audit
@app.get("/audit", response_class=HTMLResponse)
def audit_page(request: Request):
    u = me(request)
    if not u:
        return RedirectResponse("/", 303)
    admin = u["role"] == "admin"
    term = request.query_params.get("q", "").strip()[:60]
    try:
        pg = max(1, int(request.query_params.get("page", "1")))
    except ValueError:
        pg = 1
    if admin:
        where, args = "(s.brand_id=? OR a.brand_id=?)", [u["brand_id"], u["brand_id"]]
    else:
        where, args = "s.user_id=? AND s.brand_id=?", [u["id"], current_company(request, u)]
    if term:
        where += " AND (a.actor LIKE ? OR a.action LIKE ? OR a.note LIKE ? OR CAST(a.sub_id AS TEXT)=?)"
        args += [f"%{term}%", f"%{term.upper().replace(' ', '_')}%", f"%{term}%", term.lstrip("#")]
    frm = "FROM audit a LEFT JOIN submissions s ON s.id=a.sub_id"
    total = q(f"SELECT COUNT(*) AS c {frm} WHERE {where}", tuple(args))[0]["c"]
    pages = max(1, math.ceil(total / 25))
    pg = min(pg, pages)
    rows = q(f"SELECT a.* {frm} WHERE {where} ORDER BY a.id DESC LIMIT 25 OFFSET {(pg - 1) * 25}", tuple(args))
    search = (f'<div class="toolbar"><form method="get" action="/audit" role="search">'
              f'<label for="q" style="position:absolute;left:-9999px">Search the audit trail</label>'
              f'<input id="q" type="search" name="q" value="{e(term)}" placeholder="Search by person, action or submission number">'
              f'<button class="btn secondary" type="submit">{ui.icon("search", 16)}Search</button></form></div>')
    if rows:
        out = [[f'<span class="muted">{e(a["at"])}</span>', e(a["actor"]), f'<b>{e(ACTION_LABEL.get(a["action"], a["action"]))}</b>',
                f'<a href="/s/{a["sub_id"]}">#{a["sub_id"]}</a>' if a["sub_id"] else "-", e(a["note"] or "")] for a in rows]
        listing = ui.table(["When", "Who", "Event", "Submission", "Details"], out, "Audit trail") + \
            ui.pager("/audit" + (f"?q={quote(term)}" if term else ""), pg, pages)
    else:
        listing = ui.empty("No events found", "Events appear as submissions are made and decided." if not term else "Try a different search.")
    body = (ui.page_header("Audit Trail", "A history of what happened and who did it, newest first. This is a record of past events, "
                           "not the current status of a submission. File verification checks are not recorded here.")
            + ui.card("", search + listing))
    return page("Audit Trail", body, u, "audit", [("Audit Trail", None)], request)


# ---------------------------------------------------------------- admin views
def admin_dash(request, u):
    bid = u["brand_id"]
    brand = q("SELECT * FROM brands WHERE id=?", (bid,))[0]
    allrows = q(SUB_SQL + "WHERE s.brand_id=? ORDER BY s.id DESC", (bid,))
    queue = [r for r in allrows if r["status"] in QUEUE_STATUSES]
    n = Counter(r["status"] for r in allrows)
    approved = sum(n[s] for s in APPROVED_STATUSES)
    rejected = sum(n[s] for s in REJECTED_STATUSES)

    types = Counter()
    for r in allrows:
        for f in rep_of(r).get("findings", []):
            types[f["type"]] += 1
    ov = q("""SELECT a.action, COUNT(*) AS c FROM audit a JOIN submissions s ON s.id=a.sub_id
              WHERE s.brand_id=? AND a.action IN ('DISPUTE_OVERTURNED','DISPUTE_UPHELD') GROUP BY a.action""", (bid,))
    ovd = {r["action"]: r["c"] for r in ov}
    recent = q("""SELECT a.* FROM audit a LEFT JOIN submissions s ON s.id=a.sub_id
                  WHERE s.brand_id=? OR a.brand_id=? ORDER BY a.id DESC LIMIT 6""", (bid, bid))

    welcome = f"""<section class="card welcome" aria-labelledby="wl"><div class="card-head"><h2 id="wl">Welcome to your compliance workspace</h2>
      <button type="button" class="btn secondary sm" data-dismiss="builder">Dismiss</button></div>
      <p>Creators submit reels for {e(brand["name"])}. BrandGuard checks them against your approved facts and rules, and sends
      anything uncertain to you. Start with the Review Queue.</p>
      <ol class="steps"><li>Review submissions</li><li>Examine evidence</li><li>Approve, reject, or request supervision</li><li>Record the decision</li></ol></section>"""
    if queue:
        prio = sub_table(queue[:5], show_user=True, label="Priority reviews")
    else:
        prio = ui.empty("You are all caught up", "Nothing is waiting for a decision right now.")
    if types:
        common = "<ul style='margin:0;padding-left:20px'>" + "".join(
            f"<li>{e(TYPE_LABEL.get(k, k))}: <b>{v}</b></li>" for k, v in types.most_common(5)) + "</ul>"
        insights = (common + f'<p style="margin-top:12px">Disputes overturned: <b>{ovd.get("DISPUTE_OVERTURNED", 0)}</b> · '
                    f'upheld: <b>{ovd.get("DISPUTE_UPHELD", 0)}</b></p>'
                    '<p class="muted">Findings that creators successfully dispute may point to guidelines that need clearer wording.</p>')
    else:
        insights = ui.empty("No findings yet", "Insights appear after submissions are reviewed.")
    body = (ui.page_header("Compliance Overview",
                           f"Review activity for {e(brand['name'])}. Pending decisions are listed first.",
                           f'<a class="btn" href="/queue">{ui.icon("inbox", 16)}Review Queue ({len(queue)})</a>')
            + '<div class="stack">' + welcome
            + '<div class="stats">'
            + ui.stat("Awaiting review", len(queue), f"{n['SUPERVISION']} supervision, {n['DISPUTED']} disputed", "/queue", "info")
            + ui.stat("Supervision required", n["SUPERVISION"], "BrandGuard was unsure", "/queue?status=supervision", "warn")
            + ui.stat("Approved", approved, "Auto and reviewer approvals", "/reviews?status=approved", "ok")
            + ui.stat("Rejected", rejected, "", "/reviews?status=rejected", "bad")
            + '</div>'
            + ui.card("Priority reviews", prio, actions='<a href="/queue">Open queue</a>' if queue else "")
            + '<div class="grid-2">' + ui.card("Recent activity", timeline_html(recent), actions='<a href="/audit">Full audit trail</a>')
            + ui.card("Compliance insights", insights) + '</div></div>')
    return page("Overview", body, u, "overview", [], request)

    

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


def load_reg(u):
    return json.loads(q("SELECT registry FROM brands WHERE id=?", (u["brand_id"],))[0]["registry"])


def save_reg(u, reg):
    ex("UPDATE brands SET name=?, registry=? WHERE id=?",
       ((reg.get("brand") or "").strip() or "Brand", json.dumps(reg, ensure_ascii=False), u["brand_id"]))


def admin_only(request):
    u = me(request)
    return u if u and u["role"] == "admin" else None


RULE_KINDS = [
    ("banned_phrases", "Banned phrases", "Claims creators must never make. Any match is a violation.", "e.g. guaranteed returns"),
    ("confidential", "Confidential terms", "Internal terms that must never be spoken or written. A match blocks approval and is redacted in transcripts.", "e.g. dealer commission"),
    ("allowed_contacts", "Approved contact numbers", "Other phone numbers or emails are sent to a person to check.", "e.g. 9999999999"),
    ("glossary", "Speech glossary", "Project names and key terms that help the speech recogniser spell things correctly. This does not create violations.", "e.g. Demo Heights"),
]


@app.get("/admin/rules", response_class=HTMLResponse)
def rules_page(request: Request, err: str = ""):
    u = admin_only(request)
    if not u:
        return RedirectResponse("/", 303)
    reg = load_reg(u)
    term = request.query_params.get("q", "").strip().lower()[:60]
    cards, dialogs = [], []
    for key, title, desc, ph in RULE_KINDS:
        items = [x for x in reg.get(key, []) if not term or term in x.lower()]
        rows = []
        for i, x in enumerate(items):
            did = f"{key}-{i}"
            rows.append([f'<span lang="mr">{e(x)}</span>', ui.badge("Active", "ok", "check-circle"),
                         f'<button type="button" class="btn secondary sm" data-dialog="ed-{did}" aria-label="Edit {e(x)}">Edit</button> '
                         f'<button type="button" class="btn secondary sm" data-dialog="rm-{did}" aria-label="Remove {e(x)}">Remove</button>'])
            dialogs.append(ui.confirm_dialog(f"rm-{did}", "Remove this rule?",
                                             f"<b>{e(x)}</b> will no longer be checked. This affects new submissions only.",
                                             "/admin/rules/remove", "Remove rule", "danger", None, {"field": key, "value": x}))
            dialogs.append(
                f'<dialog id="ed-{did}" class="dlg" aria-labelledby="ed-{did}-t"><form method="post" action="/admin/rules/edit" data-lock>'
                f'<input type="hidden" name="field" value="{key}"><input type="hidden" name="old" value="{e(x)}">'
                f'<h2 id="ed-{did}-t">Edit rule</h2><label for="ed-{did}-v">Rule</label>'
                f'<input id="ed-{did}-v" name="value" value="{e(x)}" required maxlength="200">'
                f'<p class="muted">Changing a rule affects new submissions only. Earlier decisions are not re-evaluated.</p>'
                f'<div class="dlg-actions"><button type="button" class="btn secondary" data-close>Cancel</button>'
                f'<button type="submit" class="btn">Save change</button></div></form></dialog>')
        tbl = (ui.table(["Rule", "Status", "Actions"], rows, title) if rows else
               ui.empty("No matching rules" if term else "No rules yet", "Add one below." if not term else ""))
        add = (f'<form method="post" action="/admin/rules/add" class="toolbar" style="margin:14px 0 0" data-lock>'
               f'<input type="hidden" name="field" value="{key}"><label for="add-{key}" style="position:absolute;left:-9999px">Add to {e(title)}</label>'
               f'<input id="add-{key}" name="value" required maxlength="200" placeholder="{e(ph)}" style="flex:1;min-width:200px;margin:0">'
               f'<button class="btn" type="submit">{ui.icon("plus", 16)}Add</button></form>')
        cards.append(ui.card(f"{title} ({len(reg.get(key, []))})", tbl + add, desc))
    search = (f'<div class="toolbar"><form method="get" action="/admin/rules" role="search"><label for="q" style="position:absolute;left:-9999px">Search rules</label>'
              f'<input id="q" type="search" name="q" value="{e(term)}" placeholder="Search all rules">'
              f'<button class="btn secondary" type="submit">{ui.icon("search", 16)}Search</button></form></div>')
    body = (ui.page_header("Brand Rules", f"The rules every submission for {e(reg.get('brand', ''))} is checked against. "
                           "Changes apply to new submissions only.",
                           f'<a class="btn" href="/admin/guide">{ui.icon("upload", 16)}Import from PDF</a>')
            + '<div class="stack">' + (ui.alert(e(err), "bad") if err else "") + ui.card("", search)
            + "".join(cards) + "</div>" + "".join(dialogs))
    return page("Brand Rules", body, u, "rules", [("Brand Rules", None)], request)


def rule_field(field):
    return field if field in {k for k, *_ in RULE_KINDS} else None


@app.post("/admin/rules/add")
def rule_add(request: Request, field: str = Form(""), value: str = Form("")):
    u, field, value = admin_only(request), rule_field(field), value.strip()[:200]
    if not u or not field:
        return RedirectResponse("/", 303)
    reg = load_reg(u)
    if not value:
        return RedirectResponse("/admin/rules?err=Enter+a+value+to+add.", 303)
    if value.lower() in [x.lower() for x in reg.get(field, [])]:
        return RedirectResponse("/admin/rules?err=That+rule+already+exists.", 303)
    reg.setdefault(field, []).append(value)
    save_reg(u, reg)
    log(None, u["name"], "RULE_ADDED", f"{field}: {value}", u["brand_id"])
    request.session["flash"] = "Rule added. It applies to new submissions."
    return RedirectResponse("/admin/rules", 303)


@app.post("/admin/rules/edit")
def rule_edit(request: Request, field: str = Form(""), old: str = Form(""), value: str = Form("")):
    u, field, value = admin_only(request), rule_field(field), value.strip()[:200]
    if not u or not field:
        return RedirectResponse("/", 303)
    reg = load_reg(u)
    items = reg.get(field, [])
    if old not in items or not value:
        return RedirectResponse("/admin/rules?err=Could+not+find+that+rule.", 303)
    if value.lower() != old.lower() and value.lower() in [x.lower() for x in items]:
        return RedirectResponse("/admin/rules?err=That+rule+already+exists.", 303)
    items[items.index(old)] = value
    save_reg(u, reg)
    log(None, u["name"], "RULE_CHANGED", f"{field}: {old} -> {value}", u["brand_id"])
    request.session["flash"] = "Rule updated. It applies to new submissions."
    return RedirectResponse("/admin/rules", 303)


@app.post("/admin/rules/remove")
def rule_remove(request: Request, field: str = Form(""), value: str = Form("")):
    u, field = admin_only(request), rule_field(field)
    if not u or not field:
        return RedirectResponse("/", 303)
    reg = load_reg(u)
    if value in reg.get(field, []):
        reg[field].remove(value)
        save_reg(u, reg)
        log(None, u["name"], "RULE_REMOVED", f"{field}: {value}", u["brand_id"])
        request.session["flash"] = "Rule removed."
    return RedirectResponse("/admin/rules", 303)


def facts_view(request, u, reg, err="", form=None):
    f = form or {}
    rows, dialogs = [], []
    for i, c in enumerate(reg.get("configs", [])):
        rows.append([f'<b>{e(c["name"])}</b>', f'{ui.money(c["price"])} <span class="muted">({e(fmt_money(c["price"]))})</span>',
                     ui.badge("Checked on every review", "ok", "check-circle"),
                     f'<button type="button" class="btn secondary sm" data-dialog="ec-{i}" aria-label="Edit {e(c["name"])}">Edit</button> '
                     f'<button type="button" class="btn secondary sm" data-dialog="rc-{i}" aria-label="Remove {e(c["name"])}">Remove</button>'])
        dialogs.append(ui.confirm_dialog(f"rc-{i}", "Remove this approved price?",
                                         f"<b>{e(c['name'])}</b> will no longer be used to check prices. New submissions only.",
                                         "/admin/facts/price/remove", "Remove price", "danger", None, {"name": c["name"]}))
        dialogs.append(
            f'<dialog id="ec-{i}" class="dlg" aria-labelledby="ec-{i}-t"><form method="post" action="/admin/facts/price" data-lock>'
            f'<input type="hidden" name="old" value="{e(c["name"])}"><h2 id="ec-{i}-t">Edit approved price</h2>'
            f'<label for="ec-{i}-n">Configuration</label><input id="ec-{i}-n" name="name" value="{e(c["name"])}" required maxlength="80">'
            f'<label for="ec-{i}-p">Approved price</label><input id="ec-{i}-p" name="price" value="{c["price"]}" required>'
            f'<p class="hint">Rupees, e.g. 13000000, or 1.3 Cr, or 90 lakh. The saved value is shown back in full.</p>'
            f'<div class="dlg-actions"><button type="button" class="btn secondary" data-close>Cancel</button>'
            f'<button type="submit" class="btn">Save price</button></div></form></dialog>')
    price_tbl = (ui.table(["Configuration", "Approved price", "Engine", "Actions"], rows, "Approved prices") if rows
                 else ui.empty("No approved prices", "Add at least one price. Without it, prices cannot be verified."))
    add = (f'<form method="post" action="/admin/facts/price" data-lock style="margin-top:16px"><div class="field-grid">'
           f'<div><label for="pn">Configuration <span class="req">(required)</span></label><input id="pn" name="name" required maxlength="80" '
           f'value="{e(f.get("name", ""))}" placeholder="e.g. 2 BHK"></div>'
           f'<div><label for="pp">Approved price <span class="req">(required)</span></label><input id="pp" name="price" required '
           f'value="{e(f.get("price", ""))}" placeholder="e.g. 13000000 or 1.3 Cr" aria-describedby="pph"></div></div>'
           f'<p class="hint" id="pph">Enter rupees, or write 90 lakh / 1.3 Cr. The saved value is shown back in full so you can check lakh versus crore.</p>'
           f'<button class="btn" type="submit">{ui.icon("plus", 16)}Add approved price</button></form>')
    d = reg
    details = (f'<form method="post" action="/admin/setup" data-lock><div class="field-grid">'
               f'<div><label for="brand">Brand name</label><input id="brand" name="brand" value="{e(d.get("brand", ""))}"></div>'
               f'<div><label for="project">Project name</label><input id="project" name="project" value="{e(d.get("project", ""))}"></div>'
               f'<div><label for="rera">RERA number</label><input id="rera" name="rera" value="{e(d.get("rera", ""))}"></div>'
               f'<div><label for="poss">Possession date</label><input id="poss" name="possession" value="{e(d.get("possession", ""))}"></div></div>'
               f'<button class="btn" type="submit">Save details</button></form>')
    status = ui.table(["Fact", "Stored", "Used by the compliance engine"], [
        ["Approved prices", ui.badge("Stored", "ok", "check"), ui.badge("Checked on every review", "ok", "check-circle")],
        ["RERA number", ui.badge("Stored", "ok", "check"), ui.badge("Not checked yet", "neutral", "clock")],
        ["Possession date", ui.badge("Stored", "ok", "check"), ui.badge("Not checked yet", "neutral", "clock")]], "What is checked")
    body = (ui.page_header("Approved Facts", f"The reference information that content for {e(d.get('brand', ''))} is checked against. "
                           "Changes apply to new submissions only.")
            + '<div class="stack">' + (ui.alert(e(err), "bad") if err else "")
            + ui.card("Approved prices", price_tbl + add, "Spoken and written prices are compared with these.")
            + ui.card("Brand and project details", details)
            + ui.card("What is stored and what is checked", status,
                      "RERA numbers and possession dates are kept as reference only. Verifying them is planned, not available today.")
            + "</div>" + "".join(dialogs))
    return page("Approved Facts", body, u, "facts", [("Approved Facts", None)], request)


@app.get("/admin/setup")
def setup_redirect():
    return RedirectResponse("/admin/facts", 303)


@app.post("/admin/setup")
def setup_save(request: Request, brand: str = Form(None), project: str = Form(None), rera: str = Form(None),
               possession: str = Form(None), banned: str = Form(None), confidential: str = Form(None),
               contacts: str = Form(None), glossary: str = Form(None)):
    """Update only the fields that were sent. Price configurations have their own routes."""
    u = admin_only(request)
    if not u:
        return RedirectResponse("/", 303)
    reg = load_reg(u)
    for key, val in (("brand", brand), ("project", project), ("rera", rera), ("possession", possession)):
        if val is not None:
            reg[key] = val.strip()[:120]
    for key, val in (("banned_phrases", banned), ("confidential", confidential),
                     ("allowed_contacts", contacts), ("glossary", glossary)):
        if val is not None:
            reg[key] = lines(val)
    save_reg(u, reg)
    log(None, u["name"], "FACTS_UPDATED", "Brand and project details", u["brand_id"])
    request.session["flash"] = "Saved. New submissions use these details."
    return RedirectResponse("/admin/facts", 303)


@app.post("/admin/facts/price")
def price_save(request: Request, name: str = Form(""), price: str = Form(""), old: str = Form("")):
    u = admin_only(request)
    if not u:
        return RedirectResponse("/", 303)
    reg = load_reg(u)
    name = name.strip()[:80]
    val = parse_price(price) if price.strip() else None
    if not name or not val or val <= 0:
        return facts_view(request, u, reg, "Enter a configuration name and a price greater than zero, such as 13000000 or 1.3 Cr.",
                          {"name": name, "price": price})
    cfgs = reg.setdefault("configs", [])
    names = [c["name"].lower() for c in cfgs if c["name"] != old]
    if name.lower() in names:
        return facts_view(request, u, reg, f'"{name}" already has an approved price. Edit that row instead.',
                          {"name": name, "price": price})
    for c in cfgs:
        if old and c["name"] == old:
            c["name"], c["price"] = name, val
            break
    else:
        cfgs.append({"name": name, "price": val})
    save_reg(u, reg)
    log(None, u["name"], "PRICE_SAVED", f"{name} = {ui.money(val)}", u["brand_id"])
    request.session["flash"] = f"Saved {name} at {ui.money(val)}."
    return RedirectResponse("/admin/facts", 303)


@app.post("/admin/facts/price/remove")
def price_remove(request: Request, name: str = Form("")):
    u = admin_only(request)
    if not u:
        return RedirectResponse("/", 303)
    reg = load_reg(u)
    if len(reg.get("configs", [])) <= 1:
        return facts_view(request, u, reg, "At least one approved price must remain, otherwise prices cannot be verified.")
    before = len(reg["configs"])
    reg["configs"] = [c for c in reg["configs"] if c["name"] != name]
    if len(reg["configs"]) != before:
        save_reg(u, reg)
        log(None, u["name"], "PRICE_REMOVED", name, u["brand_id"])
        request.session["flash"] = "Approved price removed."
    return RedirectResponse("/admin/facts", 303)


# -------------------------------------------------------- tamper check (hash)
def verify_page(request, u, result=""):
    body = (ui.page_header("Verify an Approved File",
                           "Check whether a file is exactly the one that was approved, before you post it.")
            + '<div class="cols"><div class="stack">'
            + ui.card("", f"""<form method="post" action="/verify" enctype="multipart/form-data" data-lock>
              <label for="vf">File to check</label><input id="vf" type="file" name="file" required>
              <p class="hint">Up to {MAX_MB} MB. The file is read only to compute its fingerprint and is not stored.</p>
              <p data-busy hidden class="muted" role="status">Checking...</p>
              <button class="btn" type="submit" data-busy-label="Checking...">{ui.icon("file-check", 16)}Verify File</button></form>""")
            + result + '</div><div>'
            + ui.card("How this works", """<p class="muted">Every approved file has a SHA-256 fingerprint. Even a tiny edit changes
              it completely. If the file you upload has the same fingerprint as an approved submission, it is identical to what was approved.</p>
              <p class="muted" style="margin:0">A file that does not match has simply not been approved in this form. That does not mean it is unsafe.</p>""")
            + '</div></div>')
    return page("Verify a File", body, u, "verify", [("Verify a File", None)], request)


@app.get("/verify", response_class=HTMLResponse)
def verify_form(request: Request):
    u = me(request)
    if not u:
        return RedirectResponse("/", 303)
    return verify_page(request, u)


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
            return verify_page(request, u, ui.alert(f"This file is larger than {MAX_MB} MB, so it could not be checked.",
                                                    "bad", "Could not verify."))
        h.update(chunk)
    digest = h.hexdigest()
    rows = q("SELECT id, approval_id, brand_id, user_id FROM submissions WHERE sha256=? AND approval_id IS NOT NULL AND source_url IS NULL",
             (digest,))
    fp = f'<dl class="kv" style="margin-top:12px"><dt>File fingerprint (SHA-256)</dt><dd class="mono">{digest}</dd></dl>'
    if rows:
        r = rows[0]
        link = ""
        if can_view(u, {"brand_id": r["brand_id"], "user_id": r["user_id"]}):
            link = f' <a href="/s/{r["id"]}">View submission #{r["id"]}</a>.'
        result = ui.card("", ui.alert(f'This file is identical to an approved submission. Approval ID: <b>{e(r["approval_id"])}</b>.{link}',
                                      "ok", "Match.") + fp)
    else:
        result = ui.card("", ui.alert("This file does not match any approved record. It may have been edited after approval, "
                                      "or it was never approved in this form.", "warn", "No match.") + fp)
    return verify_page(request, u, result)

    

# ============================================================ projects, facts, access (admin)
def own_project(u, pid):
    p = RE.get_project(pid)
    return p if p and p["brand_id"] == u["brand_id"] else None


def source_id_for(u, title):
    title = (title or "").strip()
    if not title:
        return None
    hit = q("SELECT id FROM sources WHERE brand_id=? AND title=?", (u["brand_id"], title[:200]))
    return hit[0]["id"] if hit else RE.add_source(u["brand_id"], title, "document", "official", u["name"])


def parse_fact_value(key, raw):
    raw = (raw or "").strip()
    if not raw:
        raise ValueError("Enter a value.")
    if key in ("price", "booking_amount"):
        v = parse_price(raw)
        if not v or v <= 0:
            raise ValueError("Enter a price greater than zero, for example 13000000 or 1.3 Cr.")
        return float(v), None
    if key in RE.NUMERIC_FIELDS or key.startswith("landmark:"):
        try:
            v = float(raw.replace(",", ""))
        except ValueError:
            raise ValueError("Enter a number.")
        if v <= 0:
            raise ValueError("The number must be greater than zero.")
        return v, None
    if key == "possession":
        if not re.fullmatch(r"20\d\d-(0[1-9]|1[0-2])", raw):
            raise ValueError("Write possession as year-month, for example 2028-12.")
        return None, raw
    if key == "ready_to_move":
        if raw.lower() not in ("yes", "no"):
            raise ValueError("Choose yes or no.")
        return None, raw.lower()
    return None, raw[:200]


def admin_back(request, pid, msg="", err=""):
    if msg:
        request.session["flash"] = msg
    if err:
        request.session["flash"] = err
    return RedirectResponse(f"/admin/projects/{pid}", 303)


@app.get("/admin/facts")
def facts_redirect(request: Request):
    return RedirectResponse("/admin/projects", 303)


@app.get("/admin/projects", response_class=HTMLResponse)
def projects_page(request: Request):
    u = admin_only(request)
    if not u:
        return RedirectResponse("/", 303)
    rows = []
    for p in RE.brand_projects(u["brand_id"], active_only=False):
        n_units = len(RE.unit_types(p["id"]))
        rera = (e(p["rera_no"]) + "<br>" + ui.badge({"authoritative": "Confirmed with official register", "format": "Format only",
                "registry_match": "Registry match"}.get(p["rera_level"], "Not recorded"),
                "ok" if p["rera_level"] == "authoritative" else "neutral")) if p["rera_no"] else '<span class="muted">Not recorded</span>'
        rows.append([f'<a href="/admin/projects/{p["id"]}"><b>{e(p["official_name"])}</b></a>',
                     e(", ".join(x for x in (p["locality"], p["city"]) if x) or "-"), rera, str(n_units),
                     f'<a class="btn secondary sm" href="/admin/projects/{p["id"]}">Open</a>'])
    add = (f'<form method="post" action="/admin/projects/add" data-lock><div class="field-grid">'
           f'<div><label for="pn">Official project name</label><input id="pn" name="official_name" required maxlength="120"></div>'
           f'<div><label for="ps">Short name</label><input id="ps" name="short_name" maxlength="60"></div>'
           f'<div><label for="pc">City</label><input id="pc" name="city" maxlength="60"></div>'
           f'<div><label for="pl">Locality</label><input id="pl" name="locality" maxlength="60"></div>'
           f'<div><label for="pr">RERA number</label><input id="pr" name="rera_no" maxlength="20" placeholder="P followed by 11 digits"></div>'
           f'<div><label for="pa">Other names (one per line)</label><textarea id="pa" name="aliases" rows="3" '
           f'placeholder="Hindi, Marathi and short spellings"></textarea></div></div>'
           f'<button class="btn" type="submit">{ui.icon("plus", 16)}Add project</button></form>')
    body = (ui.page_header("Projects and Facts", "Every project, its property types and the approved facts that content is checked against.")
            + '<div class="stack">'
            + ui.card("Projects", ui.table(["Project", "Location", "RERA", "Property types", ""], rows, "Projects") if rows else ui.empty("No projects yet"))
            + ui.card("Add a project", add, "Aliases help BrandGuard recognise the project in Hindi, Marathi or short forms.") + "</div>")
    return page("Projects and Facts", body, u, "facts", [("Projects and Facts", None)], request)


@app.post("/admin/projects/add")
def project_add(request: Request, official_name: str = Form(""), short_name: str = Form(""), city: str = Form(""),
                locality: str = Form(""), rera_no: str = Form(""), aliases: str = Form("")):
    u = admin_only(request)
    if not u:
        return RedirectResponse("/", 303)
    if not official_name.strip():
        request.session["flash"] = "Enter the project name."
        return RedirectResponse("/admin/projects", 303)
    pid = RE.add_project(u["brand_id"], official_name, short_name, city, locality, rera_no, lines(aliases), u["name"])
    log(None, u["name"], "PROJECT_ADDED", official_name.strip(), u["brand_id"])
    request.session["flash"] = "Project added. Now add its property types and facts."
    return RedirectResponse(f"/admin/projects/{pid}", 303)


def fact_rows_html(pid, unit_id=None):
    fs = RE._q("SELECT * FROM facts WHERE project_id=? AND " + ("unit_type_id=?" if unit_id else "unit_type_id IS NULL") + " ORDER BY key, id",
               (pid, unit_id) if unit_id else (pid,))
    out = []
    for f in fs:
        cur = RE._is_current(f)
        state = ui.badge("Current", "ok", "check") if cur else ui.badge("Not current", "neutral", "clock")
        src = q("SELECT title FROM sources WHERE id=?", (f["source_id"],)) if f["source_id"] else []
        end = ""
        if cur:
            end = (f'<form method="post" action="/admin/projects/{pid}/fact/end" style="display:inline"><input type="hidden" name="fact_id" value="{f["id"]}">'
                   f'<button class="btn secondary sm" type="submit">Withdraw</button></form>')
        out.append([e(RE.FACT_LABEL.get(f["key"], f["key"].replace("offer:", "Offer: ").replace("landmark:", "Place: "))),
                    e(RE.fact_display(f)), f'{e(f["valid_from"] or "")} to {e(f["valid_to"] or "open")}',
                    e(src[0]["title"] if src else "-"), state, end])
    return out


@app.get("/admin/projects/{pid}", response_class=HTMLResponse)
def project_detail(request: Request, pid: int):
    u = admin_only(request)
    p = own_project(u, pid) if u else None
    if not p:
        return RedirectResponse("/admin/projects", 303)
    heads = ["Fact", "Value", "Valid", "Source", "State", ""]
    units_html = ""
    for ut in RE.unit_types(pid):
        cat = RE.CATEGORIES[ut["category"]][0]
        rows = fact_rows_html(pid, ut["id"])
        units_html += ui.card(f'{ut["label"]} ({cat})', ui.table(heads, rows, ut["label"]) if rows else ui.empty("No facts yet"),
                              actions=f'<a href="#fact-form">Add fact</a>')
    cat_opts = "".join(f'<option value="{k}">{e(v[0])}</option>' for k, v in RE.CATEGORIES.items())
    field_inputs = "".join(f'<div><label for="uf-{k}">{e(RE.FIELD_LABEL[k])}</label><input id="uf-{k}" name="{k}"></div>'
                           for k in ("bhk", "carpet_sqft", "builtup_sqft", "plot_sqft", "bathrooms", "balconies", "parking", "floor_range", "facing", "dimensions", "permitted_use"))
    unit_form = (f'<form method="post" action="/admin/projects/{pid}/unit" data-lock><div class="field-grid">'
                 f'<div><label for="uc">Property category</label><select id="uc" name="category">{cat_opts}</select></div>'
                 f'<div><label for="ul">Name</label><input id="ul" name="label" required placeholder="e.g. 2 BHK, Corner plot A"></div>'
                 f'<div><label for="uprice">Price (required)</label><input id="uprice" name="price" required placeholder="e.g. 1.3 Cr"></div>'
                 f'{field_inputs}'
                 f'<div><label for="usrc">Source document</label><input id="usrc" name="source" placeholder="e.g. Approved price sheet Oct 2026"></div></div>'
                 f'<p class="hint">Fill only what applies. Fields that do not apply to the category (for example BHK for a plot) are ignored.</p>'
                 f'<button class="btn" type="submit">{ui.icon("plus", 16)}Add property type</button></form>')
    unit_opts = '<option value="">Whole project</option>' + "".join(
        f'<option value="{ut["id"]}">{e(ut["label"])}</option>' for ut in RE.unit_types(pid))
    key_opts = "".join(f'<option value="{k}">{v}</option>' for k, v in (
        ("price", "Price"), ("booking_amount", "Booking amount"), ("carpet_sqft", "Carpet area (sq ft)"),
        ("builtup_sqft", "Built-up area (sq ft)"), ("plot_sqft", "Plot area (sq ft)"), ("bathrooms", "Bathrooms"),
        ("balconies", "Balconies"), ("parking", "Parking"), ("possession", "Possession (YYYY-MM)"),
        ("ready_to_move", "Ready to move (yes or no)")))
    offer_opts = "".join(f'<option value="offer:{k}">{v[0]}</option>' for k, v in RE.OFFER_TAGS.items())
    fact_form = (f'<form id="fact-form" method="post" action="/admin/projects/{pid}/fact" data-lock><div class="field-grid">'
                 f'<div><label for="fk">Fact</label><select id="fk" name="key">{key_opts}{offer_opts}</select></div>'
                 f'<div><label for="fu">Applies to</label><select id="fu" name="unit_type_id">{unit_opts}</select></div>'
                 f'<div><label for="fv">Value or terms</label><input id="fv" name="value" required></div>'
                 f'<div><label for="ffrom">Valid from</label><input id="ffrom" name="valid_from" type="date"></div>'
                 f'<div><label for="fto">Valid until (offers)</label><input id="fto" name="valid_to" type="date"></div>'
                 f'<div><label for="fs">Source document</label><input id="fs" name="source" required placeholder="Where this number comes from"></div>'
                 f'<div><label for="fr">Reason for change</label><input id="fr" name="reason" placeholder="e.g. Revised price sheet"></div></div>'
                 f'<p class="hint">Saving a new value closes the old one. Earlier approvals that used the old value are flagged for re-check, '
                 f'not changed.</p><button class="btn" type="submit">Save fact</button></form>')
    lm_form = (f'<form method="post" action="/admin/projects/{pid}/landmark" data-lock><div class="field-grid">'
               f'<div><label for="lmn">Place</label><input id="lmn" name="place" required placeholder="e.g. Wakad bridge"></div>'
               f'<div><label for="lmm">Travel time (minutes)</label><input id="lmm" name="minutes" required></div>'
               f'<div><label for="lmh">By</label><input id="lmh" name="how" placeholder="car, walking..."></div>'
               f'<div><label for="lms">Source document</label><input id="lms" name="source" required></div></div>'
               f'<button class="btn" type="submit">Save travel time</button></form>')
    proj_facts = fact_rows_html(pid, None)
    lm = RE._q("SELECT * FROM facts WHERE project_id=? AND key LIKE 'landmark:%' ORDER BY id", (pid,))
    lm_rows = [[e(f["key"].split(":", 1)[1].title()), e(f"{f['value_num']:g} min {f['unit'] or ''}"),
                f'{e(f["valid_from"] or "")} to {e(f["valid_to"] or "open")}', ui.badge("Current", "ok") if RE._is_current(f) else ui.badge("Not current", "neutral")]
               for f in lm]
    rera_info = (f'<dl class="kv"><dt>RERA number</dt><dd>{e(p["rera_no"] or "Not recorded")}</dd>'
                 f'<dt>Verification level</dt><dd>{e({"authoritative": "Confirmed with the official register", "format": "Format is valid. Not checked against any register.", "registry_match": "Matches the BrandGuard registry only"}.get(p["rera_level"], "Not recorded"))}</dd>'
                 + (f'<dt>Checked</dt><dd>{e(p["rera_checked_at"] or "")} by {e(p["rera_checked_by"] or "")} against {e(p["rera_source"] or "")}</dd>' if p["rera_level"] == "authoritative" else "")
                 + '</dl>')
    rera_form = (f'<form method="post" action="/admin/projects/{pid}/rera" data-lock><div class="field-grid">'
                 f'<div><label for="rn">RERA number</label><input id="rn" name="rera_no" value="{e(p["rera_no"] or "")}"></div>'
                 f'<div><label for="rs">Official register checked (optional)</label><input id="rs" name="source" placeholder="e.g. MahaRERA website, checked on screen"></div></div>'
                 f'<p class="hint">Fill the second box only if you have actually looked the number up on the official register. '
                 f'Otherwise it stays a format or registry match, never a confirmed registration.</p>'
                 f'<button class="btn" type="submit">Save RERA details</button></form>')
    names = RE.names_of(p)
    alias_form = (f'<form method="post" action="/admin/projects/{pid}/alias" data-lock><label for="al">Add another name</label>'
                  f'<input id="al" name="alias" required maxlength="80" placeholder="Hindi, Marathi or short spelling"><br><br>'
                  f'<button class="btn" type="submit">Add name</button></form>')
    body = (ui.page_header(p["official_name"], e(", ".join(x for x in (p["locality"], p["city"]) if x)),
                           '<a class="btn secondary" href="/admin/projects">All projects</a>')
            + '<div class="stack">'
            + ui.card("Names BrandGuard listens for", "<p>" + e(" | ".join(names)) + "</p>" + alias_form)
            + ui.card("RERA", rera_info + rera_form)
            + ui.card("Project-wide facts", ui.table(heads, proj_facts, "Project facts") if proj_facts else ui.empty("None yet"))
            + units_html
            + ui.card("Add a property type", unit_form, "Apartment, penthouse, villa, bungalow, row house or plot.")
            + ui.card("Add or change a fact", fact_form, "Possession, ready to move, booking amount, offers and unit facts.")
            + ui.card("Travel times to landmarks", (ui.table(["Place", "Time", "Valid", "State"], lm_rows, "Landmarks") if lm_rows else "") + lm_form)
            + "</div>")
    return page(p["official_name"], body, u, "facts", [("Projects and Facts", "/admin/projects"), (p["official_name"], None)], request)


def _save_fact(u, p, key, unit_type_id, value, source, reason, valid_from, valid_to):
    num, txt = parse_fact_value(key, value)
    if unit_type_id:
        ut = RE._q("SELECT * FROM unit_types WHERE id=? AND project_id=?", (unit_type_id, p["id"]))
        if not ut:
            raise ValueError("That property type does not belong to this project.")
        if key in ("possession", "ready_to_move", "booking_amount") or key.startswith("offer:"):
            unit_type_id = None
        elif key not in RE.CATEGORIES[ut[0]["category"]][1] and key != "price":
            raise ValueError("That fact does not apply to this property category.")
    elif key in RE.NUMERIC_FIELDS or key == "price":
        raise ValueError("Choose the property type this applies to.")
    if valid_from and valid_to and valid_to < valid_from:
        raise ValueError("The end date is before the start date.")
    sid_ = source_id_for(u, source)
    unit = "INR" if key in ("price", "booking_amount") else ("sq ft" if key.endswith("sqft") else "")
    fid, old = RE.set_fact(p["id"], key, num, txt, unit_type_id, unit, sid_, valid_from or None, valid_to or None,
                           u["name"], reason)
    log(None, u["name"], "FACT_SET", f'{p["official_name"]}: {RE.FACT_LABEL.get(key, key)} = {txt if txt else num}'
        + (f" (replaced {len(old)} earlier value)" if old else ""), u["brand_id"])
    return fid


@app.post("/admin/projects/{pid}/unit")
async def project_unit(request: Request, pid: int):
    u = admin_only(request)
    p = own_project(u, pid) if u else None
    if not p:
        return RedirectResponse("/admin/projects", 303)
    f = await request.form()
    cat, label = f.get("category", ""), (f.get("label", "") or "").strip()
    try:
        if cat not in RE.CATEGORIES or not label:
            raise ValueError("Choose a category and give the property type a name.")
        allowed = RE.CATEGORIES[cat][1]
        bhk = None
        if "bhk" in allowed and (f.get("bhk") or "").strip():
            try:
                bhk = int(float(f.get("bhk")))
            except ValueError:
                raise ValueError("BHK must be a number.")
        uid = RE.add_unit_type(pid, cat, label, bhk)
        _save_fact(u, p, "price", uid, f.get("price", ""), f.get("source", ""), "Added with property type", "", "")
        for k in allowed:
            if k in ("bhk",) or not (f.get(k) or "").strip():
                continue
            if k in RE.NUMERIC_FIELDS:
                _save_fact(u, p, k, uid, f.get(k), f.get("source", ""), "Added with property type", "", "")
            else:
                num, txt = None, f.get(k).strip()[:100]
                RE.set_fact(pid, k, num, txt, uid, "", source_id_for(u, f.get("source", "")), None, None, u["name"], "Added with property type")
        log(None, u["name"], "UNIT_ADDED", f'{p["official_name"]}: {label} ({cat})', u["brand_id"])
        return admin_back(request, pid, f"Added {label}.")
    except ValueError as ex_:
        return admin_back(request, pid, err=str(ex_))


@app.post("/admin/projects/{pid}/fact")
def project_fact(request: Request, pid: int, key: str = Form(""), unit_type_id: str = Form(""), value: str = Form(""),
                 source: str = Form(""), reason: str = Form(""), valid_from: str = Form(""), valid_to: str = Form("")):
    u = admin_only(request)
    p = own_project(u, pid) if u else None
    if not p:
        return RedirectResponse("/admin/projects", 303)
    if not key or not source.strip():
        return admin_back(request, pid, err="Choose a fact and name the source document.")
    if key.startswith("offer:") and not valid_to:
        return admin_back(request, pid, err="Offers need an end date, so that expired offers are never treated as current.")
    try:
        _save_fact(u, p, key, int(unit_type_id) if unit_type_id.isdigit() else None, value, source, reason, valid_from, valid_to)
    except ValueError as ex_:
        return admin_back(request, pid, err=str(ex_))
    return admin_back(request, pid, "Saved. Earlier approvals that relied on the old value have been flagged for re-check.")


@app.post("/admin/projects/{pid}/fact/end")
def project_fact_end(request: Request, pid: int, fact_id: int = Form(0)):
    u = admin_only(request)
    p = own_project(u, pid) if u else None
    if not p:
        return RedirectResponse("/admin/projects", 303)
    f = RE._q("SELECT * FROM facts WHERE id=? AND project_id=?", (fact_id, pid))
    if f:
        RE.end_fact(fact_id, u["name"])
        log(None, u["name"], "FACT_ENDED", f'{p["official_name"]}: {RE.FACT_LABEL.get(f[0]["key"], f[0]["key"])}', u["brand_id"])
    return admin_back(request, pid, "Fact withdrawn. It is no longer treated as current.")


@app.post("/admin/projects/{pid}/landmark")
def project_landmark(request: Request, pid: int, place: str = Form(""), minutes: str = Form(""), how: str = Form(""),
                     source: str = Form("")):
    u = admin_only(request)
    p = own_project(u, pid) if u else None
    if not p:
        return RedirectResponse("/admin/projects", 303)
    try:
        if not place.strip() or not source.strip():
            raise ValueError("Enter the place and the source document.")
        num, _ = parse_fact_value("landmark:x", minutes)
        RE.set_fact(pid, "landmark:" + place.strip().lower()[:60], num, None, None, (how.strip() or "min")[:30],
                    source_id_for(u, source), None, None, u["name"], "Travel time")
        log(None, u["name"], "FACT_SET", f'{p["official_name"]}: {place.strip()} {num:g} min', u["brand_id"])
    except ValueError as ex_:
        return admin_back(request, pid, err=str(ex_))
    return admin_back(request, pid, "Saved.")


@app.post("/admin/projects/{pid}/alias")
def project_alias(request: Request, pid: int, alias: str = Form("")):
    u = admin_only(request)
    p = own_project(u, pid) if u else None
    if not p:
        return RedirectResponse("/admin/projects", 303)
    if alias.strip():
        ex("INSERT INTO project_aliases (project_id, alias) VALUES (?,?)", (pid, alias.strip()[:80]))
        log(None, u["name"], "PROJECT_EDITED", f'{p["official_name"]}: added name "{alias.strip()}"', u["brand_id"])
    return admin_back(request, pid, "Name added.")


@app.post("/admin/projects/{pid}/rera")
def project_rera(request: Request, pid: int, rera_no: str = Form(""), source: str = Form("")):
    u = admin_only(request)
    p = own_project(u, pid) if u else None
    if not p:
        return RedirectResponse("/admin/projects", 303)
    rera_no = rera_no.strip().upper()
    if rera_no and not RE.rera_format_ok(rera_no):
        return admin_back(request, pid, err="A RERA number looks like P followed by 11 digits.")
    level = "none" if not rera_no else "format"
    ex("UPDATE projects SET rera_no=?, rera_level=?, rera_source=NULL, rera_checked_at=NULL, rera_checked_by=NULL WHERE id=?",
       (rera_no, level, pid))
    if rera_no and source.strip():
        ex("UPDATE projects SET rera_level='authoritative', rera_source=?, rera_checked_at=?, rera_checked_by=? WHERE id=?",
           (source.strip()[:120], RE.today(), u["name"], pid))
        log(None, u["name"], "RERA_RECORDED", f'{p["official_name"]}: {rera_no} confirmed against {source.strip()}', u["brand_id"])
    else:
        log(None, u["name"], "PROJECT_EDITED", f'{p["official_name"]}: RERA number {rera_no or "removed"}', u["brand_id"])
    return admin_back(request, pid, "RERA details saved.")


@app.get("/admin/access", response_class=HTMLResponse)
def access_page(request: Request):
    u = admin_only(request)
    if not u:
        return RedirectResponse("/", 303)
    users = q("""SELECT us.id, us.name FROM users us JOIN memberships m ON m.user_id=us.id
                 WHERE m.brand_id=? ORDER BY us.name""", (u["brand_id"],))
    projs = RE.brand_projects(u["brand_id"])
    rows = []
    for us in users:
        gs = [g for g in q("SELECT * FROM grants WHERE user_id=? AND brand_id=? ORDER BY id", (us["id"], u["brand_id"])) if RE._grant_active(g)]
        items = ""
        for g in gs:
            pr = RE.get_project(g["project_id"])
            exp = f' <span class="muted">until {e(g["expires"])}</span>' if g["expires"] else ""
            items += (f'<form method="post" action="/admin/access/revoke" style="display:inline-block;margin:2px 6px 2px 0">'
                      f'<input type="hidden" name="grant_id" value="{g["id"]}">{ui.badge(pr["official_name"] if pr else "?", "info")}{exp} '
                      f'<button class="btn secondary sm" type="submit" aria-label="Remove access to {e(pr["official_name"] if pr else "")}">Remove</button></form>')
        rows.append([e(us["name"]), items or '<span class="muted">No project access</span>'])
    boxes = "".join(f'<label class="check"><input type="checkbox" name="project_id" value="{p["id"]}"> {e(p["official_name"])}'
                    f'{" (" + e(p["city"]) + ")" if p["city"] else ""}</label>' for p in projs)
    uopts = "".join(f'<option value="{us["id"]}">{e(us["name"])}</option>' for us in users)
    form = (f'<form method="post" action="/admin/access/grant" data-lock><label for="gu">Partner or freelancer</label>'
            f'<select id="gu" name="user_id">{uopts}</select><p></p><b>Projects</b><div>{boxes}</div><p></p>'
            f'<label for="gx">Access ends on (optional)</label><input id="gx" type="date" name="expires">'
            f'<p class="hint">Tick as many projects as needed. A city or company link does not grant every project, only the ticked ones.</p>'
            f'<button class="btn" type="submit">Grant access</button></form>')
    body = (ui.page_header("Project Access", "Who may submit content for which project. Nobody needs a per-reel assignment.")
            + '<div class="stack">' + ui.card("Current access", ui.table(["Person", "Projects"], rows, "Access") if rows else ui.empty("No partners linked"))
            + ui.card("Grant access", form) + "</div>")
    return page("Project Access", body, u, "access", [("Project Access", None)], request)


@app.post("/admin/access/grant")
async def access_grant(request: Request):
    u = admin_only(request)
    if not u:
        return RedirectResponse("/", 303)
    f = await request.form()
    uid = f.get("user_id", "")
    if not str(uid).isdigit() or not q("SELECT 1 FROM memberships WHERE user_id=? AND brand_id=?", (int(uid), u["brand_id"])):
        request.session["flash"] = "That person is not linked to your company."
        return RedirectResponse("/admin/access", 303)
    n = 0
    for pid in f.getlist("project_id"):
        if str(pid).isdigit() and own_project(u, int(pid)):
            RE.grant(int(uid), u["brand_id"], int(pid), u["name"], (f.get("expires") or None))
            log(None, u["name"], "ACCESS_GRANTED", f"user {uid} -> {RE.get_project(int(pid))['official_name']}", u["brand_id"])
            n += 1
    request.session["flash"] = f"Access granted for {n} project(s)." if n else "Tick at least one project."
    return RedirectResponse("/admin/access", 303)


@app.post("/admin/access/revoke")
def access_revoke(request: Request, grant_id: int = Form(0)):
    u = admin_only(request)
    if not u:
        return RedirectResponse("/", 303)
    if RE.revoke(grant_id, u["brand_id"], u["name"]):
        log(None, u["name"], "ACCESS_REVOKED", f"grant {grant_id}", u["brand_id"])
        request.session["flash"] = "Access removed. It takes effect immediately."
    return RedirectResponse("/admin/access", 303)


# ============================================================ learned cases (new)
@app.get("/admin/learned", response_class=HTMLResponse)
def learned_page(request: Request):
    u = admin_only(request)
    if not u:
        return RedirectResponse("/", 303)
    cases = LRN.list_cases(u["brand_id"])
    rows = []
    for c in cases:
        state = ui.badge("Active", "ok", "check-circle") if c["active"] else ui.badge("Switched off", "neutral", "clock")
        said = e(c["said_text"] or "-")
        btn = ""
        if c["active"]:
            btn = (f'<form method="post" action="/admin/learned/off" style="display:inline">'
                   f'<input type="hidden" name="case_id" value="{c["id"]}">'
                   f'<button class="btn secondary sm" type="submit" aria-label="Switch off this remembered case">Switch off</button></form>')
        rows.append([e(KIND_LABEL.get(c["kind"], c["kind"])), e(str(c["heard"] or "")), e(str(c["official"] or "")), said,
                     f'<a href="/s/{c["sub_id"]}">#{c["sub_id"]}</a>', str(c["times"]), e(c["last_seen"] or c["created_at"] or ""),
                     state, btn])
    table = (ui.table(["Claim", "System heard", "Approved value", "Creator said", "Overturned in", "Seen", "Last seen", "State", ""],
                      rows, "Remembered dispute cases")
             if rows else ui.empty("Nothing remembered yet",
                                   "When you overturn a dispute about a price or booking amount, the case appears here."))
    body = (ui.page_header("Learned Cases",
                           "Disputes you overturned. If the same reading shows up again for this company, BrandGuard asks a person "
                           "to check instead of rejecting it.")
            + '<div class="stack">'
            + ui.alert("A remembered case never approves anything on its own. It only changes a rejection into a human check. "
                       "Switch a case off if you no longer want that.", "info", "How this works.")
            + ui.card("Remembered cases", table) + "</div>")
    return page("Learned Cases", body, u, "learned", [("Learned Cases", None)], request)


@app.post("/admin/learned/off")
def learned_off(request: Request, case_id: int = Form(0)):
    u = admin_only(request)
    if not u:
        return RedirectResponse("/", 303)
    if LRN.switch_off(u["brand_id"], case_id):
        log(None, u["name"], "CASE_REMEMBERED", f"Remembered case {case_id} switched off", u["brand_id"])
        request.session["flash"] = "Case switched off. That reading will be rejected normally again."
    return RedirectResponse("/admin/learned", 303)

    


# ============================================================ import brand rules and projects from a PDF (builder)
GUIDE_HEADINGS = {
    "banned_phrases": ("banned phrases", "banned phrase", "banned words", "banned claims", "prohibited phrases",
                       "prohibited claims", "restricted phrases", "do not say", "never say", "phrases to avoid"),
    "confidential": ("confidential", "confidential terms", "confidential information", "internal terms",
                     "never disclose", "do not disclose"),
    "allowed_contacts": ("approved contacts", "approved contact numbers", "approved contact", "authorised contacts",
                         "authorized contacts", "contact numbers", "official contacts"),
    "glossary": ("glossary", "speech glossary", "project names", "key terms", "brand terms"),
}
GUIDE_LABEL = {"banned_phrases": "Banned phrases", "confidential": "Confidential terms",
               "allowed_contacts": "Approved contact numbers", "glossary": "Speech glossary"}
_BULLET = re.compile(r"^\s*(?:[•●▪‣\*\-–—]|\(?\d{1,2}[.)])\s+")

# project lines: "Project: Name", then "City: Pune", then one line per property type
PROJECT_KEYS = {
    "city": ("city",),
    "locality": ("locality", "area", "location", "micro market"),
    "rera": ("rera", "rera number", "rera no", "rera registration"),
    "possession": ("possession", "possession date"),
    "ready": ("ready to move", "ready to move in"),
    "booking": ("booking amount", "token amount"),
    "short": ("short name",),
    "aliases": ("other names", "aliases", "also called", "hindi name", "marathi name"),
}
_PROJ_START = re.compile(r"^(?:project|project name)\s*[:\-–]\s*(.+)$", re.I)
_KV = re.compile(r"^([A-Za-z ]{3,30}?)\s*[:\-–]\s*(.+)$")
_UNIT = re.compile(r"^(.{2,50}?)\s*[:\-–]\s*(.*\bprice\b.*)$", re.I)


def pdf_text(data, filename):
    """Plain text of a PDF or TXT. Scanned PDFs have no text layer and are refused clearly."""
    if filename.lower().endswith(".txt"):
        return data.decode("utf-8", "ignore")
    from pypdf import PdfReader
    import io as _io
    r = PdfReader(_io.BytesIO(data))
    if r.is_encrypted:
        raise ValueError("This PDF is password protected. Remove the password and upload it again.")
    if len(r.pages) > 40:
        raise ValueError("This PDF has more than 40 pages. Upload only the brand guidelines section.")
    text = "\n".join((p.extract_text() or "") for p in r.pages)
    if len(text.strip()) < 20:
        raise ValueError("No readable text was found. This looks like a scanned image, which is not supported yet. "
                         "Upload a PDF exported from a document, or a .txt file.")
    return text


def _heading_key(line):
    """Returns (rule key, inline text after the colon) when the line is a known rules heading."""
    base = re.sub(r"\s+", " ", _BULLET.sub("", line)).strip()
    t = base.strip(":").strip().lower()
    for k, names in GUIDE_HEADINGS.items():
        if t in names:
            return k, ""
    m = re.match(r"^([A-Za-z ]{3,30})\s*:\s*(.+)$", base)
    if m:
        head = m.group(1).strip().lower()
        for k, names in GUIDE_HEADINGS.items():
            if head in names:
                return k, m.group(2)
    return None, ""


def _clean_item(key, s):
    s = re.sub(r"[\x00-\x1f]", " ", s or "")
    s = re.sub(r"\s+", " ", s).strip().strip(".;,").strip()
    if len(s) < 2 or len(s) > 80 or re.match(r"(?i)^page \d+", s):
        return None
    if key == "allowed_contacts":
        compact = re.sub(r"(?<=\d)[\s-](?=\d)", "", s)
        ph = re.search(r"(?<!\d)(?:\+?91)?([6-9]\d{9})(?!\d)", compact)
        if ph:
            return ph.group(1)
        em = re.search(r"[^@\s]+@[^@\s]+\.[A-Za-z]{2,}", s)
        return em.group(0).lower() if em else None
    return s


def _category_of(label):
    t = label.lower()
    if "penthouse" in t:
        return "penthouse"
    if re.search(r"row[\s-]?house", t):
        return "row_house"
    if "villa" in t:
        return "villa"
    if "bungalow" in t:
        return "bungalow"
    if "plot" in t:
        return "plot"
    if re.search(r"apartment|flat|\bbhk\b|\brk\b", t):
        return "apartment"
    return None


def _project_key(line):
    m = _KV.match(line)
    if not m:
        return None, ""
    head = re.sub(r"\s+", " ", m.group(1)).strip().lower()
    for k, names in PROJECT_KEYS.items():
        if head in names:
            return k, m.group(2).strip()
    return None, ""


def _unit_line(line):
    """'2 BHK Apartment: Price 1.3 Cr; Carpet 720 sq ft; Bathrooms 2' -> (unit dict, skipped pieces), or None."""
    m = _UNIT.match(line)
    if not m:
        return None
    label = re.sub(r"\s+", " ", m.group(1)).strip()
    cat = _category_of(label)
    if not cat:
        return None
    bm = re.search(r"(\d)\s*bhk", label, re.I)
    unit = {"label": label[:80], "category": cat, "bhk": int(bm.group(1)) if bm else None}
    skipped = []
    for piece in re.split(r"[;|]", m.group(2)):
        p = piece.strip().strip(".")
        if not p:
            continue
        low = p.lower()
        mm = re.match(r"^price\s*[:\-]?\s*(.+)$", low)
        if mm:
            unit["price"] = p[mm.start(1):][:40]
            continue
        got = False
        for key, pat in (("carpet_sqft", r"^carpet(?:\s+area)?\s*[:\-]?\s*([\d,\.]+)"),
                         ("builtup_sqft", r"^built[\s-]?up(?:\s+area)?\s*[:\-]?\s*([\d,\.]+)"),
                         ("plot_sqft", r"^plot(?:\s+area)?\s*[:\-]?\s*([\d,\.]+)"),
                         ("bathrooms", r"^(?:bathrooms?|baths?)\s*[:\-]?\s*(\d+)"),
                         ("bathrooms", r"^(\d+)\s*(?:bathrooms?|baths?)\b"),
                         ("balconies", r"^(?:balconies|balcony)\s*[:\-]?\s*(\d+)"),
                         ("balconies", r"^(\d+)\s*(?:balconies|balcony)\b"),
                         ("parking", r"^parking(?:\s+spaces?)?\s*[:\-]?\s*(\d+)"),
                         ("parking", r"^(\d+)\s*parking\b")):
            mm = re.match(pat, low)
            if mm:
                unit[key] = mm.group(1).replace(",", "")
                got = True
                break
        if got:
            continue
        for key, pat in (("facing", r"^facing\s*[:\-]?\s*(.+)$"), ("floor_range", r"^floors?(?:\s+range)?\s*[:\-]?\s*(.+)$"),
                         ("dimensions", r"^dimensions?\s*[:\-]?\s*(.+)$"),
                         ("permitted_use", r"^(?:permitted\s+use|use)\s*[:\-]?\s*(.+)$")):
            mm = re.match(pat, low)
            if mm:
                unit[key] = p[mm.start(1):][:60]
                got = True
                break
        if not got:
            skipped.append(p[:60])
    if "price" not in unit:
        return None
    return unit, skipped


def _poss_norm(raw):
    raw = (raw or "").strip()
    m = re.fullmatch(r"(20\d\d)-(0[1-9]|1[0-2])", raw)
    if m:
        return raw
    if re.search(r"[A-Za-z]{3}[a-z]*\s+20\d\d", raw):
        return RE._parse_poss(raw)
    return None


def _is_project_line(line):
    return bool(_PROJ_START.match(line) or _project_key(line)[0] or _unit_line(line))


def parse_guide(text):
    """Reads a brand guide made of plain headings (rules) and 'Project:' blocks (projects, prices, areas).
    No guessing: only recognised lines are taken, unrecognised lines inside a project are listed, and the
    builder confirms everything before it is saved."""
    out = {k: [] for k in GUIDE_HEADINGS}
    projects = []
    curp = None

    def add(key, raw):
        v = _clean_item(key, raw)
        if v and v.lower() not in [x.lower() for x in out[key]] and len(out[key]) < 100:
            out[key].append(v)

    cur = None
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        pm = _PROJ_START.match(line)
        if pm:
            curp = {"name": re.sub(r"\s+", " ", pm.group(1)).strip()[:120], "short": "", "city": "", "locality": "",
                    "rera": "", "possession": "", "ready": "", "booking": "", "aliases": [], "units": [],
                    "skipped": [], "notes": []}
            if len(projects) < 20:
                projects.append(curp)
            cur = None
            continue
        key, inline = _heading_key(line)
        if key:
            cur, curp = key, None
            for part in re.split(r"[;,]", inline):
                add(cur, part)
            continue
        if curp is not None:
            pk, val = _project_key(line)
            if pk:
                if pk == "aliases":
                    curp["aliases"] += [a.strip()[:80] for a in re.split(r"[;,]", val) if a.strip()]
                elif pk == "possession":
                    norm = _poss_norm(val)
                    if norm:
                        curp["possession"] = norm
                    else:
                        curp["notes"].append(f'Possession "{val[:40]}" needs a month and year, for example December 2028.')
                elif pk == "ready":
                    v = val.strip().lower()
                    if v in ("yes", "no"):
                        curp["ready"] = v
                    else:
                        curp["notes"].append(f'Ready to move "{val[:20]}" must be yes or no.')
                else:
                    curp[pk] = val.strip()[:120]
                continue
            ul = _unit_line(line)
            if ul:
                unit, sk = ul
                curp["units"].append(unit)
                curp["skipped"] += [f'{unit["label"]}: {s}' for s in sk]
                continue
        unknown_heading = (line.endswith(":") and len(line) <= 60) or (line.isupper() and len(line) > 3)
        if unknown_heading:
            cur, curp = None, None
            continue
        if curp is not None:
            if len(curp["skipped"]) < 8:
                curp["skipped"].append(line[:90])
            continue
        if _is_project_line(line):
            continue
        if cur and (_BULLET.match(line) or len(line) <= 80):
            for part in _BULLET.sub("", line).split(";"):
                add(cur, part)
    out["projects"] = projects
    return out


def _s(v, n=120):
    return re.sub(r"\s+", " ", re.sub(r"[\x00-\x1f]", " ", v)).strip()[:n] if isinstance(v, str) else ""


def _norm_projects(raw):
    """Rebuilds the project list from posted JSON, keeping only known text fields."""
    out = []
    for p in (raw if isinstance(raw, list) else [])[:20]:
        if not isinstance(p, dict) or not _s(p.get("name")):
            continue
        pr = {k: _s(p.get(k)) for k in ("name", "short", "city", "locality", "rera", "possession", "ready", "booking")}
        pr["aliases"] = [_s(a, 80) for a in (p.get("aliases") or [])[:20] if _s(a, 80)] if isinstance(p.get("aliases"), list) else []
        pr["units"] = []
        for un in (p.get("units") or [])[:30] if isinstance(p.get("units"), list) else []:
            if not isinstance(un, dict) or un.get("category") not in RE.CATEGORIES or not _s(un.get("label"), 80):
                continue
            nu = {"label": _s(un.get("label"), 80), "category": un["category"],
                  "bhk": un.get("bhk") if isinstance(un.get("bhk"), int) and 1 <= un["bhk"] <= 9 else None}
            for k in ("price", "carpet_sqft", "builtup_sqft", "plot_sqft", "bathrooms", "balconies", "parking",
                      "facing", "floor_range", "dimensions", "permitted_use"):
                if _s(un.get(k), 60):
                    nu[k] = _s(un.get(k), 60)
            pr["units"].append(nu)
        out.append(pr)
    return out


def _price_text(raw):
    v = parse_price(raw or "")
    return fmt_money(v) if v else "could not read"


@app.get("/admin/guide", response_class=HTMLResponse)
def guide_form(request: Request, err: str = ""):
    u = admin_only(request)
    if not u:
        return RedirectResponse("/", 303)
    items_html = "".join("<li><b>" + e(GUIDE_LABEL[k]) + '</b> <span class="muted">(heading, for example: '
                         + e(GUIDE_HEADINGS[k][0].title()) + ")</span></li>" for k in GUIDE_HEADINGS)
    example = ("Project: Demo Lakeview\nCity: Pune\nLocality: Baner\nRERA: P44444444444\nPossession: June 2029\n"
               "Ready to move: No\nBooking amount: 6 lakh\nOther names: Lakeview; Lake View\n"
               "2 BHK Apartment: Price 1.05 Cr; Carpet 640 sq ft; Built-up 790 sq ft; Bathrooms 2; Balconies 2; Parking 1")
    help_ = ('<p class="muted">BrandGuard reads two kinds of content, then shows you everything it found before anything is saved.</p>'
             '<p style="margin-bottom:4px"><b>1. Rules</b> <span class="muted">(a heading, then one item per line)</span></p>'
             "<ul style='margin:0 0 12px;padding-left:20px'>" + items_html + "</ul>"
             '<p style="margin-bottom:4px"><b>2. Projects, prices and facts</b> <span class="muted">(one property type per line)</span></p>'
             f'<pre class="mono" style="white-space:pre-wrap;background:#f7f9fc;border:1px solid var(--line);border-radius:7px;padding:12px;margin:0 0 8px">{e(example)}</pre>'
             '<p class="muted" style="margin:0">Keep each property type on one line, not in a table. Property types can be Apartment, '
             'Penthouse, Villa, Bungalow, Row house or Plot. Scanned images are not supported. A new project is not visible to '
             'any partner until you grant access on the Project Access page.</p>')
    form = ('<form method="post" action="/admin/guide/preview" enctype="multipart/form-data" data-lock>'
            '<label for="gf">Brand guideline document (PDF or TXT)</label>'
            '<input id="gf" type="file" name="file" accept=".pdf,.txt" required>'
            '<p class="hint">Up to 10 MB. Nothing is saved until you confirm the list on the next screen.</p>'
            f'<button class="btn" type="submit">{ui.icon("upload", 16)}Read document</button></form>')
    body = (ui.page_header("Import from a Document",
                           f"Upload your brand guide and BrandGuard turns it into rules, projects and approved prices for {e(load_reg(u).get('brand', ''))}.",
                           '<a class="btn secondary" href="/admin/rules">Back to Brand Rules</a>')
            + '<div class="stack">' + (ui.alert(e(err), "bad") if err else "")
            + ui.card("Upload", form) + ui.card("What the document should look like", help_) + "</div>")
    return page("Import", body, u, "rules", [("Brand Rules", "/admin/rules"), ("Import", None)], request)


@app.post("/admin/guide/preview", response_class=HTMLResponse)
def guide_preview(request: Request, file: UploadFile = File(...)):
    u = admin_only(request)
    if not u:
        return RedirectResponse("/", 303)
    name = (file.filename or "document")[:120]
    if not name.lower().endswith((".pdf", ".txt")):
        return guide_form(request, err="Upload a PDF or a TXT file.")
    data = file.file.read(10 * 1024 * 1024 + 1)
    if len(data) > 10 * 1024 * 1024:
        return guide_form(request, err="This file is larger than 10 MB.")
    try:
        found = parse_guide(pdf_text(data, name))
    except Exception as ex_:
        msg = str(ex_) if isinstance(ex_, ValueError) else "This file could not be read. Try exporting it as a PDF again."
        return guide_form(request, err=msg)
    reg = load_reg(u)
    projects = [p for p in found["projects"] if p["units"] or p["city"] or p["rera"] or p["possession"] or p["booking"]]
    total = sum(len(found[k]) for k in GUIDE_HEADINGS) + len(projects)
    if not total:
        return guide_form(request, err="Nothing was found. Check that the document has headings such as "
                                       "\"Banned phrases\", or blocks that start with \"Project: Name\", with the details on separate lines.")
    cards = []
    for key in GUIDE_HEADINGS:
        items = found[key]
        if not items:
            continue
        have = [x.lower() for x in reg.get(key, [])]
        boxes = ""
        for it in items:
            dup = it.lower() in have
            state = " disabled" if dup else " checked"
            note = ' <span class="muted">(already in your rules)</span>' if dup else ""
            boxes += (f'<label class="check"><input type="checkbox" name="{key}" value="{e(it)}"{state}> '
                      f'{e(it)}{note}</label>')
        cards.append(ui.card(f"{GUIDE_LABEL[key]} ({len(items)} found)", boxes))
    existing = {p["official_name"].lower(): p for p in RE.brand_projects(u["brand_id"], active_only=False)}
    for i, p in enumerate(projects):
        ex_p = existing.get(p["name"].lower())
        state = ui.badge("Already exists: values will be updated", "info", "info") if ex_p else ui.badge("New project", "ok", "plus")
        det = [("City", p["city"]), ("Locality", p["locality"]), ("RERA number", p["rera"]),
               ("Possession", p["possession"]), ("Ready to move", p["ready"]),
               ("Booking amount", _price_text(p["booking"]) if p["booking"] else ""),
               ("Other names", ", ".join(p["aliases"]))]
        dl = "".join(f"<dt>{e(k)}</dt><dd>{e(v)}</dd>" for k, v in det if v)
        rows = []
        for un in p["units"]:
            rows.append([e(un["label"]), e(RE.CATEGORIES[un["category"]][0]),
                         f'{e(un["price"])}<br><span class="muted">reads as {e(_price_text(un["price"]))}</span>',
                         e(un.get("carpet_sqft") or un.get("plot_sqft") or "-"), e(un.get("builtup_sqft") or "-"),
                         e(un.get("bathrooms") or "-"), e(un.get("balconies") or "-"), e(un.get("parking") or "-")])
        tbl = (ui.table(["Property type", "Category", "Price", "Carpet / plot sq ft", "Built-up sq ft", "Bathrooms", "Balconies", "Parking"],
                        rows, "Property types in " + p["name"]) if rows else ui.empty("No property types found for this project"))
        warn = ""
        if p["notes"] or p["skipped"]:
            lines_ = "".join(f"<li>{e(x)}</li>" for x in (p["notes"] + p["skipped"])[:12])
            warn = ui.alert("<b>Not understood, so skipped:</b><ul style='margin:6px 0 0;padding-left:18px'>" + lines_ + "</ul>", "warn")
        pick = (f'<label class="check"><input type="checkbox" name="proj" value="{i}" checked> '
                f'<b>Add this project and its prices</b></label>')
        cards.append(ui.card(p["name"], f'<p>{state}</p>{pick}<dl class="kv" style="margin:10px 0 14px">{dl}</dl>{tbl}{warn}',
                             "Check that each price reads as the amount you expect (lakh versus crore)."))
    payload = e(json.dumps(projects, ensure_ascii=False))
    form = (f'<form method="post" action="/admin/guide/apply" data-lock><input type="hidden" name="title" value="{e(name)}">'
            f'<input type="hidden" name="payload" value="{payload}">'
            + "".join(cards)
            + f'<div class="form-actions" style="margin-top:16px"><button class="btn" type="submit">{ui.icon("check", 16)}Save selected</button>'
              '<a class="btn secondary" href="/admin/guide">Cancel</a></div></form>')
    body = (ui.page_header("Check what was found", f"From {e(name)}. Untick anything that should not be saved.")
            + '<div class="stack">' + ui.alert("Nothing is saved yet. Rules and prices apply to new submissions only. "
                                                "Changing an approved price creates a new version and flags earlier approvals for re-check.", "info")
            + form + "</div>")
    return page("Import", body, u, "rules", [("Brand Rules", "/admin/rules"), ("Import", None)], request)


def _import_fact(u, p, key, uid, raw, title, stats, warns, label):
    """Saves one fact. Unchanged values are skipped, so re-importing never creates empty versions."""
    try:
        num, txt = parse_fact_value(key, raw)
        state, cur, _d = RE.resolve_fact(p["id"], key, uid)
        if state == "ok" and cur is not None:
            same = (abs((cur["value_num"] or 0) - num) < 1e-6) if num is not None else (cur["value_text"] == txt)
            if same:
                stats["unchanged"] += 1
                return
        _save_fact(u, p, key, uid, raw, title, "Imported from brand guide", "", "")
        stats["facts"] += 1
    except ValueError as ex_:
        warns.append(f"{label}: {RE.FACT_LABEL.get(key, key)} not saved. {ex_}")


def _import_project(u, pr, title, stats, warns):
    existing = next((p for p in RE.brand_projects(u["brand_id"], active_only=False)
                     if p["official_name"].lower() == pr["name"].lower()), None)
    if existing:
        pid = existing["id"]
        ex("UPDATE projects SET city=?, locality=?, short_name=? WHERE id=?",
           (pr["city"] or existing["city"], pr["locality"] or existing["locality"], pr["short"] or existing["short_name"], pid))
    else:
        pid = RE.add_project(u["brand_id"], pr["name"], pr["short"], pr["city"], pr["locality"], "", [], u["name"])
        log(None, u["name"], "PROJECT_ADDED", pr["name"] + " (from brand guide)", u["brand_id"])
        stats["projects"] += 1
    p = RE.get_project(pid)
    changed_before = stats["facts"] + stats["units"]
    if pr["rera"]:
        r = pr["rera"].strip().upper()
        if not RE.rera_format_ok(r):
            warns.append(f'{pr["name"]}: RERA number "{pr["rera"]}" was skipped. It should look like P followed by 11 digits.')
        elif r != (p["rera_no"] or ""):
            ex("UPDATE projects SET rera_no=?, rera_level='format', rera_source=NULL, rera_checked_at=NULL, rera_checked_by=NULL WHERE id=?", (r, pid))
    have = [a.lower() for a in RE.aliases_of(pid)]
    for a in pr["aliases"]:
        if a.lower() not in have:
            ex("INSERT INTO project_aliases (project_id, alias) VALUES (?,?)", (pid, a))
            have.append(a.lower())
    p = RE.get_project(pid)
    for key, field in (("possession", pr["possession"]), ("ready_to_move", pr["ready"]), ("booking_amount", pr["booking"])):
        if field:
            _import_fact(u, p, key, None, field, title, stats, warns, pr["name"])
    for un in pr["units"]:
        match = None
        for ut in RE.unit_types(pid, active_only=False):
            if (un["bhk"] is not None and ut["category"] == un["category"] and ut["bhk"] == un["bhk"]) \
                    or ut["label"].lower() == un["label"].lower():
                match = ut
                break
        try:
            if not parse_fact_value("price", un["price"])[0]:
                raise ValueError("Enter a price greater than zero.")
        except ValueError as ex_:
            warns.append(f'{pr["name"]} {un["label"]}: skipped. The price could not be read. {ex_}')
            continue
        if match:
            uid = match["id"]
        else:
            bhk = un["bhk"] if "bhk" in RE.CATEGORIES[un["category"]][1] else None
            uid = RE.add_unit_type(pid, un["category"], un["label"], bhk)
            stats["units"] += 1
        label = f'{pr["name"]} {un["label"]}'
        _import_fact(u, p, "price", uid, un["price"], title, stats, warns, label)
        for key in ("carpet_sqft", "builtup_sqft", "plot_sqft", "bathrooms", "balconies", "parking",
                    "facing", "floor_range", "dimensions", "permitted_use"):
            if un.get(key):
                _import_fact(u, p, key, uid, un[key], title, stats, warns, label)
    if existing and stats["facts"] + stats["units"] > changed_before:
        stats["updated"] += 1
    log(None, u["name"], "PROJECT_EDITED", f'{pr["name"]}: details imported from brand guide', u["brand_id"])


@app.post("/admin/guide/apply")
async def guide_apply(request: Request):
    u = admin_only(request)
    if not u:
        return RedirectResponse("/", 303)
    f = await request.form()
    reg = load_reg(u)
    added = {}
    for key in GUIDE_HEADINGS:
        cur = reg.setdefault(key, [])
        have = [x.lower() for x in cur]
        for raw in f.getlist(key)[:100]:
            v = _clean_item(key, raw)
            if v and v.lower() not in have:
                cur.append(v)
                have.append(v.lower())
                added[key] = added.get(key, 0) + 1
    title = (f.get("title") or "document")[:120]
    stats = {"projects": 0, "updated": 0, "units": 0, "facts": 0, "unchanged": 0}
    warns = []
    chosen = [int(i) for i in f.getlist("proj") if str(i).isdigit()]
    try:
        projects = _norm_projects(json.loads((f.get("payload") or "[]")[:300000]))
    except ValueError:
        projects = []
    source_title = "Brand guide: " + title
    for i in chosen:
        if 0 <= i < len(projects):
            _import_project(u, projects[i], source_title, stats, warns)
    if not added and not (stats["projects"] or stats["updated"] or stats["facts"] or stats["units"]):
        request.session["flash"] = ("Nothing new to save. " + (warns[0] if warns else "Everything selected already matched."))
        return RedirectResponse("/admin/rules", 303)
    if added:
        save_reg(u, reg)
    RE.add_source(u["brand_id"], source_title, "brand_guide", "official", u["name"])
    parts = [f"{n} {GUIDE_LABEL[k].lower()}" for k, n in added.items()]
    if stats["projects"]:
        parts.append(f'{stats["projects"]} new project(s)')
    if stats["updated"]:
        parts.append(f'{stats["updated"]} existing project(s) updated')
    if stats["units"]:
        parts.append(f'{stats["units"]} property type(s)')
    if stats["facts"]:
        parts.append(f'{stats["facts"]} approved fact(s) saved')
    log(None, u["name"], "RULES_IMPORTED", f"{title}: " + ", ".join(parts), u["brand_id"])
    msg = "Imported: " + ", ".join(parts) + "."
    if stats["unchanged"]:
        msg += f' {stats["unchanged"]} value(s) were already up to date.'
    if warns:
        msg += f' {len(warns)} item(s) skipped: ' + warns[0]
    request.session["flash"] = msg[:400]
    return RedirectResponse("/admin/projects" if (stats["projects"] or stats["updated"]) else "/admin/rules", 303)


# ============================================================ test audio for judges (public, no sign-in)
AUDIO_DIR = Path(__file__).resolve().parent / "demo_audio"
AUDIO_EXT = (".m4a", ".mp3", ".wav", ".mp4", ".ogg", ".aac", ".webm")
TEST_CLIPS = [
    {"key": "approval", "n": 1, "title": "Approval", "tone": "ok",
     "say": "Demo Heights in Wakad, Pune. A 2 BHK home at 1 crore 30 lakh. Carpet area 720 square feet, with 2 bathrooms. "
            "Possession in December 2028.",
     "result": "Auto-Approved. The price, carpet area, bathrooms and possession all match the approved facts, so an "
               "approval ID is issued with no human needed.",
     "steps": ["Download the audio below.", "Click Enter as Freelancer on the home page.",
               "Open Submit a Reel, choose Demo Developer, and upload the file.",
               "The result page opens. Look at the Claim-by-claim checks table: each spoken claim is matched to an approved fact."]},
    {"key": "rejection", "n": 2, "title": "Rejection", "tone": "bad",
     "say": "Demo Heights in Wakad. 2 BHK for 1 crore 30 lakh. Guaranteed returns, the price will double in two years. "
            "Last chance!",
     "result": "Rejected. The price is correct, but \"guaranteed returns\" and \"price will double\" are banned phrases "
               "(\"last chance\" is also flagged if the sample brand guide has been imported). Each finding shows the "
               "exact second it was spoken, why it matters and what to change.",
     "steps": ["Download the audio below.", "Enter as Freelancer and open Submit a Reel.",
               "Choose Demo Developer and upload the file.",
               "Read the findings on the result page. The creator is told exactly what to fix."]},
    {"key": "dispute", "n": 3, "title": "Dispute", "tone": "warn",
     "say": "Demo Heights, Wakad. 3 BHK flats available at 1 crore 50 lakh. Possession in December 2028.",
     "result": "Rejected, because 3 BHK is approved at 1 crore 90 lakh, not 1 crore 50 lakh. You then dispute it and "
               "play the builder to resolve it. This shows that a person always has the final word.",
     "steps": ["Download the audio below, then Enter as Freelancer, open Submit a Reel, choose Demo Developer and upload it.",
               "The submission is Rejected for a price mismatch. Click Raise a dispute.",
               "Write why the finding is wrong (for example: \"I quoted the offer price for a limited floor\"). "
               "Optionally type what you actually said. Click Submit dispute. The status becomes Disputed.",
               "In the sidebar, switch the demo role to Builder. Open Review Queue, then open the disputed submission.",
               "The builder sees the evidence and the creator's explanation. Click Overturn decision to approve it "
               "(an approval ID is issued), or Uphold rejection to keep it rejected (a reason is required).",
               "Switch back to Freelancer to see the outcome on the submission, and open Audit Trail as Builder to see "
               "every step recorded with who did it and when."]},
]


def _clip_file(key):
    for ext in AUDIO_EXT:
        p = AUDIO_DIR / f"{key}{ext}"
        if p.is_file():
            return p
    return None


@app.get("/test-audio", response_class=HTMLResponse)
def test_audio_page(request: Request):
    u = me(request)
    cards = []
    for c in TEST_CLIPS:
        f = _clip_file(c["key"])
        if f:
            media = (f'<audio controls preload="none" style="width:100%;margin:8px 0 12px" src="/test-audio/file/{c["key"]}?inline=1">'
                     f'Your browser cannot play audio.</audio>'
                     f'<a class="btn" href="/test-audio/file/{c["key"]}" download>{ui.icon("upload", 16)}Download {e(c["title"])} audio</a>')
        else:
            media = ui.alert("This audio file has not been added yet.", "warn")
        steps = "".join(f"<li>{e(s)}</li>" for s in c["steps"])
        inner = (f'<p class="muted" style="margin-bottom:4px">What is said in the clip</p>'
                 f'<p style="margin-top:0"><i>"{e(c["say"])}"</i></p>{media}'
                 f'<h3 class="sec-title">What to do</h3><ol style="margin:0 0 12px;padding-left:20px">{steps}</ol>'
                 f'<h3 class="sec-title">What you should see</h3><p style="margin:0">{e(c["result"])}</p>')
        cards.append(ui.card(f'{c["n"]}. {c["title"]} audio', inner, cls=""))
    guide = AUDIO_DIR / "Demo_Developer_Brand_Guide.pdf"
    extra = ""
    if guide.is_file():
        extra = ui.card("Optional: sample brand guide",
                        '<p class="muted">As Builder, open Brand Rules and click Import from PDF, then upload this file. '
                        'BrandGuard lists the rules it found, you confirm them, and they apply to new submissions straight away.</p>'
                        '<a class="btn secondary" href="/test-audio/file/guide" download>Download sample brand guide (PDF)</a>')
    start = ('<a class="btn" href="/enter/freelancer">Enter as Freelancer</a> '
             '<a class="btn secondary" href="/enter/admin">Enter as Builder</a>') if not u else ""
    body = (ui.page_header("Test Audio for Judges",
                           "Three short clips to test the main workflow: one approved, one rejected, one disputed. "
                           "No sign-up is needed. Use the demo roles in the sidebar or the buttons below.", start)
            + '<div class="stack">' + "".join(cards) + extra
            + ui.alert("These recordings are made for this demo. The company, projects and prices are fictional.", "info") + "</div>")
    if u:
        return page("Test Audio", body, u, "testaudio", [("Test Audio", None)], request)
    return page("Test Audio", body)


@app.get("/test-audio/file/{key}")
def test_audio_file(key: str, inline: int = 0):
    if key == "guide":
        p = AUDIO_DIR / "Demo_Developer_Brand_Guide.pdf"
        name = "Demo_Developer_Brand_Guide.pdf"
    else:
        clip = next((c for c in TEST_CLIPS if c["key"] == key), None)
        p = _clip_file(key) if clip else None
        name = f'BrandGuard_Test_{clip["n"]}_{clip["title"]}{p.suffix}' if p else ""
    if not p or not p.is_file():
        return HTMLResponse("File not found.", status_code=404)
    return FileResponse(str(p), filename=name, content_disposition_type="inline" if inline else "attachment")
