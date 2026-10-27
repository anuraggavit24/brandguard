#!/usr/bin/env python3
"""
BrandGuard - engine
audio/video -> transcript (Marathi/Hindi/English) -> price extraction
-> fact-registry check -> banned/confidential check -> verdict

Usage:
  python engine.py --selftest
  python engine.py --text "2 BHK sirf dedh crore mein" --registry sample_registry.json
  python engine.py reel.mp4 --registry sample_registry.json --lang mr --model medium
"""

import argparse
import json
import math
import re
import sys
import unicodedata
from pathlib import Path

CRORE = 10_000_000
LAKH = 100_000


# ---------------------------------------------------------------- text helpers
def norm(s):
    return unicodedata.normalize("NFC", s)


def _n(d):
    return {norm(k).lower(): v for k, v in d.items()}


DEVA_DIGITS = str.maketrans("०१२३४५६७८९", "0123456789")
EDGE = ".,;:!?()[]{}\"'|।॥-–—*…"

UNITS = _n({
    "cr": CRORE, "crore": CRORE, "crores": CRORE, "koti": CRORE, "karod": CRORE, "karor": CRORE,
    "करोड": CRORE, "करोड़": CRORE, "करोड़ों": CRORE, "कोटी": CRORE, "कोटि": CRORE,
    "lakh": LAKH, "lakhs": LAKH, "lac": LAKH, "lacs": LAKH, "laakh": LAKH, "लाख": LAKH,
    "rupees": 1, "rupee": 1, "rs": 1, "inr": 1, "रुपये": 1, "रुपया": 1, "रुपए": 1,
})

# Marathi / Hindi inflect the unit word ("लाखा", "लाखांपर्यंत", "कोटींचा", "लाखों", "lakhon"). Accept a unit stem plus a short ending.
_STEMS = [(norm(k).lower(), v) for k, v in (("लाख", LAKH), ("कोटी", CRORE), ("कोटि", CRORE), ("करोड", CRORE),
                                            ("करोड़", CRORE), ("lakh", LAKH), ("laakh", LAKH), ("crore", CRORE),
                                            ("koti", CRORE), ("karod", CRORE))]


def unit_mult(tok):
    """Multiplier for a unit word, allowing inflected endings. None if it is not a unit."""
    m = UNITS.get(tok)
    if m is not None:
        return m
    for stem, mult in _STEMS:
        if tok.startswith(stem) and 0 < len(tok) - len(stem) <= 8:
            return mult
    return None


NUMWORDS = _n({
    "ek": 1, "एक": 1, "one": 1,
    "do": 2, "दो": 2, "don": 2, "दोन": 2, "two": 2,
    "teen": 3, "तीन": 3, "three": 3,
    "char": 4, "चार": 4, "four": 4,
    "paanch": 5, "panch": 5, "पाच": 5, "पांच": 5, "five": 5,
    "chhe": 6, "cheh": 6, "छह": 6, "छे": 6, "saha": 6, "सहा": 6, "six": 6,
    "saat": 7, "सात": 7, "seven": 7,
    "aath": 8, "आठ": 8, "eight": 8,
    "nau": 9, "नौ": 9, "नऊ": 9, "nine": 9,
    "das": 10, "दस": 10, "daha": 10, "दहा": 10, "ten": 10,
})

# stand-alone fractions: "dedh crore" = 1.5, "sava crore" = 1.25
# (includes common speech-to-text mishearings of dedh / deed)
FIXED = _n({
    "dedh": 1.5, "deed": 1.5, "डेढ": 1.5, "डेढ़": 1.5, "दीड": 1.5,
    "धीर": 1.5, "धीड": 1.5, "दिड": 1.5, "डीड": 1.5, "दीर": 1.5, "दिर": 1.5,
    "dhai": 2.5, "adhai": 2.5, "adeech": 2.5, "ढाई": 2.5, "अडीच": 2.5,
    "sava": 1.25, "sawa": 1.25, "savva": 1.25, "सवा": 1.25, "सव्वा": 1.25,
})

# modifiers before a number: "saade teen" = 3.5, "pavne do" = 1.75
MODS = _n({
    "saade": 0.5, "sade": 0.5, "saadhe": 0.5, "साडे": 0.5, "साढ़े": 0.5, "साढे": 0.5,
    "sava": 0.25, "sawa": 0.25, "savva": 0.25, "सवा": 0.25, "सव्वा": 0.25,
    "paune": -0.25, "pavne": -0.25, "paun": -0.25, "पौने": -0.25, "पावणे": -0.25,
})

# tens and common two-digit words: "thirty", "tees", "तीस", "pachees"
TENS = _n({
    "ten": 10, "twenty": 20, "thirty": 30, "forty": 40, "fifty": 50, "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90,
    "bees": 20, "tees": 30, "chalis": 40, "pachas": 50, "saath": 60, "sattar": 70, "assi": 80, "nabbe": 90,
    "pachees": 25, "pachchis": 25, "pachhattar": 75,
    "बीस": 20, "तीस": 30, "चालीस": 40, "चाळीस": 40, "पचास": 50, "पन्नास": 50, "साठ": 60, "सत्तर": 70, "ऐंशी": 80,
    "नव्वद": 90, "पंचवीस": 25, "पंचाहत्तर": 75, "पचहत्तर": 75, "वीस": 20,
})
FILLERS = _n({"and": 0, "aur": 0, "और": 0, "आणि": 0, "ani": 0, "plus": 0})

POINT = {norm(x).lower() for x in ["point", "पॉइंट", "पॉईंट", "दशमलव"]}
NUM_RE = re.compile(r"\d+(?:\.\d+)?")
PHONE_RE = re.compile(r"(?<!\d)(?:\+?91)?([6-9]\d{9})(?!\d)")
EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")


def tokenize(text):
    t = norm(text).lower().translate(DEVA_DIGITS).replace("₹", " ")
    t = re.sub(r"(\d)(?=[^\d\s.,])", r"\1 ", t)  # 1.3cr -> 1.3 cr
    toks = []
    for raw in t.split():
        tok = raw.strip(EDGE)
        if not tok:
            continue
        if re.fullmatch(r"\d{1,3}(,\d{2,3}){2,}|\d{1,3},\d{3}", tok):
            tok = tok.replace(",", "")
        elif re.fullmatch(r"\d+,\d{1,2}", tok):
            tok = tok.replace(",", ".")
        toks.append(tok)
    return toks


# ---------------------------------------------------------- number extraction
def parse_quantity(toks):
    """toks = tokens just before a unit word. Returns a float or None."""
    if not toks:
        return None
    last = toks[-1]
    if NUM_RE.fullmatch(last):                                  # 1.3
        return float(last)
    if (len(toks) >= 3 and toks[-2] in POINT                    # one point three
            and last in NUMWORDS and toks[-3] in NUMWORDS):
        return NUMWORDS[toks[-3]] + NUMWORDS[last] / 10
    if last in TENS:                                            # tees, thirty
        return float(TENS[last])
    if last in NUMWORDS and len(toks) >= 2 and toks[-2] in TENS and TENS[toks[-2]] >= 20:   # thirty five
        return float(TENS[toks[-2]] + NUMWORDS[last])
    if last in FIXED:                                           # dedh, dhai, sava
        return FIXED[last]
    for key, delta in MODS.items():                             # साडेतीन (joined)
        if last.startswith(key) and last[len(key):] in NUMWORDS:
            return NUMWORDS[last[len(key):]] + delta
    if last in NUMWORDS:                                        # teen / साडे तीन
        n = NUMWORDS[last]
        if len(toks) >= 2 and toks[-2] in MODS:
            return n + MODS[toks[-2]]
        return float(n)
    return None


def extract_prices(text):
    """Money amounts in rupees found in the text. Implemented in numbers.py (any product, rupees to crores)."""
    import amounts as _amounts
    return _amounts.extract_amounts(text)


def find_unparsed_units(text):
    """Amounts (crore/lakh) that were spoken but whose number could not be read."""
    toks = tokenize(text)
    bad = []
    for i, tok in enumerate(toks):
        if (unit_mult(tok) or 0) > 1:
            if parse_quantity(toks[max(0, i - 4):i]) is None:
                bad.append(" ".join(toks[max(0, i - 3):i + 1]))
    return bad


def fmt_money(v):
    if v >= CRORE:
        return f"₹{v / CRORE:.2f} Cr"
    if v >= LAKH:
        return f"₹{v / LAKH:.2f} Lakh"
    return f"₹{v:,.0f}"


def fmt_time(t):
    t = int(t)
    return f"{t // 60}:{t % 60:02d}"


# ------------------------------------------------------------- price decision
def classify_price(value, prices, conf, threshold):
    """prices = [(config_name, price)]. Returns (status, type, explanation, name, ref)."""
    name, ref = min(prices, key=lambda p: abs(math.log(value / p[1])))
    ratio = value / ref
    if abs(ratio - 1) <= 0.005:
        return "PASS", None, "Matches approved price.", name, ref
    # magnitude error (lakh vs crore, dropped zeros): probably speech/unit error
    for k in range(1, 8):
        for scale in (10 ** k, 10 ** -k):
            if abs(ratio / scale - 1) <= 0.02:
                return ("SUPERVISION", "PRICE_UNIT_CHECK",
                        f"Heard {fmt_money(value)} vs approved {fmt_money(ref)} ({name}). "
                        f"Looks like a unit or transcription error; needs a human to listen.",
                        name, ref)
    # small deviation: possible misquote
    if abs(ratio - 1) <= 0.30:
        if conf >= threshold:
            return ("FLAG", "PRICE_MISMATCH",
                    f"Said {fmt_money(value)} but the approved price for {name} is {fmt_money(ref)}.",
                    name, ref)
        return ("SUPERVISION", "PRICE_LOW_CONFIDENCE",
                f"Heard {fmt_money(value)} (approved {fmt_money(ref)} for {name}) but the audio "
                f"confidence is low. A human should confirm what was said.", name, ref)
    return ("SUPERVISION", "PRICE_NOT_IN_REGISTRY",
            f"{fmt_money(value)} is far from every approved price. Check which unit it refers to.",
            name, ref)


# --------------------------------------------------------------------- review
def review(segments, reg, threshold=0.65, check_prices=True):
    prices = [(c["name"], c["price"]) for c in reg.get("configs", [])]
    banned = [norm(x).lower() for x in reg.get("banned_phrases", [])]
    secret = [norm(x).lower() for x in reg.get("confidential", [])]
    allowed = {re.sub(r"\D", "", c)[-10:] for c in reg.get("allowed_contacts", [])}

    findings, clean = [], []

    def add(status, severity, ftype, t, evidence, explanation, suggestion, conf=None):
        findings.append({
            "status": status, "severity": severity, "type": ftype, "time": t,
            "evidence": evidence, "explanation": explanation,
            "suggestion": suggestion, "confidence": conf,
        })

    for seg in segments:
        text = norm(seg["text"])
        low = text.lower()
        t, conf = seg["start"], seg.get("conf", 1.0)

        # 1) confidential data -> blocks approval, value is redacted everywhere
        redacted = text
        for w in secret:
            if w in low:
                redacted = re.sub(re.escape(w), "[REDACTED]", redacted, flags=re.I)
                add("FLAG", "CRITICAL", "CONFIDENTIAL_DATA", t, "[REDACTED]",
                    "Internal company information is mentioned in the content.",
                    "Remove this part of the video before resubmitting.", conf)

        # 2) unrecognised contact details -> human check
        digits = re.sub(r"[\s-]", "", text)
        for m in PHONE_RE.finditer(digits):
            if m.group(1) not in allowed:
                add("SUPERVISION", "MEDIUM", "UNKNOWN_CONTACT", t, "[phone number]",
                    "A phone number that is not on the approved contact list is present.",
                    "Confirm this is an approved sales contact.", conf)
        if EMAIL_RE.search(text):
            add("SUPERVISION", "MEDIUM", "UNKNOWN_CONTACT", t, "[email]",
                "An email address is present.", "Confirm this is an approved contact.", conf)

        # 3) banned phrases
        for w in banned:
            if w in low:
                add("FLAG", "HIGH", "BANNED_PHRASE", t, w,
                    f'"{w}" is on the banned-claims list.',
                    "Remove or rephrase this claim.", conf)

        # 4) prices
        for p in (extract_prices(text) if check_prices and prices else []):
            status, ftype, why, name, ref = classify_price(p["value"], prices, conf, threshold)
            if status == "PASS":
                continue
            fix = (f"Use the approved price: {fmt_money(ref)} for {name}."
                   if status == "FLAG" else "Send to supervision with the audio clip.")
            add(status, "HIGH" if status == "FLAG" else "MEDIUM", ftype, t, p["spoken"], why, fix, conf)

        # 5) amounts spoken but unreadable -> never pass silently
        for ctx in find_unparsed_units(text):
            add("SUPERVISION", "MEDIUM", "UNCLEAR_AMOUNT", t, ctx,
                "An amount (crore or lakh) was spoken but the number before it could not be read. "
                "The speech model may have misheard it.",
                "A human should listen to this moment.", conf)

        clean.append({"start": seg["start"], "end": seg.get("end", seg["start"]),
                      "text": redacted, "conf": conf})

    flags = [f for f in findings if f["status"] == "FLAG"]
    sups = [f for f in findings if f["status"] == "SUPERVISION"]
    if any(f["severity"] == "CRITICAL" for f in findings):
        verdict = "BLOCKED - confidential data"
    elif flags:
        verdict = "REJECT - fix and resubmit"
    elif sups:
        verdict = "SUPERVISION - manager check needed"
    else:
        verdict = "PASS - auto-clear candidate"
    return {"verdict": verdict, "flags": len(flags), "supervision": len(sups),
            "findings": findings, "transcript": clean}


# --------------------------------------------------------------- transcription
def transcribe(path, model_size, language, glossary, device, compute):
    from faster_whisper import WhisperModel
    model = WhisperModel(model_size, device=device, compute_type=compute)
    prompt = ", ".join(glossary) if glossary else None
    segs, info = model.transcribe(str(path), language=language, initial_prompt=prompt,
                                  vad_filter=True, beam_size=5)
    out = []
    for s in segs:
        out.append({"start": round(s.start, 2), "end": round(s.end, 2),
                    "text": s.text.strip(), "conf": round(math.exp(s.avg_logprob), 3)})
    return out, info


# ---------------------------------------------------------------------- output
def print_report(rep, header=""):
    print("\n==== BrandGuard report ====")
    if header:
        print(header)
    print(f"Verdict : {rep['verdict']}")
    print(f"Summary : {rep['flags']} flag(s) | {rep['supervision']} supervision")
    if not rep["findings"]:
        print("No issues found.")
    for f in rep["findings"]:
        icon = "FLAG" if f["status"] == "FLAG" else "SUPERVISION"
        c = f" (conf {f['confidence']})" if f["confidence"] is not None else ""
        print(f"\n[{icon}] {fmt_time(f['time'])}  {f['type']}  severity={f['severity']}{c}")
        print(f"   heard : {f['evidence']}")
        print(f"   why   : {f['explanation']}")
        print(f"   fix   : {f['suggestion']}")
    print()


def selftest():
    cases = [
        ("2 BHK at 1.3 Cr", 13_000_000),
        ("price is one point three crore", 13_000_000),
        ("दीड कोटी", 15_000_000),
        ("धीर कोटी", 15_000_000),
        ("सव्वा कोटी", 12_500_000),
        ("साडे तीन कोटी", 35_000_000),
        ("साडेतीन कोटी", 35_000_000),
        ("पावणे दोन कोटी", 17_500_000),
        ("डेढ़ करोड़ रुपये", 15_000_000),
        ("₹1.3Cr", 13_000_000),
        ("१.३ कोटी", 13_000_000),
        ("dedh crore", 15_000_000),
        ("1.3 lakh", 130_000),
        ("1 crore 30 lakh", 13_000_000),
        ("ek crore tees lakh", 13_000_000),
        ("एक कोटी तीस लाख", 13_000_000),
        ("1 crore thirty five lakh", 13_500_000),
        ("प्लाट हे एक कोटी 30 लाखा परेंता", 13_000_000),
        ("एक कोटी तीस लाखा", 13_000_000),
        ("1 कोटी 30 लाखांपर्यंत", 13_000_000),
        ("1 करोड़ 30 लाखों", 13_000_000),
        ("1 crore 30 lakhon", 13_000_000),
    ]
    for text, expected in cases:
        got = [p["value"] for p in extract_prices(text)]
        assert got == [expected], f"{text!r}: expected {expected}, got {got}"
        print(f"ok  {text!r} -> {fmt_money(expected)}")

    prices = [("2 BHK", 13_000_000), ("3 BHK", 19_000_000)]
    assert classify_price(13_000_000, prices, 0.9, 0.65)[0] == "PASS"
    assert classify_price(130_000, prices, 0.9, 0.65)[0] == "SUPERVISION"
    assert classify_price(11_000_000, prices, 0.9, 0.65)[0] == "FLAG"
    assert classify_price(11_000_000, prices, 0.3, 0.65)[0] == "SUPERVISION"
    assert classify_price(5_000_000, prices, 0.9, 0.65)[0] == "SUPERVISION"
    print("ok  price decisions (pass / unit error / flag / low confidence / not in registry)")

    assert find_unparsed_units("फक्त xyz कोटी मदे") != []
    assert find_unparsed_units("फक्त दीड कोटी मदे") == []
    print("ok  unreadable amounts are caught instead of passing")

    reg = {"configs": [{"name": "2 BHK", "price": 13_000_000}],
           "banned_phrases": ["guaranteed returns"], "confidential": ["dealer commission"]}
    rep = review([{"start": 3, "end": 6,
                   "text": "guaranteed returns and dealer commission is two percent", "conf": 0.9}], reg)
    types = {f["type"] for f in rep["findings"]}
    assert {"BANNED_PHRASE", "CONFIDENTIAL_DATA"} <= types
    assert "dealer commission" not in rep["transcript"][0]["text"].lower()
    print("ok  banned phrase, confidential flag and redaction")
    print("\nAll checks passed.")


def main():
    ap = argparse.ArgumentParser(description="BrandGuard engine")
    ap.add_argument("media", nargs="?", help="video or audio file (e.g. audio.wav or reel.mp4)")
    ap.add_argument("--registry", default="sample_registry.json")
    ap.add_argument("--text", help="skip speech-to-text and check this text instead")
    ap.add_argument("--conf", type=float, default=None, help="fake confidence for --text mode (default 1.0)")
    ap.add_argument("--lang", default=None, help="mr, hi or en. Leave empty for auto-detect")
    ap.add_argument("--model", default="medium", help="small | medium | large-v3")
    ap.add_argument("--device", default="auto")
    ap.add_argument("--compute", default="auto")
    ap.add_argument("--threshold", type=float, default=0.65, help="confidence needed to flag a price")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()

    if args.selftest:
        selftest()
        return

    reg_path = Path(args.registry)
    if not reg_path.exists():
        sys.exit(f"Registry not found: {reg_path}")
    reg = json.loads(reg_path.read_text(encoding="utf-8"))

    if args.text:
        conf = args.conf if args.conf is not None else 1.0
        segments = [{"start": 0, "end": 0, "text": args.text, "conf": conf}]
        print_report(review(segments, reg, args.threshold), "Mode: typed text")
        return

    if not args.media:
        sys.exit("Give a media file, or use --text / --selftest")
    media = Path(args.media)
    if not media.exists():
        sys.exit(f"File not found: {media}")

    print(f"Transcribing with model '{args.model}' (first run may download the model)...")
    segments, info = transcribe(media, args.model, args.lang, reg.get("glossary"),
                                args.device, args.compute)
    rep = review(segments, reg, args.threshold)
    rep["language"] = info.language
    rep["language_probability"] = round(info.language_probability, 3)

    out = media.with_name(media.stem + "_report.json")
    out.write_text(json.dumps(rep, indent=2, ensure_ascii=False), encoding="utf-8")

    print_report(rep, f"Language: {info.language} ({info.language_probability:.2f}) | "
                      f"{len(segments)} segments")
    print("Redacted transcript:")
    for s in rep["transcript"]:
        print(f"  [{fmt_time(s['start'])}] (conf {s['conf']}) {s['text']}")
    print(f"\nFull report saved to: {out}")


if __name__ == "__main__":
    main()