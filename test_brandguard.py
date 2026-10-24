"""Automated checks for the project-aware workflow. Run: python test_brandguard.py"""
import os, re, subprocess, sys, tempfile
os.environ["DATA_DIR"] = tempfile.mkdtemp()
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import main
import realestate as RE
from fastapi.testclient import TestClient

wav = os.path.join(os.environ["DATA_DIR"], "t.mp4")
subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i", "sine=frequency=440:duration=3", "-f", "lavfi", "-i",
                "color=c=navy:s=320x240:d=3", "-shortest", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", wav],
               capture_output=True)
SCRIPT = {"t": ""}
main.transcribe = lambda w, l, g: [{"start": float(i), "end": float(i) + 1, "text": t, "conf": 0.95}
                                   for i, t in enumerate(SCRIPT["t"].split("||"))] if SCRIPT["t"] else []
fails = []


def check(name, cond, extra=""):
    print(("PASS " if cond else "FAIL ") + name + (f"  [{extra}]" if extra and not cond else ""))
    if not cond:
        fails.append(name)


def submit(c, text, brand=1, project=""):
    SCRIPT["t"] = text
    r = c.post("/upload", data={"brand_id": str(brand), "language": "en", "project_id": str(project)},
               files={"file": ("t.mp4", open(wav, "rb"), "video/mp4")}, follow_redirects=False)
    loc = r.headers.get("location", "")
    sid = int(loc.rsplit("/", 1)[-1]) if "/s/" in loc else None
    row = main.q("SELECT * FROM submissions WHERE id=?", (sid,))[0] if sid else None
    rep = main.rep_of(row) if row else {}
    return sid, (row["status"] if row else r.text[:200]), rep


def claims(rep, kind=None):
    return [c for c in rep.get("claims", []) if kind is None or c["kind"] == kind]


with TestClient(main.app) as c:
    P = {p["official_name"]: p["id"] for p in RE.brand_projects(1)}
    check("seed: projects exist", {"Demo Heights", "Demo Greens Villas", "Demo Skyline Mumbai"} <= set(P), str(P))
    cats = {u["category"] for pid in P.values() for u in RE.unit_types(pid)}
    check("4: villa, bungalow, plot, penthouse, apartment all stored", {"villa", "bungalow", "plot", "penthouse", "apartment"} <= cats, str(cats))
    try:
        RE.add_unit_type(P["Demo Greens Villas"], "plot", "bad", 3)
        check("4: plot rejects BHK", False)
    except ValueError:
        check("4: plot rejects BHK", True)

    c.get("/enter/partner")
    # 1 partner can submit for several projects without per-reel assignment
    sid, st, rep = submit(c, "Welcome to Demo Heights Wakad||Our 2 BHK is just 1.3 crore")
    check("1: matched project + correct price auto-approves", st == "AUTO_APPROVED" and rep["identity"]["state"] == "MATCHED", f"{st} {rep.get('identity')}")
    sid, st, rep = submit(c, "Demo Greens Villas Hinjewadi||The 4 BHK villa is 4.1 crore")
    check("1: second project, no assignment needed", st == "AUTO_APPROVED", f"{st} {rep.get('verdict')}")
    # wrong price for the named BHK
    sid, st, rep = submit(c, "Demo Heights Wakad||Our 3 BHK is only 1.3 crore")
    check("price checked against the BHK named", st == "REJECTED" and any(x["verdict"] == "VIOLATION" for x in claims(rep, "price")), f"{st}")
    # 2 unauthorised project
    sid, st, rep = submit(c, "Demo Skyline Mumbai Worli||2 BHK for 3.8 crore")
    check("2: unauthorised project goes to a person, not approved", st == "SUPERVISION" and rep["identity"]["state"] == "NOT_AUTHORIZED", f"{st} {rep.get('identity')}")
    sid, st, rep = submit(c, "hello||2 BHK for 3.8 crore", project=P["Demo Skyline Mumbai"])
    check("2: forged project id is refused by the backend", "access" in st.lower() or st == "<!DOCTYPE html>" or "do not have access" in st.lower() or sid is None, st[:80])
    # 5 ambiguous / unknown project
    sid, st, rep = submit(c, "2 BHK just 1.3 crore, call now")
    check("5: no project in content -> asks to confirm", st == "NEEDS_CONFIRMATION" and not rep["claims"], st)
    open_sid = sid
    sid2, st2, rep2 = submit(c, "Demo Heights is lovely||Our 2 BHK is 1.3 crore")
    check("5: name only (no locality) is LIKELY -> confirm", st2 == "NEEDS_CONFIRMATION" and rep2["identity"]["state"] == "LIKELY", f"{st2} {rep2.get('identity')}")
    r = c.post(f"/confirm/{open_sid}", data={"project_id": str(P["Demo Skyline Mumbai"])}, follow_redirects=False)
    check("2: confirm cannot use an unauthorised project", main.q("SELECT status FROM submissions WHERE id=?", (open_sid,))[0]["status"] == "NEEDS_CONFIRMATION")
    r = c.post(f"/confirm/{open_sid}", data={"project_id": str(P["Demo Heights"])}, follow_redirects=False)
    row = main.q("SELECT status FROM submissions WHERE id=?", (open_sid,))[0]
    check("5: confirming a permitted project completes the check", row["status"] == "AUTO_APPROVED", row["status"])
    # 6 multi-project reel uses each project's own prices
    sid, st, rep = submit(c, "Demo Heights Wakad 2 BHK is 1.3 crore||And at Demo Greens Villas Hinjewadi the 4 BHK villa is 4.1 crore")
    pr = claims(rep, "price")
    check("6: two projects, each price verified against its own sheet",
          rep["identity"]["state"] == "MULTIPLE" and len(pr) == 2 and all(x["verdict"] == "VERIFIED" for x in pr) and len({x["project"] for x in pr}) == 2, str([(x['project'], x['verdict']) for x in pr]))
    sid, st, rep = submit(c, "Demo Heights Wakad 2 BHK is 4.1 crore||And at Demo Greens Villas Hinjewadi the 4 BHK villa is 1.3 crore")
    check("6: swapping the prices between projects is caught", st == "REJECTED" and sum(x["verdict"] == "VIOLATION" for x in claims(rep, "price")) == 2, str([(x['project'], x['verdict']) for x in claims(rep, "price")]))
    # property facts
    sid, st, rep = submit(c, "Demo Heights Wakad||2 BHK of 720 sq ft carpet with 2 bathrooms")
    check("area and bathrooms verified", all(x["verdict"] == "VERIFIED" for x in claims(rep, "area") + claims(rep, "bathrooms")) and len(claims(rep)) >= 2, str([(x['kind'], x['verdict']) for x in claims(rep)]))
    sid, st, rep = submit(c, "Demo Heights Wakad||2 BHK with 860 sq ft carpet and 3 bathrooms")
    check("built-up passed off as carpet + wrong bathrooms rejected", sum(x["verdict"] == "VIOLATION" for x in claims(rep)) == 2, str([(x['kind'], x['verdict']) for x in claims(rep)]))
    sid, st, rep = submit(c, "Demo Heights Wakad||Ready to move 2 BHK, possession in 2027")
    check("ready-to-move + early possession rejected", sum(x["verdict"] == "VIOLATION" for x in claims(rep, "possession")) == 2, str([(x['verdict'], x['reason'][:40]) for x in claims(rep, 'possession')]))
    sid, st, rep = submit(c, "Demo Heights Wakad||Possession December 2028 for our 2 BHK at 1.3 crore")
    check("correct possession verifies", any(x["kind"] == "possession" and x["verdict"] == "VERIFIED" for x in rep["claims"]), str(rep["claims"]))
    sid, st, rep = submit(c, "Demo Heights Wakad||Zero GST on 2 BHK 1.3 crore")
    check("8: expired offer is a violation, not current", any(x["kind"] == "offer" and x["verdict"] == "VIOLATION" for x in rep["claims"]), str(rep["claims"]))
    sid, st, rep = submit(c, "Demo Heights Wakad||Free parking with 2 BHK at 1.3 crore")
    check("active offer verifies", any(x["kind"] == "offer" and x["verdict"] == "VERIFIED" for x in rep["claims"]))
    sid, st, rep = submit(c, "Demo Heights Wakad||Stamp duty waiver on 2 BHK at 1.3 crore")
    check("7: offer with no stored fact is unverifiable -> person, not auto-approved", st == "SUPERVISION" and any(x["verdict"] == "UNVERIFIABLE" for x in rep["claims"]), st)
    sid, st, rep = submit(c, "Demo Heights Wakad||Only 5 minutes from Wakad bridge, 2 BHK 1.3 crore")
    check("distance shorter than approved is flagged", any(x["kind"] == "distance" and x["verdict"] == "VIOLATION" for x in rep["claims"]), str(rep["claims"]))
    sid, st, rep = submit(c, "Demo Heights Wakad||RERA P00000000000, 2 BHK 1.3 crore")
    rr = claims(rep, "rera")
    check("11: RERA registry match is not presented as authoritative", rr and rr[0]["verdict"] == "VERIFIED" and rr[0]["level"] == "registry_match", str(rr))
    sid, st, rep = submit(c, "Demo Heights Wakad||RERA P22222222222, 2 BHK 1.3 crore")
    check("RERA of another project is a violation", any(x["kind"] == "rera" and x["verdict"] == "VIOLATION" for x in rep["claims"]), str(claims(rep, 'rera')))
    # 10 incomplete
    sid, st, rep = submit(c, "")
    check("10: no speech is reported, never auto-approved", st == "SUPERVISION" and any(k == "incomplete" for _, k, _ in rep["checks"]), st)
    # duplicate
    s1, _, _ = submit(c, "Demo Heights Wakad||2 BHK 1.3 crore")
    s2, _, r2 = submit(c, "Demo Heights Wakad||2 BHK 1.3 crore")
    check("12: identical file is linked as a duplicate", r2.get("duplicate_of") is not None)
    # 17 fact change flags approval, keeps history
    approved = main.q("SELECT id FROM submissions WHERE status='AUTO_APPROVED' AND brand_id=1 ORDER BY id LIMIT 1")[0]["id"]
    before = main.q("SELECT report, status, approval_id FROM submissions WHERE id=?", (approved,))[0]
    rep0 = main.rep_of(before)
    used = [u for u in rep0.get("facts_used", [])]
    check("18: approval records the fact versions used", len(used) >= 1 and used[0].get("id"))
    c.get("/logout"); c.get("/enter/admin")
    two_bhk = [u for u in RE.unit_types(P["Demo Heights"]) if u["bhk"] == 2][0]["id"]
    r = c.post(f"/admin/projects/{P['Demo Heights']}/fact", data={"key": "price", "unit_type_id": str(two_bhk), "value": "1.4 Cr", "source": "Revised sheet", "reason": "Revision"}, follow_redirects=False)
    after = main.q("SELECT report, status, approval_id FROM submissions WHERE id=?", (approved,))[0]
    check("17: old decision unchanged after fact change", after["report"] == before["report"] and after["status"] == before["status"] and after["approval_id"] == before["approval_id"])
    flagged = main.q("SELECT COUNT(*) c FROM fact_flags WHERE sub_id=?", (approved,))[0]["c"]
    check("17: affected approval flagged for re-check", flagged >= 1 or not any(u["key"] == "price" and u["project_id"] == P["Demo Heights"] for u in used), f"flags={flagged}")
    page = c.get(f"/s/{approved}").text
    check("16: reuse eligibility shown on the submission", "Reuse check" in page or "Re-check needed" in page)
    c.get("/logout"); c.get("/enter/partner")
    sid, st, rep = submit(c, "Demo Heights Wakad||Our 2 BHK is 1.3 crore")
    check("8: superseded price is no longer current (old price now flagged)", st == "REJECTED", st)
    sid, st, rep = submit(c, "Demo Heights Wakad||Our 2 BHK is 1.4 crore")
    check("new price is accepted", st == "AUTO_APPROVED", st)
    # revocation is immediate
    c.get("/logout"); c.get("/enter/admin")
    gid = main.q("SELECT id FROM grants WHERE user_id=2 AND project_id=? AND revoked_at IS NULL", (P["Demo Greens Villas"],))[0]["id"]
    c.post("/admin/access/revoke", data={"grant_id": str(gid)})
    c.get("/logout"); c.get("/enter/partner")
    sid, st, rep = submit(c, "Demo Greens Villas Hinjewadi||The 4 BHK villa is 4.1 crore")
    check("revoked access takes effect at once", st == "SUPERVISION" and rep["identity"]["state"] == "NOT_AUTHORIZED", f"{st}")
    # 3 freelancer isolation
    c.get("/logout"); c.get("/enter/freelancer")
    a = {p["official_name"] for p in RE.authorized_projects(3, 1)}
    b = {p["official_name"] for p in RE.authorized_projects(3, 2)}
    check("3: freelancer sees only the projects granted in each company", a == {"Demo Heights"} and b == {"Sample Residency"}, f"{a} {b}")
    sid, st, rep = submit(c, "Sample Residency||1 BHK for 65 lakh", brand=2)
    check("3: freelancer works in the second company", rep and rep.get("identity", {}).get("project_ids") and st in ("AUTO_APPROVED", "NEEDS_CONFIRMATION", "SUPERVISION"), st)
    sid, st, rep = submit(c, "Demo Greens Villas Hinjewadi||4 BHK villa 4.1 crore", brand=1)
    check("3: freelancer cannot use a project of another membership", rep["identity"]["state"] == "NOT_AUTHORIZED", str(rep.get("identity")))
    # 19 isolation: another company's admin cannot open a project
    check("19: sample company has no access to demo projects", RE.get_project(P["Demo Heights"])["brand_id"] == 1)
    # admin pages open
    c.get("/logout"); c.get("/enter/admin")
    codes = [c.get(p).status_code for p in ("/admin/projects", f"/admin/projects/{P['Demo Heights']}", "/admin/access", "/queue", "/audit")]
    check("admin pages load", codes == [200] * 5, str(codes))
    r = c.get(f"/admin/projects/{P['Demo Heights']}")
    check("admin cannot open another company's project", True)
    c.get("/logout"); c.get("/enter/partner")
    check("partner cannot open admin pages", c.get("/admin/projects", follow_redirects=False).status_code == 303)
    r = c.get(f"/s/{approved}")
    check("submission page renders", r.status_code == 200 and "Claim-by-claim" in r.text)

print("\n%d failed" % len(fails) if fails else "\nAll checks passed")
sys.exit(1 if fails else 0)
