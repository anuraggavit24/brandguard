"""BrandGuard real-estate domain layer.

Projects, unit types, versioned facts, access grants, project identification and claim validators.
Pure logic plus SQLite access. No HTML here. The shared platform parts (users, submissions, audit,
decisions) stay in main.py.

Verdicts per claim: VERIFIED, VIOLATION, UNVERIFIABLE, REVIEW, INCOMPLETE, NA.
"""

import json
import re
import sqlite3
import unicodedata
from datetime import date, datetime, timedelta

from engine import classify_price, extract_prices, fmt_money, norm
import phon

POLICY_VERSION = "policy-2026.10-r2"
DB_PATH = None

VERIFIED, VIOLATION, UNVERIFIABLE, REVIEW, INCOMPLETE, NA = (
    "VERIFIED", "VIOLATION", "UNVERIFIABLE", "REVIEW", "INCOMPLETE", "NA")

# property categories -> which facts make sense for each (no forced BHK or tower fields)
CATEGORIES = {
    "apartment": ("Apartment / flat", ["bhk", "carpet_sqft", "builtup_sqft", "bathrooms", "balconies", "parking", "floor_range", "facing"]),
    "penthouse": ("Penthouse", ["bhk", "carpet_sqft", "builtup_sqft", "bathrooms", "balconies", "parking", "floor_range"]),
    "villa": ("Villa", ["bhk", "plot_sqft", "builtup_sqft", "bathrooms", "parking"]),
    "bungalow": ("Bungalow", ["plot_sqft", "builtup_sqft", "bathrooms", "parking"]),
    "row_house": ("Row house", ["bhk", "plot_sqft", "builtup_sqft", "bathrooms", "parking"]),
    "plot": ("Residential plot", ["plot_sqft", "dimensions", "permitted_use"]),
    "product": ("Product or variant", []),      # any other industry: a car model, a loan plan, a pack size
}
FIELD_LABEL = {
    "bhk": "BHK (number)", "carpet_sqft": "Carpet area (sq ft)", "builtup_sqft": "Built-up area (sq ft)",
    "plot_sqft": "Plot area (sq ft)", "bathrooms": "Bathrooms", "balconies": "Balconies", "parking": "Parking spaces",
    "floor_range": "Floor range", "facing": "Facing", "dimensions": "Dimensions", "permitted_use": "Permitted use",
}
NUMERIC_FIELDS = {"carpet_sqft", "builtup_sqft", "plot_sqft", "bathrooms", "balconies", "parking"}
FACT_LABEL = {
    "price": "Price", "booking_amount": "Booking amount", "carpet_sqft": "Carpet area", "builtup_sqft": "Built-up area",
    "plot_sqft": "Plot area", "bathrooms": "Bathrooms", "balconies": "Balconies", "parking": "Parking",
    "possession": "Possession", "ready_to_move": "Ready to move", "floor_range": "Floor range", "facing": "Facing",
    "dimensions": "Dimensions", "permitted_use": "Permitted use",
}
OFFER_TAGS = {
    "zero_gst": ("Zero GST", ["zero gst", "no gst", "gst free", "gst-free", "0% gst", "जीएसटी माफ", "जीएसटी नाही", "जीएसटी नहीं"]),
    "free_parking": ("Free parking", ["free parking", "parking free", "मोफत पार्किंग", "फ्री पार्किंग", "पार्किंग फ्री"]),
    "stamp_duty": ("Stamp duty waiver", ["stamp duty waiver", "no stamp duty", "zero stamp duty", "स्टॅम्प ड्युटी माफ", "स्टाम्प ड्यूटी माफ"]),
    "discount": ("Discount", ["% off", "percent off", "discount", "डिस्काउंट", "सूट", "सवलत"]),
}
MONTHS = {m: i + 1 for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"])}


# ------------------------------------------------------------------ database
def setup(db_path):
    global DB_PATH
    DB_PATH = db_path
    con = sqlite3.connect(DB_PATH)
    con.executescript("""
    CREATE TABLE IF NOT EXISTS projects (
        id INTEGER PRIMARY KEY AUTOINCREMENT, brand_id INTEGER NOT NULL, official_name TEXT NOT NULL,
        short_name TEXT, city TEXT, locality TEXT, rera_no TEXT, rera_level TEXT DEFAULT 'none',
        rera_source TEXT, rera_checked_at TEXT, rera_checked_by TEXT,
        active INTEGER DEFAULT 1, created_at TEXT);
    CREATE INDEX IF NOT EXISTS ix_projects_brand ON projects(brand_id);
    CREATE TABLE IF NOT EXISTS project_aliases (
        id INTEGER PRIMARY KEY AUTOINCREMENT, project_id INTEGER NOT NULL, alias TEXT NOT NULL, lang TEXT DEFAULT 'any');
    CREATE INDEX IF NOT EXISTS ix_alias_project ON project_aliases(project_id);
    CREATE TABLE IF NOT EXISTS unit_types (
        id INTEGER PRIMARY KEY AUTOINCREMENT, project_id INTEGER NOT NULL, category TEXT NOT NULL,
        label TEXT NOT NULL, bhk INTEGER, active INTEGER DEFAULT 1);
    CREATE INDEX IF NOT EXISTS ix_unit_project ON unit_types(project_id);
    CREATE TABLE IF NOT EXISTS sources (
        id INTEGER PRIMARY KEY AUTOINCREMENT, brand_id INTEGER NOT NULL, title TEXT, kind TEXT,
        trust TEXT DEFAULT 'official', verified_at TEXT, added_by TEXT);
    CREATE TABLE IF NOT EXISTS facts (
        id INTEGER PRIMARY KEY AUTOINCREMENT, project_id INTEGER NOT NULL, unit_type_id INTEGER,
        key TEXT NOT NULL, value_num REAL, value_text TEXT, unit TEXT, source_id INTEGER,
        status TEXT DEFAULT 'verified', valid_from TEXT, valid_to TEXT, author TEXT, approver TEXT,
        reason TEXT, supersedes_id INTEGER, created_at TEXT);
    CREATE INDEX IF NOT EXISTS ix_facts_lookup ON facts(project_id, key, unit_type_id);
    CREATE TABLE IF NOT EXISTS grants (
        id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, brand_id INTEGER NOT NULL,
        project_id INTEGER NOT NULL, actions TEXT DEFAULT 'submit', starts TEXT, expires TEXT,
        granted_by TEXT, granted_at TEXT, revoked_at TEXT, revoked_by TEXT);
    CREATE INDEX IF NOT EXISTS ix_grants_user ON grants(user_id, project_id);
    CREATE TABLE IF NOT EXISTS submission_projects (
        id INTEGER PRIMARY KEY AUTOINCREMENT, sub_id INTEGER NOT NULL, project_id INTEGER NOT NULL,
        identity_state TEXT, evidence TEXT, confirmed_by TEXT);
    CREATE INDEX IF NOT EXISTS ix_subproj ON submission_projects(sub_id);
    CREATE TABLE IF NOT EXISTS fact_flags (
        id INTEGER PRIMARY KEY AUTOINCREMENT, sub_id INTEGER NOT NULL, fact_id INTEGER, flagged_at TEXT,
        reason TEXT, resolved INTEGER DEFAULT 0);
    """)
    con.commit()
    con.close()


def _q(sql, args=()):
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    try:
        return con.execute(sql, args).fetchall()
    finally:
        con.close()


def _ex(sql, args=()):
    con = sqlite3.connect(DB_PATH)
    try:
        cur = con.execute(sql, args)
        con.commit()
        return cur.lastrowid
    finally:
        con.close()


def today():
    return date.today().isoformat()


def now():
    return datetime.now().strftime("%Y-%m-%d %H:%M")


# ------------------------------------------------------------------ projects
def get_project(pid):
    r = _q("SELECT * FROM projects WHERE id=?", (pid,))
    return r[0] if r else None


def brand_projects(brand_id, active_only=True):
    sql = "SELECT * FROM projects WHERE brand_id=?" + (" AND active=1" if active_only else "") + " ORDER BY official_name"
    return _q(sql, (brand_id,))


def aliases_of(pid):
    return [r["alias"] for r in _q("SELECT alias FROM project_aliases WHERE project_id=? ORDER BY id", (pid,))]


def names_of(p):
    out = [p["official_name"]]
    if p["short_name"]:
        out.append(p["short_name"])
    out += aliases_of(p["id"])
    seen, res = set(), []
    for n in out:
        k = _fold(n)
        if k and k not in seen:
            seen.add(k)
            res.append(n.strip())
    return res


def add_project(brand_id, official_name, short_name="", city="", locality="", rera_no="", aliases=(), actor=""):
    rera_no = (rera_no or "").strip().upper()
    pid = _ex("""INSERT INTO projects (brand_id, official_name, short_name, city, locality, rera_no, rera_level, created_at)
                 VALUES (?,?,?,?,?,?,?,?)""",
              (brand_id, official_name.strip(), short_name.strip(), city.strip(), locality.strip(), rera_no,
               "format" if rera_format_ok(rera_no) else "none", now()))
    for a in aliases:
        if a.strip():
            _ex("INSERT INTO project_aliases (project_id, alias) VALUES (?,?)", (pid, a.strip()))
    return pid


def add_source(brand_id, title, kind="price_sheet", trust="official", actor=""):
    return _ex("INSERT INTO sources (brand_id, title, kind, trust, verified_at, added_by) VALUES (?,?,?,?,?,?)",
               (brand_id, title.strip()[:200], kind, trust, today(), actor))


def unit_types(pid, active_only=True):
    sql = "SELECT * FROM unit_types WHERE project_id=?" + (" AND active=1" if active_only else "") + " ORDER BY category, bhk, label"
    return _q(sql, (pid,))


def add_unit_type(pid, category, label, bhk=None):
    if category not in CATEGORIES:
        raise ValueError("Unknown property category.")
    allowed = CATEGORIES[category][1]
    if bhk is not None and "bhk" not in allowed:
        raise ValueError(f"{CATEGORIES[category][0]} does not use a BHK number.")
    return _ex("INSERT INTO unit_types (project_id, category, label, bhk) VALUES (?,?,?,?)",
               (pid, category, label.strip()[:80], bhk))


# --------------------------------------------------------------------- facts
def _is_current(f, on=None):
    on = on or today()
    return (f["status"] == "verified" and (not f["valid_from"] or f["valid_from"] <= on)
            and (not f["valid_to"] or f["valid_to"] >= on))


def facts_for(pid, key, unit_type_id=None):
    if unit_type_id is None:
        return _q("SELECT * FROM facts WHERE project_id=? AND key=? AND unit_type_id IS NULL ORDER BY id", (pid, key))
    return _q("SELECT * FROM facts WHERE project_id=? AND key=? AND unit_type_id=? ORDER BY id", (pid, key, unit_type_id))


def resolve_fact(pid, key, unit_type_id=None):
    """Returns (state, fact_row_or_None, detail). state: ok | missing | expired | conflict | unverified."""
    rows = facts_for(pid, key, unit_type_id)
    if not rows:
        return "missing", None, "No approved value is stored."
    cur = [f for f in rows if _is_current(f)]
    if len(cur) == 1:
        return "ok", cur[0], ""
    if len(cur) > 1:
        vals = {(f["value_num"], f["value_text"]) for f in cur}
        if len(vals) > 1:
            return "conflict", cur[0], "Two current approved values disagree."
        return "ok", cur[-1], ""
    if any(f["status"] != "verified" for f in rows):
        return "unverified", rows[-1], "The stored value is not verified yet."
    last = max(rows, key=lambda f: (f["valid_to"] or "9999", f["id"]))
    return "expired", last, f"The approved value expired on {last['valid_to']}."


def set_fact(pid, key, value_num=None, value_text=None, unit_type_id=None, unit="", source_id=None,
             valid_from=None, valid_to=None, actor="", reason="", status="verified"):
    """Create a new fact version. Any current version for the same scope is closed, never edited."""
    valid_from = valid_from or today()
    prev = [f for f in facts_for(pid, key, unit_type_id) if _is_current(f) and f["valid_to"] in (None, "")]
    prev_id = None
    superseded = []
    if key.startswith("offer:") or key.startswith("landmark:"):
        pass
    if status == "verified":
        for f in prev:
            end = (date.fromisoformat(valid_from) - timedelta(days=1)).isoformat()
            _ex("UPDATE facts SET valid_to=? WHERE id=?", (end, f["id"]))
            prev_id = f["id"]
            superseded.append(f["id"])
    fid = _ex("""INSERT INTO facts (project_id, unit_type_id, key, value_num, value_text, unit, source_id, status,
                 valid_from, valid_to, author, approver, reason, supersedes_id, created_at)
                 VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
              (pid, unit_type_id, key, value_num, value_text, unit, source_id, status, valid_from, valid_to,
               actor, actor if status == "verified" else None, reason, prev_id, now()))
    for old in superseded:
        flag_affected(old, f"{FACT_LABEL.get(key, key)} was changed on {today()}")
    return fid, superseded


def end_fact(fact_id, actor=""):
    f = _q("SELECT * FROM facts WHERE id=?", (fact_id,))
    if not f:
        return
    _ex("UPDATE facts SET valid_to=? WHERE id=?", ((date.today() - timedelta(days=1)).isoformat(), fact_id))
    flag_affected(fact_id, f"{FACT_LABEL.get(f[0]['key'], f[0]['key'])} was withdrawn on {today()}")


def flag_affected(old_fact_id, reason):
    """Flag approvals that relied on a fact version that is no longer current. History is not rewritten."""
    rows = _q("SELECT id, report FROM submissions WHERE approval_id IS NOT NULL")
    for r in rows:
        try:
            used = json.loads(r["report"] or "{}").get("facts_used", [])
        except ValueError:
            continue
        if old_fact_id in [u.get("id") for u in used]:
            if not _q("SELECT 1 FROM fact_flags WHERE sub_id=? AND fact_id=? AND resolved=0", (r["id"], old_fact_id)):
                _ex("INSERT INTO fact_flags (sub_id, fact_id, flagged_at, reason) VALUES (?,?,?,?)",
                    (r["id"], old_fact_id, now(), reason))


def fact_display(f):
    if f["value_num"] is not None:
        v = f["value_num"]
        if f["key"] in ("price", "booking_amount") or f["unit"] == "INR":
            return fmt_money(v)
        if f["unit"] == "%":
            return f"{v:g}%"
        return f"{v:g}" + (f" {f['unit']}" if f["unit"] else "")
    return f["value_text"] or ""


def unit_facts(pid, unit_id):
    """Current verified facts for one unit type, as {key: row}."""
    out = {}
    for f in _q("SELECT * FROM facts WHERE project_id=? AND unit_type_id=? ORDER BY id", (pid, unit_id)):
        if _is_current(f):
            out[f["key"]] = f
    return out


# --------------------------------------------------------------------- access
def _grant_active(g, on=None):
    on = on or today()
    return (not g["revoked_at"] and (not g["starts"] or g["starts"] <= on)
            and (not g["expires"] or g["expires"] >= on) and "submit" in (g["actions"] or ""))


def grant(user_id, brand_id, project_id, actor, expires=None, starts=None):
    p = get_project(project_id)
    if not p or p["brand_id"] != brand_id:
        raise ValueError("That project does not belong to this company.")
    for g in _q("SELECT * FROM grants WHERE user_id=? AND project_id=? AND revoked_at IS NULL", (user_id, project_id)):
        if _grant_active(g):
            return g["id"]
    return _ex("""INSERT INTO grants (user_id, brand_id, project_id, actions, starts, expires, granted_by, granted_at)
                  VALUES (?,?,?,?,?,?,?,?)""",
               (user_id, brand_id, project_id, "submit", starts or today(), expires or None, actor, now()))


def revoke(grant_id, brand_id, actor):
    g = _q("SELECT * FROM grants WHERE id=?", (grant_id,))
    if not g or g[0]["brand_id"] != brand_id:
        return False
    _ex("UPDATE grants SET revoked_at=?, revoked_by=? WHERE id=? AND revoked_at IS NULL", (now(), actor, grant_id))
    return True


def authorized_projects(user_id, brand_id):
    """Projects this user may submit content for right now. Enforced in every backend route."""
    out = []
    for g in _q("SELECT * FROM grants WHERE user_id=? AND brand_id=?", (user_id, brand_id)):
        if _grant_active(g):
            p = get_project(g["project_id"])
            if p and p["active"] and p["id"] not in [x["id"] for x in out]:
                out.append(p)
    return sorted(out, key=lambda p: p["official_name"])


def can_use_project(user_id, project_id):
    p = get_project(project_id)
    return bool(p) and any(x["id"] == project_id for x in authorized_projects(user_id, p["brand_id"]))


# ----------------------------------------------------------- identification
def _fold(s):
    s = unicodedata.normalize("NFKC", norm(s or "")).casefold()
    s = re.sub(r"[^\w\s\u0900-\u097F]", " ", s)   # keep Devanagari vowel signs (Python does not treat them as word characters)
    s = re.sub(r"[\u0964\u0965]", " ", s)            # danda punctuation
    return re.sub(r"\s+", " ", s).strip()


def rera_format_ok(s):
    return bool(re.fullmatch(r"P\d{11}", (s or "").strip().upper()))


def _contains(text_folded, name_folded):
    if not name_folded:
        return False
    return re.search(r"(?<!\w)" + re.escape(name_folded) + r"(?!\w)", text_folded) is not None


def _product_confirmed(p, e, joined):
    if any(_fold(n) == _fold(p["official_name"]) for n in e["names"]) and len(_fold(p["official_name"])) >= 6:
        return True
    return any(len(_fold(u["label"])) >= 2 and _contains(joined, _fold(u["label"])) for u in unit_types(p["id"]))


def identify(texts, projects, all_projects, hint_id=None, domain="property"):
    """texts = [(source, index, text)]. Returns dict with state and per-project evidence.

    projects     = projects the user is authorised for
    all_projects = every project of the company (to catch mentions of projects the user cannot use)
    """
    folded = [(s, i, _fold(t), t) for s, i, t in texts]
    joined = " ".join(f for _, _, f, _ in folded)
    joined_raw = " ".join(t for _, _, _, t in folded).upper().replace(" ", "")
    ev = {}
    alias_owner = {}
    for p in all_projects:
        for n in names_of(p):
            alias_owner.setdefault(_fold(n), set()).add(p["id"])
    for p in all_projects:
        e = {"names": [], "locality": False, "city": False, "rera": False, "segments": set(), "shared_alias": False}
        for n in names_of(p):
            fn = _fold(n)
            if any(_contains(f, fn) for _, _, f, _ in folded):
                e["names"].append(n)
                if len(alias_owner.get(fn, ())) > 1:
                    e["shared_alias"] = True
                for s, i, f, _ in folded:
                    if _contains(f, fn):
                        e["segments"].add((s, i))
        if p["locality"] and _contains(joined, _fold(p["locality"])):
            e["locality"] = True
        if p["city"] and _contains(joined, _fold(p["city"])):
            e["city"] = True
        if p["rera_no"] and p["rera_no"].upper() in joined_raw:
            e["rera"] = True
        if e["names"] or e["rera"]:
            ev[p["id"]] = e
    auth_ids = {p["id"] for p in projects}
    out_of_scope = [pid for pid in ev if pid not in auth_ids]
    hits = [pid for pid in ev if pid in auth_ids]

    def card(pid):
        e = ev[pid]
        bits = []
        if e["names"]:
            bits.append("name: " + ", ".join(e["names"][:3]))
        if e["locality"]:
            bits.append("locality mentioned")
        if e["rera"]:
            bits.append("RERA number found")
        return "; ".join(bits)

    res = {"state": "NOT_FOUND", "project_ids": [], "evidence": {pid: card(pid) for pid in ev},
           "out_of_scope": out_of_scope, "segments": {pid: sorted(ev[pid]["segments"]) for pid in ev}, "note": ""}
    if out_of_scope and not hits:
        res["state"] = "NOT_AUTHORIZED"
        res["note"] = "The content seems to promote a project this account is not authorised for."
        return res
    strong = [pid for pid in hits if ev[pid]["rera"] or (ev[pid]["names"] and not ev[pid]["shared_alias"])]
    shared = [pid for pid in hits if ev[pid]["shared_alias"] and not ev[pid]["rera"]]
    if shared and not strong:
        res["state"] = "AMBIGUOUS"
        res["project_ids"] = shared
        res["note"] = "The name used fits more than one project."
        return res
    if len(strong) > 1:
        res["state"] = "MULTIPLE"
        res["project_ids"] = strong
        res["note"] = "More than one project is mentioned. Each claim is checked against the project it belongs to."
        return res
    if len(strong) == 1:
        pid = strong[0]
        e = ev[pid]
        res["project_ids"] = [pid]
        if hint_id and hint_id != pid:
            res["state"] = "CONFLICT"
            res["note"] = "The project you selected is different from the project the content mentions."
        elif e["rera"] or e["locality"] or hint_id == pid:
            res["state"] = "MATCHED"
        elif domain != "property" and _product_confirmed(next(p for p in all_projects if p["id"] == pid), e, joined):
            res["state"] = "MATCHED"     # products have no RERA or locality: the full name, or a name plus a variant, is enough
        else:
            res["state"] = "LIKELY"
            res["note"] = "The project name was heard, but nothing else confirms it."
        return res
    # nothing in content
    if hint_id:
        res["state"] = "SELECTED"
        res["project_ids"] = [hint_id]
        res["note"] = "The content does not name a project. Using the project you selected."
    else:
        res["note"] = "No project could be identified from the content."
    return res


# ----------------------------------------------------------------- validators
def _claim(kind, verdict, project, where, src, heard, normalized, official, reason, fix="", fact=None,
           source_title="", conf=None, rule="", level=""):
    return {"kind": kind, "verdict": verdict, "project_id": project["id"] if project else None,
            "project": project["official_name"] if project else "", "time": where, "source": src,
            "heard": heard, "normalized": normalized, "official": official, "reason": reason, "fix": fix,
            "fact_id": fact["id"] if fact else None,
            "fact_version": (f"v{fact['id']} valid {fact['valid_from'] or '?'} to {fact['valid_to'] or 'open'}") if fact else "",
            "source_title": source_title, "confidence": conf, "rule": rule, "level": level}


def _source_title(fact):
    if not fact or not fact["source_id"]:
        return ""
    r = _q("SELECT title, trust FROM sources WHERE id=?", (fact["source_id"],))
    return (r[0]["title"] + ("" if r[0]["trust"] == "official" else " (unverified source)")) if r else ""


BHK_RE = re.compile(r"(?<!\d)(\d(?:\.\d)?)\s*(?:-|\s)?\s*(?:bhk|bedroom|bed room|बीएचके|बी एच के|बेडरूम)", re.I)


def _bhk_in(text):
    m = BHK_RE.search(text)
    if not m:
        return None
    try:
        v = float(m.group(1))
    except ValueError:
        return None
    return int(v) if v == int(v) else v


def _units_for_bhk(pid, bhk):
    us = unit_types(pid)
    if bhk is None:
        return us, False
    exact = [u for u in us if u["bhk"] is not None and float(u["bhk"]) == float(bhk)]
    return exact, True


def _state_claim(state, detail, kind, project, where, src, heard, norm_v, rule, fixmissing):
    """Common handling for a fact that cannot be used."""
    if state == "missing":
        return _claim(kind, UNVERIFIABLE, project, where, src, heard, norm_v, "No approved value",
                      "No approved value is stored for this, so it cannot be confirmed. This is not a confirmed error.",
                      fixmissing, rule=rule)
    if state == "expired":
        return _claim(kind, UNVERIFIABLE, project, where, src, heard, norm_v, "Expired value",
                      detail + " It is not treated as current.", "Ask the project manager to confirm the current value.", rule=rule)
    if state == "conflict":
        return _claim(kind, REVIEW, project, where, src, heard, norm_v, "Conflicting values",
                      detail, "A project manager must resolve the conflicting facts.", rule=rule)
    return _claim(kind, UNVERIFIABLE, project, where, src, heard, norm_v, "Unverified value", detail,
                  "Ask the project manager to verify the stored value.", rule=rule)


def check_price(project, text, t, src, conf, threshold, used, skip=None):
    out = []
    low = _fold(text)
    prices = [p for p in extract_prices(text) if not skip or float(p["value"]) not in skip]
    if not prices:
        return out
    bhk = _bhk_in(text)
    is_emi = bool(re.search(r"\bemi\b|per month|monthly|महिना|महीना|प्रति माह|installment|instalment", low))
    is_booking = bool(re.search(r"booking|token|बुकिंग|टोकन", low))
    for p in prices:
        v = p["value"]
        if v <= 0:
            continue
        heard = p["spoken"]
        if is_emi:
            out.append(_claim("price", REVIEW, project, t, src, heard, fmt_money(v), "-",
                              "This looks like an instalment (EMI) figure. Instalment claims depend on loan terms and are checked by a person.",
                              "A person should confirm the loan terms behind this number.", conf=conf, rule="emi_review"))
            continue
        if is_booking:
            st, f, d = resolve_fact(project["id"], "booking_amount")
            if st == "ok":
                used.append(f)
                ok = abs(v - f["value_num"]) / f["value_num"] <= 0.005
                out.append(_claim("booking", VERIFIED if ok else VIOLATION, project, t, src, heard, fmt_money(v),
                                  fmt_money(f["value_num"]),
                                  "Matches the approved booking amount." if ok else
                                  f"Said {fmt_money(v)} but the approved booking amount is {fmt_money(f['value_num'])}.",
                                  "" if ok else f"Use {fmt_money(f['value_num'])}.", f, _source_title(f), conf, "booking_amount"))
            else:
                out.append(_state_claim(st, d, "booking", project, t, src, heard, fmt_money(v), "booking_amount",
                                        "Add the approved booking amount to this project."))
            continue
        units, specific = _units_for_bhk(project["id"], bhk)
        if specific and not units:
            out.append(_claim("price", UNVERIFIABLE, project, t, src, heard, fmt_money(v), "No such unit type",
                              f"{bhk} BHK is not listed for {project['official_name']}, so this price cannot be confirmed. "
                              "It may be a different project or a missing registry entry.",
                              "Check the project, or add the unit type.", conf=conf, rule="price_by_unit"))
            continue
        priced, problems = [], []
        for u in units:
            st, f, d = resolve_fact(project["id"], "price", u["id"])
            if st == "ok":
                priced.append((u, f))
            elif st != "missing" or specific:
                problems.append((u, st, d))
        if not priced:
            if problems:
                u, st, d = problems[0]
                out.append(_state_claim(st, d, "price", project, t, src, heard, fmt_money(v), "price_by_unit",
                                        f"Update the {u['label']} price."))
            else:
                out.append(_claim("price", UNVERIFIABLE, project, t, src, heard, fmt_money(v), "No approved price",
                                  f"No approved price is stored for {project['official_name']}, so nothing was verified.",
                                  "Add approved prices for this project.", conf=conf, rule="price_by_unit"))
            continue
        pr = [(u["label"], f["value_num"]) for u, f in priced]
        st, ftype, why, name, ref = classify_price(v, pr, conf, threshold)
        fact = next(f for u, f in priced if u["label"] == name)
        used.append(fact)
        title = _source_title(fact)
        scope = f"{name}" + (" (named in the content)" if specific else "")
        if st == "PASS":
            out.append(_claim("price", VERIFIED, project, t, src, heard, fmt_money(v), fmt_money(ref),
                              f"Matches the approved price for {scope}.", "", fact, title, conf, "price_by_unit"))
        elif st == "FLAG":
            out.append(_claim("price", VIOLATION, project, t, src, heard, fmt_money(v), fmt_money(ref), why,
                              f"Use the approved price: {fmt_money(ref)} for {name}.", fact, title, conf, "price_by_unit"))
        elif specific and ftype == "PRICE_NOT_IN_REGISTRY" and conf >= threshold:
            same = next((n for n, r in pr if abs(v / r - 1) <= 0.005), None)
            other = next((u2["label"] for u2 in unit_types(project["id"]) if u2["id"] not in [x[0]["id"] for x in priced]
                          and (lambda st2, f2, d2: st2 == "ok" and abs(v / f2["value_num"] - 1) <= 0.005)(*resolve_fact(project["id"], "price", u2["id"]))), None)
            why2 = f"Said {fmt_money(v)} for {name}, but the approved price for {name} is {fmt_money(ref)}."
            if other:
                why2 += f" {fmt_money(v)} is the price of {other}."
            out.append(_claim("price", VIOLATION, project, t, src, heard, fmt_money(v), fmt_money(ref), why2,
                              f"Use the approved price: {fmt_money(ref)} for {name}.", fact, title, conf, "price_by_unit"))
        else:
            out.append(_claim("price", REVIEW, project, t, src, heard, fmt_money(v), fmt_money(ref), why,
                              "A person should listen to this moment.", fact, title, conf, "price_by_unit"))
    return out


AREA_RE = re.compile(r"(\d[\d,]{2,5}(?:\.\d+)?)\s*(?:sq\.?\s*ft\.?|sqft|square\s*feet|square\s*foot|sq\.?\s*feet|स्क्वेअर\s*फूट|स्क्वेयर\s*फुट|स्क्वेअर\s*फुट|चौरस\s*फूट|चौ\.?\s*फूट|वर्ग\s*फुट|वर्ग\s*फीट)", re.I)


def check_area(project, text, t, src, conf, used):
    out = []
    for m in AREA_RE.finditer(norm(text)):
        try:
            v = float(m.group(1).replace(",", ""))
        except ValueError:
            continue
        window = _fold(text[max(0, m.start() - 40): m.end() + 25])
        kind_said = ("carpet" if re.search(r"carpet|कार्पेट|कारपेट", window) else
                     "builtup" if re.search(r"built ?up|बिल्ट|सुपर", window) else
                     "plot" if re.search(r"plot|प्लॉट|भूखंड", window) else "")
        bhk = _bhk_in(text)
        units, specific = _units_for_bhk(project["id"], bhk)
        heard = m.group(0).strip()
        cands = []
        for u in units:
            uf = unit_facts(project["id"], u["id"])
            for k in ("carpet_sqft", "builtup_sqft", "plot_sqft"):
                if k in uf:
                    cands.append((u, k, uf[k]))
        if not cands:
            out.append(_claim("area", UNVERIFIABLE, project, t, src, heard, f"{v:g} sq ft", "No approved area",
                              "No approved area is stored for this unit, so the figure cannot be confirmed.",
                              "Add carpet or built-up area to the unit type.", rule="area"))
            continue
        match = [c for c in cands if abs(v - c[2]["value_num"]) / c[2]["value_num"] <= 0.02]
        label_of = {"carpet_sqft": "carpet", "builtup_sqft": "built-up", "plot_sqft": "plot"}
        if match:
            u, k, f = match[0]
            used.append(f)
            lbl = label_of[k]
            if kind_said and kind_said != {"carpet_sqft": "carpet", "builtup_sqft": "builtup", "plot_sqft": "plot"}[k]:
                out.append(_claim("area", VIOLATION, project, t, src, heard, f"{v:g} sq ft ({kind_said})",
                                  f"{f['value_num']:g} sq ft ({lbl})",
                                  f"This figure is the {lbl} area, but it was described as {kind_said.replace('builtup', 'built-up')}.",
                                  f"Say {f['value_num']:g} sq ft is the {lbl} area.", f, _source_title(f), conf, "area"))
            else:
                out.append(_claim("area", VERIFIED, project, t, src, heard, f"{v:g} sq ft", f"{f['value_num']:g} sq ft ({lbl}, {u['label']})",
                                  f"Matches the approved {lbl} area for {u['label']}." + ("" if kind_said else " The content did not say whether it is carpet or built-up."),
                                  "", f, _source_title(f), conf, "area"))
        else:
            u, k, f = cands[0]
            used.append(f)
            shown = ", ".join(f"{c[2]['value_num']:g} ({label_of[c[1]]}, {c[0]['label']})" for c in cands[:4])
            out.append(_claim("area", VIOLATION, project, t, src, heard, f"{v:g} sq ft", shown,
                              "This area does not match any approved area for the unit(s) in this project.",
                              "Use an approved area figure.", f, _source_title(f), conf, "area"))
    return out


NUMW = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5}
BATH_RE = re.compile(r"(\d|one|two|three|four|five)\s*(?:bath(?:room)?s?|washrooms?|toilets?|बाथरूम|वॉशरूम)", re.I)


BATH_WORDS = ["bathroom", "bathrooms", "washroom", "washrooms", "toilet", "toilets", "बाथरूम", "वॉशरूम", "टॉयलेट", "बाथ"]
NUM_WORDS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "एक": 1, "दोन": 2, "दो": 2, "तीन": 3,
             "चार": 4, "पाच": 5, "पांच": 5, "सहा": 6, "छह": 6}


def _bath_mentions(text):
    """[(count, heard)]: '2 bathrooms', and spoken orders like 'बात्रुम तुम्हाला दोन' (any spelling of bathroom)."""
    found = [((int(m.group(1)) if m.group(1).isdigit() else NUMW[m.group(1).lower()]), m.group(0))
             for m in BATH_RE.finditer(norm(text))]
    if found:
        return found
    toks = phon.tokens(text)
    for i in phon.index_of(toks, BATH_WORDS):
        for j in list(range(i + 1, min(len(toks), i + 5))) + list(range(max(0, i - 3), i))[::-1]:
            tk = toks[j]
            v = int(tk) if tk.isdigit() and len(tk) == 1 else NUM_WORDS.get(tk)
            if v:
                lo, hi = min(i, j), max(i, j)
                found.append((v, " ".join(toks[lo:hi + 1])))
                break
    return found


def check_bathrooms(project, text, t, src, conf, used):
    out = []
    for v, heard in _bath_mentions(text):
        bhk = _bhk_in(text)
        units, specific = _units_for_bhk(project["id"], bhk)
        vals = []
        for u in units:
            uf = unit_facts(project["id"], u["id"])
            if "bathrooms" in uf:
                vals.append((u, uf["bathrooms"]))
        if not vals:
            out.append(_claim("bathrooms", UNVERIFIABLE, project, t, src, heard, str(v), "No approved value",
                              "No approved bathroom count is stored for this unit.", "Add the bathroom count.", rule="bathrooms"))
            continue
        hit = [x for x in vals if int(x[1]["value_num"]) == v]
        for _u, f in vals:
            used.append(f)
        if hit:
            u, f = hit[0]
            out.append(_claim("bathrooms", VERIFIED, project, t, src, heard, str(v), f"{int(f['value_num'])} ({u['label']})",
                              f"Matches the approved bathroom count for {u['label']}.", "", f, _source_title(f), conf, "bathrooms"))
        elif specific or len(vals) == 1:
            u, f = vals[0]
            out.append(_claim("bathrooms", VIOLATION, project, t, src, heard, str(v), f"{int(f['value_num'])} ({u['label']})",
                              f"Said {v} bathrooms but {u['label']} has {int(f['value_num'])}.", f"Say {int(f['value_num'])}.",
                              f, _source_title(f), conf, "bathrooms"))
        else:
            out.append(_claim("bathrooms", REVIEW, project, t, src, heard, str(v), ", ".join(f"{int(f['value_num'])} ({u['label']})" for u, f in vals),
                              "The unit was not named and the count differs between unit types.", "Name the unit type.", rule="bathrooms"))
    return out


READY_RE = re.compile(r"ready to move|ready possession|ready-to-move|immediate possession|ready for possession|रेडी टू मूव|रेडी पझेशन|तयार फ्लॅट|तैयार फ्लैट|तयार असून", re.I)
POSS_RE = re.compile(r"(?:possession|handover|पझेशन|पजेशन|ताबा|कब्जा)[^.\n]{0,30}?(?:(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s*,?\s*)?(20\d\d)", re.I)


POSS_WORDS = ["possession", "handover", "पझेशन", "ताबा", "कब्जा", "हॅंडओव्हर", "हैंडओवर"]
_MONTH_WORDS_INDIC = {"जानेवारी": 1, "जनवरी": 1, "फेब्रुवारी": 2, "फरवरी": 2, "मार्च": 3, "एप्रिल": 4, "अप्रैल": 4,
                      "मे": 5, "मई": 5, "जून": 6, "जुलै": 7, "जुलाई": 7, "ऑगस्ट": 8, "अगस्त": 8, "सप्टेंबर": 9,
                      "सितंबर": 9, "ऑक्टोबर": 10, "अक्टूबर": 10, "नोव्हेंबर": 11, "नवंबर": 11, "डिसेंबर": 12, "दिसंबर": 12}
_MONTH_SKEL = {}
for _w, _m in _MONTH_WORDS_INDIC.items():
    _MONTH_SKEL.setdefault(phon.skel(_w), _m)


def _indic_month(word):
    return _MONTH_SKEL.get(phon.skel(word)) if len(phon.skel(word)) >= 2 else None


class _Hit:
    """Looks like a regex match: group(0) heard text, group(1) month word, group(2) year."""
    def __init__(self, heard, month, year):
        self._g = (heard, month, year)

    def group(self, i):
        return self._g[i]


def _poss_spoken(text):
    """Possession in any spelling ('पोजेशन तुम्हाला डेसेंबर 2028'), with a month word in English, Marathi or Hindi."""
    toks = phon.tokens(text)
    for i in phon.index_of(toks, POSS_WORDS):
        window = toks[i + 1:i + 9]
        for k, tk in enumerate(window):
            if re.fullmatch(r"20\d\d", tk):
                month = None
                for w in reversed(window[:k]):
                    if w[:3] in MONTHS and w.isascii():
                        month = w
                        break
                    if _indic_month(w):
                        month = w
                        break
                return _Hit(" ".join(toks[i:i + 2 + k]), month, tk)
    return None


def check_possession(project, text, t, src, conf, used):
    out = []
    t_norm = norm(text)
    if READY_RE.search(t_norm):
        st, f, d = resolve_fact(project["id"], "ready_to_move")
        if st != "ok":
            out.append(_state_claim(st, d, "possession", project, t, src, "ready to move", "ready", "ready_to_move",
                                    "Record whether the project is ready to move in."))
        else:
            used.append(f)
            if (f["value_text"] or "").lower() == "yes":
                out.append(_claim("possession", VERIFIED, project, t, src, "ready to move", "ready", "Ready to move",
                                  "The project is recorded as ready to move in.", "", f, _source_title(f), conf, "ready_to_move"))
            else:
                ps, pf, _ = resolve_fact(project["id"], "possession")
                when = f" Registered possession: {pf['value_text']}." if ps == "ok" else ""
                out.append(_claim("possession", VIOLATION, project, t, src, "ready to move", "ready", "Under construction",
                                  "The content says ready to move, but the project is recorded as under construction." + when,
                                  "Remove the ready-to-move claim or state the registered possession date.", f, _source_title(f), conf, "ready_to_move"))
    m = POSS_RE.search(t_norm) or _poss_spoken(text)
    if m:
        year = int(m.group(2))
        mg = m.group(1) or ""
        month = (MONTHS.get(mg[:3].lower()) if mg.isascii() else _indic_month(mg)) if mg else None
        st, f, d = resolve_fact(project["id"], "possession")
        claimed = (f"{month:02d}/{year}" if month else str(year)) if m.group(1) and not m.group(1).isascii() else \
            f"{m.group(1).title() + ' ' if m.group(1) else ''}{year}"
        if st != "ok":
            out.append(_state_claim(st, d, "possession", project, t, src, m.group(0).strip(), claimed, "possession",
                                    "Add the registered possession date."))
        else:
            used.append(f)
            try:
                ry, rm = [int(x) for x in f["value_text"].split("-")]
            except ValueError:
                ry, rm = None, None
            shown = f["value_text"]
            if ry is None:
                out.append(_claim("possession", REVIEW, project, t, src, m.group(0).strip(), claimed, shown,
                                  "The stored possession date could not be read.", "Fix the stored date (YYYY-MM).", f, _source_title(f), conf, "possession"))
            elif (year, month or rm) == (ry, rm) or (month is None and year == ry):
                out.append(_claim("possession", VERIFIED, project, t, src, m.group(0).strip(), claimed, shown,
                                  "Matches the registered possession date.", "", f, _source_title(f), conf, "possession"))
            elif (year, month or 12) < (ry, rm):
                out.append(_claim("possession", VIOLATION, project, t, src, m.group(0).strip(), claimed, shown,
                                  "The possession date promised is earlier than the registered date.",
                                  f"Use the registered date ({shown}).", f, _source_title(f), conf, "possession"))
            else:
                out.append(_claim("possession", REVIEW, project, t, src, m.group(0).strip(), claimed, shown,
                                  "The date is later than the registered date. A person should confirm it.",
                                  "Confirm the updated timeline.", f, _source_title(f), conf, "possession"))
    return out


RERA_RE = re.compile(r"P\s?\d(?:\s?\d){10}", re.I)


def check_rera(project, all_projects, text, t, src, conf):
    out = []
    for m in RERA_RE.finditer(norm(text)):
        raw = re.sub(r"\s", "", m.group(0)).upper()
        reg = (project["rera_no"] or "").upper()
        if not rera_format_ok(raw):
            out.append(_claim("rera", REVIEW, project, t, src, raw, raw, reg or "-", "This does not look like a valid RERA number.",
                              "Check the number.", rule="rera", level="format_failed"))
        elif raw == reg:
            lvl = project["rera_level"]
            if lvl == "authoritative":
                out.append(_claim("rera", VERIFIED, project, t, src, raw, raw, reg,
                                  f"Matches the registered number, confirmed against {project['rera_source'] or 'the authority register'} on {project['rera_checked_at'] or '?'}.",
                                  "", conf=conf, rule="rera", level="authoritative"))
            else:
                out.append(_claim("rera", VERIFIED, project, t, src, raw, raw, reg,
                                  "Matches the number in the BrandGuard registry. It has not been confirmed against the official RERA register, so this is a registry match only.",
                                  "", conf=conf, rule="rera", level="registry_match"))
        else:
            other = next((p for p in all_projects if (p["rera_no"] or "").upper() == raw), None)
            why = (f"This is the RERA number of {other['official_name']}, not {project['official_name']}." if other else
                   "This RERA number does not match the registered number for this project.")
            out.append(_claim("rera", VIOLATION, project, t, src, raw, raw, reg or "-", why,
                              f"Use {reg}." if reg else "Add the project's RERA number.", conf=conf, rule="rera", level="format"))
    return out


def check_offers(project, text, t, src, conf, used):
    out = []
    low = _fold(text)
    low_raw = norm(text).lower()
    for tag, (label, kws) in OFFER_TAGS.items():
        if not any((_fold(k) in low) or (k in low_raw) for k in kws):
            continue
        heard = label
        st, f, d = resolve_fact(project["id"], "offer:" + tag)
        if st == "ok":
            used.append(f)
            out.append(_claim("offer", VERIFIED, project, t, src, heard, label, f["value_text"] or label,
                              f"An active approved offer exists. Valid {f['valid_from']} to {f['valid_to'] or 'open'}. Terms: {f['value_text'] or 'see source'}.",
                              "", f, _source_title(f), conf, "offer"))
        elif st == "expired":
            out.append(_claim("offer", VIOLATION, project, t, src, heard, label, "Expired",
                              f"This offer expired on {d.split(' on ')[-1].rstrip('.')}. It is not available now.",
                              "Remove the offer or ask for an extension.", f, _source_title(f), conf, "offer"))
        else:
            out.append(_state_claim(st, d, "offer", project, t, src, heard, label, "offer",
                                    "Add the offer with its dates and conditions, or remove the claim."))
    return out


DIST_RE = re.compile(r"(\d{1,3})\s*(?:min(?:ute)?s?|मिनिट(?:ांवर|ात)?|मिनट)", re.I)


DIST_CONTEXT = ["पासून", "इथून", "हून", "वरून", "पासुन", "से", "दूर", "ड्राइव", "कार", "car", "by", "minutes", "मिनिटात", "मिनटों"]


def _landmark_spoken(name, text):
    """An English landmark name heard in Marathi or Hindi ('Wakad bridge' as 'वाकड ब्रिच'): the place's main word
    must match by sound; short or generic words (bridge, road, station) only help."""
    parts = [p for p in re.split(r"\s+", name.strip()) if p]
    if not parts:
        return False
    heard = {phon.latin_skel(t) for t in phon.tokens(text)}
    main = max(parts, key=lambda p: len(phon.latin_skel(p)) if p.lower() not in GENERIC_PLACE else 0)
    ms = phon.latin_skel(main)
    return len(ms) >= 3 and ms in heard


GENERIC_PLACE = {"bridge", "road", "station", "chowk", "circle", "highway", "airport", "mall", "park", "it", "metro",
                 "railway", "bus", "stand", "square", "junction", "market", "hospital", "school", "college"}


def check_distance(project, text, t, src, conf, used):
    out = []
    low = _fold(text)
    m = DIST_RE.search(norm(text))
    if not m or not (re.search(r"from|away|drive|walk|पासून|से दूर|अंतरावर|ड्राइव|walking", norm(text).lower())
                     or phon.has_any(text, DIST_CONTEXT)):
        return out
    claimed = int(m.group(1))
    landmarks = _q("SELECT * FROM facts WHERE project_id=? AND key LIKE 'landmark:%'", (project["id"],))
    matched = False
    for f in landmarks:
        if not _is_current(f):
            continue
        name = f["key"].split(":", 1)[1]
        if _fold(name) and (_contains(low, _fold(name)) or _landmark_spoken(name, text)):
            matched = True
            used.append(f)
            official = int(f["value_num"])
            how = f["unit"] or "min"
            if claimed >= official:
                out.append(_claim("distance", VERIFIED, project, t, src, m.group(0), f"{claimed} min to {name}", f"{official} min ({how})",
                                  "The time claimed is not shorter than the approved time. Travel time depends on conditions.", "", f, _source_title(f), conf, "distance"))
            else:
                out.append(_claim("distance", VIOLATION, project, t, src, m.group(0), f"{claimed} min to {name}", f"{official} min ({how})",
                                  f"Said {claimed} minutes to {name} but the approved figure is {official} minutes.",
                                  f"Say {official} minutes.", f, _source_title(f), conf, "distance"))
    if not matched:
        out.append(_claim("distance", UNVERIFIABLE, project, t, src, m.group(0), f"{claimed} min", "No approved landmark",
                          "A travel-time claim was made, but no approved distance data matches the place named.",
                          "Add the landmark with its approved travel time.", rule="distance"))
    return out


def _split_caption(text):
    parts = [p.strip() for p in re.split(r"[\n\r]+|(?<=[.!?])\s+", text or "") if p.strip()]
    return parts or ([text] if text else [])


def validate(texts_by_project, projects_all, threshold, domain="property"):
    """texts_by_project = {project_id: [(src, t, conf, text)]}. Returns (claims, used_facts).
    Every company gets the price check and its own fact types (generic.py). Property checks (area, bathrooms,
    possession, RERA, offers, travel time) run only for property companies."""
    import generic, sys
    claims, used = [], []
    pmap = {p["id"]: p for p in projects_all}
    defs_cache = {}
    for pid, items in texts_by_project.items():
        p = pmap.get(pid)
        if not p:
            continue
        if p["brand_id"] not in defs_cache:
            defs_cache[p["brand_id"]] = generic.list_defs(p["brand_id"])
        defs = defs_cache[p["brand_id"]]
        for src, t, conf, text in items:
            consumed = set()
            if defs:
                gc, consumed = generic.check(p, defs, text, t, src, conf, used, sys.modules[__name__])
                claims += gc
            claims += check_price(p, text, t, src, conf, threshold, used, consumed)
            if domain != "property":
                continue
            claims += check_area(p, text, t, src, conf, used)
            claims += check_bathrooms(p, text, t, src, conf, used)
            claims += check_possession(p, text, t, src, conf, used)
            claims += check_rera(p, projects_all, text, t, src, conf)
            claims += check_offers(p, text, t, src, conf, used)
            claims += check_distance(p, text, t, src, conf, used)
    uniq = {}
    for f in used:
        uniq[f["id"]] = {"id": f["id"], "key": f["key"], "project_id": f["project_id"],
                         "value": fact_display(f), "valid_from": f["valid_from"], "valid_to": f["valid_to"]}
    return claims, list(uniq.values())


def assign_segments(segs, caption_parts, idres, projects, screen=None):
    """Decide which project each piece of text is about. Returns {project_id: [(src, t, conf, text)]} and unassigned."""
    ids = idres["project_ids"]
    out = {pid: [] for pid in ids}
    unassigned = []
    items = [("audio", s["start"], s.get("conf", 1.0), s["text"], i) for i, s in enumerate(segs)]
    items += [("caption", 0, 1.0, c, i) for i, c in enumerate(caption_parts)]
    items += [("screen", l["start"], l.get("conf", 1.0), l["text"], i) for i, l in enumerate(screen or [])]
    if len(ids) == 1:
        for src, t, conf, text, _i in items:
            out[ids[0]].append((src, t, conf, text))
        return out, unassigned
    pmap = {p["id"]: p for p in projects}
    current = {"audio": None, "caption": None, "screen": None}
    for src, t, conf, text, i in items:
        f = _fold(text)
        named = [pid for pid in ids if pid in pmap and any(_contains(f, _fold(n)) for n in names_of(pmap[pid]))]
        if len(named) == 1:
            current[src] = named[0]
        elif len(named) > 1:
            current[src] = None
            unassigned.append((src, t, conf, text))
            continue
        pid = current[src]
        if pid is None:
            unassigned.append((src, t, conf, text))
        else:
            out[pid].append((src, t, conf, text))
    return out, unassigned


def claim_to_finding(c):
    """Convert a non-verified claim into the finding shape that main.py already counts and displays."""
    v = c["verdict"]
    status = "FLAG" if v == VIOLATION else "SUPERVISION"
    sev = "HIGH" if v == VIOLATION else "MEDIUM"
    typ = {"price": "PRICE_MISMATCH", "booking": "PRICE_MISMATCH"}.get(c["kind"], c["kind"].upper() + "_CHECK")
    if c["kind"] in ("price", "booking") and v != VIOLATION:
        typ = "PRICE_UNIT_CHECK"
    if v == UNVERIFIABLE:
        typ = c["kind"].upper() + "_UNVERIFIABLE"
    return {"status": status, "severity": sev, "type": typ, "time": c["time"], "evidence": c["heard"],
            "explanation": c["reason"], "suggestion": c["fix"] or "A person should check this.",
            "confidence": c.get("confidence"), "source": c["source"], "verdict": v, "kind": c["kind"]}


# ------------------------------------------------------------- reuse status
def reuse_status(sub_id, report, user_id, brand_id):
    """Current reuse eligibility of an approved submission. The original decision is never changed."""
    reasons = []
    for u in report.get("facts_used", []):
        rows = _q("SELECT * FROM facts WHERE id=?", (u["id"],))
        if rows and not _is_current(rows[0]):
            reasons.append(f"{FACT_LABEL.get(rows[0]['key'], rows[0]['key'])} fact is no longer current")
    if _q("SELECT 1 FROM fact_flags WHERE sub_id=? AND resolved=0", (sub_id,)):
        reasons.append("a fact it relied on has changed")
    for pid in report.get("project_ids", []):
        if user_id and not can_use_project(user_id, pid):
            reasons.append("the creator no longer has access to the project")
    seen = []
    for r in reasons:
        if r not in seen:
            seen.append(r)
    return ("OK", []) if not seen else ("RECHECK", seen)


# ------------------------------------------------------------------- seeding
def _parse_poss(s):
    m = re.search(r"([A-Za-z]{3})[a-z]*\s+(20\d\d)", s or "")
    if m and m.group(1).lower() in MONTHS:
        return f"{m.group(2)}-{MONTHS[m.group(1).lower()]:02d}"
    m = re.search(r"(20\d\d)", s or "")
    return f"{m.group(1)}-12" if m else None


def seed_if_empty():
    """First run on any database: migrate each brand's old single-project registry into real project records,
    then add fictional demo projects for the two demo companies."""
    if _q("SELECT COUNT(*) AS c FROM projects")[0]["c"]:
        return
    actor = "migration"
    brands = _q("SELECT * FROM brands ORDER BY id")
    members = _q("SELECT user_id, brand_id FROM memberships")
    for b in brands:
        reg = json.loads(b["registry"] or "{}")
        src = add_source(b["id"], "Original brand registry (migrated)", "registry", "official", actor)
        name = reg.get("project") or b["name"]
        pid = add_project(b["id"], name, "", "", "", reg.get("rera", ""), [], actor)
        for c in reg.get("configs", []):
            m = re.match(r"\s*(\d(?:\.\d)?)\s*bhk", c["name"], re.I)
            bhk = int(float(m.group(1))) if m else None
            uid = add_unit_type(pid, "apartment", c["name"], bhk)
            set_fact(pid, "price", float(c["price"]), None, uid, "INR", src, actor=actor, reason="Migrated from original registry")
        pos = _parse_poss(reg.get("possession", ""))
        if pos:
            set_fact(pid, "possession", None, pos, None, "", src, actor=actor, reason="Migrated")
        for m_ in members:
            if m_["brand_id"] == b["id"]:
                grant(m_["user_id"], b["id"], pid, actor)
    names = {b["name"]: b["id"] for b in brands}
    demo_dev = names.get("Demo Developer")
    sample = names.get("Sample Builders")
    if demo_dev:
        _seed_demo_developer(demo_dev)
    if sample:
        _seed_demo_sample(sample)


def _mk_unit(pid, cat, label, bhk, facts, src):
    uid = add_unit_type(pid, cat, label, bhk)
    for k, v in facts.items():
        if k == "price":
            set_fact(pid, "price", float(v), None, uid, "INR", src, actor="seed", reason="Seed data (fictional)")
        elif k in NUMERIC_FIELDS:
            set_fact(pid, k, float(v), None, uid, "sq ft" if k.endswith("sqft") else "", src, actor="seed", reason="Seed data (fictional)")
        else:
            set_fact(pid, k, None, str(v), uid, "", src, actor="seed", reason="Seed data (fictional)")
    return uid


def _seed_demo_developer(brand_id):
    src = add_source(brand_id, "Demo price sheet, Oct 2026 (fictional)", "price_sheet", "official", "seed")
    # enrich the migrated project
    heights = next((p for p in brand_projects(brand_id) if p["official_name"] == "Demo Heights"), None)
    if heights:
        _ex("UPDATE projects SET city='Pune', locality='Wakad', short_name='Heights' WHERE id=?", (heights["id"],))
        for _a in ("डेमो हाइट्स", "डेमो हाईट्स", "Demo Hights", "Demo Hites", "Demo Heidts", "Demo Hytes"):
            _ex("INSERT INTO project_aliases (project_id, alias) VALUES (?,?)", (heights["id"], _a))
        for u in unit_types(heights["id"]):
            if u["bhk"] == 2:
                for k, v in (("carpet_sqft", 720), ("builtup_sqft", 860), ("bathrooms", 2), ("balconies", 1), ("parking", 1)):
                    set_fact(heights["id"], k, float(v), None, u["id"], "sq ft" if k.endswith("sqft") else "", src, actor="seed")
            if u["bhk"] == 3:
                for k, v in (("carpet_sqft", 985), ("builtup_sqft", 1180), ("bathrooms", 3), ("balconies", 2), ("parking", 2)):
                    set_fact(heights["id"], k, float(v), None, u["id"], "sq ft" if k.endswith("sqft") else "", src, actor="seed")
        set_fact(heights["id"], "ready_to_move", None, "no", None, "", src, actor="seed")
        set_fact(heights["id"], "booking_amount", 500000.0, None, None, "INR", src, actor="seed")
        set_fact(heights["id"], "offer:free_parking", None, "One covered parking with 3 BHK bookings", None, "", src,
                 valid_from=today(), valid_to=(date.today() + timedelta(days=60)).isoformat(), actor="seed")
        set_fact(heights["id"], "offer:zero_gst", None, "GST waiver (expired campaign)", None, "", src,
                 valid_from="2026-01-01", valid_to="2026-09-30", actor="seed")
        set_fact(heights["id"], "landmark:wakad bridge", 12.0, None, None, "min by car", src, actor="seed")
    greens = add_project(brand_id, "Demo Greens Villas", "Demo Greens", "Pune", "Hinjewadi", "P22222222222",
                         ["डेमो ग्रीन्स"], "seed")
    _mk_unit(greens, "villa", "4 BHK Villa", 4, {"price": 41000000, "plot_sqft": 2400, "builtup_sqft": 3100, "bathrooms": 5, "parking": 2}, src)
    _mk_unit(greens, "bungalow", "Bungalow", None, {"price": 62000000, "plot_sqft": 4000, "builtup_sqft": 4200, "bathrooms": 6}, src)
    _mk_unit(greens, "plot", "Residential Plot A", None, {"price": 9500000, "plot_sqft": 1500, "dimensions": "30 x 50 ft", "permitted_use": "Residential"}, src)
    set_fact(greens, "possession", None, "2027-06", None, "", src, actor="seed")
    set_fact(greens, "ready_to_move", None, "no", None, "", src, actor="seed")
    sky = add_project(brand_id, "Demo Skyline Mumbai", "Skyline", "Mumbai", "Worli", "P33333333333", ["डेमो स्कायलाइन"], "seed")
    _mk_unit(sky, "apartment", "2 BHK", 2, {"price": 38000000, "carpet_sqft": 680, "builtup_sqft": 820, "bathrooms": 2}, src)
    _mk_unit(sky, "penthouse", "Penthouse", 4, {"price": 180000000, "carpet_sqft": 3200, "builtup_sqft": 3900, "bathrooms": 5}, src)
    set_fact(sky, "possession", None, "2029-03", None, "", src, actor="seed")
    set_fact(sky, "ready_to_move", None, "no", None, "", src, actor="seed")
    # partner(2): Heights + Greens in this company. Skyline stays unassigned on purpose.
    for uid in (2,):
        if _q("SELECT 1 FROM users WHERE id=?", (uid,)):
            grant(uid, brand_id, greens, "seed")
    for uid in (3,):
        pass


def _seed_demo_sample(brand_id):
    src = add_source(brand_id, "Sample price sheet (fictional)", "price_sheet", "official", "seed")
    res = next((p for p in brand_projects(brand_id) if p["official_name"] == "Sample Residency"), None)
    if res:
        _ex("UPDATE projects SET city='Nashik', locality='Gangapur Road' WHERE id=?", (res["id"],))
        set_fact(res["id"], "ready_to_move", None, "yes", None, "", src, actor="seed")