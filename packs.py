"""Starter rule packs by industry.

A new company should not have to type every banned phrase from scratch. At sign-up it picks its industry and gets the
general advertising rules plus that industry's starter list. The lists are copied into the company's own rules, so
everything is visible and can be edited or removed on the Brand Rules page. Packs can also be added later.

How the lists are built
* Pattern families: a short list of assurance words ("guaranteed", "assured", "100%", Hindi and Marathi equivalents)
  is combined with the outcome words that matter in each industry ("returns", "placement", "claim settlement").
  A new outcome word adds a whole set of phrases at once, and nobody types them by hand.
* Sources: each pack lists the public rule or guideline that the pack is based on, so a company can see why a phrase is
  there and judge whether it applies to its product.
* Phrases are specific multi-word claims on purpose, so ordinary sentences are not rejected. Matching is whole-word.

These are starter lists of claims commonly challenged in advertising. They are not legal advice. Some phrases are
fine for some products (for example a bank's fixed deposit may state its fixed interest). The company must review the
list for its own products and regulators, and can remove anything that does not apply.
"""

# ------------------------------------------------------------- pattern pieces
ASSURE_SAFE = ["guaranteed", "100% guaranteed", "assured", "sure shot", "surefire"]
ASSURE_HI = ["गारंटीड", "पक्का", "पक्की", "100% गारंटीड", "निश्चित"]
ASSURE_MR = ["हमी", "हमीदार", "खात्रीशीर", "पक्का", "पक्की", "100% हमी"]
ABSOLUTE = ["100%", "total", "complete", "absolute"]
SPEED = ["instant", "overnight"]
LASTING = ["permanent", "lifetime", "forever"]
MIRACLE = ["miracle", "magic", "magical"]


def _join(prefixes, words):
    return [f"{p} {w}" for p in prefixes for w in words]


def _expand(spec):
    """Turn a pack spec into a de-duplicated list of phrases."""
    out = []
    out += spec.get("fixed", [])
    out += _join(spec.get("assure", ASSURE_SAFE), spec.get("outcomes", []))
    out += _join(["100%"], spec.get("percent", []))
    out += _join(["no", "zero", "without any"], spec.get("no", []))
    out += _join(SPEED, spec.get("fast", []))
    out += _join(LASTING, spec.get("lasting", []))
    out += _join(MIRACLE, spec.get("miracle", []))
    out += _join(spec.get("verbs", []), spec.get("things", []))
    out += _join(ASSURE_HI, spec.get("hi", []))
    out += _join(ASSURE_MR, spec.get("mr", []))
    out += spec.get("fixed_indic", [])
    seen, res = set(), []
    for p in out:
        k = " ".join(p.lower().split())
        if k and k not in seen:
            seen.add(k)
            res.append(" ".join(p.split()))
    return res


# diseases named in the schedule of the Drugs and Magic Remedies (Objectionable Advertisements) Act
DISEASES = ["cancer", "diabetes", "obesity", "heart disease", "high blood pressure", "blood pressure", "impotence",
            "tuberculosis", "leucoderma"]
DISEASES_INDIC = ["कैंसर", "मधुमेह", "डायबिटीज", "मोटापा", "हृदय रोग", "ब्लड प्रेशर", "क्षयरोग", "टीबी"]
CURE_VERBS = ["cures", "cure for", "permanent cure for", "reverses", "completely cures", "gets rid of"]

# ------------------------------------------------------------------ general
_GENERAL_SPEC = {
    "fixed": ["100% safe", "completely risk free", "guaranteed results", "guaranteed success", "instant results",
              "best in the world", "world's best", "number one in the world", "no. 1 in the world", "100% सुरक्षित",
              "कोई जोखिम नहीं", "जोखीम नाही", "चमत्कार", "चमत्कारी", "no risk", "risk-free", "risk free", "zero risk",
              "miracle", "100% effective", "works every time", "never fails",
              # investment-return promises, common on property and finance posters
              "double your earnings", "double your money", "double your investment", "triple your money",
              "watch your money grow", "grow your money", "your money will grow", "money will double",
              "multiply your money", "earn while you sleep", "passive income guaranteed",
              "once in a lifetime"],
}

GENERAL = {
    "label": "General advertising rules",
    "banned": _expand(_GENERAL_SPEC),
    "terminology": [],
    "tone": ["limited time only", "last chance", "don't miss out", "hurry while stocks last", "act now",
             "grab it before it's gone", "once in a blue moon"],
    "sources": [
        ("Consumer Protection Act 2019 and CCPA Guidelines for Prevention of Misleading Advertisements (2022)",
         "Advertisements must not make false or exaggerated performance claims, use bait advertising, or hide material "
         "conditions. Claims such as 'guaranteed' or 'free' need the conditions stated clearly."),
        ("ASCI Code for Self-Regulation of Advertising Content",
         "Absolute claims ('100%', 'best', 'number one') need documentary support. Without it they count as misleading."),
    ],
}

# ------------------------------------------------------------------ industries
_SPECS = {
    "real_estate": {
        "label": "Real estate",
        "spec": {
            "outcomes": ["returns", "appreciation", "rental", "rental income", "profit", "price rise", "buyback",
                         "possession", "resale value", "capital gains", "roi"],
            "no": ["hidden charges", "hidden costs", "risk"],
            "percent": ["safe investment", "legal", "clear title", "approved"],
            "fixed": ["price will double", "price will triple", "best in city", "best in the city", "number one project",
                      "no. 1 builder", "cheapest in the city", "highest returns", "returns higher than fd",
                      "better than fixed deposit", "double your investment", "limited units left", "only 2 units left",
                      "lowest price ever", "last few flats", "booking closing today", "everything approved",
                      "सर्व मंजूर", "गारंटीड रिटर्न", "पैसे दुप्पट", "किंमत दुप्पट", "कीमत दोगुनी"],
            "hi": ["रिटर्न", "रिटर्न्स", "किराया", "मुनाफा"],
            "mr": ["परतावा", "भाडे", "नफा"],
        },
        "terminology": ["cheap => affordable", "cheapest => most affordable", "RERA approved => RERA registered"],
        "tone": ["hurry", "now or never", "price hike tomorrow"],
        "sources": [
            ("RERA Act 2016, Section 12 and state RERA advertisement guidelines (for example UP-RERA, AP-RERA)",
             "The project's RERA registration number and the RERA portal must be shown prominently in every advertisement. "
             "Advertisements must not mislead buyers on approvals, amenities or completion dates."),
            ("SEBI (Collective Investment Scheme) Regulations",
             "Selling property as an investment with assured returns or buy-back can fall under collective investment rules. "
             "That is why 'assured returns', 'assured rental' and 'buyback' phrases are listed. Remove them only if your "
             "scheme is legally structured for them."),
            ("Consumer Protection Act 2019 and CCPA 2022 guidelines",
             "False or exaggerated claims about price rise, returns, or availability are misleading advertising."),
        ],
    },
    "finance": {
        "label": "Banking, investing and loans",
        "spec": {
            "outcomes": ["returns", "profit", "profits", "income", "growth", "wealth", "payout", "dividends",
                         "monthly income", "capital protection", "loan approval", "gains",
                         "appreciation", "doubling of money", "regular income", "market beating returns"],
            "no": ["risk", "loss", "credit check", "hidden charges"],
            "percent": ["safe investment", "safe", "secure investment", "approval", "loan approval", "capital protection"],
            "fixed": ["double your money", "triple your money", "get rich quick", "get rich", "never lose money",
                      "beat the market every time", "sure shot returns", "can't lose", "cannot lose", "money back guarantee",
                      "make money fast", "earn lakhs every month", "earn daily income", "guaranteed monthly income",
                      "100% safe investment", "no credit check", "guaranteed loan approval", "pre-approved for everyone", "garanteed returns",
                      "गारंटीड रिटर्न्स", "पैसे दोगुने", "पक्का मुनाफा", "पैसे दुप्पट", "जोखीममुक्त परतावा", "कोई नुकसान नहीं",
                      "तोटा नाही"],
            "hi": ["रिटर्न", "रिटर्न्स", "मुनाफा", "कमाई", "लोन"],
            "mr": ["परतावा", "नफा", "कमाई", "कर्ज"],
            "miracle": ["returns", "growth", "profit"],
            "fast": ["profit", "returns", "wealth", "money"],
        },
        "terminology": [],
        "tone": ["get rich", "easy money", "limited period interest rate"],
        "sources": [
            ("SEBI Master Circular for Mutual Funds and SEBI Advertisement Code for Mutual Funds and Investment Advisers",
             "Assured, guaranteed or fixed returns must not be promised for market-linked products. Past performance "
             "is not presented as a promise. Required risk disclaimers must be present."),
            ("SEBI (Investment Advisers) Regulations 2013 and SEBI circulars on finfluencers",
             "Investment advice or tips must not guarantee profits or hide risk."),
            ("RBI Fair Practices Code and Digital Lending Guidelines",
             "Loan advertisements must state the interest rate and fees honestly. 'Guaranteed approval' or 'no documents' "
             "claims are not allowed where the lender checks eligibility. Note: a bank may state the fixed interest of its "
             "own fixed deposit, so remove 'fixed' style phrases only if they do not apply."),
            ("CCPA guidelines 2022", "Bait advertising and hidden conditions in offers are not allowed."),
        ],
    },
    "insurance": {
        "label": "Insurance",
        "spec": {
            "outcomes": ["claim settlement", "claim approval", "claims", "claim payout", "claim", "cashless approval",
                         "policy approval", "acceptance", "coverage"],
            "no": ["claim rejection", "claim rejections", "exclusions", "hidden charges", "rejection"],
            "percent": ["claim settlement", "claim approval", "claim ratio", "cashless", "coverage", "covered"],
            "fixed": ["claim is always approved", "claims never rejected", "no claim rejection", "best insurance in india",
                      "cheapest insurance", "lowest premium guaranteed", "returns higher than fd", "double your money",
                      "100% claim settlement", "every claim paid", "all diseases covered", "all illnesses covered",
                      "covers everything", "coverage for everything", "pays for everything", "no exclusions",
                      "सर्व आजार कव्हर", "सभी बीमारियां कवर", "क्लेम हमेशा पास"],
            "hi": ["क्लेम", "कवर"],
            "mr": ["क्लेम", "कव्हर"],
        },
        "terminology": [],
        "tone": [],
        "sources": [
            ("IRDAI (Protection of Policyholders' Interests) Regulations and IRDAI advertisement guidelines",
             "Insurance advertisements must not mislead on benefits, exclusions or claim settlement, must not make claims "
             "beyond reasonable expectations, and must show that the product is insurance, with exclusions disclosed."),
            ("IRDAI note for this list",
             "Guaranteed-benefit plans may legitimately say 'guaranteed' for contract benefits, so phrases like 'guaranteed "
             "returns' are NOT in this pack. Add them yourself only if they never apply to your products."),
        ],
    },
    "pharma": {
        "label": "Pharma and healthcare",
        "spec": {
            "outcomes": ["cure", "relief", "recovery", "treatment", "results", "healing", "remedy", "improvement",
                         "safe", "effect", "pain relief"],
            "no": ["side effects", "side effect", "risk", "prescription needed", "doctor needed", "contraindications",
                   "harm", "pain"],
            "percent": ["cure", "natural", "safe", "effective", "pain free", "side effect free", "recovery", "relief"],
            "lasting": ["cure", "relief", "solution", "treatment"],
            "fast": ["cure", "relief", "recovery", "results", "weight loss"],
            "miracle": ["cure", "drug", "medicine", "treatment", "remedy", "herb", "oil"],
            "verbs": CURE_VERBS,
            "things": DISEASES,
            "fixed": ["doctors recommend it for everyone", "better than antibiotics",
                      "replaces your medicines", "stop your medicines", "no need to see a doctor", "no prescription needed",
                      "cures all diseases", "cures every disease", "works for all diseases", "kills all germs",
                      "kills 99.9% germs", "increase height", "grow taller", "boosts sexual power", "sexual power",
                      "कोई साइड इफेक्ट नहीं", "साइड इफेक्ट नाही", "पक्का इलाज", "100% इलाज", "जड़ से खत्म",
                      "डॉक्टर की ज़रूरत नहीं", "औषध घेणे थांबवा"],
            "hi": ["इलाज", "आराम", "राहत"],
            "mr": ["इलाज", "उपचार", "आराम"],
            "fixed_indic": [f"{d} का पक्का इलाज" for d in DISEASES_INDIC] + [f"{d} जड़ से खत्म" for d in DISEASES_INDIC],
        },
        "terminology": [],
        "tone": [],
        "sources": [
            ("Drugs and Magic Remedies (Objectionable Advertisements) Act 1954 and its schedule",
             "Advertising that a product cures, treats or prevents the listed diseases (including cancer, diabetes, obesity, "
             "heart disease, high blood pressure, impotence, tuberculosis and leucoderma) is an offence. The disease list "
             "in this pack is taken from that schedule."),
            ("Drugs and Cosmetics Rules and ASCI guidelines on healthcare advertising",
             "Claims of 'no side effects', 'permanent cure' or replacing a doctor need medical evidence and are normally not accepted."),
            ("Consumer Protection Act 2019", "Misleading advertisements about health products can attract penalties on the brand and the endorser."),
        ],
    },
    "food": {
        "label": "Food and beverage",
        "spec": {
            "outcomes": ["weight loss", "results", "immunity", "nutrition", "health benefits"],
            "no": ["side effects", "harmful chemicals", "harm"],
            "percent": ["pure", "natural", "organic", "healthy", "chemical free", "fresh", "authentic", "original", "safe",
                        "preservative free"],
            "fast": ["weight loss", "fat loss", "energy", "detox"],
            "miracle": ["food", "drink", "fruit", "ingredient", "superfood"],
            "verbs": CURE_VERBS + ["prevents"],
            "things": ["cancer", "diabetes", "obesity", "heart disease", "high blood pressure", "tuberculosis",
                       "fat", "belly fat", "cholesterol"],
            "fixed": ["boosts immunity", "builds immunity", "increases immunity", "prevents cancer", "diabetes safe",
                      "burns fat", "detox", "detoxifies", "zero side effects", "better than medicine", "replaces medicine",
                      "healthiest in india", "healthiest in the world", "the healthiest", "zero sugar guaranteed",
                      "100% pure", "100% natural", "100% organic", "100% fresh", "100% healthy", "सर्वात शुद्ध",
                      "100% शुद्ध", "100% प्राकृतिक", "100% नैसर्गिक"],
        },
        "terminology": [],
        "tone": ["farm fresh guaranteed", "doctor recommended", "clinically proven", "scientifically proven", "diabetic friendly"],
        "sources": [
            ("FSSAI Food Safety and Standards (Advertising and Claims) Regulations 2018",
             "Nutrition and health claims need to meet the allowed conditions. Words such as 'natural', 'fresh', 'original', "
             "'traditional', 'authentic', 'genuine', 'real' and 'pure' are restricted on labels and ads unless the conditions are met. "
             "These are conditional rules: if your product qualifies, remove the phrase."),
            ("Drugs and Magic Remedies Act 1954", "Food products must not claim to cure or prevent the listed diseases."),
            ("ASCI guidelines for advertisements making health claims", "Claims such as 'boosts immunity' or 'detox' need substantiation."),
        ],
    },
    "tech": {
        "label": "Technology and software",
        "spec": {
            "outcomes": ["uptime", "security", "accuracy", "results", "roi", "growth", "performance", "savings",
                         "compliance", "data safety", "scalability", "speed"],
            "no": ["downtime", "bugs", "errors", "latency", "risk", "data loss", "maintenance"],
            "percent": ["secure", "uptime", "accurate", "accuracy", "safe", "private", "bug free", "error free", "reliable"],
            "fast": ["setup", "roi", "results", "growth", "savings"],
            "miracle": ["tool", "software", "app", "platform", "ai"],
            "fixed": ["unhackable", "hack proof", "hackproof", "hack-proof", "unbreakable", "military grade security",
                      "military-grade security", "bank grade security", "bank-grade security", "never fails", "never crashes",
                      "never goes down", "zero downtime guaranteed", "guaranteed 10x", "10x your revenue", "double your sales",
                      "guaranteed 10x growth", "number one ai", "most accurate ai in the world", "replaces your whole team",
                      "no code needed ever", "works on every device", "works with everything", "compatible with everything",
                      "fully gdpr compliant", "totally private", "completely anonymous", "nobody can access your data",
                      "no one can access your data"],
        },
        "terminology": [],
        "tone": ["disrupt everything"],
        "sources": [
            ("ASCI Code, Chapter I (truthful presentation) and the CCPA 2022 guidelines",
             "Absolute performance claims ('100% uptime', 'unhackable', 'most accurate') need independent evidence. Without it they are exaggerated claims."),
            ("IT Act 2000 and DPDP Act 2023", "Claims about data safety and privacy that the product cannot prove can be treated as misleading."),
            ("Note", "Technology has no single advertising regulator. This pack is based on the general misleading-advertising rules."),
        ],
    },
    "education": {
        "label": "Education and coaching",
        "spec": {
            "outcomes": ["placement", "placements", "job", "jobs", "admission", "selection", "rank", "marks", "success",
                         "results", "salary", "job offer", "internship", "promotion", "visa", "scholarship", "pass", "score"],
            "no": ["failure", "risk", "dropouts", "hidden fees"],
            "percent": ["placement", "selection", "pass", "success rate", "job guarantee", "results", "admission", "visa success"],
            "fast": ["job", "rank", "results", "fluency", "salary hike", "selection"],
            "miracle": ["course", "method", "formula", "trick"],
            "fixed": ["100% placement", "guaranteed placement", "guaranteed job", "guaranteed admission", "100% selection",
                      "guaranteed rank", "100% pass", "100% success rate", "number one institute", "no. 1 coaching",
                      "india's best institute", "best faculty in india", "top rankers guaranteed", "money back if not selected",
                      "crack in one attempt",
                      "100% job", "सर्वोत्तम संस्था", "100% प्लेसमेंट", "100% सिलेक्शन", "100% नोकरी", "पक्की नोकरी",
                      "पक्की नौकरी", "गारंटीड नौकरी"],
            "hi": ["नौकरी", "प्लेसमेंट", "एडमिशन", "सिलेक्शन", "रैंक"],
            "mr": ["नोकरी", "प्लेसमेंट", "ॲडमिशन", "निवड", "रँक"],
        },
        "terminology": [],
        "tone": ["last seats", "seats filling fast", "official university", "recognised by government", "approved by every university"],
        "sources": [
            ("ASCI Guidelines for Advertisements of Educational Institutions and Coaching",
             "Placement, rank, employment and salary claims need substantiation and must not imply a guarantee. Words like "
             "'official', 'recognised' and 'accredited' need evidence. A disclaimer such as 'past record is no guarantee of "
             "future prospects' is expected."),
            ("CCPA Guidelines for Prevention of Misleading Advertisements in Coaching (2022)",
             "Coaching institutes must not make false claims about selection, rank or job outcomes and must not use student "
             "results without their consent and the course they actually took."),
            ("UGC and AICTE public notices", "Claims of approval or recognition must match the regulator's published status."),
        ],
    },
    "ecommerce": {
        "label": "E-commerce and retail",
        "spec": {
            "outcomes": ["lowest price", "best price", "original", "authentic", "discount", "savings"],
            "percent": ["original", "authentic", "genuine"],
            "no": ["hidden charges", "hidden costs"],
            "fixed": ["lowest price guaranteed", "cheapest in india", "cheapest in the world", "cheapest in the market",
                      "best price in india", "100% original guaranteed", "price match guaranteed", "lowest price ever",
                      "never sold at this price", "prices will never be this low", "everything free", "free gift worth",
                      "buy one get one free forever", "flat 90% off everything", "flat 80% off everything",
                      "100% cashback", "unlimited cashback", "सर्वात स्वस्त", "सबसे सस्ता", "सबसे सस्ती"],
        },
        "terminology": [],
        "tone": ["only few left", "selling fast", "almost sold out", "stock running out", "sale ends tonight"],
        "sources": [
            ("CCPA Guidelines for Prevention of Misleading Advertisements (2022) and Consumer Protection (E-Commerce) Rules 2020",
             "Price claims ('lowest', 'cheapest', 'best price') need evidence. Offers must state conditions clearly. 'Free' offers "
             "must not carry hidden costs. Fake urgency and false scarcity are unfair trade practices."),
            ("CCPA guidelines on bait advertising", "An offer must be available in reasonable quantity for a reasonable time."),
            ("Legal Metrology (Packaged Commodities) Rules", "Prices shown must be MRP-compliant and not misleading."),
        ],
    },
    "beauty": {
        "label": "Beauty and personal care",
        "spec": {
            "outcomes": ["results", "hair growth", "glow", "fairness", "hair removal", "anti-ageing", "wrinkle removal",
                         "acne removal", "weight loss", "whitening", "tanning removal"],
            "no": ["side effects", "chemicals", "allergy", "irritation", "downtime"],
            "percent": ["natural", "safe", "herbal", "chemical free", "organic", "hair growth", "effective", "paraben free"],
            "lasting": ["hair removal", "fairness", "glow", "results", "whitening", "smoothness"],
            "fast": ["fairness", "glow", "whitening", "hair growth", "results", "wrinkle removal"],
            "miracle": ["cream", "serum", "oil", "formula", "lotion", "shampoo"],
            "fixed": ["skin whitening", "instant fairness", "get fair", "permanent hair removal", "100% hair growth",
                      "guaranteed hair growth", "anti-ageing guaranteed", "removes wrinkles permanently", "removes wrinkles",
                      "erases wrinkles", "reverses ageing", "turns back time", "makes you look 10 years younger",
                      "grow hair overnight", "stops hair fall completely", "never gets oily", "works on all skin types",
                      "fair skin in", "lighten skin", "skin lightening", "गोरा", "गोरी", "गोरेपन की गारंटी", "गोरेपणा"],
        },
        "terminology": [],
        "tone": ["dermatologist approved", "clinically proven", "scientifically proven", "doctor approved"],
        "sources": [
            ("ASCI guidelines on advertisements for skin lightening or fairness products",
             "Ads must not suggest that darker skin is a handicap, or link fairness to success or marriage prospects."),
            ("Drugs and Cosmetics Act 1940 and Rules; BIS standards for cosmetics",
             "Cosmetic ads must not claim to treat disease or change body structure. Claims of 'permanent' and 'clinically proven' "
             "need test evidence."),
            ("CCPA guidelines 2022", "'Dermatologist approved' or 'clinically proven' need evidence and the endorser must have used the product."),
        ],
    },
}

PACKS = {}
for _k, _v in _SPECS.items():
    PACKS[_k] = {"label": _v["label"], "banned": _expand(_v["spec"]), "terminology": _v.get("terminology", []),
                 "tone": _v.get("tone", []), "sources": _v.get("sources", [])}

OPTIONS = [("", "Other (general rules only)")] + [(k, v["label"]) for k, v in PACKS.items()]


def counts(key):
    p = GENERAL if key == "general" else PACKS[key]
    return {"banned": len(p["banned"]), "terminology": len(p["terminology"]), "tone": len(p["tone"])}


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
