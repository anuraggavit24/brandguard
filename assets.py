"""Brand assets, visual consistency and accessibility checks.

Works on images (posters, banners) and on text paths (paste, documents, OCR,
transcripts). The company records settings once on the Brand Rules page:

    logo / require_logo     image logo file; optional required presence
    palette / check_palette brand colours as hex; large off-palette areas
    palette_names           colour words approved in copy (navy, gold…)
    check_color_words       flag off-brand colour words in text
    logo_name / require_logo_mention
                            text creatives must name the brand/logo
    fonts / visual_dos / visual_donts
                            optional visual-language rules for copy + captions
    min_contrast / min_text_pct
                            image contrast and min text height
    require_alt_text        soft/supervision finding when image has no alt
    check_text_a11y         ALL CAPS, wall-of-text, colour-only cues, weak CTAs
    wall_text_chars         soft wall-of-text threshold (characters)

Image-only (pixels): LOW_CONTRAST, SMALL_TEXT, OFF_PALETTE, LOGO_MISSING.
Text / OCR / transcript: OFF_BRAND_COLOR, LOGO_MENTION_MISSING, VISUAL_DONT,
FONT_OFF_BRAND, ALL_CAPS, WALL_OF_TEXT, COLOR_ONLY_CUE, UNCLEAR_CTA, MISSING_ALT.

Limits: contrast uses OCR boxes only; logo match is template-based; colour-word
and font checks are keyword heuristics, not true vision or font ID.
"""

import os
import re

DEFAULTS = {
    "palette": [],
    "palette_names": [],
    "min_contrast": 4.5,
    "min_text_pct": 1.2,
    "require_logo": False,
    "check_palette": False,
    "check_color_words": False,
    "logo": "",
    "logo_name": "",
    "require_logo_mention": False,
    "fonts": [],
    "visual_dos": [],
    "visual_donts": [],
    "require_alt_text": False,
    "check_text_a11y": True,
    "wall_text_chars": 600,
}

# Common colour words → used to spot off-brand colour language in copy.
_COLOR_WORDS = {
    "red", "crimson", "scarlet", "maroon", "burgundy",
    "orange", "amber", "coral",
    "yellow", "gold", "golden", "mustard",
    "green", "lime", "olive", "emerald", "mint",
    "blue", "navy", "azure", "teal", "cyan", "turquoise", "indigo",
    "purple", "violet", "magenta", "lilac", "lavender",
    "pink", "hot pink", "neon pink", "fuchsia",
    "brown", "beige", "tan", "cream",
    "black", "white", "grey", "gray", "silver", "charcoal",
}
_NEUTRAL_COLORS = {"black", "white", "grey", "gray", "silver", "charcoal", "cream", "beige", "tan"}

# Well-known fonts; if approved fonts are set, mentions of others are soft-flagged.
_KNOWN_FONTS = (
    "arial", "helvetica", "times new roman", "times", "georgia", "verdana",
    "comic sans", "comic sans ms", "impact", "papyrus", "courier", "courier new",
    "roboto", "open sans", "montserrat", "lato", "inter", "poppins", "raleway",
    "futura", "gill sans", "calibri", "cambria", "garamond", "baskerville",
)

_COLOR_ONLY_RE = re.compile(
    r"\b(?:click|tap|press|select|choose|look\s+for|follow)\s+(?:(?:on|the)\s+)*"
    r"(?:red|green|blue|yellow|orange|purple|pink|black|white|grey|gray|gold|navy|"
    r"crimson|teal|violet|magenta)\s+"
    r"(?:button|link|box|icon|arrow|circle|tab|badge|banner|cta)\b",
    re.I,
)
_WEAK_CTA_RE = re.compile(
    r"\b(?:click\s+here|tap\s+here|click\s+this|tap\s+this|read\s+more\s+here|"
    r"learn\s+more\s+here|click\s+below|tap\s+below)\b",
    re.I,
)


def config(reg):
    c = dict(DEFAULTS)
    raw = reg.get("assets") or {}
    c.update(raw)
    # Normalise list-ish fields that may arrive as comma strings from older saves.
    for key in ("palette_names", "fonts", "visual_dos", "visual_donts"):
        c[key] = _as_list(c.get(key))
    c["palette"] = list(c.get("palette") or [])
    return c


def _as_list(v):
    if v is None:
        return []
    if isinstance(v, list):
        return [str(x).strip() for x in v if str(x).strip()][:40]
    return [x.strip() for x in re.split(r"[,;\n]+", str(v)) if x.strip()][:40]


def parse_palette(s):
    out = []
    for h in re.findall(r"#?([0-9a-fA-F]{6}|[0-9a-fA-F]{3})\b", s or ""):
        if len(h) == 3:
            h = "".join(ch * 2 for ch in h)
        out.append("#" + h.upper())
    return list(dict.fromkeys(out))[:12]


def parse_list(s, limit=20):
    return _as_list(s)[:limit]


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

# Finding types produced by this module (kept across confirm re-runs).
ASSET_TYPES = {
    "LOW_CONTRAST", "SMALL_TEXT", "OFF_PALETTE", "LOGO_MISSING",
    "OFF_BRAND_COLOR", "LOGO_MENTION_MISSING", "VISUAL_DONT", "FONT_OFF_BRAND",
    "ALL_CAPS", "WALL_OF_TEXT", "COLOR_ONLY_CUE", "UNCLEAR_CTA", "MISSING_ALT",
}

ASSET_CHECK_NAMES = {
    "Text contrast and size", "Brand colours", "Brand logo",
    "Visual language (text)", "Text accessibility", "Alt text",
}


def text_blob(lines=None, segments=None, caption="", alt_text=""):
    parts = []
    if caption and str(caption).strip():
        parts.append(str(caption).strip())
    if alt_text and str(alt_text).strip():
        parts.append(str(alt_text).strip())
    for l in lines or []:
        t = (l.get("raw") or l.get("text") or "").strip()
        if t:
            parts.append(t)
    for s in segments or []:
        t = (s.get("text") or "").strip()
        if t:
            parts.append(t)
    return "\n".join(parts)


def check_image(path, lines, reg, make_finding):
    """Returns (findings, check_rows) for one image (pixel checks)."""
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


def _approved_color_names(cfg):
    names = {n.lower() for n in cfg.get("palette_names") or []}
    # Hex alone does not yield colour words; keep neutrals always allowed.
    names |= _NEUTRAL_COLORS
    return names


def check_text(text, reg, make_finding, source="screen"):
    """Visual-language + text accessibility heuristics on paste / docs / OCR / transcripts."""
    cfg = config(reg)
    found, checks = [], []
    blob = (text or "").strip()
    if not blob:
        checks.append(("Visual language (text)", "not_available", "No text available for visual-language checks."))
        checks.append(("Text accessibility", "not_available", "No text available for accessibility checks."))
        return found, checks

    low = blob.lower()

    # --- Visual: off-brand colour words ---
    approved = _approved_color_names(cfg)
    color_hits = []
    if cfg.get("check_color_words") and cfg.get("palette_names"):
        for w in sorted(_COLOR_WORDS, key=len, reverse=True):
            if w in _NEUTRAL_COLORS or w in approved:
                continue
            if any(w == a or w in a.split() for a in approved):
                continue
            # Prefer the longest match only (e.g. "neon pink" not also "pink").
            if any(w != h and w in h for h in color_hits):
                continue
            if re.search(r"(?<![a-z])" + re.escape(w) + r"(?![a-z])", low):
                if w not in color_hits:
                    color_hits.append(w)
        for w in color_hits[:4]:
            found.append(make_finding(
                "NOTE", "LOW", "OFF_BRAND_COLOR", 0, w,
                f"The copy mentions “{w}”, which is not in the approved brand colour names "
                f"({', '.join(cfg['palette_names'])}).",
                "Use an approved brand colour name, or drop the colour reference if it is not needed.",
                None, source))

    # --- Visual: required logo / brand asset name in text ---
    logo_missing = False
    if cfg.get("require_logo_mention") and (cfg.get("logo_name") or "").strip():
        name = cfg["logo_name"].strip()
        name_ok = bool(re.search(re.escape(name), blob, re.I))
        brand_bit = (reg.get("brand") or "").strip()
        brand_near_logo = bool(brand_bit and re.search(
            re.escape(brand_bit) + r".{0,40}\blogo\b|\blogo\b.{0,40}" + re.escape(brand_bit), low, re.I))
        logo_word = bool(re.search(r"\b(?:logo|brand\s+mark|wordmark)\b", low))
        if not (name_ok or brand_near_logo or (logo_word and brand_bit and brand_bit.lower() in low)):
            logo_missing = True
            found.append(make_finding(
                "SUPERVISION", "LOW", "LOGO_MENTION_MISSING", 0, name,
                f"Brand rules require creatives to name the brand/logo (“{name}”), and it was not found in this text.",
                f"Add “{name}” or an approved logo credit so the brand asset is clearly present.",
                None, source))

    # --- Visual: visual_donts ---
    dont_hits = []
    for d in cfg.get("visual_donts") or []:
        if len(d) >= 3 and d.lower() in low:
            dont_hits.append(d)
    for d in dont_hits[:5]:
        found.append(make_finding(
            "NOTE", "LOW", "VISUAL_DONT", 0, d[:80],
            f"This matches a visual don’t for the brand: “{d}”.",
            "Remove or rephrase so the creative follows the brand visual language.",
            None, source))

    # --- Visual: fonts mentioned vs approved ---
    fonts = [f.lower() for f in (cfg.get("fonts") or [])]
    font_hits = []
    if fonts:
        for fn in sorted(_KNOWN_FONTS, key=len, reverse=True):
            if any(fn == a or fn in a or a in fn for a in fonts):
                continue
            if re.search(r"(?<![a-z0-9])" + re.escape(fn) + r"(?![a-z0-9])", low):
                if fn not in font_hits:
                    font_hits.append(fn)
        for fn in font_hits[:3]:
            found.append(make_finding(
                "NOTE", "LOW", "FONT_OFF_BRAND", 0, fn,
                f"The copy mentions “{fn}”, which is not in the approved brand fonts "
                f"({', '.join(cfg['fonts'])}).",
                "Use an approved brand font, or remove the font name from the creative.",
                None, source))

    visual_active = bool(cfg.get("palette_names") and cfg.get("check_color_words")) or bool(
        cfg.get("visual_donts") or cfg.get("fonts") or cfg.get("require_logo_mention"))
    if visual_active:
        bits = []
        if color_hits:
            bits.append(f"{len(color_hits)} off-brand colour(s)")
        if dont_hits:
            bits.append(f"{len(dont_hits)} visual don’t(s)")
        if font_hits:
            bits.append(f"{len(font_hits)} off-brand font(s)")
        if logo_missing:
            bits.append("logo name missing")
        elif cfg.get("require_logo_mention"):
            bits.append("logo name present")
        checks.append(("Visual language (text)", "done",
                       ("; ".join(bits) + ".") if bits else "No visual-language issues in the text."))
    else:
        checks.append(("Visual language (text)", "not_available",
                       "Set palette names, fonts or visual don’ts on Brand Rules to enable text visual checks."))

    # --- Accessibility (text) ---
    a11y_n = 0
    if cfg.get("check_text_a11y"):
        # ALL CAPS spam: 4+ consecutive caps words, or high caps letter ratio on a long span.
        caps_run = re.findall(r"\b[A-Z]{3,}(?:\s+[A-Z]{3,}){3,}\b", blob)
        letters = re.findall(r"[A-Za-z]", blob)
        caps_ratio = (sum(1 for ch in letters if ch.isupper()) / len(letters)) if len(letters) >= 24 else 0.0
        if caps_run or caps_ratio >= 0.55:
            ev = (caps_run[0][:80] if caps_run else blob[:80])
            found.append(make_finding(
                "NOTE", "LOW", "ALL_CAPS", 0, ev,
                "Large stretches of ALL CAPS make marketing copy harder to read, especially for screen readers "
                "and people with reading difficulties.",
                "Use sentence case; reserve capitals for short emphasis or acronyms.",
                None, source))
            a11y_n += 1

        # Wall of text: long run with little punctuation.
        limit = int(cfg.get("wall_text_chars") or 600)
        for para in re.split(r"\n+", blob):
            para = para.strip()
            if len(para) < limit:
                continue
            marks = len(re.findall(r"[.!?।]", para))
            if marks < max(1, len(para) // 280):
                found.append(make_finding(
                    "NOTE", "LOW", "WALL_OF_TEXT", 0, para[:80] + ("…" if len(para) > 80 else ""),
                    f"A block of about {len(para)} characters has little punctuation, which is hard to scan.",
                    "Break it into shorter sentences or paragraphs.",
                    None, source))
                a11y_n += 1
                break

        # Colour-only meaning
        for m in _COLOR_ONLY_RE.finditer(blob):
            found.append(make_finding(
                "NOTE", "LOW", "COLOR_ONLY_CUE", 0, m.group(0)[:80],
                "This instruction relies on colour alone (“" + m.group(0) + "”), which people who cannot "
                "perceive that colour may miss.",
                "Name the control by its label or position as well as (or instead of) its colour.",
                None, source))
            a11y_n += 1
            break

        # Weak / unclear CTAs
        for m in _WEAK_CTA_RE.finditer(blob):
            found.append(make_finding(
                "NOTE", "LOW", "UNCLEAR_CTA", 0, m.group(0)[:80],
                f"“{m.group(0)}” is a vague call to action — destination and purpose are unclear for assistive tech.",
                "Use a descriptive CTA such as “Book a site visit” or “Download the price list”.",
                None, source))
            a11y_n += 1
            break

        checks.append(("Text accessibility", "done",
                       f"{a11y_n} accessibility note(s) on the text." if a11y_n else "No text accessibility issues flagged."))
    else:
        checks.append(("Text accessibility", "not_available", "Text accessibility checks are switched off."))

    return found, checks


def check_alt_text(alt_text, reg, make_finding, kind="image"):
    """Optional alt/caption requirement for image uploads."""
    cfg = config(reg)
    if kind != "image" or not cfg.get("require_alt_text"):
        return [], [("Alt text", "not_available",
                     "Alt text is not required, or this is not an image." if kind != "image"
                     else "Alt-text requirement is off.")]
    if (alt_text or "").strip():
        return [], [("Alt text", "done", "Alt text / image description provided.")]
    return [make_finding(
        "SUPERVISION", "LOW", "MISSING_ALT", 0, "(no alt text)",
        "Brand accessibility rules require an alt text or short image description for posters and images.",
        "Add a brief description of what the image shows and any key text or offer on it.",
        None, "screen")], [("Alt text", "done", "Alt text missing.")]


def check_content(reg, make_finding, *, path=None, lines=None, segments=None, caption="",
                  alt_text="", kind="document", source=None):
    """Run the right mix of image + text visual/a11y checks for this submission kind.

    - image: pixel checks + OCR/caption text rules + optional alt
    - document / paste: text rules on document body
    - video: text rules on transcript + OCR aggregate (no per-frame pixel pass — too slow/fragile for demo)
    """
    found, checks = [], []
    src = source or ("screen" if kind in ("image", "document") else "audio")

    if kind == "image" and path:
        f, c = check_image(path, lines, reg, make_finding)
        found += f
        checks += c
        af, ac = check_alt_text(alt_text, reg, make_finding, kind="image")
        found += af
        checks += ac

    blob = text_blob(lines=lines, segments=segments, caption=caption, alt_text=alt_text)
    # Prefer screen source for OCR/document; caption-only falls back.
    text_source = src
    if kind == "video":
        text_source = "screen" if lines else "audio"
    elif kind == "document":
        text_source = "screen"
    elif kind == "image":
        text_source = "screen"

    tf, tc = check_text(blob, reg, make_finding, source=text_source)
    found += tf
    checks += tc
    return found, checks
