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
OCR_LANGS = os.environ.get("OCR_LANGS", "eng+hin+mar")       # packs that are not installed are skipped automatically
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


_LANGS = None


def langs():
    """The requested OCR languages that are actually installed (English is always kept)."""
    global _LANGS
    if _LANGS is None:
        try:
            r = subprocess.run([TESSERACT, "--list-langs"], capture_output=True, text=True, timeout=20)
            have = set(r.stdout.split()) | set(r.stderr.split())
        except Exception:
            have = {"eng"}
        want = [x for x in OCR_LANGS.split("+") if x]
        got = [x for x in want if x in have] or ["eng"]
        _LANGS = "+".join(got)
    return _LANGS


def _ocr_one(png):
    r = subprocess.run([TESSERACT, str(png), "stdout", "-l", langs(), "--psm", "11", "tsv"],
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
    return t.replace("₹", " rs ").replace("¥", " ").replace("Rs.", " rs ").replace("Rs ", " rs ")


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

# ------------------------------------------------------------------ still images (posters, banners, flyers)
def _tsv_lines(png, psm, scale=1.0):
    """[{"text", "conf", "box": (x, y, w, h)}] from one Tesseract pass, boxes in original image pixels."""
    r = subprocess.run([TESSERACT, str(png), "stdout", "-l", langs(), "--psm", str(psm), "tsv"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=90)
    groups = {}
    for row in r.stdout.splitlines()[1:]:
        p = row.split("\t")
        if len(p) < 12 or not p[11].strip():
            continue
        try:
            conf = float(p[10])
            x, y, w, h = (int(p[6]), int(p[7]), int(p[8]), int(p[9]))
        except ValueError:
            continue
        if conf < MIN_CONF:
            continue
        groups.setdefault((p[2], p[3], p[4]), []).append((p[11].strip(), conf, x, y, w, h))
    out = []
    for words in groups.values():
        text = " ".join(w[0] for w in words)
        core = re.sub(r"\W", "", text)
        if len(core) < 2 or not re.search(r"\w{2}", text):
            continue
        x0 = min(w[2] for w in words); y0 = min(w[3] for w in words)
        x1 = max(w[2] + w[4] for w in words); y1 = max(w[3] + w[5] for w in words)
        hs = sorted(w[5] for w in words)
        out.append({"text": text, "conf": sum(w[1] for w in words) / len(words) / 100.0,
                    "box": (int(x0 / scale), int(y0 / scale), int((x1 - x0) / scale), int((y1 - y0) / scale)),
                    "text_h": int(hs[len(hs) // 2] / scale)})
    return out


def preprocess(src, dst):
    """Upscale small images and even out contrast, so small or low-contrast text is read. Returns the scale used."""
    import cv2
    img = cv2.imread(str(src))
    if img is None:
        raise ValueError("not an image")
    h, w = img.shape[:2]
    scale = 1.0
    if max(h, w) < 1600:
        scale = min(3.0, 1600.0 / max(h, w))
        img = cv2.resize(img, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
    g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    g = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(g)
    cv2.imwrite(str(dst), g)
    # a black-and-white copy brings out faint text (light grey on white, white on pale colours)
    b = cv2.adaptiveThreshold(cv2.GaussianBlur(g, (3, 3), 0), 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 41, 6)
    cv2.imwrite(str(Path(dst).with_name("bin.png")), b)
    return scale


def read_image(path):
    """Text on a still image, read twice (as is, and enhanced) and merged. Returns a list of lines
    {"start", "end", "text", "raw", "conf", "box", "text_h"} or None if OCR is unavailable."""
    if not (OCR_ENABLED and TESSERACT):
        return None
    try:
        with tempfile.TemporaryDirectory() as d:
            enh = Path(d) / "enh.png"
            scale = preprocess(path, enh)
            passes = (_tsv_lines(path, 11) + _tsv_lines(enh, 11, scale) + _tsv_lines(enh, 3, scale)
                      + _tsv_lines(Path(d) / "bin.png", 11, scale))
    except Exception:
        return None
    best = {}
    for l in passes:
        k = _key(l["text"])
        if k and (k not in best or l["conf"] > best[k]["conf"]):
            best[k] = l
    lines = []
    for l in best.values():
        lines.append({"start": 0, "end": 0, "text": normalise(l["text"]), "raw": l["text"], "conf": l["conf"],
                      "box": l["box"], "text_h": l["text_h"]})
    lines = _drop_contained(lines)
    lines.sort(key=lambda l: (l["box"][1], l["box"][0]))
    return pair_lines(lines)


def read_image_bytes(data, suffix=".png"):
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / ("img" + suffix)
        p.write_bytes(data)
        return read_image(p)


def _drop_contained(lines):
    """A line whose text is part of a longer line at an overlapping place is the same text read partially."""
    keep = []
    for l in sorted(lines, key=lambda x: -len(_key(x["text"]))):
        k = _key(l["text"])
        if any(k in _key(h["text"]) and _overlap(l["box"], h["box"]) for h in keep):
            continue
        keep.append(l)
    return keep


def _overlap(a, b):
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    return not (ax + aw < bx or bx + bw < ax or ay + ah < by or by + bh < ay)


_PRICE_HINT = re.compile(r"(\d|lakh|cr\b|crore|rs\b|₹|%)", re.I)


def _is_value_only(text):
    """A line that is mostly a number (price, percentage) with at most one other word."""
    words = re.findall(r"[^\W\d_]{2,}", text)
    words = [w for w in words if w.lower() not in ("lakh", "cr", "crore", "rs", "only", "onwards", "inr", "off", "lac", "lacs")]
    return bool(_PRICE_HINT.search(text)) and len(words) <= 1


def pair_lines(lines):
    """Posters put a label and its price on separate lines ("2 BHK" above "₹1.3 Cr*"). A value-only line is
    joined with the nearest label line directly above it (or just left of it on the same row), so the price
    is checked against the right variant. The original text is kept in "raw"."""
    for i, l in enumerate(lines):
        if not _is_value_only(l["text"]):
            continue
        x, y, w, h = l["box"]
        best, gap_best = None, None
        for j, o in enumerate(lines):
            if j == i or _is_value_only(o["text"]):
                continue
            ox, oy, ow, oh = o["box"]
            above = oy + oh <= y + h * 0.3 and (y - (oy + oh)) <= 2.5 * max(h, oh) and not (ox + ow < x or x + w < ox)
            left = abs((oy + oh / 2) - (y + h / 2)) <= max(h, oh) * 0.6 and ox + ow <= x + 5 and x - (ox + ow) <= 4 * max(h, oh)
            if not (above or left):
                continue
            gap = (y - (oy + oh)) if above else (x - (ox + ow))
            if gap_best is None or gap < gap_best:
                best, gap_best = o, gap
        if best is not None:
            l["text"] = best["text"] + " " + l["text"]
            l["paired_with"] = best["raw"]
    return lines
