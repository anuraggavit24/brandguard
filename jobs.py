"""BrandGuard background queue for bulk uploads.

Videos are stored first, then one worker reviews them one at a time, so a free server is never asked to
process many videos at once. The queue lives in the database: after a restart, unfinished jobs resume
(a job that crashed the server three times is marked failed instead of looping forever).
A batch is complete when none of its jobs is queued or running; the person is then emailed a summary once.
"""

import sqlite3
import threading
import time
from datetime import datetime

DB_PATH = None
MAX_ATTEMPTS = 3
_worker = {"thread": None, "stop": False}


def setup(db_path):
    global DB_PATH
    DB_PATH = db_path
    con = sqlite3.connect(DB_PATH)
    con.execute("""CREATE TABLE IF NOT EXISTS batches (
        id INTEGER PRIMARY KEY AUTOINCREMENT, brand_id INTEGER NOT NULL, user_id INTEGER NOT NULL,
        created_at TEXT, notified_at TEXT)""")
    con.execute("""CREATE TABLE IF NOT EXISTS jobs (
        id INTEGER PRIMARY KEY AUTOINCREMENT, batch_id INTEGER NOT NULL, brand_id INTEGER NOT NULL, user_id INTEGER NOT NULL,
        filename TEXT, path TEXT, sha TEXT, language TEXT, hint_pid INTEGER, status TEXT DEFAULT 'QUEUED',
        sub_id INTEGER, error TEXT, attempts INTEGER DEFAULT 0, created_at TEXT, started_at TEXT, finished_at TEXT)""")
    con.commit()
    con.close()


def _con():
    con = sqlite3.connect(DB_PATH, timeout=30)
    con.row_factory = sqlite3.Row
    return con


def _now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


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


def pending_count(user_id):
    return _rows("SELECT COUNT(*) AS c FROM jobs WHERE user_id=? AND status IN ('QUEUED','PROCESSING')", (user_id,))[0]["c"]


def create_batch(brand_id, user_id, items, language, hint_pid):
    """items: [{filename, path, sha}]. Returns the batch id."""
    con = _con()
    try:
        bid = con.execute("INSERT INTO batches (brand_id, user_id, created_at) VALUES (?,?,?)",
                          (brand_id, user_id, _now())).lastrowid
        for it in items:
            con.execute("""INSERT INTO jobs (batch_id, brand_id, user_id, filename, path, sha, language, hint_pid, created_at)
                           VALUES (?,?,?,?,?,?,?,?,?)""",
                        (bid, brand_id, user_id, it["filename"], str(it["path"]), it["sha"], language, hint_pid, _now()))
        con.commit()
        return bid
    finally:
        con.close()


def reset_stuck():
    """After a restart: jobs left PROCESSING go back to the queue; too many crashes means failed."""
    _run("UPDATE jobs SET status='FAILED', error='The server stopped while reviewing this file several times.', finished_at=? "
         "WHERE status='PROCESSING' AND attempts>=?", (_now(), MAX_ATTEMPTS))
    _run("UPDATE jobs SET status='QUEUED' WHERE status='PROCESSING'")


def claim_next():
    r = _rows("SELECT * FROM jobs WHERE status='QUEUED' ORDER BY id LIMIT 1")
    if not r:
        return None
    _id, n = _run("UPDATE jobs SET status='PROCESSING', started_at=?, attempts=attempts+1 WHERE id=? AND status='QUEUED'",
                  (_now(), r[0]["id"]))
    return _rows("SELECT * FROM jobs WHERE id=?", (r[0]["id"],))[0] if n else None


def finish(job_id, sub_id=None, error=None):
    _run("UPDATE jobs SET status=?, sub_id=?, error=?, finished_at=? WHERE id=?",
         ("FAILED" if error else "DONE", sub_id, (error or "")[:300] or None, _now(), job_id))


def get_batch(batch_id):
    r = _rows("SELECT * FROM batches WHERE id=?", (batch_id,))
    return r[0] if r else None


def batch_jobs(batch_id):
    return _rows("""SELECT j.*, s.status AS sub_status, s.verdict AS verdict FROM jobs j
                    LEFT JOIN submissions s ON s.id=j.sub_id WHERE j.batch_id=? ORDER BY j.id""", (batch_id,))


def ahead_of(job):
    """How many jobs are queued or running before this one."""
    return _rows("SELECT COUNT(*) AS c FROM jobs WHERE status IN ('QUEUED','PROCESSING') AND id<?", (job["id"],))[0]["c"]


def batch_done(batch_id):
    return _rows("SELECT COUNT(*) AS c FROM jobs WHERE batch_id=? AND status IN ('QUEUED','PROCESSING')", (batch_id,))[0]["c"] == 0


def summary(batch_id):
    """Counts by outcome for a batch."""
    out = {"total": 0, "waiting": 0, "approved": 0, "rejected": 0, "check": 0, "failed": 0}
    for j in batch_jobs(batch_id):
        out["total"] += 1
        if j["status"] in ("QUEUED", "PROCESSING"):
            out["waiting"] += 1
        elif j["status"] == "FAILED":
            out["failed"] += 1
        elif j["sub_status"] in ("AUTO_APPROVED", "APPROVED"):
            out["approved"] += 1
        elif j["sub_status"] in ("REJECTED", "BLOCKED", "REJECTED_FINAL"):
            out["rejected"] += 1
        else:
            out["check"] += 1
    return out


def recent_batches(user_id, limit=10):
    return _rows("SELECT * FROM batches WHERE user_id=? ORDER BY id DESC LIMIT ?", (user_id, limit))


def unnotified_done_batches():
    return [b for b in _rows("SELECT * FROM batches WHERE notified_at IS NULL ORDER BY id") if batch_done(b["id"])]


def mark_notified(batch_id):
    _run("UPDATE batches SET notified_at=? WHERE id=? AND notified_at IS NULL", (_now(), batch_id))


# ------------------------------------------------------------------ worker
def run_once(process, notify=None):
    """Handle one queued job, then send any due batch summaries. Returns True if a job was processed."""
    job = claim_next()
    did = False
    if job:
        did = True
        try:
            sub_id, err = process(job)
        except Exception as ex_:                       # one bad file must never stop the queue
            sub_id, err = None, "Something went wrong while reviewing this file."
        finish(job["id"], sub_id, err)
    if notify:
        for b in unnotified_done_batches():
            mark_notified(b["id"])
            try:
                notify(b)
            except Exception:
                pass
    return did


def start(process, notify=None, idle=3.0):
    """Start the single background worker thread (once)."""
    if _worker["thread"] and _worker["thread"].is_alive():
        return

    def loop():
        while not _worker["stop"]:
            try:
                busy = run_once(process, notify)
            except Exception:
                busy = False
            if not busy:
                time.sleep(idle)

    _worker["stop"] = False
    t = threading.Thread(target=loop, name="bulk-worker", daemon=True)
    _worker["thread"] = t
    t.start()


def stop():
    _worker["stop"] = True
