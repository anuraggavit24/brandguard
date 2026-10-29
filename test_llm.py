"""Checks for the shared AI client (no network). Run: python test_llm.py"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ["GROQ_API_KEY"] = "test-key"
for k in ("AI_MODEL", "AI_FALLBACK_MODEL", "LESSON_MODEL"):
    os.environ.pop(k, None)
import llm
llm.time.sleep = lambda s: None
fails = []


def check(name, cond, extra=""):
    print(("PASS " if cond else "FAIL ") + name + (f"  [{extra}]" if extra and not cond else ""))
    if not cond:
        fails.append(name)


class R:
    def __init__(self, code, content=None, err=""):
        self.status_code, self._c, self._e, self.headers = code, content, err, {}

    def json(self):
        if self.status_code == 200:
            return {"choices": [{"message": {"content": self._c}}]}
        return {"error": {"message": self._e}}


calls = []


def script(*replies):
    it = iter(replies)

    def post(model, system, user, temperature, json_mode, timeout):
        calls.append((model, json_mode))
        return next(it)
    calls.clear()
    llm._post = post


check("retired model names are never used", llm.models() == ["openai/gpt-oss-120b", "openai/gpt-oss-20b"])
os.environ["LESSON_MODEL"] = "llama-3.3-70b-versatile"
check("an old model left in a setting is skipped", llm.models("LESSON_MODEL") == ["openai/gpt-oss-120b", "openai/gpt-oss-20b"])
os.environ["LESSON_MODEL"] = "my/new-model"
check("a per-feature model is tried first", llm.models("LESSON_MODEL")[0] == "my/new-model")
os.environ.pop("LESSON_MODEL")
script(R(200, '{"ok": true}'))
check("normal JSON reply", llm.chat_json("s", "u") == {"ok": True})
script(R(404, err="The model does not exist"), R(200, '{"ok": 1}'))
check("missing model falls back to the second model", llm.chat_json("s", "u") == {"ok": 1} and calls[1][0] == "openai/gpt-oss-20b")
script(R(429, err="rate limit"), R(200, '{"ok": 2}'))
check("rate limit is retried once", llm.chat_json("s", "u") == {"ok": 2} and len(calls) == 2)
script(R(400, err="json_validate_failed: response_format"), R(200, 'Sure! {"ok": 3} hope this helps'))
check("JSON-mode error retried without JSON mode, JSON cut out of the reply", llm.chat_json("s", "u") == {"ok": 3} and calls[1] == ("openai/gpt-oss-120b", False))
script(R(401, err="Invalid API Key"), R(401, err="Invalid API Key"))
try:
    llm.chat_json("s", "u")
    check("a bad key raises with the reason", False)
except llm.AIError as ex_:
    check("a bad key raises with the reason", "Invalid API Key" in str(ex_) and "Invalid API Key" in llm.last_error)
os.environ.pop("GROQ_API_KEY")
try:
    llm.chat_json("s", "u")
    check("no key is explained", False)
except llm.AIError as ex_:
    check("no key is explained", "GROQ_API_KEY" in str(ex_))
print("\n%d failed" % len(fails) if fails else "\nALL PASSED")
sys.exit(1 if fails else 0)
