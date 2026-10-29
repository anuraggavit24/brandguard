"""Checks that uploads are deleted after review and that menu labels fit the company. Run: python test_cleanup.py"""
import os, subprocess, sys, tempfile, time
os.environ["DATA_DIR"] = tempfile.mkdtemp()
os.environ.pop("GROQ_API_KEY", None)
os.environ.pop("KEEP_UPLOADS", None)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import main
from fastapi.testclient import TestClient

fails = []


def check(name, cond, extra=""):
    print(("PASS " if cond else "FAIL ") + name + (f"  [{extra}]" if extra and not cond else ""))
    if not cond:
        fails.append(name)


wav = os.path.join(os.environ["DATA_DIR"], "t.mp4")
subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i", "sine=frequency=440:duration=2", "-c:a", "aac", wav], capture_output=True)
main.transcribe = lambda w, l, g: [{"start": 0.0, "end": 1.0, "text": "Welcome to Demo Heights, 2 BHK at 1.3 crore", "conf": 0.95}]
main.OCR.read_screen = lambda *a, **k: None

with TestClient(main.app) as c:
    c.get("/enter/partner")
    r = c.post("/upload", data={"brand_id": "1", "language": "en", "project_id": ""},
               files={"file": ("t.mp4", open(wav, "rb"), "video/mp4")}, follow_redirects=False)
    check("upload is reviewed", r.headers.get("location", "").startswith("/s/"))
    check("the uploaded copy is deleted after review", list(main.UPLOAD_DIR.iterdir()) == [], str(list(main.UPLOAD_DIR.iterdir())))
    sid = int(r.headers["location"].rsplit("/", 1)[-1])
    row = main.q("SELECT * FROM submissions WHERE id=?", (sid,))[0]
    check("the report and file hash are kept", row["report"] and len(row["sha256"]) == 64)
    check("the result page still opens", c.get(f"/s/{sid}").status_code == 200)

    old = main.UPLOAD_DIR / "old.mp4"
    old.write_bytes(b"x")
    os.utime(old, (time.time() - 3 * 86400, time.time() - 3 * 86400))
    new = main.UPLOAD_DIR / "new.mp4"
    new.write_bytes(b"x")
    queued = main.UPLOAD_DIR / "queued.mp4"
    queued.write_bytes(b"x")
    os.utime(queued, (time.time() - 3 * 86400, time.time() - 3 * 86400))
    main.ex("INSERT INTO jobs (batch_id, brand_id, user_id, filename, path, sha, language, status, created_at) "
            "VALUES (999, 1, 2, 'q.mp4', ?, 'x', 'en', 'QUEUED', '2026-01-01')", (str(queued),))
    main.sweep_uploads()
    check("old leftovers are swept", not old.exists())
    check("recent files are kept", new.exists())
    check("files still waiting in the bulk queue are kept", queued.exists())

    check("submitters see 'Submit Content'", "Submit Content" in c.get("/").text)
    c.get("/logout"); c.get("/enter/admin")
    check("a property company keeps 'Projects and Facts'", "Projects and Facts" in c.get("/").text)
    c.get("/logout")
    c.post("/signup", data={"company": "Zippy", "name": "M", "email": "m@z.test", "password": "a-long-password-1", "industry": "tech"})
    page = c.get("/").text
    check("a product company sees 'Products and Facts' and 'Product Access'", "Products and Facts" in page and "Product Access" in page
          and "Projects and Facts" not in page)

print("\n%d failed" % len(fails) if fails else "\nALL PASSED")
sys.exit(1 if fails else 0)
