"""BrandGuard dispute memory.

When a builder overturns a rejection that a creator disputed, the price readings that were
rejected are remembered for that company. If the same reading shows up again, BrandGuard does
not reject it outright. It sends the claim to a person and points to the earlier case.

It never approves anything by itself and never changes approved facts or rules.
"""

import sqlite3
from datetime import datetime

from engine import extract_prices

DB_PATH = None
KINDS = ("price", "booking")


def setup(db_path):
    global DB_PATH
    DB_PATH = db_path
    con = sqlite3.connect(DB_PATH)
    con.execute("""CREATE TABLE IF NOT EXISTS dispute_cases (
        id INTEGER PRIMARY KEY AUTOINCREMENT, brand_id INTEGER NOT NULL, key TEXT NOT NULL, kind TEXT,
        heard TEXT, official TEXT, said_text TEXT, said_value INTEGER, sub_id INTEGER, builder_note TEXT,
        times INTEGER DEFAULT 1, active INTEGER DEFAULT 1, created_at TEXT, last_seen TEXT,
        UNIQUE(brand_id, key))""")
    try:
        con.execute("ALTER TABLE submissions ADD COLUMN dispute_said TEXT")
    except sqlite3.OperationalError:
        pass
    con.commit()
    con.close()


def _rows(sql, args=()):
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    try:
        return con.execute(sql, args).fetchall()
    finally:
        con.close()


def _run(sql, args=()):
    con = sqlite3.connect(DB_PATH)
    try:
        con.execute(sql, args)
        con.commit()
    finally:
        con.close()


def case_key(claim):
    return f'{claim.get("kind")}|{claim.get("normalized")}|{claim.get("official")}'


def said_value_of(text):
    found = extract_prices(text or "")
    return found[0]["value"] if found else None


def record_overturn(sub, rep, builder_note=""):
    """Call when a builder overturns a disputed rejection. Returns how many readings were remembered."""
    bad = [c for c in rep.get("claims", []) if c.get("verdict") == "VIOLATION" and c.get("kind") in KINDS]
    if not bad:
        return 0
    said_text = (sub["dispute_said"] or "").strip()
    said_value = said_value_of(said_text) if len(bad) == 1 else None
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    note = (builder_note or "").strip()[:300]
    for c in bad:
        key = case_key(c)
        have = _rows("SELECT id FROM dispute_cases WHERE brand_id=? AND key=?", (sub["brand_id"], key))
        if have:
            _run("""UPDATE dispute_cases SET times=times+1, active=1, sub_id=?, said_text=?, said_value=?,
                    builder_note=?, last_seen=? WHERE id=?""",
                 (sub["id"], said_text, said_value, note, now, have[0]["id"]))
        else:
            _run("""INSERT INTO dispute_cases (brand_id, key, kind, heard, official, said_text, said_value,
                    sub_id, builder_note, created_at, last_seen) VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                 (sub["brand_id"], key, c.get("kind"), c.get("normalized"), c.get("official"),
                  said_text, said_value, sub["id"], note, now, now))
    return len(bad)


def precedent(brand_id, claim):
    """An earlier overturned case with the same reading and the same approved price, or None."""
    rows = _rows("SELECT * FROM dispute_cases WHERE brand_id=? AND key=? AND active=1",
                 (brand_id, case_key(claim)))
    return rows[0] if rows else None


def list_cases(brand_id):
    return _rows("SELECT * FROM dispute_cases WHERE brand_id=? ORDER BY last_seen DESC", (brand_id,))


def switch_off(brand_id, case_id):
    _run("UPDATE dispute_cases SET active=0 WHERE id=? AND brand_id=?", (case_id, brand_id))