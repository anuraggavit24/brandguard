# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

Two co-equal audiences with different jobs:

- **Creators**: channel partners, agencies and freelancers who make marketing content every day (videos in Marathi, Hindi and English, posters, brochures, captions, blog posts). They submit content, read findings, fix wording, confirm the project, and dispute findings.
- **Company reviewers (builders / managers)**: set brand rules, products and approved facts, manage access, work the Review Queue, approve or reject with a note, and read Compliance Insights.

## Product Purpose

Brand governance before publish. BrandGuard checks each piece of content against the company's approved facts and brand rules before it goes live, explains every problem in plain words (where, what, why, what to change), suggests a fix, and sends anything it is unsure about to a person. Nothing is approved unless every check passed or a person decided. Success: wrong prices, banned claims, confidential leaks and inaccessible posters are caught before publication, and creators can fix them without losing their message.

## Positioning

Proof, not AI scoring. Decisions come from deterministic code checked against dated, versioned approved facts (including Indian number formats and Hindi/Marathi number words in speech). AI never approves or rejects; it only advises, and uncertainty is a status that goes to a person, never a pass. Approvals carry an ID and SHA-256 file fingerprint, tied to the fact versions used, with a full audit trail.

## Operating Context

- Content formats: video/audio (speech to text, text on screen), posters/images (OCR), PDF/Word/text, web pages, pasted copy, bulk upload with background queue.
- Industries: real-estate projects (BHK, area, possession, RERA) or any product with company-defined fact types and rules.
- Statuses: AUTO_APPROVED, REJECTED, BLOCKED, SUPERVISION, NEEDS_CONFIRMATION.
- Company sign-up, invites with per-project access, emailed one-time codes, password reset, email notifications.
- Three fictional demo roles on the home page (Channel Partner, Builder, plus a third) for judges and evaluators.

## Capabilities and Constraints

- Current implementation: one FastAPI process, server-rendered HTML (design system in `ui.py`), SQLite, no front-end build step. Recorded as the current state, not a binding commitment.
- Stage: pilot / hackathon demo (CodeAxis Round 3, team Sentinel-X). Live on Render free tier; the server sleeps and data resets on redeploy.
- Known limits stated in SOLUTION.md: accuracy not measured on a labelled set; speech and OCR make mistakes; AI is weaker in Hindi/Marathi; visual checks limited to logo, colours, contrast and text size; RERA numbers format-checked only.
- Terminology: Review Queue, Risk Radar, Compliance Insights, lessons, findings, approval ID.
- Undecided: production stage beyond pilot, accessibility standard for the product's own UI, any binding visual or stack constraints.

## Brand Commitments

Name: BrandGuard. Voice in docs is plain-spoken and candid about limitations. No visual identity commitments confirmed.

## Evidence on Hand

- Demo clips (`demo_audio/`, `Clip1.mp4`, `Clip2.mp4`), sample data auto-created on first start.
- `docs/BrandGuard_Round3_Product.pdf`, `README.md`, `SOLUTION.md`.
- 519 automated checks (README/SOLUTION.md), all passing per those docs.
- Absent: labelled accuracy benchmarks, real customer testimonials or case studies. Do not fabricate them.

## Product Principles

1. Automate what can be proven; give humans what cannot.
2. Uncertainty is a status, never a silent pass.
3. Every finding explains where, what, why and what to change.
4. AI advises; code, approved facts and people decide.
5. Say plainly what was and was not checked.

## Accessibility & Inclusion

Users work across Marathi, Hindi and English; content and UI must respect all three. No formal accessibility standard confirmed for the product's own UI (undecided).
