"""BrandGuard presentation layer: design tokens, icons, app shell and small HTML components.

Pure rendering helpers. No database access and no business rules live here.
"""

import html

e = html.escape

# ---------------------------------------------------------------------- icons
# Lucide-style 24x24 stroke icons (path data only).
_ICONS = {
    "home": '<path d="m3 9 9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/><path d="M9 22V12h6v10"/>',
    "sun": '<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2m-7.07-14.93 1.41 1.41m11.32 11.32 1.41 1.41M2 12h2m16 0h2M4.93 19.07l1.41-1.41m11.32-11.32 1.41-1.41"/>',
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
    # --- wow / demo surfaces ---
    "radar": '<circle cx="12" cy="12" r="2"/><path d="M12 2v2M12 20v2M2 12h2M20 12h2"/><path d="M6.3 6.3 7.7 7.7M16.3 16.3l1.4 1.4M6.3 17.7 7.7 16.3M16.3 7.7l1.4-1.4"/><circle cx="12" cy="12" r="6"/><path d="m12 12 5-2"/>',
    "sparkles": '<path d="M12 3v3M12 18v3M3 12h3M18 12h3"/><path d="m5.6 5.6 2.1 2.1M16.3 16.3l2.1 2.1M5.6 18.4l2.1-2.1M16.3 7.7l2.1-2.1"/><circle cx="12" cy="12" r="3.2"/>',
    "megaphone": '<path d="m3 11 18-5v12L3 13v-2z"/><path d="M11.6 16.8a3 3 0 1 1-5.8-1.6"/>',
    "image": '<rect width="18" height="18" x="3" y="3" rx="2"/><circle cx="9" cy="9" r="2"/><path d="m21 15-3.1-3.1a2 2 0 0 0-2.8 0L6 21"/>',
    "video": '<path d="m16 13 5.2 3.0V8L16 11"/><rect width="14" height="12" x="2" y="6" rx="2"/>',
    "clipboard": '<rect width="14" height="16" x="5" y="4" rx="2"/><path d="M9 4V3a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v1"/><path d="M9 12h6M9 16h4"/>',
    "git-branch": '<circle cx="6" cy="6" r="2.5"/><circle cx="18" cy="6" r="2.5"/><circle cx="6" cy="18" r="2.5"/><path d="M6 8.5v7M8.5 6h7M8.5 18c4 0 7-3 7-7"/>',
    "passport": '<rect width="16" height="20" x="4" y="2" rx="2"/><circle cx="12" cy="10" r="3"/><path d="M8 17h8M9 7.5c.6-.8 1.7-1.3 3-1.3s2.4.5 3 1.3"/>',
    "sliders": '<path d="M4 21v-7M4 10V3M12 21v-9M12 8V3M20 21v-5M20 12V3M1 14h6M9 8h6M17 16h6"/>',
    "vault": '<rect width="18" height="12" x="3" y="8" rx="2"/><path d="M7 8V6a5 5 0 0 1 10 0v2"/><circle cx="12" cy="14" r="2"/><path d="M12 16v2"/>',
    "wand": '<path d="M15 4V2M15 16v-2M8 9H6M22 9h-2M18.4 4.6l1.4-1.4M18.4 13.4l1.4 1.4M11.6 4.6 10.2 3.2M16 9h.01"/><path d="m3 21 9-9M12.5 5.5l6 6"/>',
    "layers": '<path d="m12 2 9 4.5-9 4.5L3 6.5 12 2z"/><path d="m3 12.5 9 4.5 9-4.5"/><path d="m3 17.5 9 4.5 9-4.5"/>',
    "activity": '<path d="M22 12h-4l-3 9L9 3l-3 9H2"/>',
    "pen": '<path d="M12 20h9"/><path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4Z"/>',
    "thumbs-up": '<path d="M7 10v12"/><path d="M15 5.88 14 10h5.8a2 2 0 0 1 1.9 2.6l-2.3 6.4a2 2 0 0 1-1.9 1.4H7V10h2.3a2 2 0 0 0 1.9-1.3L14 2.5a1.6 1.6 0 0 1 3 .9Z"/>',
    "thumbs-down": '<path d="M17 14V2"/><path d="M9 18.12 10 14H4.2a2 2 0 0 1-1.9-2.6l2.3-6.4A2 2 0 0 1 6.5 3.6H17V14h-2.3a2 2 0 0 0-1.9 1.3L10 21.5a1.6 1.6 0 0 1-3-.9Z"/>',
    "refresh": '<path d="M3 12a9 9 0 0 1 15.4-6.4L21 8"/><path d="M21 3v5h-5"/><path d="M21 12a9 9 0 0 1-15.4 6.4L3 16"/><path d="M8 16H3v5"/>',
    "zap": '<path d="M13 2 3 14h8l-1 8 10-12h-8l1-8z"/>',
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
    ("insights", "/admin/insights", "Compliance Insights", "activity"),
    ("rules", "/admin/rules", "Brand Rules", "shield"),
    ("facts", "/admin/projects", "Projects and Facts", "tag"),
    ("access", "/admin/access", "Project Access", "users"),
    ("team", "/admin/team", "Team and Invites", "users"),
    ("disputes", "/disputes", "Disputes", "scale"),
    ("learned", "/admin/learned", "Lessons", "sparkles"),
    ("approvals", "/approvals", "Approval Records", "badge-check"),
    ("audit", "/audit", "Audit Trail", "history"),
    ("verify", "/verify", "Verify a File", "file-check"),
    ("testaudio", "/test-audio", "Demo Files", "play"),
]
# The reviewer menu is grouped by job: decide, set up, prove. Setup and proof fold away until one of their pages is open.
NAV_ADMIN_GROUPS = [
    ("", ("overview",)),
    ("Work", ("queue", "reviews", "disputes", "insights")),
    ("Set up", ("rules", "facts", "access", "team", "learned")),
    ("Proof", ("approvals", "audit", "verify")),
]
NAV_SUB = [
    ("overview", "/", "My Dashboard", "home"),
    ("submit", "/submit", "Submit Content", "upload"),
    ("bulk", "/bulk", "Bulk Upload", "layers"),
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


def approval_record(approval_id, sha256, decided=""):
    """The proof artifact: ID and file fingerprint set out like an entry in a ledger."""
    by = f'<div class="rec-row"><dt>Recorded</dt><dd>{e(decided)}</dd></div>' if decided else ""
    return (f'<section class="approval-record" aria-label="Approval record">'
            f'<p class="rec-title">{icon("badge-check", 18)}Approval record</p>'
            f'<dl><div class="rec-row"><dt>Approval ID</dt><dd class="rec-id">{e(approval_id)}</dd></div>'
            f'<div class="rec-row"><dt>File fingerprint (SHA-256)</dt><dd class="mono">{e(sha256 or "Not applicable (no file)")}</dd></div>'
            f'{by}</dl></section>')


def disclosure(title, inner, desc=""):
    """Collapsed group for audit evidence; the content stays in the page for keyboard and print."""
    d = f'<span class="muted">{desc}</span>' if desc else ""
    return (f'<details class="evidence"><summary><span class="evidence-title">{e(title)}</span>{d}</summary>'
            f'<div class="evidence-body">{inner}</div></details>')


def card(title, inner, desc="", actions="", cls=""):
    h = ""
    if title or actions:
        t = f"<h2>{e(title)}</h2>" if title else "<span></span>"
        h = f'<div class="card-head">{t}{actions}</div>'
    d = f'<p class="muted card-desc">{desc}</p>' if desc else ""
    scope = ' data-keyscope tabindex="-1"' if "keyscope" in cls.split() else ""
    return f'<section class="card {cls}"{scope}>{h}{d}{inner}</section>'


def empty(title, text="", action="", ic="inbox"):
    return (f'<div class="empty"><span class="empty-ic">{icon(ic, 32)}</span>'
            f'<p class="empty-title">{e(title)}</p>'
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


_STATUS_CLS = {"ok": "c-ok", "warn": "c-warn", "bad": "c-bad", "neutral": "c-neutral", "d1": "c-d1", "d2": "c-d2", "d3": "c-d3"}


def donut(parts, center_label, label):
    """parts: [(name, count, tone)]. Counts come from real data; a total of 0 draws an empty ring."""
    total = sum(v for _, v, _ in parts)
    segs, legend, off = [], [], 0.0
    for name, v, tone in parts:
        cls = _STATUS_CLS.get(tone, "c-d1")
        pct = (v / total * 100) if total else 0
        if v and total:
            dash = max(pct - 1.2, 0.6)
            segs.append(f'<circle class="seg {cls}" cx="21" cy="21" r="15.9155" pathLength="100" '
                        f'stroke-dasharray="{dash:.2f} {100 - dash:.2f}" stroke-dashoffset="{-off:.2f}"/>')
        off += pct
        legend.append(f'<li><span class="dot {cls}"></span>{e(name)}<span class="lv">{v}</span>'
                      f'<span class="lp">{round(pct)}%</span></li>')
    summary = ", ".join(f"{n}: {v}" for n, v, _ in parts)
    return (f'<div class="donut-wrap"><div class="donut"><svg viewBox="0 0 42 42" role="img" aria-label="{e(label)}. {e(summary)}">'
            f'<circle class="track" cx="21" cy="21" r="15.9155"/>{"".join(segs)}</svg>'
            f'<div class="donut-center"><b>{total}</b><span>{e(center_label)}</span></div></div>'
            f'<ul class="legend">{"".join(legend)}</ul></div>')


def hbars(items, empty="Nothing to show yet."):
    """items: [(label, count)]; bar length is relative to the largest count."""
    if not items:
        return f'<p class="chart-empty">{e(empty)}</p>'
    top = max(v for _, v in items) or 1
    rows = "".join(f'<li><div class="hb-top"><span>{e(n)}</span><b>{v}</b></div>'
                   f'<div class="hb-track"><span class="hb-fill" style="--v:{round(v / top * 100)}"></span></div></li>' for n, v in items)
    return f'<ul class="hbars">{rows}</ul>'


def vbars(items):
    """items: [(label, count, highlight)] drawn as columns, tallest = full height."""
    top = max((v for _, v, _ in items), default=0) or 1
    summary = ", ".join(f"{n}: {v}" for n, v, _ in items)
    cols = "".join(f'<div class="vb{" on" if on else ""}"><span class="vb-n">{v}</span>'
                   f'<span class="vb-bar" style="--v:{round(v / top * 100)}"></span><span class="vb-l">{e(n)}</span></div>'
                   for n, v, on in items)
    return f'<div class="vbars" role="img" aria-label="{e(summary)}">{cols}</div>'


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
/* guided tour */
.tour-ring{position:fixed;z-index:90;border-radius:var(--rad-lg);box-shadow:0 0 0 3px var(--tour-ring),0 0 0 9999px var(--scrim);pointer-events:none;transition:all .2s}
.tour-pop{position:fixed;z-index:91;width:min(340px,calc(100vw - 32px));background:var(--surface);color:var(--text);border-radius:var(--rad-lg);
  box-shadow:var(--sh-pop);padding:16px 18px}
.tour-pop h3{font-size:var(--fs-lg);margin:0 0 6px}.tour-pop p{margin:0 0 12px;font-size:var(--fs-base);color:var(--text-2)}
.tour-pop .tour-row{display:flex;gap:8px;align-items:center}.tour-pop .tour-n{font-size:var(--fs-xs);color:var(--text-2);margin-right:auto}
.tour-pop::before{content:"";position:absolute;left:-8px;top:18px;border:8px solid transparent;border-left:0;border-right-color:var(--surface)}
.tour-pop.center::before{display:none}
.tour-start{background:none;border:0;color:var(--side-text);font:inherit;font-size:var(--fs-base);cursor:pointer;display:flex;gap:8px;align-items:center;justify-content:flex-start;padding:8px 10px;width:100%;text-align:left}
.tour-start:hover{color:var(--text)}
input[type=checkbox],input[type=radio]{width:auto;min-height:0;margin:0 8px 0 0;vertical-align:middle;accent-color:var(--accent)}
.checklist{list-style:none;margin:0;padding:0}.checklist li{display:flex;gap:12px;align-items:flex-start;padding:12px 0;border-bottom:1px solid var(--line-2)}
.checklist li:last-child{border-bottom:0}.checklist .dot{flex:0 0 26px;height:26px;border-radius:50%;display:grid;place-items:center;font-size:var(--fs-sm);font-weight:700;
  background:var(--accent-bg);color:var(--accent-ink)}.checklist .done .dot{background:var(--ok-bg);color:var(--ok)}
.checklist .done b{text-decoration:line-through;color:var(--text-2)}

:root{
  --bg:#f6f4fb;--surface:#fff;--line:#e8e4f3;--line-2:#f1eef9;--text:#1c1a2e;--text-2:#6b6784;
  --accent:#6d3bd8;--accent-hover:#5a2dbd;--accent-ink:#5a2dbd;--accent-bg:#f0eafd;--link:#6d3bd8;--accent-grad:linear-gradient(145deg,#7a4ae6,#5a2dbd);
  --navy:#1c1a2e;--navy-2:#2b2845;
  --side-bg:#fbfaff;--side-text:#4a4663;--side-muted:#6b6784;--side-hover:#f1eefa;--side-active-bg:#ffffff;--side-active-text:#5a2dbd;--side-line:#e8e4f3;
  --ok:#136c3a;--ok-bg:#e3f5ea;--warn:#8a5300;--warn-bg:#fff2d6;--bad:#a61b1b;--bad-bg:#fde8e8;
  --neutral:#4a5568;--neutral-bg:#eceaf3;--field-line:#8a85a3;
  --ok-line:#4f9d6f;--warn-line:#b88a28;--bad-line:#cf6a6a;--info-line:#8a63e8;--media-bg:#000000;
  --focus:#8a63e8;--nav-text:#cfd8e8;--nav-muted:#aab8d0;--panel:#faf9fd;--panel-2:#f8f6fd;
  --on-accent:#ffffff;--danger:#b42323;--danger-dk:#951b1b;--success:#15803d;--success-dk:#106530;
  --info-ink:#4a2699;--warn-ink:#6b4100;--tour-ring:#f2a900;--warn-wash:#fffaf0;--info-wash:#f7f3ff;--ok-wash:#fbfefc;
  --icon-muted:#8a86a3;--line-strong:#d6d0e6;--scrim:rgba(28,26,46,.55);
  --d1:#6d3bd8;--d2:#5aa2ff;--d3:#a98bf0;--d-ok:#2db873;--d-warn:#f0b429;--d-bad:#e5484d;--d-neutral:#a29fb8;
  --sh-pop:0 12px 40px rgba(28,26,46,.3);--sh-toast:0 6px 20px rgba(0,0,0,.25);--sh-logo:0 4px 14px rgba(90,45,189,.3);--sh-lift-lg:0 10px 28px rgba(60,40,120,.12);--sh-lift:0 2px 10px rgba(60,40,120,.08);--sh-nav:0 1px 3px rgba(60,40,120,.14);--sh-stage:0 18px 40px rgba(28,26,46,.28);
  --fs-xs:12px;--fs-sm:13px;--fs-base:14px;--fs-md:15px;--fs-lg:17px;--fs-xl:20px;--fs-2xl:24px;--fs-3xl:28px;--fs-hero:clamp(30px,4.2vw,42px);
  --rad-xs:6px;--rad-sm:10px;--rad-lg:16px;--rad-xl:20px;color-scheme:light;
  --r:16px;--sh:0 1px 2px rgba(60,40,120,.05);
  --side:248px;
  --font:Manrope,"Segoe UI","Noto Sans","Noto Sans Devanagari","Nirmala UI","Mangal",system-ui,sans-serif;
}
:root[data-theme="dark"]{--bg:#0f0c1f;--surface:#17132b;--line:#2a2447;--line-2:#201b3a;--text:#ece9f7;--text-2:#a9a4c4;--accent:#7a4ae0;--accent-hover:#6638cc;--accent-ink:#cdbbff;--accent-bg:#2a1f52;--link:#b79cff;--accent-grad:linear-gradient(145deg,#8559ee,#5a2dbd);--navy:#0c0919;--navy-2:#1c1736;--side-bg:#0c0919;--side-text:#cfcae6;--side-muted:#9b96b8;--side-hover:#1c1736;--side-active-bg:#241d47;--side-active-text:#ffffff;--side-line:#201b3a;--ok:#6fd09a;--ok-bg:#12281d;--warn:#f0b863;--warn-bg:#33270f;--bad:#ff9a9a;--bad-bg:#3a1618;--neutral:#b4bfd0;--neutral-bg:#262140;--field-line:#8a85a8;--line-strong:#3a3360;--panel:#1d1837;--panel-2:#1d1837;--warn-wash:#2a2110;--info-wash:#1f1840;--ok-wash:#102219;--info-ink:#d6c8ff;--warn-ink:#ffd9a0;--icon-muted:#948fb2;--sh:0 1px 2px rgba(0,0,0,.4);--sh-nav:0 1px 3px rgba(0,0,0,.5);color-scheme:dark;}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--bg:#0f0c1f;--surface:#17132b;--line:#2a2447;--line-2:#201b3a;--text:#ece9f7;--text-2:#a9a4c4;--accent:#7a4ae0;--accent-hover:#6638cc;--accent-ink:#cdbbff;--accent-bg:#2a1f52;--link:#b79cff;--accent-grad:linear-gradient(145deg,#8559ee,#5a2dbd);--navy:#0c0919;--navy-2:#1c1736;--side-bg:#0c0919;--side-text:#cfcae6;--side-muted:#9b96b8;--side-hover:#1c1736;--side-active-bg:#241d47;--side-active-text:#ffffff;--side-line:#201b3a;--ok:#6fd09a;--ok-bg:#12281d;--warn:#f0b863;--warn-bg:#33270f;--bad:#ff9a9a;--bad-bg:#3a1618;--neutral:#b4bfd0;--neutral-bg:#262140;--field-line:#8a85a8;--line-strong:#3a3360;--panel:#1d1837;--panel-2:#1d1837;--warn-wash:#2a2110;--info-wash:#1f1840;--ok-wash:#102219;--info-ink:#d6c8ff;--warn-ink:#ffd9a0;--icon-muted:#948fb2;--sh:0 1px 2px rgba(0,0,0,.4);--sh-nav:0 1px 3px rgba(0,0,0,.5);color-scheme:dark;}}

.u-narrow{max-width:460px;margin-left:auto;margin-right:auto}.u-form{max-width:520px;margin:40px auto}.u-w200{max-width:200px}.u-w340{max-width:340px}.u-w100{width:100%}.u-list{margin:0;padding-left:20px}.u-indent{padding-left:20px}.u-my14{margin:14px 0}.u-m10-14{margin:10px 0 14px}.u-fs13{font-size:var(--fs-sm)}.u-mt0{margin-top:0}.u-mt10{margin-top:10px}.u-mt22{margin-top:22px}.u-mb6{margin-bottom:6px}.u-mb10{margin-bottom:10px}.u-mb12{margin-bottom:12px}.u-mb28{margin-bottom:28px}
.note-disclosure{margin:10px 0 18px}.check-row{padding:10px 0;border-bottom:1px solid var(--line-2)}.check-row-top{display:flex;gap:8px;align-items:center;justify-content:space-between;flex-wrap:wrap}
.plain-list{list-style:none;margin:0;padding:0}.sort-select{width:auto;margin:0;flex:none}.inline-add{flex:1;min-width:200px;margin:0}.based-on{padding:8px 0 0 14px}
.revoke-form{display:inline-block;margin:2px 6px 2px 0}.all-projects{display:block;font-weight:600}.sub-project{display:block;margin-left:22px}
.example-pre{white-space:pre-wrap;background:var(--panel-2);border:1px solid var(--line);border-radius:var(--rad-sm);padding:12px;margin:0 0 8px}
.media-player{width:100%;max-height:360px;margin:8px 0 12px;background:var(--media-bg);border-radius:var(--r)}
.u-inline{display:inline}.u-m0{margin:0}.u-mt4{margin-top:4px}.u-mt6{margin-top:6px}.u-mt8{margin-top:8px}.u-mt12{margin-top:12px}.u-mt14{margin-top:14px}.u-mt16{margin-top:16px}.u-mt20{margin-top:20px}.u-mb4{margin-bottom:4px}
.sr-only{position:absolute;left:-9999px;width:1px;height:1px;overflow:hidden}
*{box-sizing:border-box}
html{-webkit-text-size-adjust:100%}
body{margin:0;font-family:var(--font);font-size:var(--fs-md);line-height:1.55;background:var(--bg);color:var(--text)}
h1,h2,h3{margin:0;line-height:1.3;color:var(--text);text-wrap:balance}
h1{font-size:var(--fs-3xl);font-weight:800;letter-spacing:-.02em}
h2{font-size:var(--fs-lg);font-weight:700}
h3{font-size:var(--fs-md);font-weight:600}
p{margin:0 0 12px;text-wrap:pretty}
a{color:var(--link)}
.muted{color:var(--text-2);font-size:var(--fs-base)}
.check{display:flex;align-items:center;gap:8px;margin:6px 0;font-weight:400}
.check input{width:auto}
.mono{font-family:Consolas,"SFMono-Regular",monospace;font-size:var(--fs-sm);overflow-wrap:anywhere}
.ic{flex:none;vertical-align:-3px}
:focus-visible{outline:3px solid var(--focus);outline-offset:2px;border-radius:var(--rad-xs)}
.skip{position:absolute;left:-999px;top:8px;background:var(--navy);color:var(--on-accent);padding:8px 14px;border-radius:var(--rad-sm);z-index:100}
.skip:focus{left:8px}

/* shell */
.shell{display:grid;grid-template-columns:var(--side) minmax(0,1fr);min-height:100vh}
.side{background:var(--side-bg);border-right:1px solid var(--side-line);color:var(--side-text);display:flex;flex-direction:column;position:sticky;top:0;height:100vh;overflow-y:auto}
.brand{display:flex;align-items:center;gap:10px;padding:18px 20px;color:var(--text);font-weight:800;font-size:var(--fs-lg);letter-spacing:-.01em;text-decoration:none}
.brand .logo{width:30px;height:30px;border-radius:var(--rad-sm);background:var(--accent-grad);display:grid;place-items:center;color:var(--on-accent);box-shadow:var(--sh-logo)}
.side nav{padding:8px 12px;flex:1}
.side nav a{display:flex;align-items:center;gap:12px;padding:10px 12px;margin:2px 0;border-radius:var(--rad-sm);color:var(--side-text);text-decoration:none;font-size:var(--fs-base);font-weight:500;min-height:44px}
.side nav a:hover{background:var(--side-hover);color:var(--text)}
.side nav a[aria-current=page]{background:var(--side-active-bg);color:var(--side-active-text);font-weight:700;box-shadow:var(--sh-nav)}
.side nav a[aria-current=page] .ic{color:var(--accent)}
.side .count{margin-left:auto;background:var(--accent);color:var(--on-accent);border-radius:999px;padding:0 8px;font-size:var(--fs-xs);font-weight:700;line-height:20px}
.side-foot{padding:14px 16px 18px;border-top:1px solid var(--side-line);font-size:var(--fs-sm)}
.side-foot .lbl{text-transform:uppercase;letter-spacing:.06em;font-size:var(--fs-xs);color:var(--side-muted);margin-bottom:6px}
.side-foot a{display:flex;align-items:center;gap:8px;color:var(--side-text);text-decoration:none;padding:7px 4px;min-height:44px}
kbd{font-family:Consolas,"SFMono-Regular",monospace;font-size:var(--fs-xs);background:var(--neutral-bg);border:1px solid var(--line);border-bottom-width:2px;border-radius:var(--rad-xs);padding:0 5px}
.navgroup{margin:6px 0}
.navgroup>summary{list-style:none;cursor:pointer;display:flex;align-items:center;justify-content:space-between;padding:8px 12px;min-height:44px;font-size:var(--fs-xs);font-weight:600;letter-spacing:.04em;text-transform:uppercase;color:var(--side-muted);border-radius:var(--rad-sm)}
.navgroup>summary::-webkit-details-marker{display:none}
.navgroup>summary::after{content:"";width:7px;height:7px;border-right:2px solid currentColor;border-bottom:2px solid currentColor;transform:rotate(-45deg);transition:transform .15s}
.navgroup[open]>summary::after{transform:rotate(45deg)}
.navgroup>summary:hover{color:var(--text)}
.demo-switch{margin-bottom:6px}
.demo-switch>summary{cursor:pointer;color:var(--side-muted);padding:7px 4px;min-height:44px;display:flex;align-items:center}
.demo-switch>summary:hover{color:var(--text)}
.side-foot a:hover{color:var(--text)}
.side-foot a.cur{color:var(--text);font-weight:700}
.main-col{min-width:0;display:flex;flex-direction:column}
.top{background:transparent;padding:12px 28px 0;min-height:56px;display:flex;align-items:center;gap:14px}
.crumbs{font-size:var(--fs-base);color:var(--text-2);display:flex;align-items:center;gap:6px;flex-wrap:wrap}
.crumbs a{color:var(--text-2);text-decoration:none}.crumbs a:hover{text-decoration:underline}
.crumbs [aria-current]{color:var(--text);font-weight:600}
.top .sp{flex:1}
.who{display:flex;align-items:center;gap:10px;font-size:var(--fs-base)}
.who .role{background:var(--accent-bg);color:var(--accent-ink);border-radius:var(--rad-sm);padding:2px 10px;font-size:var(--fs-xs);font-weight:600}
.menu-btn{display:none;background:none;border:1px solid var(--line);border-radius:var(--rad-sm);width:44px;height:44px;color:var(--text);cursor:pointer;place-items:center}
.company-switch{display:flex;align-items:center;gap:8px;font-size:var(--fs-base)}
.company-switch select{width:auto;margin:0;padding:6px 10px;min-height:44px}
main{padding:20px 28px 40px;max-width:1240px;width:100%}
.scrim{display:none}

/* page */
.page-head{display:flex;justify-content:space-between;align-items:flex-start;gap:16px;flex-wrap:wrap;margin-bottom:24px}
.page-desc{color:var(--text-2);margin:6px 0 0;max-width:68ch}
.page-actions{display:flex;gap:8px;flex-wrap:wrap}
.stack{display:flex;flex-direction:column;gap:20px}
.card{background:var(--surface);border:1px solid var(--line);border-radius:var(--r);padding:22px;box-shadow:var(--sh)}
.card-head{display:flex;justify-content:space-between;align-items:center;gap:12px;margin-bottom:14px;flex-wrap:wrap}
.card-desc{margin:-6px 0 14px}
.stats{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:16px}
.stat{display:flex;flex-direction:column;gap:2px;background:var(--surface);border:1px solid var(--line);border-radius:var(--r);padding:16px 18px;box-shadow:var(--sh);text-decoration:none;color:var(--text)}
a.stat:hover{border-color:var(--link)}
.stat.ok .stat-value{color:var(--ok)}.stat.warn .stat-value{color:var(--warn)}.stat.bad .stat-value{color:var(--bad)}.stat.info .stat-value{color:var(--accent-ink)}
.stat-label{font-size:var(--fs-sm);color:var(--text-2);font-weight:600}
.stat-value{font-size:var(--fs-3xl);font-weight:800;line-height:1.15;letter-spacing:-.02em;font-variant-numeric:tabular-nums}
.stat-hint{font-size:var(--fs-xs);color:var(--text-2);min-height:18px}
.stat.hero{background:var(--accent-grad);border-color:transparent;color:var(--on-accent)}
.stat.hero .stat-label,.stat.hero .stat-hint,.stat.hero .stat-value{color:var(--on-accent)}
.stat{gap:6px;padding:18px 20px}
.grid-2{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:20px}
.cols{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1.2fr);gap:20px;align-items:start}
.cols-3{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:20px}
.cols-2{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:20px}
.empty{text-align:center;padding:36px 16px;color:var(--text-2)}
.empty .ic,.empty-ic{color:var(--icon-muted);margin-bottom:8px;display:inline-flex}
.empty-ic{width:56px;height:56px;border-radius:var(--rad-xl);background:var(--accent-bg);color:var(--accent-ink);align-items:center;justify-content:center;margin:0 auto 12px}
.empty-title{font-weight:650;color:var(--text);margin:0 0 4px;font-size:var(--fs-lg)}

/* chips, alerts */
.chip{display:inline-flex;align-items:center;gap:5px;padding:2px 10px;border-radius:999px;font-size:var(--fs-xs);font-weight:600;white-space:nowrap;background:var(--neutral-bg);color:var(--neutral)}
.chip.ok{background:var(--ok-bg);color:var(--ok)}.chip.warn{background:var(--warn-bg);color:var(--warn)}.chip.bad{background:var(--bad-bg);color:var(--bad)}
.chip.info{background:var(--accent-bg);color:var(--accent-ink)}
.alert{display:flex;gap:12px;align-items:flex-start;padding:12px 14px;border-radius:var(--r);border:1px solid;font-size:var(--fs-base)}
.alert>div{min-width:0;overflow-wrap:anywhere}
.alert.info{background:var(--accent-bg);border-color:var(--info-line);color:var(--info-ink)}
.alert.ok{background:var(--ok-bg);border-color:var(--ok-line);color:var(--ok)}
.alert.warn{background:var(--warn-bg);border-color:var(--warn-line);color:var(--warn-ink)}
.alert.bad{background:var(--bad-bg);border-color:var(--bad-line);color:var(--bad)}

/* buttons, forms */
.btn,button{font-family:inherit;font-size:var(--fs-base);font-weight:600;border-radius:var(--rad-sm);padding:9px 16px;min-height:44px;border:1px solid transparent;cursor:pointer;display:inline-flex;align-items:center;justify-content:center;gap:8px;text-decoration:none;line-height:1.2;background:var(--accent);color:var(--on-accent)}
.btn:hover,button:hover{background:var(--accent-hover)}
.btn.secondary,button.secondary{background:var(--surface);color:var(--text);border-color:var(--field-line)}
.btn.secondary:hover,button.secondary:hover{background:var(--bg)}
.btn.danger,button.danger{background:var(--danger)}.btn.danger:hover,button.danger:hover{background:var(--danger-dk)}
.btn.success,button.success{background:var(--success)}.btn.success:hover,button.success:hover{background:var(--success-dk)}
.btn.sm{min-height:44px;padding:5px 12px;font-size:var(--fs-sm)}
.btn:disabled,button:disabled,[aria-disabled=true]{opacity:.55;cursor:not-allowed;pointer-events:none}
label{display:block;font-size:var(--fs-base);font-weight:600;margin:0 0 6px}
.req{color:var(--bad);font-weight:500}
.hint{font-size:var(--fs-sm);color:var(--text-2);margin:-2px 0 6px}
input,select,textarea{width:100%;font-family:inherit;font-size:var(--fs-md);color:var(--text);background:var(--surface);border:1px solid var(--field-line);border-radius:var(--rad-sm);padding:9px 12px;min-height:44px;margin:0 0 16px}
textarea{resize:vertical;line-height:1.5}
input:focus,select:focus,textarea:focus{outline:3px solid var(--focus);outline-offset:0;border-color:var(--link)}
input[type=file]{padding:8px;min-height:0}
fieldset{border:0;padding:0;margin:0 0 8px}
legend{font-size:var(--fs-base);font-weight:600;padding:0;margin-bottom:8px}
.field-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:0 20px}
.form-actions{display:flex;gap:10px;flex-wrap:wrap;align-items:center;margin-top:4px}

/* tables */
.table-wrap{overflow-x:auto;border:1px solid var(--line);border-radius:var(--r)}
table.data{width:100%;border-collapse:collapse;font-size:var(--fs-base);background:var(--surface)}
table.data th{background:var(--panel-2);color:var(--text-2);font-size:var(--fs-xs);font-weight:600;text-transform:uppercase;letter-spacing:.04em;text-align:left;padding:10px 14px;border-bottom:1px solid var(--line);white-space:nowrap}
table.data td:first-child{white-space:nowrap}
table.data td{padding:12px 14px;border-bottom:1px solid var(--line-2);vertical-align:top;overflow-wrap:anywhere}
table.data td .btn{white-space:nowrap}
table.data tr:last-child td{border-bottom:0}
table.data tbody tr:hover{background:var(--panel)}
.trunc{display:block;max-width:260px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.toolbar{display:flex;gap:12px;flex-wrap:wrap;align-items:center;margin-bottom:14px}
.toolbar form{display:flex;gap:8px;flex:1;min-width:220px}
.toolbar input{margin:0}
.tabs{display:flex;gap:6px;flex-wrap:wrap}
.tabs a{padding:6px 14px;border-radius:999px;border:1px solid var(--line);background:var(--surface);color:var(--text);text-decoration:none;font-size:var(--fs-base);min-height:44px;display:inline-flex;align-items:center}
.tabs a[aria-current=true]{background:var(--accent-bg);color:var(--accent-ink);border-color:var(--accent);font-weight:700}
.pager{display:flex;gap:12px;align-items:center;justify-content:flex-end;margin-top:14px}

/* steps */
.steps{list-style:none;counter-reset:s;display:flex;gap:10px;flex-wrap:wrap;margin:12px 0 0;padding:0}
.steps li{counter-increment:s;display:flex;align-items:center;gap:8px;font-size:var(--fs-base);background:var(--surface);border:1px solid var(--line);border-radius:999px;padding:4px 14px 4px 6px}
.steps li::before{content:counter(s);width:24px;height:24px;border-radius:50%;background:var(--navy);color:var(--on-accent);display:grid;place-items:center;font-size:var(--fs-xs);font-weight:700}
.welcome{background:var(--accent-bg);border-color:var(--info-line);box-shadow:none}

/* findings */
.verdict{display:flex;gap:14px;align-items:flex-start}
.verdict .ic{margin-top:3px}
.verdict.ok{color:var(--ok)}.verdict.warn{color:var(--warn)}.verdict.bad{color:var(--bad)}
.verdict h2{font-size:var(--fs-xl);color:inherit}
.verdict p{color:var(--text);margin:4px 0 0}
.finding{border:1px solid var(--line);border-radius:var(--r);padding:12px 14px;margin-bottom:12px;background:var(--surface)}
.finding.bad{border-color:var(--bad-line)}.finding.warn{border-color:var(--warn-line)}.finding.ok{border-color:var(--ok-line)}
.finding-top{display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin-bottom:6px}
.finding dl{display:grid;grid-template-columns:110px minmax(0,1fr);gap:4px 12px;margin:8px 0 0;font-size:var(--fs-base)}
.finding dt{color:var(--text-2)}.finding dd{margin:0;overflow-wrap:anywhere}
.sec-title{font-size:var(--fs-sm);text-transform:uppercase;letter-spacing:.05em;color:var(--text-2);font-weight:600;margin:20px 0 10px}
.sec-title:first-child{margin-top:0}
.kv{display:grid;grid-template-columns:150px minmax(0,1fr);gap:8px 14px;margin:0;font-size:var(--fs-base)}
.kv dt{color:var(--text-2)}.kv dd{margin:0;overflow-wrap:anywhere}
.tr-row{display:grid;grid-template-columns:54px minmax(0,1fr) auto;gap:12px;padding:10px 0;border-bottom:1px solid var(--line-2);font-size:var(--fs-md);line-height:1.7}
.tr-row:last-child{border-bottom:0}
.tr-row time{color:var(--text-2);font-variant-numeric:tabular-nums;font-size:var(--fs-sm);padding-top:2px}
.tr-row.low{background:var(--warn-bg);margin:0 -10px;padding-left:10px;padding-right:10px}
.timeline{list-style:none;margin:0;padding:0}
.timeline li{display:grid;grid-template-columns:150px minmax(0,1fr);gap:12px;padding:10px 0;border-bottom:1px solid var(--line-2);font-size:var(--fs-base)}
.timeline li:last-child{border-bottom:0}
.timeline .when{color:var(--text-2);font-size:var(--fs-sm)}
.dropzone{border:2px dashed var(--field-line);border-radius:var(--r);padding:28px 16px;text-align:center;background:var(--panel);margin-bottom:16px;cursor:pointer}
.dropzone:focus-within{outline:3px solid var(--focus);outline-offset:2px}
.dropzone.over{border-color:var(--link);background:var(--accent-bg)}
.dropzone .ic{color:var(--link)}
.dropzone p{margin:6px 0}
.dropzone input{position:absolute;opacity:0;width:1px;height:1px;min-height:0;margin:0}
.picked{display:none;align-items:center;gap:10px;padding:10px 12px;border:1px solid var(--line);border-radius:var(--rad-sm);margin-bottom:16px;background:var(--surface)}
.picked.on{display:flex}.picked b{overflow-wrap:anywhere}
.picked .sp{flex:1}
.method{display:flex;gap:8px;margin-bottom:18px}
.method [role=tab]{background:var(--surface);color:var(--text);border:1px solid var(--field-line)}
.method [role=tab][aria-selected=true]{background:var(--accent-bg);color:var(--accent-ink);border-color:var(--accent)}

/* dialog + toast */
dialog.dlg{border:0;border-radius:var(--rad-lg);padding:0;width:min(480px,calc(100vw - 32px));box-shadow:var(--sh-pop)}
dialog.dlg::backdrop{background:var(--scrim)}
dialog.dlg form{padding:22px}
dialog.dlg h2{margin-bottom:8px;font-size:var(--fs-xl)}
.dlg-actions{display:flex;justify-content:flex-end;gap:10px;margin-top:6px;flex-wrap:wrap}
#toasts{position:fixed;right:16px;bottom:16px;display:flex;flex-direction:column;gap:8px;z-index:60}
.toast{background:var(--navy);color:var(--on-accent);padding:12px 16px;border-radius:var(--r);box-shadow:var(--sh-toast);max-width:340px;font-size:var(--fs-base)}

/* landing */
.land{max-width:1180px;margin:0 auto;padding:40px 24px 56px}
body:has(.land){background:radial-gradient(1000px 520px at 8% -10%,var(--accent-bg) 0%,transparent 60%),radial-gradient(800px 420px at 100% 0%,var(--info-wash) 0%,transparent 55%),var(--bg);background-attachment:fixed}
.land-brand{display:flex;align-items:center;gap:10px;font-weight:700;font-size:var(--fs-xl);margin-bottom:28px;color:var(--text);letter-spacing:-.02em}
.land-brand .logo{width:38px;height:38px;border-radius:var(--rad-lg);background:linear-gradient(145deg,var(--navy),var(--accent));display:grid;place-items:center;color:var(--on-accent);box-shadow:var(--sh-logo)}
.land-top{display:grid;grid-template-columns:minmax(0,1.1fr) minmax(0,1fr);gap:32px;align-items:center;margin-bottom:28px}
.land-hero{max-width:62ch}
.sample{background:var(--surface);border:1px solid var(--line);border-radius:var(--r);padding:18px 20px;box-shadow:var(--sh)}
.sample-tag{margin:0 0 8px;font-size:var(--fs-xs);font-weight:600;color:var(--text-2)}
.sample-copy{margin:0 0 14px;font-size:var(--fs-md)}
.sample-copy mark{background:var(--bad-bg);color:var(--bad);padding:0 3px;border-radius:var(--rad-xs)}
.sample-result{border-top:1px solid var(--line-2);padding-top:12px;margin-bottom:10px}
.sample-result dl{display:grid;grid-template-columns:110px minmax(0,1fr);gap:4px 12px;margin:10px 0 0;font-size:var(--fs-base)}
.sample-result dt{color:var(--text-2)}.sample-result dd{margin:0}
.sample-foot{margin:0;font-size:var(--fs-sm);color:var(--text-2)}
.role-card h2{display:flex;align-items:center;gap:10px}
.role-card h2 .ic{color:var(--accent-ink);vertical-align:0}
.land-hero h1{font-size:var(--fs-hero);letter-spacing:-.025em;margin-bottom:10px}
.land-hero .page-desc{font-size:var(--fs-lg);line-height:1.6}
.role-card{display:flex;flex-direction:column;gap:10px;transition:border-color .15s,box-shadow .15s;min-height:100%}
.role-card:hover{border-color:var(--line-strong);box-shadow:var(--sh-lift-lg)}
.role-card .ic-lg{width:44px;height:44px;border-radius:var(--rad-lg);background:var(--accent-bg);color:var(--accent-ink);display:grid;place-items:center}
.role-card .btn{margin-top:auto;align-self:flex-start}
.feature-pills{display:flex;flex-wrap:wrap;gap:8px;margin:14px 0 0}
.feature-pills span{display:inline-flex;align-items:center;gap:6px;padding:6px 12px;border-radius:999px;background:var(--surface);border:1px solid var(--line);font-size:var(--fs-sm);font-weight:600;color:var(--text-2)}

/* Brand Risk Radar */
.radar-wrap{display:flex;flex-direction:column;gap:16px}
.radar-score{display:flex;gap:14px;align-items:center}
.radar-num{font-size:var(--fs-3xl);font-weight:750;min-width:64px;min-height:64px;border-radius:var(--rad-xl);display:grid;place-items:center;padding:0 10px}
.radar-grid{display:grid;grid-template-columns:minmax(240px,340px) minmax(0,1fr);gap:18px;align-items:start}
.radar-svg{display:block;max-width:100%;height:auto;background:linear-gradient(180deg,var(--panel-2),var(--surface));border:1px solid var(--line);border-radius:var(--rad-lg)}
.radar-low{--band:var(--ok)}.radar-med{--band:var(--warn)}.radar-high,.radar-crit{--band:var(--bad)}
.radar-data{fill:var(--band);fill-opacity:.2;stroke:var(--band);stroke-width:2.5}.radar-crit .radar-data{fill-opacity:.33}.radar-dot{fill:var(--band)}
.radar-ring{fill:none;stroke:var(--line-strong);stroke-width:1}
.radar-axis{stroke:var(--line-strong);stroke-width:1}
.radar-label{font-size:var(--fs-xs);fill:var(--text-2);font-family:var(--font)}
.radar-dims{display:flex;flex-direction:column;gap:6px}
.radar-dim{border:1px solid var(--line);border-radius:var(--r);background:var(--surface);padding:0}
.radar-dim summary{display:flex;gap:8px;align-items:center;flex-wrap:wrap;cursor:pointer;padding:10px 12px;list-style:none;font-size:var(--fs-base)}
.radar-dim summary::-webkit-details-marker{display:none}
.radar-dim[open] summary{border-bottom:1px solid var(--line-2)}
.radar-cites{margin:0;padding:8px 12px 12px 28px;font-size:var(--fs-sm)}
.radar-cites li{margin:4px 0}

/* Claim → fact graph */
.claim-graph{display:flex;flex-direction:column;gap:10px}
.claim-edge{display:grid;grid-template-columns:minmax(0,1.1fr) 28px minmax(0,1.1fr) minmax(120px,.8fr);gap:10px;align-items:center;padding:12px;border:1px solid var(--line);border-radius:var(--r);background:var(--surface)}
.claim-edge.ok{border-color:var(--ok-line)}.claim-edge.bad{border-color:var(--bad-line)}.claim-edge.warn{border-color:var(--warn-line)}
.claim-node{min-width:0}.claim-node b{display:block;overflow-wrap:anywhere;font-size:var(--fs-base)}
.claim-arrow{display:grid;place-items:center;color:var(--text-2)}
.claim-meta{display:flex;flex-direction:column;gap:4px;align-items:flex-start}

/* Guideline health */
.health-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px}
.health-card{border:1px solid var(--line);border-radius:var(--rad-lg);padding:14px 16px;background:var(--surface)}
.health-card.warn{border-color:var(--warn-line);background:var(--surface)af0}
.health-card.info{border-color:var(--info-line);background:var(--info-wash)}
.health-card.ok{border-color:var(--ok-line)}
.health-top{display:flex;gap:8px;align-items:center;flex-wrap:wrap}

/* Counterfactual rewrite variants */
.rewrite-box{border:1px dashed var(--line-strong);border-radius:var(--r);padding:10px 12px;background:var(--panel);margin-top:6px}
.rewrite-variants{display:flex;flex-direction:column;gap:8px;margin-top:8px}
.rewrite-var{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:10px;align-items:start;padding:10px;border:1px solid var(--line);border-radius:var(--r);background:var(--surface)}
.rewrite-var .strat{font-size:var(--fs-xs);font-weight:700;text-transform:uppercase;letter-spacing:.04em;color:var(--accent-ink)}
.side-by-side{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-top:8px}
.side-by-side .pane{padding:10px 12px;border-radius:var(--r);border:1px solid var(--line);background:var(--surface);font-size:var(--fs-base)}
.side-by-side .pane.orig{background:var(--bad-bg);border-color:var(--bad-line)}
.side-by-side .pane.fix{background:var(--ok-bg);border-color:var(--ok-line)}
.side-by-side .lbl{font-size:var(--fs-xs);font-weight:700;text-transform:uppercase;letter-spacing:.05em;color:var(--text-2);margin-bottom:4px}

/* Submit method icons */
.method{gap:10px}
.method [role=tab]{gap:8px}

/* Finding polish */
.approval-record{margin-top:16px;border:1px solid var(--ok-line);border-radius:var(--r);background:var(--ok-wash);padding:12px 16px}
.rec-title{margin:0 0 6px;display:flex;align-items:center;gap:8px;font-weight:650;color:var(--ok)}
.approval-record dl{margin:0}
.rec-row{display:grid;grid-template-columns:180px minmax(0,1fr);gap:12px;padding:8px 0;border-top:1px solid var(--line-2)}
.rec-row dt{color:var(--text-2);font-size:var(--fs-sm)}
.rec-row dd{margin:0;overflow-wrap:anywhere}
.rec-id{font-family:Consolas,"SFMono-Regular",monospace;font-size:var(--fs-lg);font-weight:700;letter-spacing:.02em}
.evidence summary{cursor:pointer;display:flex;flex-direction:column;gap:2px;min-height:44px;justify-content:center;list-style:none;background:var(--surface);border:1px solid var(--line);border-radius:var(--r);padding:12px 20px;box-shadow:var(--sh)}
.evidence summary::-webkit-details-marker{display:none}
.evidence-title{font-size:var(--fs-lg);font-weight:600;line-height:1.3}
.evidence summary .evidence-title::before{content:"";display:inline-block;width:7px;height:7px;margin-right:10px;border-right:2px solid var(--text-2);border-bottom:2px solid var(--text-2);transform:rotate(-45deg);transition:transform .15s}
.evidence[open] summary .evidence-title::before{transform:rotate(45deg)}
.evidence-body{margin-top:16px}
.finding{transition:box-shadow .15s}
.finding:hover{box-shadow:var(--sh-lift)}
.finding-top .chip{flex:none}


.sample-stage{position:relative;padding:22px}
.sample-stage::before{content:"";position:absolute;inset:0;background:var(--accent-grad);border-radius:var(--rad-xl);box-shadow:var(--sh-lift-lg)}
.sample-stage .sample{position:relative}
.sample-stage .sample{box-shadow:var(--sh-stage);border-color:transparent}
.land-hero h1{font-weight:800;letter-spacing:-.03em;line-height:1.08}
.land-hero .page-desc{color:var(--text-2)}
.role-card{border-radius:var(--rad-xl)}.role-card:hover{border-color:var(--info-line)}
.btn,button{font-weight:700}
/* bento grid, charts */
.bento{display:grid;grid-template-columns:repeat(12,minmax(0,1fr));gap:16px;align-items:stretch}
.bento>*{min-width:0}.span-12{grid-column:span 12}.span-8{grid-column:span 8}.span-6{grid-column:span 6}.span-4{grid-column:span 4}
.donut-wrap{display:flex;align-items:center;gap:22px;flex-wrap:wrap}
.donut{position:relative;width:148px;height:148px;flex:none}
.donut svg{width:100%;height:100%;transform:rotate(-90deg)}
.donut .track{fill:none;stroke:var(--line-2);stroke-width:5}
.donut .seg{fill:none;stroke-width:5;stroke-linecap:butt}
.donut-center{position:absolute;inset:0;display:flex;flex-direction:column;align-items:center;justify-content:center;text-align:center}
.donut-center b{font-size:var(--fs-3xl);font-weight:800;line-height:1.1;letter-spacing:-.02em;font-variant-numeric:tabular-nums}
.donut-center span{font-size:var(--fs-xs);color:var(--text-2)}
.legend{list-style:none;margin:0;padding:0;display:grid;gap:8px;flex:1;min-width:150px}
.legend li{display:flex;align-items:center;gap:10px;font-size:var(--fs-base)}
.legend .lv{margin-left:auto;font-weight:700;font-variant-numeric:tabular-nums}
.legend .lp{color:var(--text-2);font-size:var(--fs-xs);min-width:38px;text-align:right}
.dot{width:10px;height:10px;border-radius:50%;flex:none}
.c-ok{background:var(--d-ok);stroke:var(--d-ok)}.c-warn{background:var(--d-warn);stroke:var(--d-warn)}.c-bad{background:var(--d-bad);stroke:var(--d-bad)}
.c-neutral{background:var(--d-neutral);stroke:var(--d-neutral)}.c-d1{background:var(--d1);stroke:var(--d1)}.c-d2{background:var(--d2);stroke:var(--d2)}.c-d3{background:var(--d3);stroke:var(--d3)}
.hbars{list-style:none;margin:0;padding:0;display:grid;gap:14px}
.hbars .hb-top{display:flex;justify-content:space-between;gap:12px;font-size:var(--fs-base);margin-bottom:6px}
.hbars .hb-top b{font-variant-numeric:tabular-nums}
.hb-track{height:8px;border-radius:999px;background:var(--line-2);overflow:hidden}
.hb-fill{display:block;height:100%;width:calc(var(--v) * 1%);border-radius:999px;background:linear-gradient(90deg,var(--d3),var(--d1))}
.vbars{display:flex;align-items:flex-end;gap:10px;height:150px;padding-top:8px}
.vb{flex:1;display:flex;flex-direction:column;align-items:center;justify-content:flex-end;gap:6px;height:100%;min-width:0}
.vb-bar{display:block;width:100%;max-width:34px;height:calc(var(--v) * 1%);min-height:4px;border-radius:var(--rad-xs) var(--rad-xs) 4px 4px;background:var(--line-strong)}
.vb.on .vb-bar{background:linear-gradient(180deg,var(--d3),var(--d1))}
.vb-n{font-size:var(--fs-xs);font-weight:700;font-variant-numeric:tabular-nums}
.vb-l{font-size:var(--fs-xs);color:var(--text-2)}
.chart-empty{color:var(--text-2);font-size:var(--fs-base);margin:0}
@media (max-width:1100px){.span-8,.span-6,.span-4{grid-column:span 12}.stats{grid-template-columns:repeat(2,minmax(0,1fr))}.cols{grid-template-columns:minmax(0,1fr)}.cols-3,.cols-2{grid-template-columns:minmax(0,1fr)}}
@media (max-width:900px){
  .land-top{grid-template-columns:minmax(0,1fr)}
  .btn.sm,.tabs a,.company-switch select,.side-foot a,.navgroup>summary,.demo-switch>summary{min-height:44px}
  .shell{grid-template-columns:minmax(0,1fr)}
  .side{position:fixed;left:0;top:0;bottom:0;width:272px;z-index:50;transform:translateX(-100%);transition:transform .2s}
  .side.open{transform:none}
  .scrim.on{display:block;position:fixed;inset:0;background:var(--scrim);z-index:40}
  .menu-btn{display:grid}
  .top{padding:0 16px}main{padding:20px 16px}
  .grid-2,.field-grid{grid-template-columns:minmax(0,1fr)}
  .who .name{display:none}
  .radar-grid,.health-grid,.side-by-side,.claim-edge{grid-template-columns:minmax(0,1fr)}
  .claim-arrow{display:none}
}
@media (max-width:640px){
  h1{font-size:var(--fs-2xl)}
  .stats{grid-template-columns:minmax(0,1fr)}
  .card{padding:16px}
  table.data thead{position:absolute;left:-9999px}
  table.data,table.data tbody,table.data tr,table.data td{display:block;width:100%}
  table.data tr{padding:10px 14px;border-bottom:1px solid var(--line)}
  table.data td{border:0;padding:4px 0;display:grid;grid-template-columns:104px minmax(0,1fr);gap:8px}
  table.data td::before{content:attr(data-label);color:var(--text-2);font-size:var(--fs-xs);font-weight:600}
  .trunc{max-width:none;white-space:normal}
  table.data td .chip{white-space:normal}
  .finding dl,.kv,.timeline li,.rec-row{grid-template-columns:minmax(0,1fr)}
  .tr-row{grid-template-columns:44px minmax(0,1fr)}.tr-row .conf{grid-column:2}
  .company-switch span{display:none}
  .who .role{display:none}
}
@media (pointer:coarse){.btn.sm,.tabs a,.company-switch select,.side-foot a,.navgroup>summary,.demo-switch>summary,.evidence summary{min-height:44px}}
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
  // guided tour: points at each menu item and says what it is for (starts once for a new user, and from "Take the tour")
  (function(){
    var cfg=$('#tour-data');if(!cfg)return;
    var steps=JSON.parse(cfg.textContent||'[]'),key='bg_tour_done_'+cfg.getAttribute('data-user'),i=0,ring,pop,opener;
    function store(){try{localStorage.setItem(key,'1')}catch(e){}}
    function seen(){try{return localStorage.getItem(key)==='1'}catch(e){return true}}
    function close(){if(ring)ring.remove();if(pop)pop.remove();ring=pop=null;store();document.removeEventListener('keydown',onKey);if(opener&&opener.focus&&document.contains(opener))opener.focus();opener=null}
    function onKey(ev){if(ev.key==='Tab'&&pop){var f=pop.querySelectorAll('button');if(f.length){var a=f[0],z=f[f.length-1];if(ev.shiftKey&&document.activeElement===a){ev.preventDefault();z.focus()}else if(!ev.shiftKey&&document.activeElement===z){ev.preventDefault();a.focus()}else if(!pop.contains(document.activeElement)){ev.preventDefault();a.focus()}}}if(ev.key==='Escape')close();if(ev.key==='ArrowRight')go(i+1);if(ev.key==='ArrowLeft'&&i>0)go(i-1)}
    function go(n){
      if(n>=steps.length){close();return}
      i=n;var s=steps[i],el=s.href?$('#side nav a[href="'+s.href+'"]'):null;
      if(el){var grp=el.closest('details');if(grp)grp.open=true}
      var small=window.matchMedia('(max-width:900px)').matches;
      if(el&&small&&typeof nav==='function'&&!side.classList.contains('open')){nav(true);setTimeout(function(){go(n)},320);return}
      if(!ring){ring=document.createElement('div');ring.className='tour-ring';document.body.appendChild(ring)}
      if(!pop){opener=document.activeElement;pop=document.createElement('div');pop.className='tour-pop';pop.setAttribute('role','dialog');pop.setAttribute('aria-modal','true');
        pop.setAttribute('aria-labelledby','tour-t');document.body.appendChild(pop);document.addEventListener('keydown',onKey)}
      pop.innerHTML='<h3 id="tour-t"></h3><p></p><div class="tour-row"><span class="tour-n"></span>'
        +(i>0?'<button type="button" class="btn secondary sm" data-t="back">Back</button>':'<button type="button" class="btn secondary sm" data-t="skip">Skip</button>')
        +'<button type="button" class="btn sm" data-t="next">'+(i===steps.length-1?'Finish':'Next')+'</button></div>';
      pop.querySelector('h3').textContent=s.title;pop.querySelector('p').textContent=s.text;
      pop.querySelector('.tour-n').textContent=(i+1)+' of '+steps.length;
      pop.querySelector('[data-t=next]').onclick=function(){go(i+1)};
      var b=pop.querySelector('[data-t=back]');if(b)b.onclick=function(){go(i-1)};
      var k=pop.querySelector('[data-t=skip]');if(k)k.onclick=close;
      place(el);
      if(small&&el)setTimeout(function(){if(pop)place(el)},380);   // the menu slides in on phones: measure again when it has stopped
      pop.querySelector('[data-t=next]').focus();
    }
    function place(el){
      if(el){
        el.scrollIntoView({block:'nearest'});
        var r=el.getBoundingClientRect();
        ring.style.display='block';ring.style.left=(r.left-4)+'px';ring.style.top=(r.top-4)+'px';ring.style.width=(r.width+8)+'px';ring.style.height=(r.height+8)+'px';
        pop.classList.remove('center');
        var left=r.right+16,top=Math.max(12,Math.min(r.top-10,window.innerHeight-pop.offsetHeight-12));
        if(left+pop.offsetWidth>window.innerWidth-8){
          left=Math.max(8,(window.innerWidth-pop.offsetWidth)/2);pop.classList.add('center');
          top=(r.bottom+12+pop.offsetHeight<window.innerHeight)?r.bottom+12:Math.max(8,r.top-pop.offsetHeight-12)}
        pop.style.left=left+'px';pop.style.top=top+'px';
      }else{
        ring.style.display='none';pop.classList.add('center');
        pop.style.left=Math.max(8,(window.innerWidth-pop.offsetWidth)/2)+'px';pop.style.top=Math.max(12,(window.innerHeight-pop.offsetHeight)/2)+'px';
      }
    }
    $$('[data-tour-start]').forEach(function(b){b.addEventListener('click',function(){if(ring||pop)close();go(0)})});
    if(cfg.getAttribute('data-auto')==='1'&&!seen())setTimeout(function(){go(0)},400);
    window.addEventListener('resize',function(){if(pop)go(i)});
  })();
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
  // theme: auto (follow the system), light or dark; remembered in this browser only
  (function(){var b=$('[data-theme-toggle]');if(!b)return;
    function cur(){try{return localStorage.getItem('bg_theme')||'auto'}catch(e){return 'auto'}}
    function apply(t){var r=document.documentElement;if(t==='auto')r.removeAttribute('data-theme');else r.setAttribute('data-theme',t);b.querySelector('.theme-label').textContent='Theme: '+t.charAt(0).toUpperCase()+t.slice(1)}
    apply(cur());
    b.addEventListener('click',function(){var n={auto:'light',light:'dark',dark:'auto'}[cur()];try{localStorage.setItem('bg_theme',n)}catch(e){}apply(n)})})();
  // single-key shortcuts: active only while focus is inside an element marked data-keyscope (WCAG 2.1.4), never while typing
  document.addEventListener('keydown',function(ev){
    if(ev.ctrlKey||ev.metaKey||ev.altKey||ev.key.length!==1)return;
    var t=ev.target,tag=t&&t.tagName;
    if(!t||!t.closest||!t.closest('[data-keyscope]'))return;
    if(tag==='INPUT'||tag==='TEXTAREA'||tag==='SELECT'||t.isContentEditable||document.querySelector('dialog[open]'))return;
    var el=document.querySelector('[data-key="'+ev.key.toLowerCase()+'"]');
    if(el){ev.preventDefault();el.click()}
  });
  $$('select[data-autosubmit]').forEach(function(s){s.addEventListener('change',function(){s.form.submit()})});
})();
"""

_LOGO = ('<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" '
         'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' + _ICONS["shield"] +
         '<path d="m9 12 2 2 4-4"/></svg>')

import hashlib as _hashlib

# CSS and JS are served once from /assets and cached by the browser, not repeated inside every page.
ASSET_VER = _hashlib.sha1((CSS + JS).encode("utf-8")).hexdigest()[:10]
_FONT_URL = ("https://fonts.googleapis.com/css2?family=Manrope:wght@400;500;600;700;800"
             "&family=Noto+Sans+Devanagari:wght@400;600&display=swap")
_HEAD = ("<!doctype html><html lang='en'><head><meta charset='utf-8'>"
         "<script>try{var t=localStorage.getItem('bg_theme');if(t==='light'||t==='dark')document.documentElement.setAttribute('data-theme',t)}catch(e){}</script>"
         "<meta name='viewport' content='width=device-width,initial-scale=1'>"
         "<link rel='preconnect' href='https://fonts.googleapis.com'>"
         "<link rel='preconnect' href='https://fonts.gstatic.com' crossorigin>"
         # the font stylesheet loads without blocking first paint; system fonts show until it arrives
         f"<link rel='stylesheet' href='{_FONT_URL}' media='print' onload=\"this.media='all'\">"
         f"<noscript><link rel='stylesheet' href='{_FONT_URL}'></noscript>"
         f"<link rel='stylesheet' href='/assets/app.css?v={ASSET_VER}'>")
_TAIL_JS = f"<script src='/assets/app.js?v={ASSET_VER}' defer></script>"


def landing(body):
    return (_HEAD + "<title>BrandGuard</title></head><body>"
            f'<a class="skip" href="#main">Skip to content</a>'
            f'<div class="land"><div class="land-brand"><span class="logo">{_LOGO}</span>BrandGuard</div>'
            f'<main id="main" style="padding:0">{body}</main></div>'
            f'<div id="toasts" role="status" aria-live="polite"></div>{_TAIL_JS}</body></html>')


GENERAL_LABELS = {"facts": "Products and Facts", "access": "Product Access"}


def tour_steps(is_admin, general):
    """What each menu item is for, in the order the tour shows them."""
    thing, things = ("product", "products") if general else ("project", "projects")
    if is_admin:
        return [
            {"title": "Welcome to BrandGuard", "text": "A short tour of where everything is. It takes a minute. You can replay it any time from \"Take the tour\" at the bottom of the menu.", "href": ""},
            {"title": "Overview", "text": "Your daily view: what waits for a decision, a setup checklist, and recent activity.", "href": "/"},
            {"title": "Brand Rules", "text": "Banned phrases, confidential terms, wording and tone rules, industry starter packs, brand colours and your logo.", "href": "/admin/rules"},
            {"title": ("Products" if general else "Projects") + " and Facts", "text": f"The approved prices and facts every claim is checked against. Add {things} by hand, import a spreadsheet or brochure, or load sample data.", "href": "/admin/projects"},
            {"title": "Team and Invites", "text": "Invite channel partners, freelancers, agencies and managers. Each invite is a one-time link.", "href": "/admin/team"},
            {"title": ("Product" if general else "Project") + " Access", "text": f"Choose which {things} each partner may promote. A partner can only submit for {things} they have access to.", "href": "/admin/access"},
            {"title": "Review Queue", "text": "Content BrandGuard was not sure about, and disputes. You approve or reject here, with a reason.", "href": "/queue"},
            {"title": "Disputes", "text": "When a creator disagrees with a rejection, you decide. Your decisions on wording become lessons.", "href": "/disputes"},
            {"title": "Lessons", "text": "What BrandGuard learned from your dispute decisions. You can switch any lesson off. Prices are never learned.", "href": "/admin/learned"},
            {"title": "Approval Records and Audit Trail", "text": "Every approval, rejection and rule change is recorded with who, when and why.", "href": "/approvals"},
        ]
    return [
        {"title": "Welcome to BrandGuard", "text": "Check your content before it goes live. Here is where everything is. Replay this any time from \"Take the tour\" at the bottom of the menu.", "href": ""},
        {"title": "My Dashboard", "text": "Your results at a glance: approved, rejected and waiting for a person.", "href": "/"},
        {"title": "Submit Content", "text": f"Upload a video, poster, image or document, or paste a link. BrandGuard finds the {thing} and checks every claim.", "href": "/submit"},
        {"title": "Bulk Upload", "text": "Send several files at once. They are reviewed one by one in the background, and you can leave the page.", "href": "/bulk"},
        {"title": "My Submissions", "text": "Every result with its reasons: what was checked, what matched, and what to fix.", "href": "/reviews"},
        {"title": "Disputes", "text": "If you think a rejection is wrong, dispute it with a note. A person at the company decides.", "href": "/disputes"},
        {"title": "Verify a File", "text": "Check that a file is exactly the one that was approved, before you post it.", "href": "/verify"},
        {"title": "Help and Guidelines", "text": "What each result means and what BrandGuard checks.", "href": "/help"},
    ]


def shell(title, body, user, role_label, active="", crumbs=None, queue_count=0,
          company=None, flash="", demo_users=(), general=False):
    """company = (current_id, [(id, name), ...]) for submitters; None otherwise.
    general = the company is not a property company, so it sells products, not projects."""
    is_admin = user["role"] == "admin"
    items = NAV_ADMIN if is_admin else NAV_SUB
    link_by_key = {}
    for key, href, label, ic in items:
        if general:
            label = GENERAL_LABELS.get(key, label)
        cur = ' aria-current="page"' if key == active else ""
        cnt = f'<span class="count" aria-label="{queue_count} waiting">{queue_count}</span>' if key == "queue" and queue_count else ""
        link_by_key[key] = f'<a href="{href}"{cur}>{icon(ic)}<span>{e(label)}</span>{cnt}</a>'
    if is_admin:
        links = []
        for gname, keys in NAV_ADMIN_GROUPS:
            inner = "".join(link_by_key[k] for k in keys if k in link_by_key)
            if not gname:
                links.append(inner)
            else:
                op = " open" if gname == "Work" or active in keys else ""
                links.append(f'<details class="navgroup"{op}><summary>{e(gname)}</summary>{inner}</details>')
        foot_extra = link_by_key.get("testaudio", "")
    else:
        links = [v for k, v in link_by_key.items() if k != "testaudio"]
        foot_extra = link_by_key.get("testaudio", "")

    demo = "".join(
        f'<a href="/enter/{k}"{" class=cur" if current else ""}>{icon("users", 16)}{e(lbl)}</a>'
        for k, lbl, current in demo_users)
    if demo:
        demo = f'<details class="demo-switch" open><summary>Switch demo role</summary>{demo}</details>'

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
    import json as _json
    tour = (f'<script type="application/json" id="tour-data" data-user="{e(str(user["id"]))}" data-auto="1">'
            + _json.dumps(tour_steps(is_admin, general)).replace("</", "<\\/") + '</script>')
    return (_HEAD + f"<title>{e(title)} - BrandGuard</title></head><body>"
            '<a class="skip" href="#main">Skip to content</a>'
            '<div class="shell">'
            f'<aside class="side" id="side"><a class="brand" href="/"><span class="logo">{_LOGO}</span>BrandGuard</a>'
            f'<nav aria-label="Main">{"".join(links)}</nav>'
            f'<div class="side-foot">{demo}'
            f'<a href="/account">{icon("users", 16)}My account</a>{foot_extra}'
            f'<button type="button" class="tour-start" data-tour-start>{icon("help", 16)}Take the tour</button>'
            f'<button type="button" class="tour-start" data-theme-toggle>{icon("sun", 16)}<span class="theme-label">Theme: Auto</span></button>'
            f'<a href="/logout">{icon("log-out", 16)}Log out</a></div></aside>'
            '<div class="scrim" id="scrim"></div>'
            '<div class="main-col"><header class="top">'
            f'<button class="menu-btn" id="menu-btn" aria-label="Open navigation" aria-controls="side" aria-expanded="false" type="button" style="padding:0">{icon("menu", 22)}</button>'
            f'{crumbs_html}<span class="sp"></span>{comp}'
            f'<div class="who"><span class="name">{e(user["name"])}</span><span class="role">{e(role_label)}</span></div>'
            '</header>'
            f'<main id="main">{body}</main></div></div>'
            f'<div id="toasts" role="status" aria-live="polite"></div>{toast}{tour}{_TAIL_JS}</body></html>')