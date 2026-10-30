"""One place for every text-AI call (lessons, rewrites, AI review, brochure import).

Why it exists: Groq shut down llama-3.3-70b-versatile and llama-3.1-8b-instant on 16 August 2026, and every AI
feature broke at once because each file named the model itself. Now:
* the model is set once (AI_MODEL), with a fallback (AI_FALLBACK_MODEL) that is tried when the first model is
  missing, retired, overloaded or rate-limited;
* an old model name left in a setting (LESSON_MODEL=llama-3.3-70b-versatile) is skipped automatically;
* if a model rejects JSON mode, the call is retried without it and the JSON object is cut out of the reply;
* the last failure reason is kept (last_error) so the page can say why the AI did not run, instead of guessing.
Every caller still treats the reply as untrusted and checks it in code.
"""

import json
import os
import re
import time

URL = os.environ.get("AI_URL", os.environ.get("LESSON_URL", "https://api.groq.com/openai/v1/chat/completions"))
RETIRED = {"llama-3.3-70b-versatile", "llama-3.1-8b-instant", "qwen/qwen3-32b", "meta-llama/llama-4-scout-17b-16e-instruct",
           "meta-llama/llama-4-maverick-17b-128e-instruct", "moonshotai/kimi-k2-instruct-0905", "qwen/qwen3.6-27b",
           "groq/compound", "groq/compound-mini", "mixtral-8x7b-32768", "gemma2-9b-it", "llama3-70b-8192", "llama3-8b-8192"}
last_error = ""


class AIError(RuntimeError):
    pass


def models(specific_env=None):
    """Models to try, in order: a per-feature setting, AI_MODEL, AI_FALLBACK_MODEL. Retired names are dropped."""
    names = [os.environ.get(specific_env, "") if specific_env else "", os.environ.get("AI_MODEL", "openai/gpt-oss-120b"),
             os.environ.get("AI_FALLBACK_MODEL", "openai/gpt-oss-20b")]
    out = []
    for n in names:
        n = (n or "").strip()
        if n and n not in RETIRED and n not in out:
            out.append(n)
    return out


def configured():
    return bool(os.environ.get("GROQ_API_KEY"))


def _extract_json(text):
    text = (text or "").strip()
    try:
        return json.loads(text)
    except ValueError:
        pass
    m = re.search(r"\{.*\}", text, re.S)
    if m:
        return json.loads(m.group(0))
    raise ValueError("no JSON in reply")


def _post(model, system, user, temperature, json_mode, timeout):
    import requests
    body = {"model": model, "temperature": temperature,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]}
    if json_mode:
        body["response_format"] = {"type": "json_object"}
    return requests.post(URL, headers={"Authorization": f"Bearer {os.environ.get('GROQ_API_KEY', '').strip().strip(chr(34)).strip(chr(39))}"},
                         json=body, timeout=timeout)


def _reason(r):
    try:
        msg = r.json().get("error", {}).get("message", "")
    except Exception:
        msg = ""
    return f"HTTP {r.status_code}" + (f": {msg[:160]}" if msg else "")


def chat_json(system, user, temperature=0, timeout=40, specific_env=None):
    """Return the model's reply parsed as a JSON object. Raises AIError with a short reason."""
    global last_error
    if not configured():
        last_error = "No GROQ_API_KEY is set on this server."
        raise AIError(last_error)
    reasons = []
    for model in models(specific_env):
        for json_mode in (True, False):
            for attempt in range(2):
                try:
                    r = _post(model, system, user, temperature, json_mode, timeout)
                except Exception as ex_:
                    reasons.append(f"{model}: could not connect ({type(ex_).__name__})")
                    break
                if r.status_code == 200:
                    try:
                        data = _extract_json(r.json()["choices"][0]["message"]["content"])
                        last_error = ""
                        return data
                    except Exception:
                        reasons.append(f"{model}: reply was not valid JSON")
                        break
                if r.status_code in (429, 500, 502, 503) and attempt == 0:
                    time.sleep(min(4.0, float(r.headers.get("retry-after", "2") or 2)))
                    continue
                reasons.append(f"{model}: {_reason(r)}")
                break
            else:
                continue
            last = reasons[-1] if reasons else ""
            # a JSON-mode complaint is worth one try without JSON mode; anything else moves to the next model
            if json_mode and ("json" in last.lower() or "response_format" in last.lower()):
                continue
            break
    last_error = "; ".join(reasons)[-400:] or "unknown error"
    raise AIError(last_error)
