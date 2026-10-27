"""BrandGuard amount reader: amounts and percentages spoken or written in English, Hindi and Marathi.

It composes a number the way people say it, for any product, from a few rupees to crores:
  "9 हजार 477 रुपये", "nine thousand four hundred seventy", "नऊ हजार चारशे सत्तर रुपये",
  "1 crore 30 lakh", "डेढ़ हजार", "साडेतीन लाख", "30%", "तीस टक्के".

Design:
* Number words 1-99 are a fixed list per language (not an open-ended patch list); hundreds, thousands, lakhs and
  crores are multipliers combined by one rule (Indian numbering).
* A number only counts as money when it is a lakh/crore amount or sits next to a currency word (rupees, Rs, INR, रुपये).
  A bare "2 BHK" or "30" is never a price.
* Everything here is deterministic. An AI step (see aiassist.py) may suggest readings, and code checks them against this.
"""

import re

CRORE, LAKH, THOUSAND, HUNDRED = 10_000_000, 100_000, 1_000, 100

NUM_RE = re.compile(r"\d+(?:\.\d+)?")
EDGE = ".,;:!?()[]{}\"'|।॥-–—*…/"
DEVA_DIGITS = str.maketrans("०१२३४५६७८९", "0123456789")


def _norm(s):
    import unicodedata
    return unicodedata.normalize("NFC", s or "")


# ----------------------------------------------------------- number words 1-99
_HI = """एक|दो|तीन|चार|पांच,पाँच|छह,छः,छे,छ|सात|आठ|नौ|दस|ग्यारह|बारह|तेरह|चौदह|पंद्रह,पन्द्रह|सोलह|सत्रह|अठारह|उन्नीस|बीस
इक्कीस|बाईस|तेईस|चौबीस|पच्चीस|छब्बीस|सत्ताईस|अट्ठाईस,अठाईस|उनतीस|तीस
इकतीस|बत्तीस|तैंतीस,तेंतीस|चौंतीस,चौतीस|पैंतीस,पैतीस|छत्तीस|सैंतीस,सैतीस|अड़तीस,अडतीस|उनतालीस,उन्तालीस|चालीस
इकतालीस|बयालीस|तैंतालीस,तितालीस|चौवालीस,चवालीस|पैंतालीस|छियालीस|सैंतालीस|अड़तालीस,अडतालीस|उनचास|पचास
इक्यावन|बावन|तिरपन,तिरेपन|चौवन|पचपन|छप्पन|सत्तावन|अट्ठावन,अठावन|उनसठ|साठ
इकसठ|बासठ|तिरसठ,तिरेसठ|चौंसठ|पैंसठ|छियासठ|सड़सठ,सरसठ|अड़सठ|उनहत्तर,उन्हत्तर|सत्तर
इकहत्तर|बहत्तर|तिहत्तर|चौहत्तर|पचहत्तर|छिहत्तर|सतहत्तर|अठहत्तर|उन्यासी,उनासी|अस्सी
इक्यासी|बयासी|तिरासी|चौरासी|पचासी|छियासी|सत्तासी|अट्ठासी,अठासी|नवासी|नब्बे
इक्यानवे|बानवे|तिरानवे|चौरानवे|पचानवे|छियानवे|सत्तानवे|अट्ठानवे,अठानवे|निन्यानवे"""

_MR = """एक|दोन|तीन|चार|पाच|सहा|सात|आठ|नऊ|दहा|अकरा|बारा|तेरा|चौदा|पंधरा|सोळा|सतरा|अठरा|एकोणीस|वीस
एकवीस|बावीस|तेवीस|चोवीस|पंचवीस|सव्वीस|सत्तावीस|अठ्ठावीस,अट्ठावीस|एकोणतीस|तीस
एकतीस|बत्तीस|तेहतीस|चौतीस|पस्तीस|छत्तीस|सदतीस|अडतीस|एकोणचाळीस|चाळीस
एक्केचाळीस|बेचाळीस|त्रेचाळीस|चव्वेचाळीस|पंचेचाळीस|सेहेचाळीस,सेचाळीस|सत्तेचाळीस|अठ्ठेचाळीस|एकोणपन्नास|पन्नास
एकावन्न|बावन्न|त्रेपन्न|चोपन्न|पंचावन्न|छप्पन्न|सत्तावन्न|अठ्ठावन्न|एकोणसाठ|साठ
एकसष्ट|बासष्ट|त्रेसष्ट|चौसष्ट|पासष्ट|सहासष्ट|सदुसष्ट|अडुसष्ट|एकोणसत्तर|सत्तर
एकाहत्तर|बाहत्तर|त्र्याहत्तर|चौऱ्याहत्तर|पंच्याहत्तर|शहात्तर|सत्त्याहत्तर,सत्याहत्तर|अठ्ठ्याहत्तर|एकोणऐंशी|ऐंशी
एक्क्याऐंशी|ब्याऐंशी|त्र्याऐंशी|चौऱ्याऐंशी|पंचाऐंशी|शह्याऐंशी|सत्त्याऐंशी|अठ्ठ्याऐंशी|एकोणनव्वद|नव्वद
एक्क्याण्णव|ब्याण्णव|त्र्याण्णव|चौऱ्याण्णव|पंचाण्णव|शहाण्णव|सत्त्याण्णव|अठ्ठ्याण्णव|नव्व्याण्णव"""

_EN = ("one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen "
       "eighteen nineteen twenty").split()
_EN_TENS = {"thirty": 30, "forty": 40, "fourty": 40, "fifty": 50, "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90}

# common romanised (Latin-script) spellings, as speech models often write them
_ROMAN = {
    "ek": 1, "do": 2, "don": 2, "teen": 3, "char": 4, "chaar": 4, "paanch": 5, "panch": 5, "paach": 5, "pach": 5,
    "chhe": 6, "cheh": 6, "chah": 6, "saha": 6, "saat": 7, "aath": 8, "aat": 8, "nau": 9, "nav": 9,
    "das": 10, "daha": 10, "gyarah": 11, "akra": 11, "barah": 12, "bara": 12, "terah": 13, "tera": 13, "chaudah": 14,
    "pandrah": 15, "pandhra": 15, "solah": 16, "sola": 16, "satrah": 17, "satra": 17, "atharah": 18, "athra": 18,
    "unnis": 19, "bees": 20, "vees": 20, "pachchis": 25, "pachees": 25, "pachis": 25, "tees": 30, "tis": 30,
    "chalis": 40, "chaalis": 40, "pachas": 50, "pannas": 50, "saath": 60, "sath": 60, "sattar": 70, "satar": 70,
    "assi": 80, "ashi": 80, "nabbe": 90, "navvad": 90, "pachhattar": 75, "pachattar": 75, "pachahattar": 75,
}

WORDS = {}


def _load(table):
    """The lists are consecutive: the n-th entry is the number n (alternate spellings joined by commas)."""
    entries = [e for line in table.split("\n") for e in line.split("|")]
    assert len(entries) == 99, len(entries)
    for n, forms in enumerate(entries, start=1):
        for f in forms.split(","):
            if f.strip():
                WORDS.setdefault(_norm(f.strip()).lower(), n)


_load(_HI)
_load(_MR)
for i, w in enumerate(_EN):
    WORDS[w] = i + 1
WORDS.update(_EN_TENS)
WORDS.update({_norm(k): v for k, v in _ROMAN.items()})
WORDS["zero"] = 0

# stand-alone fractions before a multiplier: "dedh hazar" = 1500, "dhai lakh" = 2.5 lakh
FRACTION = {_norm(k): v for k, v in {
    "dedh": 1.5, "deed": 1.5, "डेढ": 1.5, "डेढ़": 1.5, "दीड": 1.5, "dhai": 2.5, "adhai": 2.5, "ढाई": 2.5, "अडीच": 2.5,
    "sava": 1.25, "sawa": 1.25, "savva": 1.25, "सवा": 1.25, "सव्वा": 1.25}.items()}
# modifiers before a number: "saade teen" = 3.5, "pavne do" = 1.75
MODIFIER = {_norm(k): v for k, v in {
    "saade": 0.5, "sade": 0.5, "saadhe": 0.5, "साडे": 0.5, "साढ़े": 0.5, "साढे": 0.5,
    "paune": -0.25, "pavne": -0.25, "paun": -0.25, "पौने": -0.25, "पावणे": -0.25}.items()}
CONNECTORS = {"and", "आणि", "आणी"}
# also accept the speech-model mishearings already collected in engine.py (e.g. "धीर" for dedh)
from engine import FIXED as _EFIXED, MODS as _EMODS  # noqa: E402
FRACTION.update(_EFIXED)
MODIFIER.update(_EMODS)
POINT = {"point", "dot", "पॉइंट", "पॉईंट", "पॉइन्ट", "दशमलव"}

# multipliers (a few spellings plus inflected endings such as लाखा, लाखांपर्यंत, lakhon)
_MULT_EXACT = {"hundred": HUNDRED, "sau": HUNDRED, "सौ": HUNDRED, "शंभर": HUNDRED, "shambhar": HUNDRED, "सो": HUNDRED,
               "thousand": THOUSAND, "k": THOUSAND, "cr": CRORE}
_MULT_STEMS = [("हजार", THOUSAND), ("हज़ार", THOUSAND), ("hazar", THOUSAND), ("hazaar", THOUSAND), ("hajar", THOUSAND),
               ("thousand", THOUSAND), ("लाख", LAKH), ("lakh", LAKH), ("laakh", LAKH), ("lac", LAKH),
               ("कोटी", CRORE), ("कोटि", CRORE), ("करोड", CRORE), ("करोड़", CRORE), ("crore", CRORE), ("koti", CRORE),
               ("karod", CRORE), ("karor", CRORE)]
_MULT_STEMS = [(_norm(s), m) for s, m in _MULT_STEMS]
_HUNDRED_SUFFIX = re.compile(r"^(.+?)(शे|शें|she|shey|sho)$")

_CUR_STEMS = ("रुपय", "रुपए", "रुपये", "रुपया", "रू", "rupee", "rupay", "rupaye", "rupaya", "rupe", "inr", "rs", "रु", "₹")
_PCT_WORDS = ("%", "percent", "percentage", "pct", "प्रतिशत", "टक्के", "टक्का", "टक्क्यांनी", "टक्क्यांचा", "फीसदी",
              "फ़ीसदी", "pratishat", "takke", "takka", "fisadi")
_NON_MONEY_AFTER = {"sq", "sqft", "square", "feet", "foot", "फूट", "चौरस", "km", "किमी", "kg", "किलो", "mm", "gb", "mb",
                    "mah", "watt", "year", "years", "वर्ष", "साल", "वर्षे", "months", "महीने", "महिने"}


def multiplier_of(tok):
    m = _MULT_EXACT.get(tok)
    if m:
        return m
    for stem, mult in _MULT_STEMS:
        if tok.startswith(stem) and len(tok) - len(stem) <= 8:
            return mult
    return None


def is_currency(tok):
    return any(tok == c or (len(c) >= 4 and tok.startswith(c)) for c in _CUR_STEMS)


def is_percent(tok):
    return tok in _PCT_WORDS or any(tok.startswith(w) for w in _PCT_WORDS if len(w) >= 6)


# -------------------------------------------------------------- tokenising
def tokenize(text):
    t = _norm(text).lower().translate(DEVA_DIGITS)
    t = t.replace("₹", " rs ").replace("%", " % ")
    t = re.sub(r"(\d)(?=[^\d\s.,])", r"\1 ", t)          # 1.3cr -> 1.3 cr ; 9hazar -> 9 hazar
    toks = []
    for raw in t.split():
        tok = raw.strip(EDGE)
        if not tok:
            continue
        if re.fullmatch(r"\d{1,3}(,\d{2,3}){1,}", tok):   # 9,477 and 1,30,000
            tok = tok.replace(",", "")
        elif re.fullmatch(r"\d+,\d{1,2}", tok):
            tok = tok.replace(",", ".")
        toks.append(tok)
    return toks


def classify(tok):
    """('num', value) | ('mult', m) | ('frac', v) | ('mod', delta) | ('point',) | None"""
    if NUM_RE.fullmatch(tok):
        return ("num", float(tok))
    if tok in POINT:
        return ("point", 0)
    if tok in CONNECTORS:
        return ("conn", 0)
    if tok in WORDS:
        return ("num", float(WORDS[tok]))
    if tok in FRACTION:
        return ("frac", FRACTION[tok])
    if tok in MODIFIER:
        return ("mod", MODIFIER[tok])
    m = multiplier_of(tok)
    if m:
        return ("mult", m)
    h = _HUNDRED_SUFFIX.match(tok)                          # चारशे = चार + शे, charshe
    if h and h.group(1) in WORDS and 0 < WORDS[h.group(1)] < 10:
        return ("num", float(WORDS[h.group(1)] * 100))
    for key, delta in MODIFIER.items():                     # साडेतीन (joined)
        if tok.startswith(key) and tok[len(key):] in WORDS:
            return ("num", WORDS[tok[len(key):]] + delta)
    return None


# ----------------------------------------------------------------- composing
def _combinable(prev, v):
    """Can the number v directly follow prev inside one amount? tens+ones, hundreds+tens/ones."""
    if prev is None:
        return False
    if 20 <= prev < 100 and prev % 10 == 0 and 0 < v < 10:
        return True
    return prev >= 100 and prev % 100 == 0 and 0 < v < 100


def _compose(items):
    """items: [(kind, value)] of one candidate phrase. Returns (value, multipliers_seen) or None."""
    total, cur, prev, last_mult, seen, pending = 0.0, None, None, None, [], 0.0
    i = 0
    while i < len(items):
        kind, v = items[i][0], items[i][1]
        if kind == "conn":
            pass
        elif kind == "mod":
            pending = v
        elif kind == "frac":
            if cur is not None:
                return None
            cur, prev = v, None
        elif kind == "num":
            v += pending
            pending = 0.0
            if cur is None:
                cur, prev = v, v
            elif _combinable(prev, v):
                cur, prev = cur + v, v
            else:
                return None                                  # two unrelated numbers in a row
        elif kind == "point":                                # "one point three"
            digits, j = "", i + 1
            while j < len(items) and items[j][0] == "num" and items[j][1] == int(items[j][1]) and 0 <= items[j][1] <= 9:
                digits += str(int(items[j][1]))
                j += 1
            if cur is None or not digits:
                return None
            cur, prev = cur + float("0." + digits), None
            i = j
            continue
        elif kind == "mult":
            if v == HUNDRED:
                cur = (cur if cur is not None else 1) * HUNDRED
                prev = cur
            else:
                if last_mult is not None and v >= last_mult:
                    return None                              # order must go down: crore, lakh, thousand
                total += (cur if cur is not None else 1) * v
                cur, prev, last_mult = None, None, v
                seen.append(v)
        i += 1
    return total + (cur or 0), seen


def phrases(text):
    """Find number phrases. Returns [{'value','mults','start','end','toks'}] with token indexes."""
    toks = tokenize(text)
    cls = [classify(t) for t in toks]
    # the letter "l" counts as lakh only straight after a number: "1.3 L"
    for i, t in enumerate(toks):
        if t == "l" and i and cls[i - 1] and cls[i - 1][0] == "num" and NUM_RE.fullmatch(toks[i - 1]):
            cls[i] = ("mult", LAKH)
    out, i = [], 0
    while i < len(toks):
        if cls[i] is None or cls[i][0] in ("point", "conn"):
            i += 1
            continue
        j = i
        while j < len(toks) and cls[j] is not None:
            j += 1
        while j > i and cls[j - 1][0] == "conn":
            j -= 1
        # longest valid prefix of the run i..j
        end = j
        got = None
        while end > i:
            if cls[end - 1][0] == "conn":
                end -= 1
                continue
            got = _compose([cls[k] for k in range(i, end)])
            if got is not None and got[0] > 0:
                break
            got = None
            end -= 1
        if got is None:
            i += 1
            continue
        out.append({"value": got[0], "mults": got[1], "start": i, "end": end, "toks": toks})
        i = end
    return out


def _near_currency(toks, start, end):
    before = [t for t in toks[max(0, start - 2):start]]
    after = [t for t in toks[end:end + 2]]
    return any(is_currency(t) for t in before + after)


def extract_amounts(text):
    """Money amounts in rupees: [{'value': int, 'spoken': str}]. Same shape the checker already uses."""
    out = []
    for p in phrases(text):
        toks, s, e = p["toks"], p["start"], p["end"]
        big = any(m >= LAKH for m in p["mults"])
        cur = _near_currency(toks, s, e)
        after = toks[e] if e < len(toks) else ""
        if not (big or cur):
            continue
        if after in _NON_MONEY_AFTER or is_percent(after):
            continue
        spoken = " ".join(toks[max(0, s - 1 if s and is_currency(toks[s - 1]) else s):min(len(toks), e + (1 if after and is_currency(after) else 0))])
        out.append({"value": round(p["value"]), "spoken": spoken})
    return out


def extract_percents(text):
    """Percentages: [{'value': float, 'spoken': str}]  e.g. '30% off', 'तीस टक्के सूट'."""
    out = []
    for p in phrases(text):
        toks, e = p["toks"], p["end"]
        if e < len(toks) and is_percent(toks[e]) and not p["mults"]:
            out.append({"value": round(p["value"], 2), "spoken": " ".join(toks[p["start"]:e + 1])})
    return out
