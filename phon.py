"""Sound-alike matching for words heard by speech-to-text.

Speech-to-text spells the same Marathi or Hindi word many ways ('पझेशन', 'पोजेशन', 'पजेशन'), and writes English
place names in Devanagari ('वाकड' for Wakad). A word's skeleton keeps only its consonant sounds, with aspirated and
unaspirated forms merged and vowels dropped, so these spellings compare equal:
    skel('पझेशन') == skel('पोजेशन') == 'pjsn'
    latin_skel('Wakad') == latin_skel('वाकड') == 'vkd'
Short skeletons (fewer than 3 consonants) are too ambiguous to match by sound; those words must match exactly.
"""
import re

_DEVA = {
    "क": "k", "ख": "k", "क़": "k", "ख़": "k", "ग": "g", "घ": "g", "ग़": "g", "ङ": "n",
    "च": "c", "छ": "c", "ज": "j", "झ": "j", "ज़": "j", "ञ": "n",
    "ट": "t", "ठ": "t", "त": "t", "थ": "t",
    "ड": "d", "ढ": "d", "ड़": "d", "ढ़": "d", "द": "d", "ध": "d",
    "ण": "n", "न": "n", "प": "p", "फ": "p", "फ़": "p", "ब": "b", "भ": "b", "म": "m",
    "य": "y", "य़": "y", "र": "r", "ऱ": "r", "ल": "l", "ळ": "l", "व": "v",
    "श": "s", "ष": "s", "स": "s", "ह": "h",
}
# English spellings, longest first so 'sh' is read before 's'
_LATIN = [("sch", "s"), ("tch", "c"), ("ch", "c"), ("sh", "s"), ("th", "t"), ("dh", "d"), ("ph", "p"), ("bh", "b"),
          ("kh", "k"), ("gh", "g"), ("jh", "j"), ("ck", "k"), ("dg", "j"), ("x", "ks"), ("q", "k"), ("z", "j"),
          ("f", "p"), ("w", "v"), ("c", "k")]
_LATIN_CONS = set("bcdghjklmnprstvy")
_DIGITS = str.maketrans("०१२३४५६७८९", "0123456789")
_TOKEN = re.compile(r"(?:[^\W_]|[ऀ-ॣ०-ॿ])+")


def tokens(text):
    """Lower-case words of a sentence, Devanagari vowel signs kept, Devanagari digits read as 0-9."""
    return [t for t in _TOKEN.findall((text or "").translate(_DIGITS).lower())]


def skel(word):
    """Consonant skeleton of one word, in Latin letters, for Devanagari or English spelling."""
    w = (word or "").lower().translate(_DIGITS).replace("़", "")  # nukta
    out = []
    i = 0
    while i < len(w):
        ch = w[i]
        if ch in _DEVA:
            out.append(_DEVA[ch])
        elif ch.isdigit():
            out.append(ch)
        elif "a" <= ch <= "z":
            for src, dst in _LATIN:
                if w.startswith(src, i):
                    out.append(dst)
                    i += len(src)
                    break
            else:
                if ch in _LATIN_CONS:
                    out.append(ch)
                i += 1
            continue
        i += 1  # vowels, vowel signs, anusvara, halant: dropped
    s = "".join(out)
    return re.sub(r"(.)\1+", r"\1", s)  # 'tt' and 'त्त' are one sound


latin_skel = skel  # the skeleton is already in Latin letters, so English and Devanagari spellings compare directly


def _matches(tok, word):
    if tok == word:
        return True
    ws, ts = skel(word), skel(tok)
    if len(ws) < 3:
        return False
    # allow a short Marathi/Hindi ending on the heard word ('पझेशनची')
    return ts == ws or (len(ws) >= 4 and ts.startswith(ws) and len(ts) <= len(ws) + 2)


def index_of(toks, words):
    """Positions in toks of any of words, in any spelling that sounds the same."""
    words = [w.lower() for w in words]
    return [i for i, t in enumerate(toks) if any(_matches(t, w) for w in words)]


def has_any(text, words):
    return bool(index_of(tokens(text), words))
