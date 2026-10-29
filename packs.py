"""Starter rule packs by industry.

A new company should not have to type every banned phrase from scratch. At sign-up it picks its industry and gets the
general advertising rules plus that industry's starter list. The lists are copied into the company's own rules, so
everything is visible and can be edited or removed on the Brand Rules page. Packs can also be added later.

These are starter lists of claims that are commonly challenged in advertising (guarantees, "risk free", cures,
"100% secure"). They are not legal advice, and each company must review them for its own products and regulators.
Phrases are specific multi-word claims on purpose, so ordinary sentences are not rejected.
"""

GENERAL = {
    "label": "General advertising rules",
    "banned": ["100% safe", "100% guaranteed", "completely risk free", "risk-free", "risk free", "zero risk", "no risk",
               "guaranteed results", "guaranteed success", "miracle", "instant results", "best in the world",
               "world's best", "number one in the world", "100% सुरक्षित", "कोई जोखिम नहीं", "जोखीम नाही", "चमत्कार"],
    "terminology": [],
    "tone": ["limited time only", "last chance", "don't miss out"],
}

PACKS = {
    "real_estate": {
        "label": "Real estate",
        "banned": ["guaranteed returns", "assured returns", "guaranteed appreciation", "price will double",
                   "best in city", "no hidden charges", "assured rental", "गारंटीड रिटर्न", "पैसे दुप्पट"],
        "terminology": ["cheap => affordable"],
        "tone": [],
    },
    "finance": {
        "label": "Banking, investing and loans",
        "banned": ["guaranteed returns", "assured returns", "guaranteed profit", "sure shot returns", "double your money",
                   "risk-free investment", "get rich quick", "never lose money", "beat the market every time",
                   "100% safe investment", "no credit check", "guaranteed loan approval", "गारंटीड रिटर्न",
                   "गारंटीड रिटर्न्स", "पैसे दुप्पट", "पैसे दोगुने", "पक्का मुनाफा"],
        "terminology": [],
        "tone": ["get rich"],
    },
    "insurance": {
        "label": "Insurance",
        "banned": ["guaranteed claim settlement", "100% claim settlement", "no claim rejection", "claim is always approved",
                   "guaranteed returns", "assured returns"],
        "terminology": [],
        "tone": [],
    },
    "pharma": {
        "label": "Pharma and healthcare",
        "banned": ["guaranteed cure", "100% cure", "permanent cure", "miracle cure", "no side effects", "zero side effects",
                   "cures cancer", "cures diabetes", "reverses diabetes", "no prescription needed",
                   "कोई साइड इफेक्ट नहीं", "साइड इफेक्ट नाही", "पक्का इलाज", "100% इलाज"],
        "terminology": [],
        "tone": [],
    },
    "food": {
        "label": "Food and beverage",
        "banned": ["cures", "heals", "boosts immunity", "prevents cancer", "diabetes safe", "zero side effects",
                   "100% pure", "100% natural", "burns fat", "detox"],
        "terminology": [],
        "tone": [],
    },
    "tech": {
        "label": "Technology and software",
        "banned": ["100% secure", "unhackable", "hack proof", "hackproof", "unbreakable", "military grade security",
                   "100% uptime", "zero downtime guaranteed", "never fails", "100% accurate", "guaranteed 10x"],
        "terminology": [],
        "tone": [],
    },
    "education": {
        "label": "Education and coaching",
        "banned": ["100% placement", "guaranteed placement", "guaranteed job", "guaranteed admission", "100% selection",
                   "guaranteed rank", "100% pass", "100% success rate"],
        "terminology": [],
        "tone": [],
    },
    "ecommerce": {
        "label": "E-commerce and retail",
        "banned": ["lowest price guaranteed", "cheapest in india", "cheapest in the world", "best price in india",
                   "100% original guaranteed"],
        "terminology": [],
        "tone": ["only few left", "selling fast"],
    },
    "beauty": {
        "label": "Beauty and personal care",
        "banned": ["skin whitening", "instant fairness", "get fair", "permanent hair removal", "100% hair growth",
                   "guaranteed hair growth", "anti-ageing guaranteed", "removes wrinkles permanently"],
        "terminology": [],
        "tone": [],
    },
}

OPTIONS = [("", "Other (general rules only)")] + [(k, v["label"]) for k, v in PACKS.items()]


def apply(reg, keys):
    """Merge the general pack and the chosen industry packs into a registry. Returns the counts added."""
    added = {"banned_phrases": 0, "terminology": 0, "avoid_tone": 0}
    chosen = [GENERAL] + [PACKS[k] for k in keys if k in PACKS]
    for pack in chosen:
        for field, src in (("banned_phrases", "banned"), ("terminology", "terminology"), ("avoid_tone", "tone")):
            have = {x.lower() for x in reg.get(field, [])}
            for item in pack.get(src, []):
                if item.lower() not in have:
                    reg.setdefault(field, []).append(item)
                    have.add(item.lower())
                    added[field] += 1
    return added
