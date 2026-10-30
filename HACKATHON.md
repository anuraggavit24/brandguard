# BrandGuard — Hackathon submission & ops pack

Concise pack for team, judges, and live demo. Full product/architecture: **[SOLUTION.md](SOLUTION.md)**. Product deep-dive: **[README.md](README.md)**.

---

## 1. Problem

Growing organisations publish through employees, agencies, freelancers and AI tools. Wrong prices, banned claims, off-brand tone, inaccessible creatives and confidential leaks ship before anyone notices. Manual review does not scale; blind AI approval is unsafe.

---

## 2. Solution + why

**Pre-publish brand governance:** ingest multi-format content → check against approved guidelines, versioned facts and brand assets → **explain** every issue and **suggest** intent-preserving fixes → auto-approve only a fully verified pass; otherwise human queue / dispute / audit → **insights** on repeated mistakes and unclear guidelines.

**Why:** brand risk is mostly *provable* (banned phrases, wrong facts, confidential terms, off-palette assets). A **deterministic core** keeps verdicts explainable and repeatable; optional AI helps speech/paraphrase only and is re-validated in code. Uncertainty never becomes a silent pass.

→ Details, flow, architecture, requirement map: **[SOLUTION.md](SOLUTION.md)**.

---

## 3. Stack

| Layer | Choice |
|---|---|
| App | **FastAPI** — mostly server-rendered HTML + form POSTs (`main.py`, `ui.py`) |
| Data | **SQLite** (auto-migrate; `DATA_DIR`) |
| Rules / facts | Deterministic engine (`engine.py`, `realestate.py` / `generic.py`) |
| Media (optional) | ffmpeg + Whisper (Groq or local) + Tesseract OCR |
| AI (optional) | Groq chat for paraphrase / AI review |
| Deploy | Single process; Docker / Render ready |

No frontend build step. Paste-copy / docs / pages demo the full loop **without** speech.

---

## 4. What we shipped (wow + core)

**Demo wow (offline-safe — no API key required):**

| Feature | Where |
|---|---|
| **Brand Risk Radar** | SVG spider + 0–100 explainable score on review |
| **Counterfactual rewrites** | 2–3 labeled strategies; Apply + side-by-side |
| **Claim provenance** | Claim → approved-fact evidence panel |
| **Guideline Health** | Cards on Compliance Insights |
| **Paste copy** | Fast path for captions / ads / scripts |
| **Compliance Insights** | `/admin/insights` — repeated findings, wording, overturn signal |
| **SVG UI** | Lucide-style inline icons; navy/blue polished chrome |

**Also shipped (core product):** multi-format ingest (video/audio, image, PDF/DOCX/TXT, URL, paste); banned/confidential/tone/terminology; fact validators; human review queue + disputes + audit; approval ID + SHA-256 verify; project access grants; brand-guide import; **visual + a11y on images and text/OCR** (palette/logo + colour words, fonts/visual don’ts, contrast, ALL CAPS, CTAs, alt text).

**Not shipped (do not demo as live):** Shadow Mode rule simulator, full Confidentiality Vault reveal UX, full Unified Brand Passport timeline (rewrite lineage stub only).

---

## 5. Gap / coverage vs problem statement

**Score: ~8.5 / 10** — covers the statement end-to-end for a judged hackathon; not a production SSO SaaS.

| | |
|---|---|
| **Strongest** | Paste → reject → Risk Radar / rewrites / provenance → Insights; human queue; offline demo without Groq |
| **Weakest** | Visual/font checks are heuristic (no real font ID); live video/OCR fragile & slow; demo-role auth (`/enter/{role}`) |

---

## 6. Hackathon readiness verdict

**READY WITH CAVEATS — ship as-is before 10AM.**

Do **not** add features, large refactors, or live Whisper/OCR demos unless pre-cached. Use the paste path.

---

## 7. Demo path (~90 seconds)

1. Open `/` → **Enter as Partner**.
2. **Submit Content** → **Paste copy** — use this text (add a unique tag each run so the run is clearly “yours”):

```text
Book Demo Heights 2 BHK with guaranteed returns and the lowest price — hurry, limited units! [demo-TAG]
```

Replace `TAG` with something unique (time, initials, etc.).

3. Result: **Rejected** → show **Brand Risk Radar** → **Claim provenance** → **Apply** a counterfactual (“Soften claim” / disclaimer).
4. Switch role → **Builder** → **Compliance Insights** → **Guideline Health** + repeated wording.

**Correct insights URL:** [`/admin/insights`](http://127.0.0.1:8000/admin/insights) (not a different path).

Skip live video/Whisper/OCR in the timed pitch unless a short clip is already processed.

---

## 8. APIs & speed

- Stack is **FastAPI**. Most surfaces are **HTML/SSR + forms**, not a public JSON REST API.
- **Fast:** paste-copy, rules pages, insights UI.
- **Slow:** video → Whisper + frame OCR — avoid on stage.
- Optional Groq only for speech + AI paraphrase; wow surfaces run heuristic/offline.

---

## 9. Security

**Good enough for hackathon / pilot:** session roles; backend project/brand scoping; upload type/size limits; parameterized SQL; confidential redaction + `BLOCKED`; files not kept by default (hash retained); secrets via env (`.env` git-ignored).

**Caveat:** open **`/enter/{role}`** is intentional demo login — no real passwords for the three roles. Not production SSO.

**Judge 2-liner:** *FastAPI session app — paste review in seconds; Whisper only for media; real auth limits and no leftover uploads — demo enter-by-role is deliberate for the pitch.*

---

## 10. Local run

```bash
cd brandguard
source .venv/bin/activate   # or use .venv/bin/python directly
.venv/bin/python -m uvicorn main:app --host 127.0.0.1 --port 8000
```

- **URL:** http://127.0.0.1:8000/
- **Health:** http://127.0.0.1:8000/health
- **Stop:** find the uvicorn PID (`lsof -nP -iTCP:8000 -sTCP:LISTEN`) then `kill <PID>` (do not kill unrelated processes).

---

## 11. Env notes

- Template: **[.env.example](.env.example)** (no secrets committed).
- **`GROQ_API_KEY`** — optional. Paste-copy, Risk Radar, counterfactuals, provenance and Guideline Health work **without** it.
- Set Groq (or `TRANSCRIBE_MODE=local` + faster-whisper) only if you need live speech / optional AI rewrite.
- Set a strong `SECRET_KEY` for any shared deploy.

---

## 12. Deferred / what’s next (if judges ask)

1. **Shadow Mode** — simulate rule changes before publishing them.
2. **Full Confidentiality Vault** — controlled reveal + reveal audit UX.
3. **Unified Brand Passport** — full content lineage timeline (stub exists when rewrites are applied).
4. Real authentication (SSO), managed DB + job queue for media, true font/layout vision models, online RERA lookup when APIs exist.

---

*Fictional demo company/projects/prices only. Ship the paste path; point judges at SOLUTION.md for architecture.*
