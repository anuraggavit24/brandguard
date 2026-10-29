"""BrandGuard accounts: real sign-up, login, company creation and invites.

* Passwords are stored as salted scrypt hashes. Plain passwords are never stored or logged.
* A company is created by its first user, who becomes its builder (admin).
* An owner invites people by email address. Each invite is a single-use link bound to that address, expires in 7 days,
  and carries a role and the exact projects the person may use. Only a hash of the link token is stored.
* The demo logins (/enter/...) stay as a separate "try the demo" mode. Demo users have no password and cannot sign in here.
"""

import base64
import hashlib
import hmac
import json
import re
import secrets
import sqlite3
import threading
import time
from datetime import datetime, timedelta

DB_PATH = None

KINDS = {  # invite kind -> (label shown to people, account role)
    "partner": ("Channel partner", "submitter"),
    "freelancer": ("Freelancer", "submitter"),
    "agency": ("Agency", "submitter"),
    "manager": ("Manager (full builder access)", "admin"),
}
INVITE_DAYS = 7
MIN_PASSWORD = 10
EMAIL_RE = re.compile(r"^[^@\s]{1,64}@[^@\s]{1,190}\.[^@\s]{2,}$")
_SCRYPT = dict(n=2 ** 14, r=8, p=1, dklen=32)

_fails = {}            # login throttle: key -> [timestamps]
_lock = threading.Lock()
MAX_FAILS, WINDOW = 5, 300


# ------------------------------------------------------------------ storage
def setup(db_path):
    global DB_PATH
    DB_PATH = db_path
    con = sqlite3.connect(DB_PATH)
    for sql in ("ALTER TABLE users ADD COLUMN pw_hash TEXT", "ALTER TABLE users ADD COLUMN created_at TEXT",
                "ALTER TABLE memberships ADD COLUMN kind TEXT", "ALTER TABLE memberships ADD COLUMN joined_at TEXT",
                "ALTER TABLE memberships ADD COLUMN all_projects INTEGER DEFAULT 0",
                "ALTER TABLE users ADD COLUMN pw_version INTEGER DEFAULT 0", "ALTER TABLE users ADD COLUMN notify INTEGER DEFAULT 1"):
        try:
            con.execute(sql)
        except sqlite3.OperationalError:
            pass
    con.execute("""CREATE TABLE IF NOT EXISTS password_resets (
        id INTEGER PRIMARY KEY AUTOINCREMENT, token_hash TEXT UNIQUE NOT NULL, user_id INTEGER NOT NULL,
        created_at TEXT, expires_at TEXT, used_at TEXT)""")
    con.execute("""CREATE TABLE IF NOT EXISTS invites (
        id INTEGER PRIMARY KEY AUTOINCREMENT, token_hash TEXT UNIQUE NOT NULL, brand_id INTEGER NOT NULL,
        email TEXT NOT NULL, kind TEXT NOT NULL, project_ids TEXT, invited_by TEXT, created_at TEXT,
        expires_at TEXT, used_at TEXT, used_by INTEGER, revoked_at TEXT)""")
    con.commit()
    con.close()


def _con():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con


def _rows(sql, args=()):
    con = _con()
    try:
        return con.execute(sql, args).fetchall()
    finally:
        con.close()


def _run(sql, args=()):
    con = _con()
    try:
        cur = con.execute(sql, args)
        con.commit()
        return cur.lastrowid, cur.rowcount
    finally:
        con.close()


def _now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


# --------------------------------------------------------------- passwords
def hash_password(pw):
    salt = secrets.token_bytes(16)
    h = hashlib.scrypt(pw.encode(), salt=salt, **_SCRYPT)
    return "scrypt$" + base64.b64encode(salt).decode() + "$" + base64.b64encode(h).decode()


def verify_password(pw, stored):
    try:
        scheme, salt, h = (stored or "").split("$")
        if scheme != "scrypt":
            return False
        calc = hashlib.scrypt((pw or "").encode(), salt=base64.b64decode(salt), **_SCRYPT)
        return hmac.compare_digest(calc, base64.b64decode(h))
    except Exception:
        return False


_DUMMY = hash_password("not-a-real-password")


def check_password_rules(pw):
    """Returns an error message, or '' if the password is acceptable."""
    if len(pw or "") < MIN_PASSWORD:
        return f"Use at least {MIN_PASSWORD} characters."
    if (pw or "").lower() in {"password123", "1234567890", "qwertyuiop", "password12", "passw0rd123"}:
        return "That password is too common."
    return ""


def clean_email(s):
    s = (s or "").strip().lower()
    return s if EMAIL_RE.match(s) else ""


# ------------------------------------------------------------------ throttle
def _throttle_key(email, ip):
    return f"{(email or '').lower()}|{ip or ''}"


def too_many_attempts(email, ip):
    key, now = _throttle_key(email, ip), time.time()
    with _lock:
        _fails[key] = [t for t in _fails.get(key, []) if now - t < WINDOW]
        return len(_fails[key]) >= MAX_FAILS


def _note_fail(email, ip):
    with _lock:
        _fails.setdefault(_throttle_key(email, ip), []).append(time.time())


def _clear_fails(email, ip):
    with _lock:
        _fails.pop(_throttle_key(email, ip), None)


# --------------------------------------------------------------- accounts
def email_taken(email):
    return bool(_rows("SELECT 1 FROM users WHERE lower(email)=?", (email.lower(),)))


def _new_registry(company, industry=""):
    import packs
    prop = industry == "real_estate"
    reg = {"brand": company, "banned_phrases": [], "confidential": [], "allowed_contacts": [],
           "domain": "property" if prop else "general",
           "glossary": [company] + (["RERA", "BHK", "possession"] if prop else []) + ["crore", "lakh", "कोटी", "लाख"]}
    packs.apply(reg, [industry] if industry else [])
    return reg


def create_company(company, owner_name, email, password, industry=""):
    """Create a company and its first builder. Returns (user_id, brand_id) or raises ValueError with a clear message."""
    company, owner_name, email = (company or "").strip(), (owner_name or "").strip(), clean_email(email)
    if not (2 <= len(company) <= 80):
        raise ValueError("Enter your company name (2 to 80 characters).")
    if not (1 <= len(owner_name) <= 80):
        raise ValueError("Enter your name.")
    if not email:
        raise ValueError("Enter a valid email address.")
    bad = check_password_rules(password)
    if bad:
        raise ValueError(bad)
    if email_taken(email):
        raise ValueError("An account with that email already exists. Sign in instead.")
    con = _con()
    try:
        bid = con.execute("INSERT INTO brands (name, registry) VALUES (?,?)",
                          (company, json.dumps(_new_registry(company, industry), ensure_ascii=False))).lastrowid
        uid = con.execute("INSERT INTO users (name, email, role, brand_id, pw_hash, created_at) VALUES (?,?,?,?,?,?)",
                          (owner_name, email, "admin", bid, hash_password(password), _now())).lastrowid
        con.commit()
    finally:
        con.close()
    return uid, bid


def authenticate(email, password, ip=""):
    """Returns the user row, None on a wrong login, or raises ValueError when throttled."""
    email = clean_email(email)
    if too_many_attempts(email, ip):
        raise ValueError("Too many failed attempts. Wait a few minutes and try again.")
    rows = _rows("SELECT * FROM users WHERE lower(email)=?", (email,)) if email else []
    user = rows[0] if rows else None
    stored = user["pw_hash"] if user and user["pw_hash"] else _DUMMY      # same work either way
    ok = verify_password(password, stored) and bool(user and user["pw_hash"])
    if not ok:
        _note_fail(email, ip)
        return None
    _clear_fails(email, ip)
    return user


# ------------------------------------------------------------------ invites
def _hash_token(tok):
    return hashlib.sha256(tok.encode()).hexdigest()


def create_invite(brand_id, email, kind, project_ids, invited_by, all_projects=False):
    """Returns the raw token (shown once). Raises ValueError on bad input.
    all_projects: the person may use every project of the company, including ones added later."""
    email = clean_email(email)
    if not email:
        raise ValueError("Enter a valid email address.")
    if kind not in KINDS:
        raise ValueError("Choose a role.")
    if KINDS[kind][1] == "submitter" and not project_ids and not all_projects:
        raise ValueError("Choose what this person may promote: tick \"All projects\" or at least one project.")
    existing = _rows("SELECT * FROM users WHERE lower(email)=?", (email,))
    if existing and existing[0]["role"] == "admin" and existing[0]["brand_id"] == brand_id:
        raise ValueError("That person is already a builder in your company.")
    tok = secrets.token_urlsafe(32)
    _run("""INSERT INTO invites (token_hash, brand_id, email, kind, project_ids, invited_by, created_at, expires_at)
            VALUES (?,?,?,?,?,?,?,?)""",
         (_hash_token(tok), brand_id, email, kind, json.dumps(["*"] if all_projects else [int(p) for p in project_ids]),
          invited_by, _now(),
          (datetime.now() + timedelta(days=INVITE_DAYS)).strftime("%Y-%m-%d %H:%M:%S")))
    return tok


def get_invite(tok):
    """The invite row if the link is valid (not used, revoked or expired), else None."""
    if not tok or len(tok) > 100:
        return None
    r = _rows("""SELECT i.*, b.name AS company FROM invites i JOIN brands b ON b.id=i.brand_id WHERE token_hash=?""",
              (_hash_token(tok),))
    if not r:
        return None
    inv = r[0]
    if inv["used_at"] or inv["revoked_at"] or inv["expires_at"] < _now():
        return None
    return inv


def accept_invite(tok, name, password):
    """Consume an invite. Creates the account, or signs in the existing one. Returns (user_id, brand_id, kind).
    Raises ValueError with a clear message."""
    inv = get_invite(tok)
    if not inv:
        raise ValueError("This invite link is not valid any more. Ask for a new one.")
    kind = inv["kind"]
    role = KINDS[kind][1]
    existing = _rows("SELECT * FROM users WHERE lower(email)=?", (inv["email"],))
    if existing:
        user = existing[0]
        if not user["pw_hash"] or not verify_password(password, user["pw_hash"]):
            raise ValueError("That email already has an account. Enter its password to accept the invite.")
        if user["role"] != role:
            raise ValueError("This email is already used for a different kind of account, so it cannot accept this invite.")
        uid = user["id"]
    else:
        name = (name or "").strip()
        if not name:
            raise ValueError("Enter your name.")
        bad = check_password_rules(password)
        if bad:
            raise ValueError(bad)
        uid, _n = _run("INSERT INTO users (name, email, role, brand_id, pw_hash, created_at) VALUES (?,?,?,?,?,?)",
                       (name[:80], inv["email"], role, inv["brand_id"] if role == "admin" else None,
                        hash_password(password), _now()))
    if role == "submitter" and not _rows("SELECT 1 FROM memberships WHERE user_id=? AND brand_id=?", (uid, inv["brand_id"])):
        _run("INSERT INTO memberships (user_id, brand_id, kind, joined_at) VALUES (?,?,?,?)",
             (uid, inv["brand_id"], kind, _now()))
    _id, n = _run("UPDATE invites SET used_at=?, used_by=? WHERE id=? AND used_at IS NULL", (_now(), uid, inv["id"]))
    if not n:
        raise ValueError("This invite link was just used.")
    return uid, inv["brand_id"], kind


# ------------------------------------------------------------ one-time codes (OTP)
OTP_MINUTES, OTP_TRIES, OTP_RESEND_SECONDS = 10, 5, 60


def _otp_table():
    _run("""CREATE TABLE IF NOT EXISTS otps (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, purpose TEXT,
            code_hash TEXT, created_at TEXT, expires_at TEXT, attempts INTEGER DEFAULT 0, used_at TEXT)""")


def new_otp(user_id, purpose):
    """Returns (code, None), or (None, seconds to wait) if a code was sent less than a minute ago."""
    _otp_table()
    last = _rows("SELECT created_at FROM otps WHERE user_id=? AND purpose=? ORDER BY id DESC LIMIT 1", (user_id, purpose))
    if last:
        age = (datetime.now() - datetime.strptime(last[0]["created_at"], "%Y-%m-%d %H:%M:%S")).total_seconds()
        if age < OTP_RESEND_SECONDS:
            return None, int(OTP_RESEND_SECONDS - age) + 1
    _run("UPDATE otps SET used_at=? WHERE user_id=? AND purpose=? AND used_at IS NULL", (_now(), user_id, purpose))
    code = f"{secrets.randbelow(1000000):06d}"
    _run("INSERT INTO otps (user_id, purpose, code_hash, created_at, expires_at) VALUES (?,?,?,?,?)",
         (user_id, purpose, _hash_token(f"{user_id}:{purpose}:{code}"), _now(),
          (datetime.now() + timedelta(minutes=OTP_MINUTES)).strftime("%Y-%m-%d %H:%M:%S")))
    return code, None


def check_otp(user_id, purpose, code):
    """True if the code is right. Each code allows a few tries, expires, and works once."""
    _otp_table()
    r = _rows("SELECT * FROM otps WHERE user_id=? AND purpose=? AND used_at IS NULL ORDER BY id DESC LIMIT 1", (user_id, purpose))
    if not r or r[0]["expires_at"] < _now() or r[0]["attempts"] >= OTP_TRIES:
        return False
    row = r[0]
    code = re.sub(r"\D", "", code or "")
    if hmac.compare_digest(row["code_hash"], _hash_token(f"{user_id}:{purpose}:{code}")):
        _run("UPDATE otps SET used_at=? WHERE id=?", (_now(), row["id"]))
        return True
    _run("UPDATE otps SET attempts=attempts+1 WHERE id=?", (row["id"],))
    return False


# ------------------------------------------------------------ password reset
RESET_MINUTES = 60


def request_reset(email, cooldown_minutes):
    """Returns (user_row, raw_token) when a reset email should be sent, or (None, reason) when not.
    reason is 'unknown' (no such account, or a demo account without a password) or 'cooldown'.
    The caller shows the same message either way, so nobody can find out which emails have accounts."""
    email = clean_email(email)
    rows = _rows("SELECT * FROM users WHERE lower(email)=?", (email,)) if email else []
    if not rows or not rows[0]["pw_hash"]:
        return None, "unknown"
    user = rows[0]
    since = (datetime.now() - timedelta(minutes=max(1, int(cooldown_minutes)))).strftime("%Y-%m-%d %H:%M:%S")
    if _rows("SELECT 1 FROM password_resets WHERE user_id=? AND created_at>=?", (user["id"], since)):
        return None, "cooldown"
    _run("UPDATE password_resets SET used_at=? WHERE user_id=? AND used_at IS NULL", (_now(), user["id"]))  # one live link
    tok = secrets.token_urlsafe(32)
    _run("INSERT INTO password_resets (token_hash, user_id, created_at, expires_at) VALUES (?,?,?,?)",
         (_hash_token(tok), user["id"], _now(), (datetime.now() + timedelta(minutes=RESET_MINUTES)).strftime("%Y-%m-%d %H:%M:%S")))
    return user, tok


def get_reset(tok):
    if not tok or len(tok) > 100:
        return None
    r = _rows("""SELECT r.*, u.email, u.name FROM password_resets r JOIN users u ON u.id=r.user_id WHERE token_hash=?""",
              (_hash_token(tok),))
    if not r or r[0]["used_at"] or r[0]["expires_at"] < _now():
        return None
    return r[0]


def complete_reset(tok, password):
    """Set the new password. Signs the user out everywhere else. Returns the user id or raises ValueError."""
    r = get_reset(tok)
    if not r:
        raise ValueError("This reset link is not valid any more. Ask for a new one.")
    bad = check_password_rules(password)
    if bad:
        raise ValueError(bad)
    _id, n = _run("UPDATE password_resets SET used_at=? WHERE id=? AND used_at IS NULL", (_now(), r["id"]))
    if not n:
        raise ValueError("This reset link was just used.")
    _run("UPDATE users SET pw_hash=?, pw_version=COALESCE(pw_version,0)+1 WHERE id=?", (hash_password(password), r["user_id"]))
    _clear_fails(r["email"], "")
    return r["user_id"]


def change_password(user_id, current, new):
    rows = _rows("SELECT * FROM users WHERE id=?", (user_id,))
    if not rows or not rows[0]["pw_hash"] or not verify_password(current, rows[0]["pw_hash"]):
        raise ValueError("The current password is wrong.")
    bad = check_password_rules(new)
    if bad:
        raise ValueError(bad)
    _run("UPDATE users SET pw_hash=?, pw_version=COALESCE(pw_version,0)+1 WHERE id=?", (hash_password(new), user_id))


def revoke_invite(brand_id, invite_id):
    _id, n = _run("UPDATE invites SET revoked_at=? WHERE id=? AND brand_id=? AND used_at IS NULL AND revoked_at IS NULL",
                  (_now(), invite_id, brand_id))
    return n > 0


def pending_invites(brand_id):
    return _rows("""SELECT * FROM invites WHERE brand_id=? AND used_at IS NULL AND revoked_at IS NULL AND expires_at>=?
                    ORDER BY id DESC""", (brand_id, _now()))


def members(brand_id):
    """Everyone with access to this company: builders and invited submitters."""
    return _rows("""SELECT u.id, u.name, u.email, 'builder' AS kind, u.created_at AS joined FROM users u
                    WHERE u.role='admin' AND u.brand_id=?
                    UNION ALL
                    SELECT u.id, u.name, u.email, COALESCE(m.kind, 'partner'), m.joined_at FROM memberships m
                    JOIN users u ON u.id=m.user_id WHERE m.brand_id=? AND u.role='submitter'
                    ORDER BY 4, 2""", (brand_id, brand_id))


def remove_member(brand_id, user_id):
    """Take a submitter out of the company. Their project access is revoked by the caller."""
    _id, n = _run("DELETE FROM memberships WHERE user_id=? AND brand_id=?", (user_id, brand_id))
    return n > 0
