"""BrandGuard presentation layer: design tokens, icons, app shell and small HTML components.

Pure rendering helpers. No database access and no business rules live here.
"""

import html

e = html.escape

# ---------------------------------------------------------------------- icons
# Lucide-style 24x24 stroke icons (path data only).
_ICONS = {
    "home": '<path d="m3 9 9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/><path d="M9 22V12h6v10"/>',
    "inbox": '<path d="M22 12h-6l-2 3h-4l-2-3H2"/><path d="M5.45 5.11 2 12v6a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-6l-3.45-6.89A2 2 0 0 0 16.76 4H7.24a2 2 0 0 0-1.79 1.11z"/>',
    "list": '<path d="M8 6h13M8 12h13M8 18h13M3 6h.01M3 12h.01M3 18h.01"/>',
    "shield": '<path d="M20 13c0 5-3.5 7.5-7.66 8.95a1 1 0 0 1-.67-.01C7.5 20.5 4 18 4 13V6a1 1 0 0 1 1-1c2 0 4.5-1.2 6.24-2.72a1.17 1.17 0 0 1 1.52 0C14.51 3.81 17 5 19 5a1 1 0 0 1 1 1z"/>',
    "tag": '<path d="M12.586 2.586A2 2 0 0 0 11.172 2H4a2 2 0 0 0-2 2v7.172a2 2 0 0 0 .586 1.414l8.704 8.704a2.426 2.426 0 0 0 3.42 0l6.58-6.58a2.426 2.426 0 0 0 0-3.42z"/><circle cx="7.5" cy="7.5" r=".5"/>',
    "scale": '<path d="m16 16 3-8 3 8c-.87.65-1.92 1-3 1s-2.13-.35-3-1z"/><path d="m2 16 3-8 3 8c-.87.65-1.92 1-3 1s-2.13-.35-3-1z"/><path d="M7 21h10M12 3v18M3 7h2c2 0 5-1 7-2 2 1 5 2 7 2h2"/>',
    "badge-check": '<path d="M3.85 8.62a4 4 0 0 1 4.78-4.77 4 4 0 0 1 6.74 0 4 4 0 0 1 4.78 4.78 4 4 0 0 1 0 6.74 4 4 0 0 1-4.77 4.78 4 4 0 0 1-6.75 0 4 4 0 0 1-4.78-4.77 4 4 0 0 1 0-6.76z"/><path d="m9 12 2 2 4-4"/>',
    "history": '<path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/><path d="M3 3v5h5"/><path d="M12 7v5l4 2"/>',
    "upload": '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><path d="m17 8-5-5-5 5"/><path d="M12 3v12"/>',
    "folder": '<path d="M20 20a2 2 0 0 0 2-2V8a2 2 0 0 0-2-2h-7.9a2 2 0 0 1-1.69-.9L9.6 3.9A2 2 0 0 0 7.93 3H4a2 2 0 0 0-2 2v13a2 2 0 0 0 2 2z"/>',
    "help": '<circle cx="12" cy="12" r="10"/><path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"/><path d="M12 17h.01"/>',
    "file-check": '<path d="M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7z"/><path d="M14 2v4a2 2 0 0 0 2 2h4"/><path d="m9 15 2 2 4-4"/>',
    "menu": '<path d="M4 6h16M4 12h16M4 18h16"/>',
    "x": '<path d="M18 6 6 18M6 6l12 12"/>',
    "check": '<path d="M20 6 9 17l-5-5"/>',
    "check-circle": '<path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><path d="m9 11 3 3L22 4"/>',
    "x-circle": '<circle cx="12" cy="12" r="10"/><path d="m15 9-6 6M9 9l6 6"/>',
    "alert": '<path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3"/><path d="M12 9v4M12 17h.01"/>',
    "clock": '<circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/>',
    "info": '<circle cx="12" cy="12" r="10"/><path d="M12 16v-4M12 8h.01"/>',
    "search": '<circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/>',
    "link": '<path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/><path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/>',
    "file": '<path d="M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7z"/><path d="M14 2v4a2 2 0 0 0 2 2h4"/>',
    "log-out": '<path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><path d="m16 17 5-5-5-5M21 12H9"/>',
    "users": '<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.87M16 3.13a4 4 0 0 1 0 7.75"/>',
    "building": '<rect width="16" height="20" x="4" y="2" rx="2"/><path d="M9 22v-4h6v4M8 6h.01M16 6h.01M12 6h.01M12 10h.01M12 14h.01M16 10h.01M16 14h.01M8 10h.01M8 14h.01"/>',
    "chevron-right": '<path d="m9 18 6-6-6-6"/>',
    "arrow-right": '<path d="M5 12h14M12 5l7 7-7 7"/>',
    "plus": '<path d="M5 12h14M12 5v14"/>',
    "play": '<polygon points="6 3 20 12 6 21 6 3"/>',
    "message": '<path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>',
    "eye": '<path d="M2.06 12.35a1 1 0 0 1 0-.7 10.75 10.75 0 0 1 19.88 0 1 1 0 0 1 0 .7 10.75 10.75 0 0 1-19.88 0"/><circle cx="12" cy="12" r="3"/>',
    "lock": '<rect width="18" height="11" x="3" y="11" rx="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/>',
}


def icon(name, size=18):
    return (f'<svg class="ic" width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" '
            f'stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" '
            f'aria-hidden="true" focusable="false">{_ICONS.get(name, "")}</svg>')


# ----------------------------------------------------------------- navigation
NAV_ADMIN = [
    ("overview", "/", "Overview", "home"),
    ("queue", "/queue", "Review Queue", "inbox"),
    ("reviews", "/reviews", "All Reviews", "list"),
    ("rules", "/admin/rules", "Brand Rules", "shield"),
    ("facts", "/admin/projects", "Projects and Facts", "tag"),
    ("access", "/admin/access", "Project Access", "users"),
    ("disputes", "/disputes", "Disputes", "scale"),
    ("learned", "/admin/learned", "Learned Cases", "history"),
    ("approvals", "/approvals", "Approval Records", "badge-check"),
    ("audit", "/audit", "Audit Trail", "history"),
    ("verify", "/verify", "Verify a File", "file-check"),
    ("testaudio", "/test-audio", "Demo Files", "play"),
]
NAV_SUB = [
    ("overview", "/", "My Dashboard", "home"),
    ("submit", "/submit", "Submit a Video", "upload"),
    ("reviews", "/reviews", "My Submissions", "folder"),
    ("disputes", "/disputes", "Disputes", "scale"),
    ("verify", "/verify", "Verify a File", "file-check"),
    ("help", "/help", "Help and Guidelines", "help"),
    ("testaudio", "/test-audio", "Demo Files", "play"),
]

# ------------------------------------------------------------------- statuses
# status code -> (label, tone, icon)
STATUS = {
    "AUTO_APPROVED": ("Auto-Approved", "ok", "check-circle"),
    "APPROVED": ("Approved by Reviewer", "ok", "check-circle"),
    "REJECTED": ("Rejected", "bad", "x-circle"),
    "BLOCKED": ("Blocked: confidential data", "bad", "x-circle"),
    "REJECTED_FINAL": ("Rejected (final)", "bad", "x-circle"),
    "SUPERVISION": ("Supervision Required", "warn", "alert"),
    "NEEDS_CONFIRMATION": ("Confirm Project", "warn", "search"),
    "DISPUTED": ("Disputed", "warn", "scale"),
    "FLAG": ("Violation", "bad", "x-circle"),
    "PASS": ("Matches", "ok", "check-circle"),
}


def chip(status):
    label, tone, ic = STATUS.get(status, (status.replace("_", " ").title(), "neutral", "clock"))
    return f'<span class="chip {tone}">{icon(ic, 14)}{e(label)}</span>'


def badge(text, tone="neutral", ic=None):
    return f'<span class="chip {tone}">{icon(ic, 14) if ic else ""}{e(text)}</span>'


def money(v):
    """Indian digit grouping, e.g. 15000000 -> ₹1,50,00,000."""
    s = str(int(v))
    if len(s) > 3:
        head, tail = s[:-3], s[-3:]
        parts = []
        while len(head) > 2:
            parts.insert(0, head[-2:])
            head = head[:-2]
        if head:
            parts.insert(0, head)
        s = ",".join(parts) + "," + tail
    return "₹" + s


# ----------------------------------------------------------------- components
def page_header(title, desc="", actions=""):
    d = f'<p class="page-desc">{desc}</p>' if desc else ""
    a = f'<div class="page-actions">{actions}</div>' if actions else ""
    return f'<div class="page-head"><div><h1>{e(title)}</h1>{d}</div>{a}</div>'


def card(title, inner, desc="", actions="", cls=""):
    h = ""
    if title or actions:
        t = f"<h2>{e(title)}</h2>" if title else "<span></span>"
        h = f'<div class="card-head">{t}{actions}</div>'
    d = f'<p class="muted card-desc">{desc}</p>' if desc else ""
    return f'<section class="card {cls}">{h}{d}{inner}</section>'


def empty(title, text="", action=""):
    return (f'<div class="empty">{icon("inbox", 28)}<p class="empty-title">{e(title)}</p>'
            f'<p class="muted">{text}</p>{action}</div>')


def alert(text, tone="info", title=""):
    ic = {"info": "info", "ok": "check-circle", "warn": "alert", "bad": "x-circle"}[tone]
    t = f"<b>{e(title)}</b> " if title else ""
    return f'<div class="alert {tone}" role="{"alert" if tone in ("bad", "warn") else "status"}">{icon(ic)}<div>{t}{text}</div></div>'


def stat(label, value, hint="", href="", tone="neutral"):
    inner = (f'<span class="stat-label">{e(label)}</span><span class="stat-value">{value}</span>'
             f'<span class="stat-hint">{hint}</span>')
    if href:
        return f'<a class="stat {tone}" href="{e(href)}">{inner}</a>'
    return f'<div class="stat {tone}">{inner}</div>'


def table(headers, rows, label):
    """rows: list of lists of cell html. Cells get data-label so narrow screens can stack them."""
    th = "".join(f'<th scope="col">{e(h)}</th>' for h in headers)
    body = []
    for r in rows:
        tds = "".join(f'<td data-label="{e(h)}">{c}</td>' for h, c in zip(headers, r))
        body.append(f"<tr>{tds}</tr>")
    return (f'<div class="table-wrap" tabindex="0" role="region" aria-label="{e(label)}">'
            f'<table class="data"><thead><tr>{th}</tr></thead><tbody>{"".join(body)}</tbody></table></div>')


def confirm_dialog(dom_id, title, text, form_action, confirm_label, tone="primary",
                   field=None, extra_hidden=None):
    """A <dialog>-based confirmation. field = (name, label, required) adds a textarea."""
    hidden = "".join(f'<input type="hidden" name="{e(k)}" value="{e(v)}">' for k, v in (extra_hidden or {}).items())
    fld = ""
    if field:
        name, label, required = field
        req = " required" if required else ""
        star = ' <span class="req">(required)</span>' if required else ' <span class="muted">(optional)</span>'
        fld = (f'<label for="{dom_id}-f">{e(label)}{star}</label>'
               f'<textarea id="{dom_id}-f" name="{e(name)}" rows="3" maxlength="1000"{req}></textarea>')
    return (f'<dialog id="{dom_id}" class="dlg" aria-labelledby="{dom_id}-t">'
            f'<form method="post" action="{e(form_action)}" data-lock>{hidden}'
            f'<h2 id="{dom_id}-t">{e(title)}</h2><p class="muted">{text}</p>{fld}'
            f'<div class="dlg-actions"><button type="button" class="btn secondary" data-close>Cancel</button>'
            f'<button type="submit" class="btn {tone}">{e(confirm_label)}</button></div></form></dialog>')


def pager(base, page, pages):
    if pages <= 1:
        return ""
    sep = "&" if "?" in base else "?"
    prev = (f'<a class="btn secondary sm" href="{e(base)}{sep}page={page - 1}">Previous</a>'
            if page > 1 else '<span class="btn secondary sm" aria-disabled="true">Previous</span>')
    nxt = (f'<a class="btn secondary sm" href="{e(base)}{sep}page={page + 1}">Next</a>'
           if page < pages else '<span class="btn secondary sm" aria-disabled="true">Next</span>')
    return f'<nav class="pager" aria-label="Pagination">{prev}<span class="muted">Page {page} of {pages}</span>{nxt}</nav>'


# ------------------------------------------------------------------------ CSS
CSS = """
:root{
  --navy:#0f1f3d;--navy-2:#1a2f55;--blue:#1d5fd1;--blue-dk:#174bab;--blue-bg:#e8f0fd;
  --bg:#f5f7fa;--surface:#fff;--line:#dfe4ec;--line-2:#eceff4;
  --text:#18212f;--text-2:#556072;
  --ok:#136c3a;--ok-bg:#e3f5ea;--warn:#8a5300;--warn-bg:#fff2d6;--bad:#a61b1b;--bad-bg:#fde8e8;
  --neutral:#4a5568;--neutral-bg:#eaedf2;
  --r:8px;--sh:0 1px 2px rgba(15,31,61,.06);
  --side:248px;
  --font:Inter,"Segoe UI","Noto Sans","Noto Sans Devanagari","Nirmala UI","Mangal",system-ui,sans-serif;
}
*{box-sizing:border-box}
html{-webkit-text-size-adjust:100%}
body{margin:0;font-family:var(--font);font-size:15px;line-height:1.55;background:var(--bg);color:var(--text)}
h1,h2,h3{margin:0;line-height:1.3;color:var(--text)}
h1{font-size:28px;font-weight:650;letter-spacing:-.01em}
h2{font-size:17px;font-weight:600}
h3{font-size:15px;font-weight:600}
p{margin:0 0 12px}
a{color:var(--blue)}
.muted{color:var(--text-2);font-size:14px}
.check{display:flex;align-items:center;gap:8px;margin:6px 0;font-weight:400}
.check input{width:auto}
.mono{font-family:Consolas,"SFMono-Regular",monospace;font-size:13px;overflow-wrap:anywhere}
.ic{flex:none;vertical-align:-3px}
:focus-visible{outline:3px solid #7aa7ff;outline-offset:2px;border-radius:4px}
.skip{position:absolute;left:-999px;top:8px;background:var(--navy);color:#fff;padding:8px 14px;border-radius:6px;z-index:100}
.skip:focus{left:8px}

/* shell */
.shell{display:grid;grid-template-columns:var(--side) minmax(0,1fr);min-height:100vh}
.side{background:var(--navy);color:#cfd8e8;display:flex;flex-direction:column;position:sticky;top:0;height:100vh;overflow-y:auto}
.brand{display:flex;align-items:center;gap:10px;padding:18px 20px;color:#fff;font-weight:650;font-size:18px;text-decoration:none}
.brand .logo{width:30px;height:30px;border-radius:7px;background:var(--blue);display:grid;place-items:center;color:#fff}
.side nav{padding:8px 12px;flex:1}
.side nav a{display:flex;align-items:center;gap:12px;padding:10px 12px;margin:2px 0;border-radius:7px;color:#cfd8e8;text-decoration:none;font-size:14.5px;min-height:42px}
.side nav a:hover{background:var(--navy-2);color:#fff}
.side nav a[aria-current=page]{background:var(--blue);color:#fff;font-weight:600}
.side .count{margin-left:auto;background:#fff;color:var(--navy);border-radius:10px;padding:0 8px;font-size:12px;font-weight:700;line-height:20px}
.side-foot{padding:14px 16px 18px;border-top:1px solid var(--navy-2);font-size:13px}
.side-foot .lbl{text-transform:uppercase;letter-spacing:.06em;font-size:11px;color:#8fa0bd;margin-bottom:6px}
.side-foot a{display:flex;align-items:center;gap:8px;color:#cfd8e8;text-decoration:none;padding:7px 4px;min-height:36px}
.side-foot a:hover{color:#fff}
.side-foot a.cur{color:#fff;font-weight:600}
.main-col{min-width:0;display:flex;flex-direction:column}
.top{background:var(--surface);border-bottom:1px solid var(--line);padding:0 28px;min-height:56px;display:flex;align-items:center;gap:14px}
.crumbs{font-size:14px;color:var(--text-2);display:flex;align-items:center;gap:6px;flex-wrap:wrap}
.crumbs a{color:var(--text-2);text-decoration:none}.crumbs a:hover{text-decoration:underline}
.crumbs [aria-current]{color:var(--text);font-weight:600}
.top .sp{flex:1}
.who{display:flex;align-items:center;gap:10px;font-size:14px}
.who .role{background:var(--blue-bg);color:var(--blue-dk);border-radius:6px;padding:2px 10px;font-size:12.5px;font-weight:600}
.menu-btn{display:none;background:none;border:1px solid var(--line);border-radius:7px;width:44px;height:44px;color:var(--text);cursor:pointer;place-items:center}
.company-switch{display:flex;align-items:center;gap:8px;font-size:14px}
.company-switch select{width:auto;margin:0;padding:6px 10px;min-height:36px}
main{padding:28px;max-width:1180px;width:100%}
.scrim{display:none}

/* page */
.page-head{display:flex;justify-content:space-between;align-items:flex-start;gap:16px;flex-wrap:wrap;margin-bottom:24px}
.page-desc{color:var(--text-2);margin:6px 0 0;max-width:68ch}
.page-actions{display:flex;gap:8px;flex-wrap:wrap}
.stack{display:flex;flex-direction:column;gap:20px}
.card{background:var(--surface);border:1px solid var(--line);border-radius:var(--r);padding:20px;box-shadow:var(--sh)}
.card-head{display:flex;justify-content:space-between;align-items:center;gap:12px;margin-bottom:14px;flex-wrap:wrap}
.card-desc{margin:-6px 0 14px}
.stats{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:16px}
.stat{display:flex;flex-direction:column;gap:2px;background:var(--surface);border:1px solid var(--line);border-radius:var(--r);padding:16px 18px;box-shadow:var(--sh);text-decoration:none;color:var(--text);border-top:3px solid var(--line)}
a.stat:hover{border-color:var(--blue)}
.stat.ok{border-top-color:#2f9e5f}.stat.warn{border-top-color:#d99a1c}.stat.bad{border-top-color:#d04444}.stat.info{border-top-color:var(--blue)}
.stat-label{font-size:13.5px;color:var(--text-2);font-weight:500}
.stat-value{font-size:30px;font-weight:650;line-height:1.2}
.stat-hint{font-size:12.5px;color:var(--text-2);min-height:18px}
.grid-2{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:20px}
.cols{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1.2fr);gap:20px;align-items:start}
.cols-3{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:20px}
.empty{text-align:center;padding:32px 16px;color:var(--text-2)}
.empty .ic{color:#9aa6b8;margin-bottom:6px}
.empty-title{font-weight:600;color:var(--text);margin:0 0 4px}

/* chips, alerts */
.chip{display:inline-flex;align-items:center;gap:5px;padding:2px 10px;border-radius:999px;font-size:12.5px;font-weight:600;white-space:nowrap;background:var(--neutral-bg);color:var(--neutral)}
.chip.ok{background:var(--ok-bg);color:var(--ok)}.chip.warn{background:var(--warn-bg);color:var(--warn)}.chip.bad{background:var(--bad-bg);color:var(--bad)}
.chip.info{background:var(--blue-bg);color:var(--blue-dk)}
.alert{display:flex;gap:12px;align-items:flex-start;padding:12px 14px;border-radius:var(--r);border:1px solid;font-size:14.5px}
.alert>div{min-width:0;overflow-wrap:anywhere}
.alert.info{background:var(--blue-bg);border-color:#bcd2f7;color:#143a7a}
.alert.ok{background:var(--ok-bg);border-color:#b5e0c5;color:var(--ok)}
.alert.warn{background:var(--warn-bg);border-color:#f0d58c;color:#6b4100}
.alert.bad{background:var(--bad-bg);border-color:#f2bcbc;color:var(--bad)}

/* buttons, forms */
.btn,button{font-family:inherit;font-size:14.5px;font-weight:600;border-radius:7px;padding:9px 16px;min-height:42px;border:1px solid transparent;cursor:pointer;display:inline-flex;align-items:center;justify-content:center;gap:8px;text-decoration:none;line-height:1.2;background:var(--blue);color:#fff}
.btn:hover,button:hover{background:var(--blue-dk)}
.btn.secondary,button.secondary{background:var(--surface);color:var(--text);border-color:#c3cad6}
.btn.secondary:hover,button.secondary:hover{background:var(--bg)}
.btn.danger,button.danger{background:#b42323}.btn.danger:hover,button.danger:hover{background:#951b1b}
.btn.success,button.success{background:#15803d}.btn.success:hover,button.success:hover{background:#106530}
.btn.sm{min-height:34px;padding:5px 12px;font-size:13.5px}
.btn:disabled,button:disabled,[aria-disabled=true]{opacity:.55;cursor:not-allowed;pointer-events:none}
label{display:block;font-size:14px;font-weight:600;margin:0 0 6px}
.req{color:var(--bad);font-weight:500}
.hint{font-size:13px;color:var(--text-2);margin:-2px 0 6px}
input,select,textarea{width:100%;font-family:inherit;font-size:15px;color:var(--text);background:#fff;border:1px solid #b7c0cf;border-radius:7px;padding:9px 12px;min-height:42px;margin:0 0 16px}
textarea{resize:vertical;line-height:1.5}
input:focus,select:focus,textarea:focus{outline:3px solid #7aa7ff;outline-offset:0;border-color:var(--blue)}
input[type=file]{padding:8px;min-height:0}
fieldset{border:0;padding:0;margin:0 0 8px}
legend{font-size:14px;font-weight:600;padding:0;margin-bottom:8px}
.field-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:0 20px}
.form-actions{display:flex;gap:10px;flex-wrap:wrap;align-items:center;margin-top:4px}

/* tables */
.table-wrap{overflow-x:auto;border:1px solid var(--line);border-radius:var(--r)}
table.data{width:100%;border-collapse:collapse;font-size:14px;background:#fff}
table.data th{background:#f7f9fc;color:var(--text-2);font-size:12.5px;font-weight:600;text-transform:uppercase;letter-spacing:.04em;text-align:left;padding:10px 14px;border-bottom:1px solid var(--line);white-space:nowrap}
table.data td:first-child{white-space:nowrap}
table.data td{padding:12px 14px;border-bottom:1px solid var(--line-2);vertical-align:top;overflow-wrap:anywhere}
table.data td .btn{white-space:nowrap}
table.data tr:last-child td{border-bottom:0}
table.data tbody tr:hover{background:#fafbfd}
.trunc{display:block;max-width:260px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.toolbar{display:flex;gap:12px;flex-wrap:wrap;align-items:center;margin-bottom:14px}
.toolbar form{display:flex;gap:8px;flex:1;min-width:220px}
.toolbar input{margin:0}
.tabs{display:flex;gap:6px;flex-wrap:wrap}
.tabs a{padding:6px 14px;border-radius:999px;border:1px solid var(--line);background:#fff;color:var(--text);text-decoration:none;font-size:14px;min-height:36px;display:inline-flex;align-items:center}
.tabs a[aria-current=true]{background:var(--navy);color:#fff;border-color:var(--navy);font-weight:600}
.pager{display:flex;gap:12px;align-items:center;justify-content:flex-end;margin-top:14px}

/* steps */
.steps{list-style:none;counter-reset:s;display:flex;gap:10px;flex-wrap:wrap;margin:12px 0 0;padding:0}
.steps li{counter-increment:s;display:flex;align-items:center;gap:8px;font-size:14px;background:#fff;border:1px solid var(--line);border-radius:999px;padding:4px 14px 4px 6px}
.steps li::before{content:counter(s);width:24px;height:24px;border-radius:50%;background:var(--navy);color:#fff;display:grid;place-items:center;font-size:12.5px;font-weight:700}
.welcome{background:var(--blue-bg);border-color:#bcd2f7;box-shadow:none}

/* findings */
.verdict{display:flex;gap:14px;align-items:flex-start}
.verdict .ic{margin-top:3px}
.verdict.ok{color:var(--ok)}.verdict.warn{color:var(--warn)}.verdict.bad{color:var(--bad)}
.verdict h2{font-size:20px;color:inherit}
.verdict p{color:var(--text);margin:4px 0 0}
.finding{border:1px solid var(--line);border-left-width:4px;border-radius:var(--r);padding:12px 14px;margin-bottom:12px;background:#fff}
.finding.bad{border-left-color:#d04444}.finding.warn{border-left-color:#d99a1c}.finding.ok{border-left-color:#2f9e5f}
.finding-top{display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin-bottom:6px}
.finding dl{display:grid;grid-template-columns:110px minmax(0,1fr);gap:4px 12px;margin:8px 0 0;font-size:14px}
.finding dt{color:var(--text-2)}.finding dd{margin:0;overflow-wrap:anywhere}
.sec-title{font-size:13px;text-transform:uppercase;letter-spacing:.05em;color:var(--text-2);font-weight:600;margin:20px 0 10px}
.sec-title:first-child{margin-top:0}
.kv{display:grid;grid-template-columns:150px minmax(0,1fr);gap:8px 14px;margin:0;font-size:14px}
.kv dt{color:var(--text-2)}.kv dd{margin:0;overflow-wrap:anywhere}
.tr-row{display:grid;grid-template-columns:54px minmax(0,1fr) auto;gap:12px;padding:10px 0;border-bottom:1px solid var(--line-2);font-size:15px;line-height:1.7}
.tr-row:last-child{border-bottom:0}
.tr-row time{color:var(--text-2);font-variant-numeric:tabular-nums;font-size:13px;padding-top:2px}
.tr-row.low{background:var(--warn-bg);margin:0 -10px;padding-left:10px;padding-right:10px}
.timeline{list-style:none;margin:0;padding:0}
.timeline li{display:grid;grid-template-columns:150px minmax(0,1fr);gap:12px;padding:10px 0;border-bottom:1px solid var(--line-2);font-size:14px}
.timeline li:last-child{border-bottom:0}
.timeline .when{color:var(--text-2);font-size:13px}
.dropzone{border:2px dashed #aab4c5;border-radius:var(--r);padding:28px 16px;text-align:center;background:#fafbfd;margin-bottom:16px;cursor:pointer}
.dropzone:focus-within{outline:3px solid #7aa7ff;outline-offset:2px}
.dropzone.over{border-color:var(--blue);background:var(--blue-bg)}
.dropzone .ic{color:var(--blue)}
.dropzone p{margin:6px 0}
.dropzone input{position:absolute;opacity:0;width:1px;height:1px;min-height:0;margin:0}
.picked{display:none;align-items:center;gap:10px;padding:10px 12px;border:1px solid var(--line);border-radius:7px;margin-bottom:16px;background:#fff}
.picked.on{display:flex}.picked b{overflow-wrap:anywhere}
.picked .sp{flex:1}
.method{display:flex;gap:8px;margin-bottom:18px}
.method [role=tab]{background:#fff;color:var(--text);border:1px solid #c3cad6}
.method [role=tab][aria-selected=true]{background:var(--navy);color:#fff;border-color:var(--navy)}

/* dialog + toast */
dialog.dlg{border:0;border-radius:10px;padding:0;width:min(480px,calc(100vw - 32px));box-shadow:0 12px 40px rgba(15,31,61,.3)}
dialog.dlg::backdrop{background:rgba(15,31,61,.55)}
dialog.dlg form{padding:22px}
dialog.dlg h2{margin-bottom:8px;font-size:19px}
.dlg-actions{display:flex;justify-content:flex-end;gap:10px;margin-top:6px;flex-wrap:wrap}
#toasts{position:fixed;right:16px;bottom:16px;display:flex;flex-direction:column;gap:8px;z-index:60}
.toast{background:var(--navy);color:#fff;padding:12px 16px;border-radius:8px;box-shadow:0 6px 20px rgba(0,0,0,.25);max-width:340px;font-size:14px}

/* landing */
.land{max-width:1040px;margin:0 auto;padding:40px 20px}
.land-brand{display:flex;align-items:center;gap:10px;font-weight:650;font-size:20px;margin-bottom:28px}
.land-brand .logo{width:34px;height:34px;border-radius:8px;background:var(--navy);display:grid;place-items:center;color:#fff}
.role-card{display:flex;flex-direction:column;gap:10px}
.role-card .ic-lg{width:40px;height:40px;border-radius:8px;background:var(--blue-bg);color:var(--blue-dk);display:grid;place-items:center}
.role-card .btn{margin-top:auto;align-self:flex-start}

@media (max-width:1100px){.stats{grid-template-columns:repeat(2,minmax(0,1fr))}.cols{grid-template-columns:minmax(0,1fr)}.cols-3{grid-template-columns:minmax(0,1fr)}}
@media (max-width:900px){
  .shell{grid-template-columns:minmax(0,1fr)}
  .side{position:fixed;left:0;top:0;bottom:0;width:272px;z-index:50;transform:translateX(-100%);transition:transform .2s}
  .side.open{transform:none}
  .scrim.on{display:block;position:fixed;inset:0;background:rgba(15,31,61,.5);z-index:40}
  .menu-btn{display:grid}
  .top{padding:0 16px}main{padding:20px 16px}
  .grid-2,.field-grid{grid-template-columns:minmax(0,1fr)}
  .who .name{display:none}
}
@media (max-width:640px){
  h1{font-size:24px}
  .stats{grid-template-columns:minmax(0,1fr)}
  .card{padding:16px}
  table.data thead{position:absolute;left:-9999px}
  table.data,table.data tbody,table.data tr,table.data td{display:block;width:100%}
  table.data tr{padding:10px 14px;border-bottom:1px solid var(--line)}
  table.data td{border:0;padding:4px 0;display:grid;grid-template-columns:104px minmax(0,1fr);gap:8px}
  table.data td::before{content:attr(data-label);color:var(--text-2);font-size:12.5px;font-weight:600}
  .trunc{max-width:none;white-space:normal}
  table.data td .chip{white-space:normal}
  .finding dl,.kv,.timeline li{grid-template-columns:minmax(0,1fr)}
  .tr-row{grid-template-columns:44px minmax(0,1fr)}.tr-row .conf{grid-column:2}
  .company-switch span{display:none}
  .who .role{display:none}
}
@media (prefers-reduced-motion:reduce){*{transition:none!important;animation:none!important;scroll-behavior:auto!important}}
"""

# ------------------------------------------------------------------------- JS
JS = """
(function(){
  var $=function(s,r){return (r||document).querySelector(s)},$$=function(s,r){return Array.prototype.slice.call((r||document).querySelectorAll(s))};
  // mobile nav
  var side=$('#side'),scrim=$('#scrim'),mb=$('#menu-btn');
  function nav(open){if(!side)return;side.classList.toggle('open',open);scrim.classList.toggle('on',open);mb.setAttribute('aria-expanded',open)}
  if(mb){mb.addEventListener('click',function(){nav(!side.classList.contains('open'))});scrim.addEventListener('click',function(){nav(false)});
    document.addEventListener('keydown',function(ev){if(ev.key==='Escape')nav(false)})}
  // dialogs (native <dialog>: focus trap + Esc handled by the browser)
  $$('[data-dialog]').forEach(function(b){b.addEventListener('click',function(){var d=document.getElementById(b.getAttribute('data-dialog'));if(d&&d.showModal)d.showModal()})});
  $$('[data-close]').forEach(function(b){b.addEventListener('click',function(){b.closest('dialog').close()})});
  // toasts
  window.toast=function(msg){var t=document.createElement('div');t.className='toast';t.textContent=msg;$('#toasts').appendChild(t);setTimeout(function(){t.remove()},4500)};
  $$('[data-toast]').forEach(function(n){window.toast(n.getAttribute('data-toast'))});
  // lock forms against double submit
  $$('form[data-lock]').forEach(function(f){f.addEventListener('submit',function(){
    var b=f.querySelectorAll('button[type=submit]');
    setTimeout(function(){b.forEach(function(x){x.disabled=true});},0);
    var s=f.querySelector('[data-busy]');if(s)s.hidden=false;
    var l=f.querySelector('button[data-busy-label]');if(l)l.textContent=l.getAttribute('data-busy-label');
  })});
  // file picker + drag and drop
  var dz=$('#dropzone'),fi=$('#file'),pk=$('#picked');
  function size(n){return n>1048576?(n/1048576).toFixed(1)+' MB':Math.max(1,Math.round(n/1024))+' KB'}
  function show(){
    if(!fi)return;var f=fi.files&&fi.files[0];
    if(!f){pk.classList.remove('on');$('#submit-file').disabled=false;return}
    var max=parseInt(fi.getAttribute('data-max'),10),msg=$('#file-err');
    var ok=(fi.getAttribute('data-ext')||'').split(',');var ext='.'+f.name.split('.').pop().toLowerCase();
    var err='';if(ok.indexOf(ext)<0)err='This file type is not supported.';else if(f.size>max)err='This file is larger than the '+Math.round(max/1048576)+' MB limit.';
    msg.textContent=err;msg.hidden=!err;$('#picked-name').textContent=f.name+' ('+size(f.size)+')';pk.classList.add('on');
    $('#submit-file').disabled=!!err;
  }
  if(fi){fi.addEventListener('change',show);
    $('#remove-file').addEventListener('click',function(){fi.value='';show()});
    dz.addEventListener('dragover',function(ev){ev.preventDefault();dz.classList.add('over')});
    dz.addEventListener('dragleave',function(){dz.classList.remove('over')});
    dz.addEventListener('drop',function(ev){ev.preventDefault();dz.classList.remove('over');if(ev.dataTransfer.files.length){fi.files=ev.dataTransfer.files;show()}});
    dz.addEventListener('click',function(ev){if(ev.target.tagName!=='LABEL')fi.click()});
  }
  // submit method tabs
  $$('[role=tab]').forEach(function(t){t.addEventListener('click',function(){
    $$('[role=tab]').forEach(function(x){var on=x===t;x.setAttribute('aria-selected',on);document.getElementById(x.getAttribute('aria-controls')).hidden=!on});
  })});
  // dismiss welcome panel (remembered per portal, per browser)
  $$('[data-dismiss]').forEach(function(b){var k='bg-welcome-'+b.getAttribute('data-dismiss'),p=b.closest('.welcome');
    try{if(localStorage.getItem(k)){p.hidden=true}}catch(x){}
    b.addEventListener('click',function(){p.hidden=true;try{localStorage.setItem(k,'1')}catch(x){}})});
  $$('select[data-autosubmit]').forEach(function(s){s.addEventListener('change',function(){s.form.submit()})});
})();
"""

_LOGO = ('<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" '
         'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' + _ICONS["shield"] +
         '<path d="m9 12 2 2 4-4"/></svg>')

_HEAD = ("<!doctype html><html lang='en'><head><meta charset='utf-8'>"
         "<meta name='viewport' content='width=device-width,initial-scale=1'>"
         "<link rel='preconnect' href='https://fonts.googleapis.com'>"
         "<link rel='stylesheet' href='https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700"
         "&family=Noto+Sans+Devanagari:wght@400;600&display=swap'>")


def landing(body):
    return (_HEAD + f"<title>BrandGuard</title><style>{CSS}</style></head><body>"
            f'<a class="skip" href="#main">Skip to content</a>'
            f'<div class="land"><div class="land-brand"><span class="logo">{_LOGO}</span>BrandGuard</div>'
            f'<main id="main" style="padding:0">{body}</main></div>'
            f'<div id="toasts" role="status" aria-live="polite"></div><script>{JS}</script></body></html>')


def shell(title, body, user, role_label, active="", crumbs=None, queue_count=0,
          company=None, flash="", demo_users=()):
    """company = (current_id, [(id, name), ...]) for submitters; None otherwise."""
    is_admin = user["role"] == "admin"
    items = NAV_ADMIN if is_admin else NAV_SUB
    links = []
    for key, href, label, ic in items:
        cur = ' aria-current="page"' if key == active else ""
        cnt = f'<span class="count" aria-label="{queue_count} waiting">{queue_count}</span>' if key == "queue" and queue_count else ""
        links.append(f'<a href="{href}"{cur}>{icon(ic)}<span>{e(label)}</span>{cnt}</a>')

    demo = "".join(
        f'<a href="/enter/{k}"{" class=cur" if current else ""}>{icon("users", 16)}{e(lbl)}</a>'
        for k, lbl, current in demo_users)

    home = "Overview" if is_admin else "My Dashboard"
    trail = [(home, "/")] + list(crumbs or [])
    cr = []
    for i, (lbl, href) in enumerate(trail):
        last = i == len(trail) - 1
        cr.append(f'<span aria-current="page">{e(lbl)}</span>' if last or not href
                  else f'<a href="{href}">{e(lbl)}</a>')
    sep = icon("chevron-right", 14)
    crumbs_html = f'<nav class="crumbs" aria-label="Breadcrumb">{sep.join(cr)}</nav>'

    comp = ""
    if company:
        cur_id, opts = company
        if len(opts) > 1:
            o = "".join(f'<option value="{i}"{" selected" if i == cur_id else ""}>{e(n)}</option>' for i, n in opts)
            comp = (f'<form class="company-switch" method="get" action="/company">'
                    f'<label for="company" style="margin:0"><span>Company</span></label>'
                    f'<select id="company" name="id" data-autosubmit>{o}</select>'
                    f'<noscript><button class="btn sm">Switch</button></noscript></form>')
        elif opts:
            comp = f'<span class="chip info">{icon("building", 14)}{e(opts[0][1])}</span>'

    toast = f'<div hidden data-toast="{e(flash)}"></div>' if flash else ""
    return (_HEAD + f"<title>{e(title)} - BrandGuard</title><style>{CSS}</style></head><body>"
            '<a class="skip" href="#main">Skip to content</a>'
            '<div class="shell">'
            f'<aside class="side" id="side"><a class="brand" href="/"><span class="logo">{_LOGO}</span>BrandGuard</a>'
            f'<nav aria-label="Main">{"".join(links)}</nav>'
            f'<div class="side-foot"><div class="lbl">Switch demo role</div>{demo}'
            f'<a href="/logout">{icon("log-out", 16)}Log out</a></div></aside>'
            '<div class="scrim" id="scrim"></div>'
            '<div class="main-col"><header class="top">'
            f'<button class="menu-btn" id="menu-btn" aria-label="Open navigation" aria-controls="side" aria-expanded="false" type="button" style="padding:0">{icon("menu", 22)}</button>'
            f'{crumbs_html}<span class="sp"></span>{comp}'
            f'<div class="who"><span class="name">{e(user["name"])}</span><span class="role">{e(role_label)}</span></div>'
            '</header>'
            f'<main id="main">{body}</main></div></div>'
            f'<div id="toasts" role="status" aria-live="polite"></div>{toast}<script>{JS}</script></body></html>')