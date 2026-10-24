#!/usr/bin/env python3
"""BrandGuard CLI - stage 1: ingest a video, extract audio + frames + manifest."""

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROLES = {
    "partner":    {"label": "Channel Partner",  "frame_every_sec": 2, "strictness": "high",
                   "focus": ["claims", "rera", "pricing", "tone"]},
    "agency":     {"label": "Marketing Agency", "frame_every_sec": 2, "strictness": "high",
                   "focus": ["logo", "palette", "fonts", "claims"]},
    "freelancer": {"label": "Freelancer",       "frame_every_sec": 3, "strictness": "medium",
                   "focus": ["copyright", "music", "fonts", "logo"]},
    "internal":   {"label": "Internal Team",    "frame_every_sec": 5, "strictness": "low",
                   "focus": ["claims", "tone"]},
}

OUTPUT_ROOT = Path("submissions")


def check_tools():
    for tool in ("ffmpeg", "ffprobe"):
        if shutil.which(tool) is None:
            sys.exit(f"ERROR: '{tool}' not found. Install ffmpeg and make sure it is on your PATH.")


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def probe(video: Path) -> dict:
    cmd = [
        "ffprobe", "-v", "error", "-print_format", "json",
        "-show_format", "-show_streams", str(video),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        sys.exit(f"ERROR: could not read video.\n{result.stderr}")
    return json.loads(result.stdout)


def extract_audio(video: Path, out_wav: Path) -> bool:
    # 16 kHz mono WAV is the standard input for speech-to-text models
    cmd = [
        "ffmpeg", "-y", "-i", str(video),
        "-vn", "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le",
        str(out_wav),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.returncode == 0 and out_wav.exists()


def extract_frames(video: Path, out_dir: Path, every_sec: int) -> int:
    out_dir.mkdir(parents=True, exist_ok=True)
    cmd = [
        "ffmpeg", "-y", "-i", str(video),
        "-vf", f"fps=1/{every_sec}", "-q:v", "2",
        str(out_dir / "frame_%04d.jpg"),
    ]
    subprocess.run(cmd, capture_output=True, text=True)
    return len(list(out_dir.glob("frame_*.jpg")))


def main():
    parser = argparse.ArgumentParser(description="BrandGuard - pre-publication content review")
    parser.add_argument("video", help="Path to the video file")
    parser.add_argument("--role", required=True, choices=ROLES.keys(),
                        help="Who is submitting: partner | agency | freelancer | internal")
    parser.add_argument("--submitter", default="unknown", help="Name or ID of the submitter")
    parser.add_argument("--language", default="auto", help="Spoken language hint (hi, mr, en) or auto")
    args = parser.parse_args()

    check_tools()

    video = Path(args.video)
    if not video.exists():
        sys.exit(f"ERROR: file not found: {video}")

    role = ROLES[args.role]
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    sub_dir = OUTPUT_ROOT / f"{stamp}_{args.role}_{video.stem}"
    sub_dir.mkdir(parents=True, exist_ok=True)

    print(f"[1/4] Reading video as {role['label']}...")
    info = probe(video)
    streams = info.get("streams", [])
    has_audio = any(s.get("codec_type") == "audio" for s in streams)
    duration = float(info.get("format", {}).get("duration", 0))
    file_hash = sha256_of(video)

    print("[2/4] Extracting audio...")
    audio_path = sub_dir / "audio.wav"
    audio_ok = extract_audio(video, audio_path) if has_audio else False
    if not has_audio:
        print("      No audio track found - flagged in manifest.")

    print("[3/4] Extracting frames...")
    frame_count = extract_frames(video, sub_dir / "frames", role["frame_every_sec"])

    print("[4/4] Writing manifest...")
    manifest = {
        "submitted_at": datetime.now().isoformat(timespec="seconds"),
        "submitter": args.submitter,
        "role": args.role,
        "role_label": role["label"],
        "strictness": role["strictness"],
        "check_focus": role["focus"],
        "language_hint": args.language,
        "source_file": str(video),
        "sha256": file_hash,
        "duration_sec": round(duration, 2),
        "has_audio": has_audio,
        "audio_file": str(audio_path) if audio_ok else None,
        "frames_dir": str(sub_dir / "frames"),
        "frame_count": frame_count,
        "status": "EXTRACTED_PENDING_ANALYSIS",
    }
    with open(sub_dir / "manifest.json", "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)

    print(f"\nDone. Output folder: {sub_dir}")
    print(f"  audio : {'yes' if audio_ok else 'NO AUDIO'}")
    print(f"  frames: {frame_count}")
    print(f"  sha256: {file_hash[:16]}...")


if __name__ == "__main__":
    main()