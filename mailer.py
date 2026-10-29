"""Sending email: invites, bulk-batch results and test messages.

Two ways, tried in this order:
1. Brevo email API over HTTPS (BREVO_API_KEY + MAIL_FROM). Works on Render's free tier, which blocks normal email
   ports. Brevo's free plan sends up to 300 emails a day. MAIL_FROM must be a sender verified in Brevo
   (a single address such as a Gmail address can be verified by clicking a link Brevo sends to it).
2. Plain SMTP (SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, MAIL_FROM), for example Gmail with an app password.
   Only works where outgoing email ports are open (Render paid plans, your own PC).
Without either, nothing is sent and send() returns False, so callers show the link on screen instead.
send() never raises; the reason for the last failure is kept in last_error for the settings check.
"""
import os

last_error = ""


def provider():
    if os.environ.get("BREVO_API_KEY") and os.environ.get("MAIL_FROM"):
        return "brevo"
    if os.environ.get("SMTP_HOST") and os.environ.get("MAIL_FROM"):
        return "smtp"
    return ""


def configured():
    return bool(provider())


def _brevo(to, subject, text):
    import requests
    r = requests.post("https://api.brevo.com/v3/smtp/email", timeout=15,
                      headers={"api-key": os.environ["BREVO_API_KEY"], "accept": "application/json"},
                      json={"sender": {"name": os.environ.get("MAIL_FROM_NAME", "BrandGuard"), "email": os.environ["MAIL_FROM"]},
                            "to": [{"email": to}], "subject": subject, "textContent": text})
    if r.status_code in (200, 201, 202):
        return True, ""
    try:
        msg = r.json().get("message", "")
    except Exception:
        msg = ""
    return False, f"Brevo said HTTP {r.status_code}" + (f": {msg[:160]}" if msg else "")


def _smtp(to, subject, text):
    import smtplib
    from email.message import EmailMessage
    m = EmailMessage()
    m["From"] = f'{os.environ.get("MAIL_FROM_NAME", "BrandGuard")} <{os.environ["MAIL_FROM"]}>'
    m["To"], m["Subject"] = to, subject
    m.set_content(text)
    port = int(os.environ.get("SMTP_PORT", "587"))
    host = os.environ["SMTP_HOST"]
    if port == 465:
        s = smtplib.SMTP_SSL(host, port, timeout=15)
    else:
        s = smtplib.SMTP(host, port, timeout=15)
        s.starttls()
    try:
        if os.environ.get("SMTP_USER"):
            s.login(os.environ["SMTP_USER"], os.environ.get("SMTP_PASSWORD", ""))
        s.send_message(m)
    finally:
        try:
            s.quit()
        except Exception:
            pass
    return True, ""


def send(to, subject, text):
    global last_error
    p = provider()
    if not p:
        last_error = "Email is not set up on this server."
        return False
    try:
        ok, why = (_brevo if p == "brevo" else _smtp)(to, subject, text)
    except Exception as ex_:
        ok, why = False, f"{type(ex_).__name__}: {str(ex_)[:160]}"
        if p == "smtp" and ("unreachable" in why.lower() or "timed out" in why.lower()):
            why += " (this host may block email ports; use Brevo instead)"
    last_error = "" if ok else why
    return ok
