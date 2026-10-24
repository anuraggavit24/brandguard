"""On-screen text reading for BrandGuard.

The video is split into frames and EVERY frame is read, so no text is skipped:
  - one frame per second, plus
  - an extra frame at every scene change (so text that flashes between two regular frames is still caught).
Each frame is read with Tesseract. Identical lines seen again on later frames are merged,
but a changed line (for example a different price) is always kept.

Fail-safe: if OCR is off, Tesseract is missing or anything breaks, read_screen returns None and the
review carries on as speech-only (and says so).
"""
import os
import re
import shutil
import subprocess
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

OCR_ENABLED = os.environ.get("OCR_ENABLED", "1") != "0"
OCR_FPS = float(os.environ.get("OCR_FPS", "2"))              # regular frames per second
OCR_SCENE = float(os.environ.get("OCR_SCENE", "0.01"))        # scene-change sensitivity (lower = more frames)
OCR_MAX_FRAMES = int(os.environ.get("OCR_MAX_FRAMES", "400"))
OCR_LANGS = os.environ.get("OCR_LANGS", "eng")               # e.g. eng+hin+mar if those packs are installed
OCR_WORKERS = int(os.environ.get("OCR_WORKERS", "3"))
OCR_BUDGET = float(os.environ.get("OCR_BUDGET", "75"))      # seconds; after this the rest is left unread and reported as partial
MIN_CONF = 40

# Tesseract is found on PATH, or in its default Windows install folders (so a missing PATH entry doesn't break OCR)
TESSERACT = os.environ.get("TESSERACT_CMD") or shutil.which("tesseract") or next(
    (p for p in (r"C:\Program Files\Tesseract-OCR\tesseract.exe",
                 r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe") if os.path.exists(p)), None)


def available():
    return bool(OCR_ENABLED and TESSERACT and shutil.which("ffmpeg"))


def has_video(src):
    try:
        r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                            "stream=codec_type", "-of", "csv=p=0", str(src)],
                           capture_output=True, text=True, timeout=30)
        return "video" in r.stdout
    except Exception:
        return False


def _frames(src, outdir, max_seconds):
    """Return [(timestamp_seconds, path)] for regular and scene-change frames, oldest first."""
    out = []
    # regular frames: timestamp = index / fps
    subprocess.run(["ffmpeg", "-y", "-t", str(max_seconds), "-i", str(src), "-vf",
                    f"fps={OCR_FPS},scale=1280:-2", str(Path(outdir) / "r_%04d.png")],
                   capture_output=True, timeout=180)
    for p in sorted(Path(outdir).glob("r_*.png")):
        n = int(p.stem.split("_")[1])
        out.append(((n - 1) / OCR_FPS, p))
    # scene-change frames: real timestamps from showinfo
    r = subprocess.run(["ffmpeg", "-y", "-t", str(max_seconds), "-i", str(src), "-vf",
                        f"select='gt(scene,{OCR_SCENE})',scale=1280:-2,showinfo", "-vsync", "vfr",
                        str(Path(outdir) / "s_%04d.png")],
                       capture_output=True, text=True, timeout=180)
    times = [float(m) for m in re.findall(r"pts_time:([\d.]+)", r.stderr)]
    for p, t in zip(sorted(Path(outdir).glob("s_*.png")), times):
        out.append((t, p))
    out.sort(key=lambda x: x[0])
    return out[:OCR_MAX_FRAMES]


def _ocr_one(png):
    r = subprocess.run([TESSERACT, str(png), "stdout", "-l", OCR_LANGS, "--psm", "11", "tsv"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=45)
    lines = {}
    for row in r.stdout.splitlines()[1:]:
        p = row.split("\t")
        if len(p) < 12 or not p[11].strip():
            continue
        try:
            conf = float(p[10])
        except ValueError:
            continue
        if conf < MIN_CONF:
            continue
        lines.setdefault((p[2], p[3], p[4]), []).append((p[11].strip(), conf))
    out = []
    for words in lines.values():
        text = " ".join(w for w, _ in words)
        conf = sum(c for _, c in words) / len(words) / 100.0
        core = re.sub(r"\W", "", text)
        letters = sum(ch.isalnum() for ch in text)
        if len(core) >= 3 and letters >= 0.6 * len(text.replace(" ", "")) and re.search(r"\w{3}", text):
            out.append((text, conf))
    return out


_AMOUNT = re.compile(r"(?<![\d.,])(\d{1,3}(?:,\d{2})*,\d{3})(?![\d,])")


def normalise(text):
    """Make screen text readable by the spoken-number engine: 1,30,00,000 -> 1.3 cr, 95 L -> 95 lakh."""
    def money(m):
        v = int(m.group(1).replace(",", ""))
        if v >= 10_000_000:
            return f"{v / 1e7:g} cr"
        if v >= 100_000:
            return f"{v / 1e5:g} lakh"
        return m.group(0)
    t = _AMOUNT.sub(money, text)
    t = re.sub(r"(?i)(\d(?:\.\d+)?)\s*(?:L|Lac|Lacs)\b", r"\1 lakh", t)
    t = re.sub(r"(?i)(\d(?:\.\d+)?)\s*Cr\.?(?=\W|$)", r"\1 cr", t)
    return t.replace("₹", " ").replace("¥", " ").replace("Rs.", " rs ").replace("Rs ", " rs ")


def read_screen(src, max_seconds=180):
    """Return {"lines": [{"start","end","text","raw","conf"}], "frames": n} for text shown on screen,
    or None when OCR is off, unavailable, or failed (the review then says on-screen text was not checked)."""
    try:
        if not available() or not has_video(src):
            return None
        with tempfile.TemporaryDirectory() as d:
            frames = _frames(src, d, max_seconds)
            n_total = len(frames)
            if not frames:
                return None
            results, t0 = [], time.time()
            with ThreadPoolExecutor(max_workers=OCR_WORKERS) as ex:
                for i in range(0, len(frames), OCR_WORKERS * 2):
                    if time.time() - t0 > OCR_BUDGET:
                        break
                    batch = frames[i:i + OCR_WORKERS * 2]
                    results += list(ex.map(lambda tp: _ocr_one(tp[1]), batch))
            frames = frames[:len(results)] if results else frames
        out, seen = [], {}
        for (t, _p), lines in zip(frames, results):
            for text, conf in lines:
                k = re.sub(r"\W+", "", text.lower())
                if not k:
                    continue
                if k in seen:                       # same line again: extend its time, keep one entry
                    seen[k]["end"] = max(seen[k]["end"], t + 0.5)
                    seen[k]["conf"] = max(seen[k]["conf"], conf)
                    continue
                item = {"start": round(t, 1), "end": round(t + 0.5, 1), "text": normalise(text), "raw": text, "conf": conf}
                seen[k] = item
                out.append(item)
        out = _merge_partial(out)
        return {"lines": out, "frames": len(frames), "total": n_total, "partial": len(frames) < n_total}
    except Exception:
        return None


def _key(t):
    return re.sub(r"\W+", "", t.lower())


def _merge_partial(lines):
    """Text that animates in is read as partial lines ("DEMO HE", "DEMO HEIGHTS"). Keep the fullest version
    and the earliest time it was seen. A line that differs in any other way (for example another price) is kept."""
    keep = []
    for l in sorted(lines, key=lambda x: -len(_key(x["text"]))):
        k = _key(l["text"])
        host = next((h for h in keep if k and k in _key(h["text"])), None)
        if host:
            host["start"] = min(host["start"], l["start"])
            host["end"] = max(host["end"], l["end"])
        else:
            keep.append(dict(l))
    keep.sort(key=lambda x: x["start"])
    return keep