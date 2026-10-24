import os
import sys
import requests

key = os.environ["GROQ_API_KEY"]
path = sys.argv[1]
lang = sys.argv[2] if len(sys.argv) > 2 else None

glossary = "Demo Heights, RERA, BHK, possession, crore, lakh, दीड कोटी, सव्वा कोटी, साडे तीन कोटी, डेढ़ करोड़, कोटी, ताबा"

data = {
    "model": "whisper-large-v3",
    "response_format": "verbose_json",
    "temperature": "0",
    "prompt": glossary,
}
if lang:
    data["language"] = lang

with open(path, "rb") as f:
    r = requests.post(
        "https://api.groq.com/openai/v1/audio/transcriptions",
        headers={"Authorization": f"Bearer {key}"},
        files={"file": (os.path.basename(path), f)},
        data=data,
        timeout=120,
    )

print("Status:", r.status_code)
if r.status_code != 200:
    print(r.text)
    sys.exit(1)

j = r.json()
print("\nFull text:\n", j.get("text"))
print("\nSegments:")
for s in j.get("segments", []):
    print(f"[{s['start']:.1f}-{s['end']:.1f}] conf_logprob={s.get('avg_logprob'):.2f}  {s['text']}")