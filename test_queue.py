"""Checks for the bulk upload queue. Run: python test_queue.py"""
import os, subprocess, sys, tempfile
os.environ["DATA_DIR"] = tempfile.mkdtemp()
os.environ["BG_WORKER"] = "0"          # the tests drive the worker by hand
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import main
import jobs as JOBS
from fastapi.testclient import TestClient

wav = os.path.join(os.environ["DATA_DIR"], "t.mp4")
subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i", "sine=frequency=440:duration=3", "-f", "lavfi", "-i",
                "color=c=navy:s=320x240:d=3", "-shortest", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", wav],
               capture_output=True)
SCRIPTS = {}
main.transcribe = lambda w, l, g: [{"start": float(i), "end": float(i) + 1, "text": t, "conf": 0.95}
                                   for i, t in enumerate("Welcome to Demo Heights Wakad||Our 2 BHK is 1.3 crore".split("||"))]
fails = []


def check(name, cond, extra=""):
    print(("PASS " if cond else "FAIL ") + name + (f"  [{extra}]" if extra and not cond else ""))
    if not cond:
        fails.append(name)


def files(n, name="v{}.mp4"):
    data = open(wav, "rb").read()
    return [("files", (name.format(i), data, "video/mp4")) for i in range(n)]


with TestClient(main.app) as c:
    c.get("/enter/partner")
    check("bulk page opens", c.get("/bulk").status_code == 200)
    r = c.post("/bulk", data={"brand_id": "1", "language": "en", "project_id": ""}, files=files(3), follow_redirects=False)
    check("upload returns at once with a batch page", r.status_code == 303 and "/bulk/" in r.headers["location"])
    bid = int(r.headers["location"].rsplit("/", 1)[-1])
    js = JOBS.batch_jobs(bid)
    check("all files stored and queued, none reviewed yet", len(js) == 3 and all(j["status"] == "QUEUED" for j in js))
    check("nothing was reviewed during the upload", main.q("SELECT COUNT(*) c FROM submissions")[0]["c"] == 0)
    page = c.get(f"/bulk/{bid}").text
    check("progress page shows waiting and refreshes itself", "Waiting" in page and "refresh" in page)
    check("queue position shown", "ahead" in page)

    check("worker handles exactly one job per step", main.run_queue_once() is True
          and [j["status"] for j in JOBS.batch_jobs(bid)] == ["DONE", "QUEUED", "QUEUED"])
    check("no summary sent while jobs are still waiting", not main.q("SELECT 1 FROM audit WHERE action='BATCH_DONE'"))
    main.run_queue_once(); main.run_queue_once()
    js = JOBS.batch_jobs(bid)
    check("all jobs finished with a stored review", all(j["status"] == "DONE" and j["sub_id"] for j in js), str([dict(j)["status"] for j in js]))
    check("each file became a normal submission", main.q("SELECT COUNT(*) c FROM submissions")[0]["c"] == 3)
    sm = JOBS.summary(bid)
    check("summary counts add up", sm["total"] == 3 and sm["waiting"] == 0 and sm["approved"] + sm["rejected"] + sm["check"] == 3, str(sm))
    check("completion logged exactly once", len(main.q("SELECT 1 FROM audit WHERE action='BATCH_DONE'")) == 1)
    main.run_queue_once()
    check("completion is not repeated", len(main.q("SELECT 1 FROM audit WHERE action='BATCH_DONE'")) == 1)
    page = c.get(f"/bulk/{bid}").text
    check("done page has reports and no refresh", "Open report" in page and 'http-equiv="refresh"' not in page)

    # failure does not stop the queue
    r = c.post("/bulk", data={"brand_id": "1", "language": "en", "project_id": ""}, files=files(2, "w{}.mp4"), follow_redirects=False)
    b2 = int(r.headers["location"].rsplit("/", 1)[-1])
    first = JOBS.batch_jobs(b2)[0]
    os.remove(first["path"])
    main.run_queue_once(); main.run_queue_once()
    js = JOBS.batch_jobs(b2)
    check("a missing file fails alone, the next one still runs", js[0]["status"] == "FAILED" and js[1]["status"] == "DONE", str([j["status"] for j in js]))
    check("failure reason is shown", "missing" in c.get(f"/bulk/{b2}").text)
    check("a batch with a failure still completes", JOBS.batch_done(b2))

    # limits and validation
    r = c.post("/bulk", data={"brand_id": "1", "language": "en", "project_id": ""}, files=files(main.BULK_MAX_FILES + 1))
    check("too many files refused", "at most" in r.text)
    r = c.post("/bulk", data={"brand_id": "1", "language": "en", "project_id": ""},
               files=[("files", ("a.exe", b"MZ", "application/octet-stream"))])
    check("wrong file type refused", "None of the files" in r.text)
    r = c.post("/bulk", data={"brand_id": "1", "language": "en", "project_id": ""},
               files=files(1) + [("files", ("a.txt", b"hello", "text/plain"))], follow_redirects=False)
    check("one good and one bad file: good one is queued", r.status_code == 303)

    # restart behaviour
    b3 = int(r.headers["location"].rsplit("/", 1)[-1])
    j = JOBS.claim_next()
    check("a claimed job is marked running", j["status"] == "PROCESSING")
    JOBS.reset_stuck()
    check("after a restart a running job goes back to the queue", JOBS.batch_jobs(b3)[0]["status"] == "QUEUED")
    main.ex("UPDATE jobs SET status='PROCESSING', attempts=3 WHERE id=?", (j["id"],))
    JOBS.reset_stuck()
    check("a job that keeps crashing the server is failed, not retried forever", JOBS.batch_jobs(b3)[0]["status"] == "FAILED")

    # access control
    check("pending count is per user", JOBS.pending_count(3) == 0)

with TestClient(main.app) as other:
    other.get("/enter/fvideoancer")
    check("a different submitter cannot open the batch", other.get(f"/bulk/{bid}", follow_redirects=False).status_code == 303)
    check("a logged-out visitor cannot open the batch", TestClient(main.app).get(f"/bulk/{bid}", follow_redirects=False).status_code == 303)
with TestClient(main.app) as adm:
    adm.get("/enter/admin")
    check("the company's builder can open it", adm.get(f"/bulk/{bid}", follow_redirects=False).status_code == 200)
    check("builder has no bulk upload form", adm.get("/bulk", follow_redirects=False).status_code == 303)

print("\n%d failed" % len(fails) if fails else "\nALL PASSED")
sys.exit(1 if fails else 0)
