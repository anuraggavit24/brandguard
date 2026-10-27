"""Checks for the amount and percentage reader. Run: python test_amounts.py"""
import sys
import amounts as A

fails = []


def money(text, expect):
    got = [p["value"] for p in A.extract_amounts(text)]
    ok = got == expect
    print(("PASS " if ok else "FAIL ") + f"money {text!r} -> {got}" + ("" if ok else f"  expected {expect}"))
    if not ok:
        fails.append(text)


def pct(text, expect):
    got = [p["value"] for p in A.extract_percents(text)]
    ok = got == expect
    print(("PASS " if ok else "FAIL ") + f"percent {text!r} -> {got}" + ("" if ok else f"  expected {expect}"))
    if not ok:
        fails.append(text)


# small products
money("हा प्रोडक्ट 9 हजार 477 रुपयाला आहे", [9477])
money("nau hazar charshe satar rupaye la product", [9470])
money("नऊ हजार चारशे सत्तर रुपये", [9470])
money("9 thousand 477 rupees", [9477])
money("price is 9,477 rupees", [9477])
money("9477 rupees only", [9477])
money("Rs. 499/-", [499])
money("₹1,299", [1299])
money("Rs 99", [99])
money("five rupees", [5])
money("four hundred and seventy rupees", [470])
money("पंचवीस हजार रुपये", [25000])
money("डेढ़ हजार रुपये", [1500])
money("सत्याहत्तर रुपये", [77])
money("price 1 lakh 20 thousand rupees", [120000])
# property sized
money("2 BHK at 1.3 Cr", [13000000])
money("1 crore 30 lakh", [13000000])
money("1 crore 80 lakh 50 thousand", [18050000])
money("2 crore 3 lakh", [20300000])
money("एक कोटी 30 लाखा परेंता", [13000000])
money("साडेतीन लाख", [350000])
money("पावणे दोन कोटी", [17500000])
money("one point three crore", [13000000])
# things that are NOT prices
money("2 BHK flat", [])
money("only 30 percent left", [])
money("1200 sq ft", [])
money("2 thousand sq ft", [])
money("We do not offer it", [])
money("call us now", [])
money("20 and 30", [])
# percentages
pct("30% discount", [30.0])
pct("flat 30 percent off", [30.0])
pct("तीस टक्के सूट", [30.0])
pct("बावन्न टक्के", [52.0])
pct("20% off on 5 lakh", [20.0])
pct("2 BHK", [])
pct("5 lakh", [])
pct("1 crore 30 lakh", [])
# both in one sentence
money("nau hazar charshe satar rupaye la product, 30% discount", [9470])
pct("nau hazar charshe satar rupaye la product, 30% discount", [30.0])

print("\n%d failed" % len(fails) if fails else "\nALL PASSED")
sys.exit(1 if fails else 0)
