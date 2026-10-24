# BrandGuard

Pre-publication review for promotional content. A creator uploads a reel; BrandGuard transcribes the
audio (Marathi, Hindi, English), checks every price and claim against the brand's approved facts,
blocks confidential information, and routes risky or uncertain items to a human. Nothing is approved
without a recorded decision.

Live demo: https://brandguard-55p0.onrender.com (use the one-click demo roles, no sign-up needed)

## Run locally (Windows)

1. Install Python 3.11+ and ffmpeg (`winget install Gyan.FFmpeg`).
2. Double-click `start_brandguard.bat`. On first run it sets everything up and asks for a free
   Groq API key (console.groq.com), then opens http://localhost:8000.

## Main parts

- `main.py`: web app (two portals, upload, review, approve, dispute, audit trail, file-hash check)
- `engine.py`: number normaliser (including Marathi/Hindi forms like "dede crore"), price decisions, claim rules
- `brandguard.py`: command-line ingestion prototype (audio and frame extraction)

## Notes

- Speech-to-text uses Groq's hosted Whisper in the demo; a local Whisper mode is also supported.
- Link checking (YouTube, Instagram, Facebook) works locally; it is switched off on the hosted demo
  because those platforms block cloud servers.
