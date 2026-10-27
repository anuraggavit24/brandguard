"""Email sending over HTTPS (Brevo). Render's free tier blocks normal SMTP ports, so this uses the web API.

Set BREVO_API_KEY and MAIL_FROM (a sender address verified in Brevo). Without them, nothing is sent and
send() returns False, so callers show the link on screen instead. It never raises.
"""
import os


def configured():
    return bool(os.environ.get("BREVO_API_KEY") and os.environ.get("MAIL_FROM"))


def send(to, subject, text):
    if not configured():
        return False
    try:
        import requests
        r = requests.post("https://api.brevo.com/v3/smtp/email", timeout=15,
                          headers={"api-key": os.environ["BREVO_API_KEY"], "accept": "application/json"},
                          json={"sender": {"name": os.environ.get("MAIL_FROM_NAME", "BrandGuard"),
                                           "email": os.environ["MAIL_FROM"]},
                                "to": [{"email": to}], "subject": subject, "textContent": text})
        return r.status_code in (200, 201, 202)
    except Exception:
        return False
