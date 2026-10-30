"""Generic product facts for any industry.

A company defines its own fact types once (for example "Discount" as a percentage, "Mileage" as a number in kmpl,
"Processing fee" as money, "Delivery date" as a date, "Free insurance" as yes/no, "Colour options" as text).
Each product (or a variant of it) then gets approved values. The matcher finds claims about those facts in a
transcript, caption, screen text or document and compares them with the approved values.

Fact types
    percent  "30% off", "तीस टक्के"            compared as a number
    money    "999 rupees", "नऊशे रुपये"         compared as a number (rupees)
    number   "22 kmpl", "5 years"              number followed by the fact's unit (or one of its unit spellings)
    date     "15 March 2027", "March 2027"     compared at the precision of the approved value
    yes_no   "free insurance", "no insurance"  the sentence's polarity is compared with yes or no
    text     "available in red and blue"       one of the approved wordings must be present

Direction (how a claimed number may differ from the approved one)
    exact    must be equal (default)
    max      must not be higher (a discount, a mileage, a warranty: claiming more is the violation)
    min      must not be lower (an interest rate, a delivery date: claiming less is the violation)

Values are stored as ordinary versioned facts (key "g:<label>"), so history, expiry, sources and re-check flags work
the same way as property facts.
"""

import json
import re
import sqlite3
from datetime import datetime

import amounts

DB_PATH = None
TYPES = {"percent": "Percentage", "money": "Money (rupees)", "number": "Number with a unit", "date": "Date",
         "yes_no": "Yes or no", "text": "Text"}
DIRECTIONS = {"exact": "Must be exactly this", "max": "Must not be more than this", "min": "Must not be less than this"}
NEGATORS = {"no", "not", "without", "never", "isn't", "isnt", "don't", "dont", "doesn't", "doesnt", "zero", "nil", "none",
            "nahi", "nahin", "nai", "नहीं", "नही", "नाही", "बिना", "शिवाय", "न"}
MONTHS = {m: i + 1 for i, m in enumerate(["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"])}
MONTH_WORDS = {"january", "february", "march", "april", "may", "june", "july", "august", "september", "october",
               "november", "december", "jan", "feb", "mar", "apr", "jun", "jul", "aug", "sep", "sept", "oct", "nov", "dec"}
MONTHS_INDIC = {"जानेवारी": 1, "जनवरी": 1, "फेब्रुवारी": 2, "फरवरी": 2, "मार्च": 3, "एप्रिल": 4, "अप्रैल": 4, "मे": 5,
                "मई": 5, "जून": 6, "जुलै": 7, "जुलाई": 7, "ऑगस्ट": 8, "अगस्त": 8, "सप्टेंबर": 9, "सितंबर": 9,
                "ऑक्टोबर": 10, "अक्टूबर": 10, "नोव्हेंबर": 11, "नवंबर": 11, "डिसेंबर": 12, "दिसंबर": 12}


# ------------------------------------------------------------------ storage
def setup(db_path):
    global DB_PATH
    DB_PATH = db_path
    con = sqlite3.connect(DB_PATH)
    con.execute("""CREATE TABLE IF NOT EXISTS fact_defs (
        id INTEGER PRIMARY KEY AUTOINCREMENT, brand_id INTEGER NOT NULL, label TEXT NOT NULL, ftype TEXT NOT NULL,
        unit TEXT, aliases TEXT, direction TEXT DEFAULT 'exact', active INTEGER DEFAULT 1, created_at TEXT)""")
    con.execute("CREATE INDEX IF NOT EXISTS ix_fact_defs_brand ON fact_defs(brand_id)")
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


def key_of(label):
    return "g:" + re.sub(r"\s+", " ", (label or "").strip().lower())[:60]


def _list(s):
    if isinstance(s, (list, tuple)):
        return [str(x).strip() for x in s if str(x).strip()]
    return [x.strip() for x in re.split(r"[,;|\n]", s or "") if x.strip()]


def add_def(brand_id, label, ftype, unit="", aliases=(), direction="exact"):
    """Create or update a fact type for a company. Returns its id. Raises ValueError on bad input."""
    label = re.sub(r"\s+", " ", (label or "").strip())[:60]
    if len(label) < 2:
        raise ValueError("Give the fact a name, for example Discount or Mileage.")
    if ftype not in TYPES:
        raise ValueError("Choose the type of value: percentage, money, number, date, yes/no or text.")
    if direction not in DIRECTIONS:
        direction = "exact"
    units = _list(unit)
    if ftype == "number" and not units:
        raise ValueError("A number needs its unit, for example kmpl, years or GB, so it can be found in the content.")
    data = (ftype, "|".join(units)[:120], json.dumps(_list(aliases)[:12], ensure_ascii=False), direction)
    old = get_def(brand_id, label)
    if old:
        _ex("UPDATE fact_defs SET ftype=?, unit=?, aliases=?, direction=?, active=1 WHERE id=?", data + (old["id"],))
        return old["id"]
    return _ex("INSERT INTO fact_defs (brand_id, label, ftype, unit, aliases, direction, created_at) VALUES (?,?,?,?,?,?,?)",
               (brand_id, label) + data + (datetime.now().strftime("%Y-%m-%d %H:%M"),))


def get_def(brand_id, label):
    r = _q("SELECT * FROM fact_defs WHERE brand_id=? AND lower(label)=?", (brand_id, (label or "").strip().lower()))
    return _row(r[0]) if r else None


def get_def_by_id(brand_id, def_id):
    r = _q("SELECT * FROM fact_defs WHERE brand_id=? AND id=?", (brand_id, def_id))
    return _row(r[0]) if r else None


def list_defs(brand_id):
    return [_row(r) for r in _q("SELECT * FROM fact_defs WHERE brand_id=? AND active=1 ORDER BY label", (brand_id,))]


def remove_def(brand_id, def_id):
    _ex("UPDATE fact_defs SET active=0 WHERE id=? AND brand_id=?", (def_id, brand_id))


def _row(r):
    d = dict(r)
    d["aliases"] = json.loads(d.get("aliases") or "[]")
    d["units"] = [u for u in (d.get("unit") or "").split("|") if u]
    d["key"] = key_of(d["label"])
    return d


# ------------------------------------------------------------------ values
def parse_value(ftype, raw):
    """Parse an approved value typed by a person. Returns (value_num, value_text). Raises ValueError."""
    s = (str(raw) if raw is not None else "").strip()
    if not s:
        raise ValueError("Enter a value.")
    if ftype == "percent":
        n = _number(s.replace("%", ""))
        if n is None or not (0 <= n <= 100):
            raise ValueError("Enter a percentage between 0 and 100, for example 30 or 8.75.")
        return n, None
    if ftype == "money":
        got = amounts.extract_amounts(s if re.search(r"rs|₹|rupee|lakh|crore|cr|l\b", s, re.I) else s + " rupees")
        n = got[0]["value"] if got else _number(s.replace(",", ""))
        if n is None or n < 0:
            raise ValueError("Enter an amount, for example 999, 9,470 or 1.2 lakh.")
        return float(n), None
    if ftype == "number":
        n = _number(re.sub(r"[^\d.,-]", " ", s).split()[0] if re.search(r"\d", s) else "")
        if n is None:
            raise ValueError("Enter a number, for example 22 or 5.")
        return n, None
    if ftype == "date":
        d = parse_date(s)
        if not d:
            raise ValueError("Enter a date like 2027-03-15, 15 March 2027 or March 2027.")
        return None, d
    if ftype == "yes_no":
        low = s.lower()
        if low in ("yes", "y", "true", "1", "हो", "हाँ", "होय", "available", "included"):
            return None, "yes"
        if low in ("no", "n", "false", "0", "नाही", "नहीं", "not available", "not included"):
            return None, "no"
        raise ValueError("Enter yes or no.")
    return None, s[:300]


def _number(s):
    import math
    try:
        v = float(str(s).replace(",", "").strip())
    except (ValueError, TypeError, OverflowError):
        return None
    return v if math.isfinite(v) and abs(v) < 1e15 else None    # no infinity, NaN or absurd sizes


def parse_date(s):
    """Returns 'YYYY-MM-DD' or 'YYYY-MM', or None."""
    s = (s or "").strip()
    m = re.match(r"^(\d{4})-(\d{1,2})(?:-(\d{1,2}))?$", s)
    if m:
        y, mo, d = int(m.group(1)), int(m.group(2)), m.group(3)
        if 1 <= mo <= 12:
            return f"{y:04d}-{mo:02d}" + (f"-{int(d):02d}" if d else "")
    found = find_dates(s)
    return found[0][0] if found else None


DATE_NUM = re.compile(r"(?<!\d)(\d{1,2})[/.-](\d{1,2})[/.-](\d{4})(?!\d)")
DATE_WORD = re.compile(r"(?:(\d{1,2})(?:st|nd|rd|th)?\s+)?([a-z]{3,9}|[ऀ-ॿ]{2,10})\.?,?\s+(\d{4})", re.I)


def find_dates(text):
    """[(iso, spoken)] dates mentioned in text."""
    out = []
    for m in DATE_NUM.finditer(text or ""):
        d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if 1 <= mo <= 12 and 1 <= d <= 31:
            out.append((f"{y:04d}-{mo:02d}-{d:02d}", m.group(0)))
    for m in DATE_WORD.finditer(text or ""):
        word = m.group(2).lower()
        mo = (MONTHS.get(word[:3]) if word in MONTH_WORDS else None) if word.isascii() else MONTHS_INDIC.get(word)
        if not mo:
            continue
        y = int(m.group(3))
        if not 1990 <= y <= 2100:
            continue
        iso = f"{y:04d}-{mo:02d}" + (f"-{int(m.group(1)):02d}" if m.group(1) and 1 <= int(m.group(1)) <= 31 else "")
        out.append((iso, m.group(0)))
    return out


# ------------------------------------------------------------------ matching helpers
def fold(s):
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s%₹ऀ-ॿ]", " ", (s or "").lower())).strip()


def mentions(text_f, phrase):
    p = fold(phrase)
    if not p:
        return False
    if p.isascii():
        return re.search(r"(?<!\w)" + re.escape(p) + r"(?!\w)", text_f) is not None
    return p in text_f


def names_of(d):
    return [d["label"]] + list(d["aliases"])


def polarity(text_f, d):
    """'no' if a negator sits within three words before (or two after) the fact's name, else 'yes'."""
    toks = text_f.split()
    for name in names_of(d):
        nt = fold(name).split()
        if not nt:
            continue
        for i in range(len(toks) - len(nt) + 1):
            if toks[i:i + len(nt)] == nt:
                around = toks[max(0, i - 3):i] + toks[i + len(nt):i + len(nt) + 2]
                return "no" if any(w in NEGATORS for w in around) else "yes"
    for name in names_of(d):           # Devanagari: no word boundaries, check the whole sentence
        if not fold(name).isascii() and fold(name) in text_f:
            return "no" if any(w in NEGATORS for w in toks) else "yes"
    return "yes"


def number_with_unit(text, units):
    """[(value, spoken)] numbers directly followed by one of the units."""
    out = []
    t = text or ""
    for u in sorted(units, key=len, reverse=True):
        pat = r"(?<![\d.])(\d+(?:[.,]\d+)?)\s*" + re.escape(u) + (r"(?!\w)" if u.isascii() else "")
        for m in re.finditer(pat, t, re.I):
            v = _number(m.group(1).replace(",", "."))
            if v is not None and not any(abs(v - o[0]) < 1e-9 and o[1] == m.group(0) for o in out):
                out.append((v, m.group(0)))
    return out


def compare(claimed, approved, direction, tol):
    """True when the claim is allowed."""
    if direction == "max":
        return claimed <= approved + tol
    if direction == "min":
        return claimed >= approved - tol
    return abs(claimed - approved) <= tol


def _date_cmp(claimed, approved, direction):
    n = len(approved)                     # compare at the approved value's precision (month or day)
    c = claimed[:n] if len(claimed) >= n else claimed
    if len(c) < n:                        # claim less precise than the approved value: compare months
        a = approved[:len(c)]
        c_, a_ = c, a
    else:
        c_, a_ = c, approved
    if direction == "max":
        return c_ <= a_
    if direction == "min":
        return c_ >= a_
    return c_ == a_


def _fmt(d, v):
    if v is None:
        return "-"
    if d["ftype"] == "percent":
        return f"{v:g}%"
    if d["ftype"] == "money":
        return "₹" + f"{v:,.0f}"
    if d["ftype"] == "number":
        return f"{v:g} {d['units'][0] if d['units'] else ''}".strip()
    return str(v)


# ------------------------------------------------------------------ the check
def check(project, defs, text, t, src, conf, used, RE):
    """Claims about a company's own fact types in one piece of text.
    Returns (claims, consumed) where consumed are money values already explained by a money fact (so the price check
    does not treat a fee as a product price). RE is the realestate module (claim helpers and fact storage)."""
    claims, consumed = [], set()
    tf = fold(text)
    pct = amounts.extract_percents(text)
    money = amounts.extract_amounts(text)
    used_pct = set()
    variants = RE.unit_types(project["id"])
    named = [v for v in variants if mentions(tf, v["label"])]
    for d in defs:
        rows = RE._q("SELECT * FROM facts WHERE project_id=? AND key=? ORDER BY id", (project["id"], d["key"]))
        cur = [f for f in rows if RE._is_current(f)]
        if named:
            scoped = [f for f in cur if f["unit_type_id"] in [v["id"] for v in named]] or [f for f in cur if f["unit_type_id"] is None]
        else:
            scoped = [f for f in cur if f["unit_type_id"] is None] or cur
        label_hit = any(mentions(tf, n) for n in names_of(d))
        heard = []                        # (value, spoken)
        if d["ftype"] == "percent" and label_hit:
            heard = [(p["value"], p["spoken"]) for p in pct]
            used_pct.update(p["value"] for p in pct)
        elif d["ftype"] == "money" and label_hit:
            heard = [(float(m["value"]), m["spoken"]) for m in money]
        elif d["ftype"] == "number":
            heard = number_with_unit(text, d["units"])
        elif d["ftype"] == "date" and label_hit:
            heard = find_dates(text)
        elif d["ftype"] in ("yes_no", "text") and label_hit:
            heard = [(None, d["label"])]
        if not heard:
            continue
        if not scoped:
            if d["ftype"] in ("yes_no", "text"):
                continue
            if any(not RE._is_current(f) for f in rows) and rows:
                last = rows[-1]
                claims.append(RE._claim("custom", RE.UNVERIFIABLE, project, t, src, heard[0][1], d["label"], "Expired value",
                                        f'The approved {d["label"]} for {project["official_name"]} is no longer current.',
                                        f'Ask for the current {d["label"]}.', last, RE._source_title(last), conf, d["key"]))
            else:
                claims.append(RE._claim("custom", RE.UNVERIFIABLE, project, t, src, heard[0][1], d["label"], "No approved value",
                                        f'{d["label"]} was mentioned, but no approved value is stored for {project["official_name"]}. '
                                        "This is not a confirmed error.", f'Add the approved {d["label"]}.', rule=d["key"]))
            if d["ftype"] == "money":
                consumed.update(v for v, _ in heard)
            continue
        if d["ftype"] == "yes_no":
            said = polarity(tf, d)
            ok_fact = next((f for f in scoped if f["value_text"] == said), None)
            fact = ok_fact or scoped[0]
            used.append(fact)
            if ok_fact:
                claims.append(RE._claim("custom", RE.VERIFIED, project, t, src, d["label"], f'{d["label"]}: {said}', fact["value_text"],
                                        f'Matches the approved answer for {d["label"]}.', "", fact, RE._source_title(fact), conf, d["key"]))
            elif fact["value_text"] == "no":
                claims.append(RE._claim("custom", RE.VIOLATION, project, t, src, d["label"], f'{d["label"]}: yes', "no",
                                        f'The content offers {d["label"]}, but it is not approved for {project["official_name"]}.',
                                        f'Remove the {d["label"]} claim.', fact, RE._source_title(fact), conf, d["key"]))
            else:
                claims.append(RE._claim("custom", RE.REVIEW, project, t, src, d["label"], f'{d["label"]}: no', "yes",
                                        f'The content seems to say there is no {d["label"]}, but it is approved as available.',
                                        "A person should check the wording.", fact, RE._source_title(fact), conf, d["key"]))
            continue
        if d["ftype"] == "text":
            allowed = [(f, w) for f in scoped for w in _list(f["value_text"])]
            hit = next(((f, w) for f, w in allowed if mentions(tf, w)), None)
            fact = hit[0] if hit else scoped[0]
            used.append(fact)
            if hit:
                claims.append(RE._claim("custom", RE.VERIFIED, project, t, src, hit[1], d["label"], fact["value_text"],
                                        f'Uses approved wording for {d["label"]}.', "", fact, RE._source_title(fact), conf, d["key"]))
            else:
                claims.append(RE._claim("custom", RE.REVIEW, project, t, src, d["label"], d["label"], fact["value_text"],
                                        f'{d["label"]} is mentioned, but none of the approved wording ({fact["value_text"]}) was found.',
                                        "A person should check what was said.", fact, RE._source_title(fact), conf, d["key"]))
            continue
        for value, spoken in heard:
            if d["ftype"] == "date":
                good = next((f for f in scoped if _date_cmp(value, f["value_text"], d["direction"])), None)
                fact = good or scoped[0]
                used.append(fact)
                if good:
                    claims.append(RE._claim("custom", RE.VERIFIED, project, t, src, spoken, value, fact["value_text"],
                                            f'Matches the approved {d["label"]}.', "", fact, RE._source_title(fact), conf, d["key"]))
                else:
                    claims.append(RE._claim("custom", RE.VIOLATION if conf is None or conf >= 0.65 else RE.REVIEW, project, t, src,
                                            spoken, value, fact["value_text"],
                                            f'Said {spoken} for {d["label"]}, but the approved value is {fact["value_text"]}.',
                                            f'Use {fact["value_text"]}.', fact, RE._source_title(fact), conf, d["key"]))
                continue
            tol = max(0.01, 0.005 * abs(value)) if d["ftype"] == "money" else 0.01
            good = next((f for f in scoped if f["value_num"] is not None and compare(value, f["value_num"], d["direction"], tol)), None)
            fact = good or min(scoped, key=lambda f: abs((f["value_num"] or 0) - value))
            used.append(fact)
            if d["ftype"] == "money":
                consumed.add(value)
            approved = _fmt(d, fact["value_num"])
            if good:
                note = "" if abs(value - (good["value_num"] or 0)) <= tol else f' ({DIRECTIONS[d["direction"]].lower()})'
                claims.append(RE._claim("custom", RE.VERIFIED, project, t, src, spoken, _fmt(d, value), approved,
                                        f'Within the approved {d["label"]}{note}.', "", fact, RE._source_title(fact), conf, d["key"]))
            else:
                verdict = RE.VIOLATION if conf is None or conf >= 0.65 else RE.REVIEW
                claims.append(RE._claim("custom", verdict, project, t, src, spoken, _fmt(d, value), approved,
                                        f'Said {_fmt(d, value)} for {d["label"]}, but the approved {d["label"]} is {approved} '
                                        f'({DIRECTIONS[d["direction"]].lower()}).',
                                        f'Use {approved}.', fact, RE._source_title(fact), conf, d["key"]))
    # a percentage with no named fact: if the product has approved percentages, an unknown one needs a person
    pct_defs = [d for d in defs if d["ftype"] == "percent"]
    if pct_defs:
        known = []
        for d in pct_defs:
            known += [f["value_num"] for f in RE._q("SELECT * FROM facts WHERE project_id=? AND key=?", (project["id"], d["key"]))
                      if RE._is_current(f) and f["value_num"] is not None]
        for p in pct:
            if p["value"] in used_pct or not known:
                continue
            if any(abs(p["value"] - k) <= 0.01 for k in known):
                continue
            claims.append(RE._claim("custom", RE.UNVERIFIABLE, project, t, src, p["spoken"], f'{p["value"]:g}%', "Not an approved figure",
                                    f'{p["value"]:g}% is not one of the approved percentages for {project["official_name"]}, and the '
                                    "content does not say what it refers to.", "A person should check what this percentage is for.",
                                    conf=conf, rule="percent"))
    return claims, consumed
