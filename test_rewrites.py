"""Offline (rule-based) rewrite suggestions must be clean sentences or nothing. Run: python test_rewrites.py"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rewrite as RW

fails = []


def check(name, cond, extra=""):
    print(("PASS " if cond else "FAIL ") + name + (f"  [{extra}]" if extra and not cond else ""))
    if not cond:
        fails.append(name)


REG = {"banned_phrases": ["guaranteed returns", "price will double", "100% safe", "best in city"], "confidential": ["dealer commission"]}
cases = [("Invest in Demo Heights now for guaranteed returns, call today!", True),
         ("This flat price will double in 2 years, hurry!", False),
         ("तुम्हाला गारंटीड रिटर्न मिळेल, आजच बुक करा", False),
         ("Our project is 100% safe and the best in city", False),
         ("Book now, guaranteed returns of 12%", False),
         ("Get the cheapest 2 BHK in Wakad", True)]
for s, expect in cases:
    text, err = RW.demo_rewrite(s, "", "", REG)
    check(f"{'a clean suggestion' if expect else 'no suggestion'} for: {s[:40]}", bool(text) == expect, str(text))
    if text:
        check(f"suggestion passes every rule check: {s[:30]}", RW.check_rewrite(s, text, REG) == "" and RW.looks_clean(text), text)
check("broken edits are recognised", not RW.looks_clean("Invest now for , call today!") and not RW.looks_clean("Our project is and the best"))
check("no AI key gives an honest message, not rule text labelled as AI", RW.ai_rewrite("x guaranteed returns", "g", "", REG)[1] == "AI is not set up on this server.")

print("\n%d failed" % len(fails) if fails else "\nALL PASSED")
sys.exit(1 if fails else 0)
