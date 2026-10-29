"""Brand assets and accessibility checks for images (posters, banners, flyers).

The company records its brand assets once on the Brand Rules page:
    logo           an image file; optionally required on every poster
    palette        brand colours as hex codes
    min_contrast   smallest text/background contrast ratio (WCAG: 4.5 for normal text, 3 for large text)
    min_text_pct   smallest text height as a percentage of the image height

Checks (code only, no AI):
    LOW_CONTRAST   text whose colour is too close to its background (needs a person to look)
    SMALL_TEXT     text smaller than the brand's minimum (advice)
    OFF_PALETTE    a large area in a colour that is not a brand colour or a neutral (advice)
    LOGO_MISSING   the logo could not be found when it is required (needs a person to look)

Limits, stated plainly: contrast is measured from the pixels around each line OCR found, so text OCR missed is not
measured; the logo search matches the logo's picture at different sizes and will miss a logo that is redrawn, rotated or
heavily recoloured; colour checks look at large areas only. Font identification is not attempted.
"""

import os
import re

DEFAULTS = {"palette": [], "min_contrast": 4.5, "min_text_pct": 1.2, "require_logo": False, "check_palette": False,
            "logo": ""}


def config(reg):
    c = dict(DEFAULTS)
    c.update(reg.get("assets") or {})
    return c


def parse_palette(s):
    out = []
    for h in re.findall(r"#?([0-9a-fA-F]{6}|[0-9a-fA-F]{3})\b", s or ""):
        if len(h) == 3:
            h = "".join(ch * 2 for ch in h)
        out.append("#" + h.upper())
    return list(dict.fromkeys(out))[:12]


def _lum(rgb):
    def ch(c):
        c = c / 255.0
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = rgb
    return 0.2126 * ch(r) + 0.7152 * ch(g) + 0.0722 * ch(b)


def contrast_ratio(a, b):
    la, lb = _lum(a), _lum(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


def _hex(rgb):
    return "#%02X%02X%02X" % tuple(int(x) for x in rgb)


def line_colours(img_rgb, box):
    """(text_rgb, background_rgb) inside a line's box, by splitting its pixels into two colour groups.
    The smaller group is the text."""
    import cv2
    import numpy as np
    x, y, w, h = box
    H, W = img_rgb.shape[:2]
    pad = max(2, h // 4)
    x0, y0, x1, y1 = max(0, x - pad), max(0, y - pad), min(W, x + w + pad), min(H, y + h + pad)
    crop = img_rgb[y0:y1, x0:x1].reshape(-1, 3).astype(np.float32)
    if len(crop) < 20:
        return None
    if len(crop) > 6000:
        crop = crop[np.random.default_rng(0).choice(len(crop), 6000, replace=False)]
    crit = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 20, 1.0)
    _c, labels, centers = cv2.kmeans(crop, 2, None, crit, 3, cv2.KMEANS_PP_CENTERS)
    counts = np.bincount(labels.flatten(), minlength=2)
    text_i = int(np.argmin(counts))
    return tuple(centers[text_i]), tuple(centers[1 - text_i])


def dominant_colours(img_rgb, k=6, min_share=0.08):
    import cv2
    import numpy as np
    small = cv2.resize(img_rgb, (120, 120), interpolation=cv2.INTER_AREA).reshape(-1, 3).astype(np.float32)
    crit = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 20, 1.0)
    _c, labels, centers = cv2.kmeans(small, k, None, crit, 3, cv2.KMEANS_PP_CENTERS)
    counts = np.bincount(labels.flatten(), minlength=k) / len(labels)
    return [(tuple(centers[i]), float(counts[i])) for i in range(k) if counts[i] >= min_share]


def _lab(rgb):
    import cv2
    import numpy as np
    px = np.uint8([[list(rgb)]])
    return cv2.cvtColor(px, cv2.COLOR_RGB2LAB)[0][0].astype(float)


def _neutral(rgb):
    import colorsys
    r, g, b = (c / 255.0 for c in rgb)
    _h, l, s = colorsys.rgb_to_hls(r, g, b)
    return s < 0.18 or l < 0.08 or l > 0.94


def _hex_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def find_logo(img_bgr, logo_bgr):
    """Best match score (0..1) of the logo anywhere in the image, tried at 60 sizes (4% to 70% of the image width)."""
    import cv2
    import numpy as np
    img = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    if max(img.shape) > 1000:                       # speed: the search runs on a smaller copy
        f = 1000.0 / max(img.shape)
        img = cv2.resize(img, None, fx=f, fy=f, interpolation=cv2.INTER_AREA)
    lg = cv2.cvtColor(logo_bgr, cv2.COLOR_BGR2GRAY)
    H, W = img.shape[:2]
    best = 0.0
    for frac in np.geomspace(0.04, 0.7, 60):
        tw = int(W * frac)
        th = int(lg.shape[0] * tw / max(1, lg.shape[1]))
        if tw < 12 or th < 8 or th >= H or tw >= W:
            continue
        t = cv2.resize(lg, (tw, th), interpolation=cv2.INTER_AREA)
        if t.std() < 1:
            continue
        best = max(best, float(cv2.matchTemplate(img, t, cv2.TM_CCOEFF_NORMED).max()))
    return best


LOGO_MATCH = float(os.environ.get("LOGO_MATCH", "0.7"))


def check_image(path, lines, reg, make_finding):
    """Returns (findings, check_rows) for one image."""
    import cv2
    cfg = config(reg)
    img_bgr = cv2.imread(str(path))
    if img_bgr is None:
        return [], [("Brand assets and accessibility", "not_available", "The image could not be opened.")]
    rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
    H = rgb.shape[0]
    found, checks = [], []

    # contrast and size of every line OCR found
    low, small = [], []
    for l in lines or []:
        if not l.get("box"):
            continue
        cols = line_colours(rgb, l["box"])
        if cols:
            ratio = contrast_ratio(*cols)
            large = (l.get("text_h") or l["box"][3]) >= 0.045 * H
            need = 3.0 if large else float(cfg["min_contrast"])
            if ratio < need:
                low.append((ratio, need, l, cols))
        pct = 100.0 * (l.get("text_h") or l["box"][3]) / max(1, H)
        if pct < float(cfg["min_text_pct"]):
            small.append((pct, l))
    for ratio, need, l, (tc, bc) in sorted(low, key=lambda x: x[0])[:5]:
        found.append(make_finding("SUPERVISION", "LOW", "LOW_CONTRAST", 0, l["raw"][:80],
                                  f"Contrast {ratio:.1f}:1 between text {_hex(tc)} and background {_hex(bc)}; at least {need:g}:1 is needed "
                                  "to be readable, including for people with low vision.",
                                  "Use a darker or lighter text colour, or a plain background behind the text.", None, "screen"))
    for pct, l in sorted(small, key=lambda x: x[0])[:5]:
        found.append(make_finding("NOTE", "LOW", "SMALL_TEXT", 0, l["raw"][:80],
                                  f"This text is {pct:.1f}% of the image height; the brand minimum is {float(cfg['min_text_pct']):g}%.",
                                  "Make the text larger, especially prices and conditions.", None, "screen"))
    measured = sum(1 for l in lines or [] if l.get("box"))
    checks.append(("Text contrast and size", "done" if measured else "incomplete",
                   f"{measured} text line(s) measured; {len(low)} below the contrast minimum, {len(small)} below the size minimum."
                   if measured else "No text was found to measure."))

    # brand colours
    pal = [_hex_rgb(h) for h in cfg["palette"]]
    if cfg["check_palette"] and pal:
        labs = [_lab(c) for c in pal]
        off = []
        for col, share in dominant_colours(rgb):
            if _neutral(col):
                continue
            dist = min(float(((_lab(col) - lb) ** 2).sum() ** 0.5) for lb in labs)
            if dist > 40:
                off.append((share, col))
        for share, col in sorted(off, reverse=True)[:3]:
            found.append(make_finding("NOTE", "LOW", "OFF_PALETTE", 0, _hex(col),
                                      f"About {round(share * 100)}% of the image is {_hex(col)}, which is not one of the brand colours "
                                      f"({', '.join(cfg['palette'])}).", "Use a brand colour, or ignore this if the colour is part of a photo.",
                                      None, "screen"))
        checks.append(("Brand colours", "done", f"{len(off)} large area(s) in a non-brand colour."))
    else:
        checks.append(("Brand colours", "not_available", "No brand colours are set, or the colour check is off."))

    # logo
    logo = cfg.get("logo") or ""
    if logo and os.path.exists(logo):
        lg = cv2.imread(logo)
        score = find_logo(img_bgr, lg) if lg is not None else 0.0
        ok = score >= LOGO_MATCH
        if not ok and cfg["require_logo"]:
            found.append(make_finding("SUPERVISION", "LOW", "LOGO_MISSING", 0, f"match {score:.2f}",
                                      "The brand logo could not be found on this image.",
                                      "Add the approved logo, or a person can confirm it is there in a form the search missed.", None, "screen"))
        checks.append(("Brand logo", "done", "Logo found." if ok else "Logo not found by the logo search"
                       + ("." if cfg["require_logo"] else " (not required).")))
    else:
        checks.append(("Brand logo", "not_available", "No logo has been uploaded on the Brand Rules page."))
    return found, checks
