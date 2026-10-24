"""Run once from the project folder:  python patch_round2_ui.py
Needs demo_files_block.py in the same folder. Changes main.py and ui.py, and writes nothing if an anchor is missing."""
import pathlib, sys

main_p, ui_p, blk_p = pathlib.Path("main.py"), pathlib.Path("ui.py"), pathlib.Path("demo_files_block.py")
m = main_p.read_text(encoding="utf-8")
u = ui_p.read_text(encoding="utf-8")
block = blk_p.read_text(encoding="utf-8").rstrip() + "\n"
problems = []

# 1. replace the whole test-audio block
start_marker = "# ============================================================ test audio for judges"
end_marker = 'content_disposition_type="inline" if inline else "attachment")'
a = m.find(start_marker)
b = m.find(end_marker)
if a < 0 or b < 0 or b < a:
    problems.append("could not find the old test-audio block in main.py")
else:
    b = b + len(end_marker)
    if m[b:b + 1] == "\n":
        b += 1
    m = m[:a] + block + m[b:]

# 2. reel -> video everywhere in the visible text
for old, new in (("Reels", "Videos"), ("reels", "videos"), ("Reel", "Video"), ("reel", "video")):
    m = m.replace(old, new)
    u = u.replace(old, new)

# 3. free-tier warning on the upload page, and honest timings
anchor = ('and shows you the result. Anything uncertain goes to a person for a decision.")\n'
          "            + '<div class=\"cols\"><div>'")
if anchor not in m:
    problems.append("could not find the Submit page header in main.py")
else:
    m = m.replace(anchor,
        'and shows you the result. Anything uncertain goes to a person for a decision.")\n'
        '            + ui.alert("This demo runs on a free Render server with very little CPU and memory. To review a video, '
        'BrandGuard turns the speech into text and then reads every frame of the video, so it can take a few minutes. '
        'The first request after a quiet period is slower still, because the server has to wake up. Please keep this page '
        'open until the result appears. On a normal server the same review takes seconds. Short videos (under 15 seconds) '
        'are quickest.", "warn", "Please be patient: free server.")\n'
        "            + '<div class=\"cols\"><div>'")
for old, new in (
    ("Reviewing. This can take 10 to 40 seconds. Please keep this page open.",
     "Reviewing. On this free server it can take a few minutes. Please keep this page open."),
    ("The audio is transcribed and checked, usually in 10 to 40 seconds.",
     "The speech is transcribed and the on-screen text is read, then both are checked. On the free demo server this can take a few minutes."),
):
    if old in m:
        m = m.replace(old, new)

# 4. nav label and landing button
if '"Test Audio"' in u:
    u = u.replace('"Test Audio"', '"Demo Files"')
else:
    problems.append("ui.py: nav label 'Test Audio' not found (already changed?)")
m = m.replace("Judges: download test audio", "Judges: demo files to download")

if problems:
    print("NOTHING WRITTEN. Problems:")
    for p in problems:
        print(" -", p)
    sys.exit(1)
main_p.write_text(m, encoding="utf-8")
ui_p.write_text(u, encoding="utf-8")
print("Done. main.py and ui.py updated.")
