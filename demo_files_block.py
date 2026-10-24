# ============================================================ demo files for judges (public, no sign-in)
AUDIO_DIR = Path(__file__).resolve().parent / "demo_audio"
AUDIO_EXT = (".mp4", ".webm", ".m4a", ".mp3", ".wav", ".ogg", ".aac")
VIDEO_EXT = (".mp4", ".webm")
TEST_CLIPS = [
    {"key": "approval", "n": 1, "title": "Approval test",
     "say": "Demo Heights in Wakad, Pune. A 2 BHK home at 1 crore 30 lakh. Carpet area 720 square feet, with 2 bathrooms. "
            "Possession in December 2028.",
     "result": "Auto-Approved. The price, carpet area, bathrooms and possession all match the approved facts, so an "
               "approval ID is issued with no human needed.",
     "steps": ["Download the file below.", "Click Enter as Freelancer on the home page.",
               "Open Submit a Video, choose Demo Developer, and upload the file.",
               "The result page opens. Look at the Claim-by-claim checks table: each spoken claim is matched to an approved fact."]},
    {"key": "rejection", "n": 2, "title": "Rejection test",
     "say": "Demo Heights in Wakad. 2 BHK for 1 crore 30 lakh. Guaranteed returns, the price will double in two years. "
            "Last chance!",
     "result": "Rejected. The price is correct, but \"guaranteed returns\" and \"price will double\" are banned phrases "
               "(\"last chance\" is also flagged if the sample brand guide has been imported). Each finding shows the "
               "exact second it appeared, whether it was spoken or shown on screen, why it matters and what to change.",
     "steps": ["Download the file below.", "Enter as Freelancer and open Submit a Video.",
               "Choose Demo Developer and upload the file.",
               "Read the findings on the result page. The creator is told exactly what to fix."]},
    {"key": "dispute", "n": 3, "title": "Dispute test",
     "say": "Demo Heights, Wakad. 3 BHK flats available at 1 crore 50 lakh. Possession in December 2028.",
     "result": "Rejected, because 3 BHK is approved at 1 crore 90 lakh, not 1 crore 50 lakh. You then dispute it and "
               "play the builder to resolve it. This shows that a person always has the final word.",
     "steps": ["Download the file below, then Enter as Freelancer, open Submit a Video, choose Demo Developer and upload it.",
               "The submission is Rejected for a price mismatch. Click Raise a dispute.",
               "Write why the finding is wrong (for example: \"I quoted the offer price for a limited floor\"). "
               "Optionally type what you actually said. Click Submit dispute. The status becomes Disputed.",
               "In the sidebar, switch the demo role to Builder. Open Review Queue, then open the disputed submission.",
               "The builder sees the evidence and the creator's explanation. Click Overturn decision to approve it "
               "(an approval ID is issued), or Uphold rejection to keep it rejected (a reason is required).",
               "Switch back to Freelancer to see the outcome on the submission, and open Audit Trail as Builder to see "
               "every step recorded with who did it and when."]},
    {"key": "ocr", "file": "test", "n": 4, "title": "On-screen text (OCR) test video",
     "say": "",
     "result": "BrandGuard reads the text on screen frame by frame. On the result page, the check \"On-screen text\" shows "
               "Done, and the card \"Text read from the screen\" lists what appeared in the video, such as the price "
               "(₹1,30,00,000), carpet area, bathrooms and possession date, each with its time. The on-screen price is "
               "compared with the approved price and with the price spoken in the video.",
     "steps": ["Download the video below.", "Click Enter as Freelancer, open Submit a Video, choose Demo Developer and upload it.",
               "Wait for the review. On the free server this takes a while (see the note at the top of this page).",
               "On the result page, open the \"Text read from the screen\" card and the \"On-screen text\" and "
               "\"Voice versus screen\" checks."]},
]


def _clip_file(key):
    clip = next((c for c in TEST_CLIPS if c["key"] == key), None)
    base = clip.get("file", key) if clip else key
    for ext in AUDIO_EXT:
        p = AUDIO_DIR / f"{base}{ext}"
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
            src = f'/test-audio/file/{c["key"]}?inline=1'
            if f.suffix.lower() in VIDEO_EXT:
                player = (f'<video controls preload="none" playsinline style="width:100%;max-height:360px;margin:8px 0 12px;'
                          f'background:#000;border-radius:8px" src="{src}">Your browser cannot play video.</video>')
            else:
                player = (f'<audio controls preload="none" style="width:100%;margin:8px 0 12px" src="{src}">'
                          f'Your browser cannot play audio.</audio>')
            media = player + (f'<a class="btn" href="/test-audio/file/{c["key"]}" download>{ui.icon("upload", 16)}'
                              f'Download demo file {c["n"]}</a>')
        else:
            media = ui.alert("This demo file has not been added yet.", "warn")
        steps = "".join(f"<li>{e(s)}</li>" for s in c["steps"])
        said = (f'<p class="muted" style="margin-bottom:4px">What is said in the clip</p>'
                f'<p style="margin-top:0"><i>"{e(c["say"])}"</i></p>') if c["say"] else ""
        inner = (said + media
                 + f'<h3 class="sec-title">What to do</h3><ol style="margin:0 0 12px;padding-left:20px">{steps}</ol>'
                 f'<h3 class="sec-title">What you should see</h3><p style="margin:0">{e(c["result"])}</p>')
        cards.append(ui.card(f'Demo file {c["n"]}: {c["title"]}', inner, cls=""))
    guide = AUDIO_DIR / "Demo_Developer_Brand_Guide.pdf"
    extra = ""
    if guide.is_file():
        extra = ui.card("Optional: sample brand guide",
                        '<p class="muted">As Builder, open Brand Rules and click Import from PDF, then upload this file. '
                        'BrandGuard lists the rules it found, you confirm them, and they apply to new submissions straight away.</p>'
                        '<a class="btn secondary" href="/test-audio/file/guide" download>Download sample brand guide (PDF)</a>')
    start = ('<a class="btn" href="/enter/freelancer">Enter as Freelancer</a> '
             '<a class="btn secondary" href="/enter/admin">Enter as Builder</a>') if not u else ""
    body = (ui.page_header("Demo Files for Judges",
                           "Ready-made demo recordings and a demo video to test the main workflow: one approved, one rejected, "
                           "one disputed, and one that shows on-screen text being read. No sign-up is needed. Use the demo "
                           "roles in the sidebar or the buttons below.", start)
            + '<div class="stack">'
            + ui.alert("These files are made for demonstration only. Download a file here, then upload it on the Submit a "
                       "Video page to see how BrandGuard reviews it. The company, projects and prices are fictional.",
                       "info", "For demo use.")
            + ui.alert("This demo runs on a free Render server, which has very little CPU and memory. A review needs speech "
                       "recognition plus reading every frame of the video, so it can take a few minutes, and the first "
                       "request after a quiet period is slower because the server has to wake up. Please keep the page open "
                       "and wait. The same review takes seconds on a normal server.",
                       "warn", "Please be patient.")
            + "".join(cards) + extra + "</div>")
    if u:
        return page("Demo Files", body, u, "testaudio", [("Demo Files", None)], request)
    return page("Demo Files", body)


@app.get("/test-audio/file/{key}")
def test_audio_file(key: str, inline: int = 0):
    if key == "guide":
        p = AUDIO_DIR / "Demo_Developer_Brand_Guide.pdf"
        name = "Demo_Developer_Brand_Guide.pdf"
    else:
        clip = next((c for c in TEST_CLIPS if c["key"] == key), None)
        p = _clip_file(key) if clip else None
        name = f'BrandGuard_Demo_{clip["n"]}_{re.sub(r"[^A-Za-z0-9]+", "_", clip["title"]).strip("_")}{p.suffix}' if p else ""
    if not p or not p.is_file():
        return HTMLResponse("File not found.", status_code=404)
    return FileResponse(str(p), filename=name, content_disposition_type="inline" if inline else "attachment")
