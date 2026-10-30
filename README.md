# BrandGuard

**Brand governance before publish.** Channel partners, agencies and freelancers create marketing content every day: videos in Marathi, Hindi and English, posters, brochures, captions and blog posts. BrandGuard checks each piece against the company's approved facts and brand rules *before* it goes live, explains every problem in plain words, suggests a fix, and sends anything it is unsure about to a person. Nothing is approved unless every check passed or a person decided.

- **Live:** https://brandguard-55p0.onrender.com
- **Repository:** https://github.com/anuraggavit24/brandguard
- **Team:** Sentinel-X (Anurag Gavit) — CodeAxis Round 3
- **Product document (PDF):** [docs/BrandGuard_Round3_Product.pdf](docs/BrandGuard_Round3_Product.pdf)

---

## Try it in 3 minutes (no sign-up)

The home page has three demo roles. They are fictional sample accounts, separate from real accounts.

| Journey | Steps | What you should see |
|---|---|---|
| **1. A creator's content is checked** | Enter as **Channel Partner** → **Submit Content** → **Paste copy** → paste `Book Demo Heights in Wakad, Pune: 2 BHK at 1.3 crore with guaranteed returns, hurry!` → submit | **Rejected.** Each finding says where it is, why it matters and what to change; the price is verified against the approved fact; a Risk Radar summarises the problems. |
| **2. A video in Marathi** | Open **Demo Files** (home page) → download a clip → as Channel Partner upload it under **Submit Content** | Speech is transcribed, text on screen is read, every price and fact is checked. A short clip takes 1–3 minutes on the free server. |
| **3. The company side** | Enter as **Builder** → **Review Queue** → open an item → approve or reject with a note → **Compliance Insights** | The decision is recorded in the audit trail; insights show repeated mistakes and rules that are often disputed. |

To set up a real company: **Create company account** on the home page. A guided tour and a "Get started" checklist walk you through brand rules, products and facts (spreadsheet, brochure or sample data), and inviting your team.

---

## What it does

| Need | How BrandGuard handles it |
|---|---|
| Many formats | Video and audio (speech + text on screen), posters and images (OCR), PDF / Word / text documents, blog and web pages, pasted copy, bulk upload with a background queue. |
| Any industry | Real-estate projects with BHK, area, possession and RERA, **or** products of any kind with the company's own fact types (discount %, warranty years, mileage, fees, interest rate, dates, yes/no, text) and a rule per fact (exact / must not be more / must not be less). |
| Check facts | Prices and amounts in Indian numbering and Hindi/Marathi words ("नऊ हजार चारशे सत्तर", "दीड कोटी"), percentages, dates and units are compared with the approved, dated fact of the right project or product. |
| Brand rules | Banned phrases (including misread ones), confidential terms (redacted, and figures like "2% commission"), preferred terminology, tones to avoid, industry starter packs with sources. |
| Brand assets and accessibility | Logo search, brand colours, text contrast (WCAG), minimum text size on images; ALL CAPS, wall-of-text and colour-only cues in text. |
| Explain and suggest | Every finding: where, what, why, what to do. A rule-based suggestion when a clean one exists; an AI rewrite on request, checked in code before it is shown. |
| AI where it helps | Speech to text; an AI reviewer that catches banned claims said in other words and gives a summary in the content's language; lessons from resolved disputes. **AI never approves or rejects.** |
| People decide | Review Queue, disputes, approve / reject with a note, lessons the builder can switch off, approval ID + SHA-256 file fingerprint, full audit trail. |
| A real product | Company sign-up, invites (single or from a spreadsheet) with per-project access, emailed one-time code before adding people, password reset, email notifications, rate limits. |

---

## Run it locally

**Needs:** Python 3.11, `ffmpeg` on the PATH. Optional: Tesseract OCR (text on screen and posters; add the `hin` and `mar` language packs for Hindi/Marathi), a free Groq API key (speech and AI).

```bash
git clone https://github.com/anuraggavit24/brandguard.git
cd brandguard
python -m venv .venv
# Windows: .venv\Scripts\activate        macOS / Linux: source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env                     # optional: fill in keys; every key is optional
python -m uvicorn main:app --port 8000
```

Open http://localhost:8000. The demo data is created automatically on first start.

- **Without any key** the site, paste copy, documents, web pages, posters (with Tesseract), rules, facts, insights, invites and the whole review workflow work. Speech needs `GROQ_API_KEY` (or `pip install faster-whisper` and `TRANSCRIBE_MODE=local`).
- **Windows:** `start_brandguard.bat` creates the environment and starts the app.
- Install Tesseract: Windows — UB Mannheim installer; macOS — `brew install tesseract tesseract-lang`; Ubuntu — `sudo apt install tesseract-ocr tesseract-ocr-hin tesseract-ocr-mar`.

### Run with Docker

```bash
docker build -t brandguard .
docker run -p 8000:10000 -e SECRET_KEY=change-me -e GROQ_API_KEY=your_key brandguard
```

The image is Python 3.11 with ffmpeg and Tesseract (English, Hindi, Marathi).

### Deploy to Render

1. New **Web Service** from this repository, runtime **Docker**.
2. Environment: `SECRET_KEY` (long random text), `GROQ_API_KEY`, `PUBLIC_URL` (the site address), `LINKS_ENABLED=0`; for email `BREVO_API_KEY` + `MAIL_FROM` (see `.env.example`).
3. For data that survives restarts, add a persistent disk and set `DATA_DIR` to its mount path (paid plan).
4. `/health` returns `{"ok": true}`. Builders can open `/ai-status` and `/ocr-status` to check the AI and OCR.

Every setting is listed with its default in [`.env.example`](.env.example).

---

## How a review works

```
content (file / link / web page / pasted text)
  → read it: speech-to-text (Whisper) · text on screen (Tesseract, every frame + scene changes) · document / page text
  → redact confidential terms
  → find the project or product (name, alias, variant, RERA, locality) — never guessed; unclear → creator confirms
  → deterministic checks: prices, facts, own fact types, banned / confidential / tone / terminology, contacts,
    brand assets and accessibility
  → lessons from earlier dispute decisions (only wording, never prices)
  → AI reviewer (optional): reworded banned claims → a person checks; tone, clarity → advice only
  → status: AUTO_APPROVED · REJECTED · BLOCKED · SUPERVISION · NEEDS_CONFIRMATION
  → creator and builder are emailed; person decides anything uncertain; approval ID + file hash
```

Auto-approval needs the project to be identified and at least one claim verified, with no open issue. Uncertainty is a status, never a pass.

### Architecture

One FastAPI process, server-rendered HTML, SQLite. No front-end build step.

| Module | Responsibility |
|---|---|
| `main.py` | Routes, sessions, orchestration of a review, statuses, audit, all pages |
| `ui.py` | Design system, app shell, guided tour, components |
| `engine.py` | Pure rule checks and number classification (no database) |
| `amounts.py` · `phon.py` | Amounts in Indian numbering and Hindi/Marathi words · spelling-tolerant word matching for speech-to-text |
| `realestate.py` · `generic.py` | Projects, unit types, dated facts, access, project identification, validators · company-defined fact types and their matcher |
| `ocr.py` · `formats.py` · `assets.py` | Frames and images (preprocessing, label–price pairing) · documents and safe web-page fetching · logo, colours, contrast, accessibility |
| `ai_review.py` · `rewrite.py` · `learning.py` · `llm.py` | AI reviewer (cached, verified) · suggestions · lessons from disputes · one AI client with model fallback |
| `governance.py` | Risk Radar, claim provenance, guideline health |
| `packs.py` | Industry starter rules with sources |
| `importer.py` | Spreadsheet template and brochure import (proposal → person confirms) |
| `accounts.py` · `mailer.py` · `ratelimit.py` · `jobs.py` | Accounts, invites, OTP, password reset · email (Brevo / SMTP) · rate limits · bulk queue |

### Where AI is used (and where it is not)

| Task | Tool | Can it decide? |
|---|---|---|
| Speech to text | Groq `whisper-large-v3` (or local faster-whisper) | No — numbers are re-read by code |
| Reworded banned claims, tone, summary | Groq `openai/gpt-oss-120b` (fallback `gpt-oss-20b`) | No — quotes must exist in the transcript; matches go to a person |
| Rewrite suggestions | same | No — checked for banned phrases and new numbers before shown |
| Lessons from disputes | same | No — inactive unless the wording case is clear; builder can switch off |
| Brochure import | same | No — every number must appear in the document; a person confirms each row |
| Text on screen | Tesseract OCR | No |

Code, approved facts and people make every decision. Development was assisted by Claude (Anthropic).

---

## Testing

```bash
python engine.py --selftest          # number engine
python test_judge_crawl.py           # every page and form, as every user, with bad input
python test_brandguard.py            # end-to-end workflow
# …each test_*.py runs on its own and prints PASS / FAIL
```

| File | Checks | Covers |
|---|---|---|
| `test_brandguard.py` | 41 | Project identification, price and fact checks, access control, auto-approval rule, fact versions, migration |
| `test_judge_crawl.py` | 18 | All 102 routes as visitor, builder, partner, freelancer, new and empty company: empty / garbage / script / huge input, wrong ids, broken files, double actions, empty states — no crash, no hang, no unescaped script |
| `test_spoken_variants.py` | 27 | Real Marathi clip: misspelled possession, bathrooms, travel time, booking; misread banned phrases; commission figures |
| `test_amounts.py` | 40 | Indian numbering, Hindi/Marathi number words, percentages |
| `test_improvement1.py` · `test_learning.py` · `test_rewrites.py` | 31 · 17 · 10 | Tone and terminology, suggestions, speech clarity, replay; lessons from disputes; clean offline suggestions |
| `test_ai_review.py` · `test_llm.py` | 41 · 9 | AI output verification, caching, language, failure handling; model fallback |
| `test_improvement2.py` | 37 | Posters, documents, web pages (SSRF-safe), contrast, logo, colours, OCR pairing |
| `test_improvement3.py` · `test_packs.py` | 56 · 31 | Any-industry facts, spreadsheet and brochure import, sample data; industry packs without false alarms |
| `test_accounts.py` · `test_onboarding.py` · `test_invites_bulk.py` · `test_safety.py` | 36 · 13 · 14 · 35 | Sign-up, login, invites, tour and checklist, bulk invites, OTP, password reset, rate limits, notifications |
| `test_queue.py` · `test_cleanup.py` | 28 · 10 | Bulk queue and restart recovery; upload clean-up, menu labels |

**519 automated checks** (494 in the test files + 25 in the engine self-test), all passing on Python 3.11. Speech and the AI are replaced by scripted answers in tests, so results do not depend on a network. Manual testing on the live site used real Marathi, Hindi and English clips, posters and documents.

---

## Known limitations

Stated plainly so nobody is misled.

- **Accuracy on real content has not been measured on a labelled set.** Tests use scripted transcripts; real clips were checked by hand.
- **Speech-to-text and OCR make mistakes.** Prices are re-checked by code and low confidence goes to a person, but stylised or fast text on screen can be missed.
- **AI on Hindi and Marathi** is weaker than on English; it only ever advises or sends to a person.
- **Visual checks are limited** to logo, colours, contrast and text size. Fonts and layout are not identified.
- **RERA numbers are format-checked**, not looked up on the state register (no stable public API).
- **Single process and SQLite** — right for a pilot; production would use a managed database and job queue. On Render's free plan the server sleeps and data resets on redeploy.
- **Link download** (YouTube / Instagram) works from a local machine only; cloud IPs are blocked by those sites.

## Repository layout

```
main.py  ui.py  engine.py  amounts.py  phon.py  realestate.py  generic.py
ocr.py  formats.py  assets.py  governance.py  packs.py  importer.py
ai_review.py  rewrite.py  learning.py  llm.py
accounts.py  mailer.py  ratelimit.py  jobs.py
test_*.py            automated checks (see Testing)
demo_audio/          demo clips for judges
Dockerfile  requirements.txt  .env.example  start_brandguard.bat
SOLUTION.md          design rationale and how it maps to the problem statement
```
