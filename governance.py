"""Advanced brand-governance surfaces: risk radar, claim provenance, guideline health.

Pure helpers: take a report / submission rows, return dicts + HTML snippets.
No database access. Offline-safe — no paid APIs.
"""

from __future__ import annotations

import html
import math
from collections import Counter

e = html.escape

# Finding types → risk radar dimensions (0–100 lower is safer; we invert for display score).
_DIM_MAP = {
    "claims": {"UNSUPPORTED_CLAIM", "BANNED_PHRASE", "BANNED_PHRASE_LIKELY", "BANNED_PARAPHRASE",
               "AI_ADVICE", "OFFER_CHECK"},
    "tone": {"TONE", "AI_TONE", "TERMINOLOGY", "AI_TERMINOLOGY", "AI_CLARITY"},
    "facts": {"PRICE_MISMATCH", "PRICE_UNIT_CHECK", "PRICE_LOW_CONFIDENCE", "PRICE_NOT_IN_REGISTRY",
              "AREA_CHECK", "BATHROOMS_CHECK", "POSSESSION_CHECK", "RERA_CHECK", "BOOKING_CHECK",
              "DISTANCE_CHECK", "CUSTOM_CHECK", "VOICE_SCREEN_MISMATCH"},
    "visual": {"OFF_PALETTE", "LOGO_MISSING", "NO_TEXT_FOUND", "OFF_BRAND_COLOR",
               "LOGO_MENTION_MISSING", "VISUAL_DONT", "FONT_OFF_BRAND"},
    "a11y": {"LOW_CONTRAST", "SMALL_TEXT", "ALL_CAPS", "WALL_OF_TEXT",
             "COLOR_ONLY_CUE", "UNCLEAR_CTA", "MISSING_ALT"},
    "confidentiality": {"CONFIDENTIAL_DATA", "CONFIDENTIAL_LIKELY"},
}

_DIM_LABEL = {
    "claims": "Claims",
    "tone": "Tone",
    "facts": "Facts",
    "visual": "Visual",
    "a11y": "Accessibility",
    "confidentiality": "Confidentiality",
}

_DIM_ICON = {
    "claims": "megaphone",
    "tone": "message",
    "facts": "tag",
    "visual": "image",
    "a11y": "eye",
    "confidentiality": "lock",
}

_SEV_W = {"CRITICAL": 40, "HIGH": 28, "MEDIUM": 16, "LOW": 8}


def _severity_weight(f):
    return _SEV_W.get(str(f.get("severity") or "LOW").upper(), 8)


def compute_risk(rep):
    """Return Brand Risk Radar: overall 0–100 (higher = more risk) + per-dimension breakdown."""
    findings = [f for f in (rep or {}).get("findings", []) if not f.get("dismissed")]
    dims = {}
    for key, types in _DIM_MAP.items():
        hits = [f for f in findings if f.get("type") in types]
        raw = min(100, sum(_severity_weight(f) for f in hits))
        # Supervision-only softens slightly vs hard FLAG
        soft = sum(1 for f in hits if f.get("status") == "SUPERVISION")
        if soft and not any(f.get("status") == "FLAG" for f in hits):
            raw = max(0, raw - 6)
        cites = [{
            "type": f.get("type"),
            "evidence": str(f.get("evidence") or "")[:120],
            "severity": f.get("severity"),
            "status": f.get("status"),
            "why": str(f.get("explanation") or "")[:160],
        } for f in hits[:5]]
        dims[key] = {
            "score": raw,
            "label": _DIM_LABEL[key],
            "icon": _DIM_ICON[key],
            "count": len(hits),
            "cites": cites,
        }

    # Overall: max of weighted blend and “hottest” dimension — so a single critical
    # claims/confidential hit still shows a dramatic pre-flight score for demos.
    weights = {"claims": 1.3, "tone": 0.9, "facts": 1.4, "visual": 0.7, "a11y": 0.7, "confidentiality": 1.5}
    active = [k for k in dims if dims[k]["score"] > 0]
    if active:
        blend = sum(dims[k]["score"] * weights[k] for k in active) / sum(weights[k] for k in active)
        peak = max(dims[k]["score"] for k in active)
        overall = int(round(0.55 * blend + 0.45 * peak))
    else:
        overall = 0
    # Floor: any FLAG / CRITICAL confidential → visible risk band
    if any(f.get("status") == "FLAG" for f in findings):
        overall = max(overall, 42)
    if any(f.get("type") in _DIM_MAP["confidentiality"] and f.get("severity") == "CRITICAL" for f in findings):
        overall = max(overall, 78)
    band = "LOW" if overall < 25 else "MEDIUM" if overall < 50 else "HIGH" if overall < 75 else "CRITICAL"
    return {"score": overall, "band": band, "dimensions": dims}


def risk_radar_svg(risk, size=220):
    """Spider/radar chart as inline SVG. Values are risk 0–100 (outer = high risk)."""
    dims = risk.get("dimensions") or {}
    keys = ["claims", "tone", "facts", "visual", "a11y", "confidentiality"]
    n = len(keys)
    cx = cy = size / 2
    r_max = size * 0.34
    angles = [(-math.pi / 2) + (2 * math.pi * i / n) for i in range(n)]

    def pt(i, frac):
        a = angles[i]
        rr = r_max * max(0.05, min(1.0, frac))
        return cx + rr * math.cos(a), cy + rr * math.sin(a)

    # Grid rings
    rings = []
    for g in (0.25, 0.5, 0.75, 1.0):
        pts = " ".join(f"{pt(i, g)[0]:.1f},{pt(i, g)[1]:.1f}" for i in range(n))
        rings.append(f'<polygon points="{pts}" class="radar-ring"/>')

    # Axes + labels
    axes, labels = [], []
    for i, k in enumerate(keys):
        x2, y2 = pt(i, 1.0)
        axes.append(f'<line x1="{cx:.1f}" y1="{cy:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" class="radar-axis"/>')
        lx, ly = pt(i, 1.22)
        lab = _DIM_LABEL[k]
        sc = dims.get(k, {}).get("score", 0)
        labels.append(
            f'<text x="{lx:.1f}" y="{ly:.1f}" class="radar-label" text-anchor="middle" dominant-baseline="middle">'
            f'{e(lab)} · {sc}</text>')

    # Data polygon
    data_pts = " ".join(
        f"{pt(i, (dims.get(k, {}).get('score', 0) or 0) / 100.0)[0]:.1f},"
        f"{pt(i, (dims.get(k, {}).get('score', 0) or 0) / 100.0)[1]:.1f}"
        for i, k in enumerate(keys))
    band = risk.get("band", "LOW")
    fill = {"LOW": "#136c3a33", "MEDIUM": "#8a530033", "HIGH": "#a61b1b33", "CRITICAL": "#a61b1b55"}.get(band, "#1d5fd133")
    stroke = {"LOW": "#136c3a", "MEDIUM": "#8a5300", "HIGH": "#a61b1b", "CRITICAL": "#7a1010"}.get(band, "#1d5fd1")

    return (
        f'<svg class="radar-svg" viewBox="0 0 {size} {size}" width="{size}" height="{size}" '
        f'role="img" aria-label="Brand risk radar score {risk.get("score", 0)} out of 100, {band} band">'
        f'<rect width="{size}" height="{size}" fill="transparent"/>'
        + "".join(rings) + "".join(axes)
        + f'<polygon points="{data_pts}" fill="{fill}" stroke="{stroke}" stroke-width="2.5"/>'
        + "".join(
            f'<circle cx="{pt(i, (dims.get(k, {}).get("score", 0) or 0) / 100.0)[0]:.1f}" '
            f'cy="{pt(i, (dims.get(k, {}).get("score", 0) or 0) / 100.0)[1]:.1f}" r="3.5" fill="{stroke}"/>'
            for i, k in enumerate(keys))
        + "".join(labels)
        + "</svg>"
    )


def risk_radar_html(rep, icon_fn=None):
    """Full Brand Risk Radar card body HTML."""
    risk = compute_risk(rep)
    score, band = risk["score"], risk["band"]
    tone = {"LOW": "ok", "MEDIUM": "warn", "HIGH": "bad", "CRITICAL": "bad"}.get(band, "neutral")
    svg = risk_radar_svg(risk)
    dim_rows = []
    for key, d in risk["dimensions"].items():
        cites = "".join(
            f'<li><span class="mono">{e(c["evidence"] or c["type"])}</span>'
            f'<span class="muted"> — {e(c["why"] or c["type"])}</span></li>'
            for c in d["cites"]) or '<li class="muted">No findings in this dimension.</li>'
        ic = ""
        if icon_fn:
            ic = icon_fn(d["icon"], 16)
        dim_rows.append(
            f'<details class="radar-dim"><summary>{ic}<b>{e(d["label"])}</b>'
            f'<span class="chip {tone if d["score"] >= 40 else "ok" if d["score"] < 20 else "warn"}">'
            f'{d["score"]}/100</span>'
            f'<span class="muted">{d["count"]} finding(s)</span></summary>'
            f'<ul class="radar-cites">{cites}</ul></details>')
    return (
        f'<div class="radar-wrap">'
        f'<div class="radar-score">'
        f'<div class="radar-num chip {tone}" aria-label="Overall brand risk {score}">{score}</div>'
        f'<div><b>Brand Risk · {e(band)}</b>'
        f'<p class="muted" style="margin:4px 0 0">0 = publish-ready · 100 = blocked. '
        f'Each spoke cites concrete findings — not a black-box score.</p></div></div>'
        f'<div class="radar-grid">{svg}<div class="radar-dims">{"".join(dim_rows)}</div></div></div>'
    ), risk


def claim_provenance(rep):
    """Map promotional / fact claims to approved facts: matched / mismatched / unsupported."""
    nodes = []
    for c in (rep or {}).get("claims", []):
        verdict = c.get("verdict") or c.get("status") or "REVIEW"
        if verdict in ("VERIFIED", "PASS"):
            state = "matched"
        elif verdict in ("VIOLATION", "FLAG"):
            state = "mismatched"
        elif verdict in ("UNVERIFIABLE", "NA", "INCOMPLETE"):
            state = "unsupported"
        else:
            state = "review"
        nodes.append({
            "kind": c.get("kind") or "claim",
            "heard": str(c.get("heard") or c.get("said") or "")[:140],
            "official": str(c.get("official") or c.get("approved") or c.get("config") or "—")[:140],
            "project": c.get("project") or "",
            "state": state,
            "verdict": verdict,
            "reason": str(c.get("reason") or "")[:180],
            "fact_version": c.get("fact_version") or "",
            "confidence": c.get("confidence"),      # recognition confidence of what was heard or read, when known
        })
    # Also surface unsupported promotional claims from findings
    for f in (rep or {}).get("findings", []):
        if f.get("type") != "UNSUPPORTED_CLAIM":
            continue
        nodes.append({
            "kind": "promo",
            "heard": str(f.get("evidence") or "")[:140],
            "official": "(no approved fact linked)",
            "project": "",
            "state": "unsupported",
            "verdict": "UNSUPPORTED",
            "reason": str(f.get("explanation") or "")[:180],
            "fact_version": "",
            "confidence": f.get("confidence"),
        })
    return nodes


def claim_graph_html(rep, icon_fn=None):
    nodes = claim_provenance(rep)
    if not nodes:
        empty_ic = icon_fn("git-branch", 28) if icon_fn else ""
        return (f'<div class="empty">{empty_ic}<p class="empty-title">No claims mapped yet</p>'
                f'<p>Price and product claims appear here once the engine extracts them.</p></div>')
    state_tone = {"matched": "ok", "mismatched": "bad", "unsupported": "warn", "review": "warn"}
    state_label = {"matched": "Matched", "mismatched": "Mismatched", "unsupported": "Unsupported", "review": "Needs review"}
    rows = []
    for n in nodes:
        tone = state_tone.get(n["state"], "neutral")
        arrow = icon_fn("arrow-right", 14) if icon_fn else "→"
        lock = icon_fn("tag", 14) if icon_fn else ""
        rows.append(
            f'<div class="claim-edge {tone}">'
            f'<div class="claim-node"><span class="muted">Claim</span>'
            f'<b>{e(n["heard"] or n["kind"])}</b></div>'
            f'<div class="claim-arrow" aria-hidden="true">{arrow}</div>'
            f'<div class="claim-node"><span class="muted">{lock} Approved fact</span>'
            f'<b>{e(n["official"])}</b>'
            f'{("<div class=muted>" + e(n["fact_version"]) + "</div>") if n["fact_version"] else ""}'
            f'</div>'
            f'<div class="claim-meta">{("<span class=chip " + tone + ">" + e(state_label.get(n["state"], n["state"])) + "</span>")}'
            + (f'<span class="muted">heard with {int(float(n["confidence"]) * 100)}% recognition confidence</span>'
               if isinstance(n.get("confidence"), (int, float)) and n["confidence"] < 0.995 and n.get("kind") != "promo" else "") +
            f'{("<div class=muted style=margin-top:4px>" + e(n["reason"]) + "</div>") if n["reason"] else ""}'
            f'</div></div>')
    return f'<div class="claim-graph">{"".join(rows)}</div>'


def guideline_health(rows, rep_of, type_label=None):
    """Detect rules that look too strict / vague / conflicting from disputes + repeated findings."""
    type_label = type_label or {}
    types = Counter()
    wording = Counter()
    overturn_by_type = Counter()
    uphold_by_type = Counter()
    status_by_id = {}
    for r in rows:
        status_by_id[r["id"]] = r["status"]
        rep = rep_of(r)
        for f in rep.get("findings", []):
            t = f.get("type") or "?"
            types[t] += 1
            if t in ("BANNED_PHRASE", "UNSUPPORTED_CLAIM", "TERMINOLOGY", "TONE",
                     "AI_TONE", "AI_TERMINOLOGY", "BANNED_PARAPHRASE"):
                wording[str(f.get("evidence") or "")[:80]] += 1

    # Approximate overturn association: if submission was APPROVED after DISPUTE, credit finding types
    for r in rows:
        if r["status"] != "APPROVED":
            continue
        # Only count if there was a dispute note (overturn path)
        note = r["dispute_note"] if "dispute_note" in r.keys() else None
        if not note and r["status"] != "APPROVED":
            continue
        # Prefer rows that look like dispute overturns: have dispute_note
        if not note:
            continue
        rep = rep_of(r)
        for f in rep.get("findings", []):
            if f.get("status") == "FLAG" or f.get("type") in ("BANNED_PHRASE", "UNSUPPORTED_CLAIM", "TONE", "TERMINOLOGY"):
                overturn_by_type[f.get("type") or "?"] += 1
    for r in rows:
        if r["status"] != "REJECTED_FINAL":
            continue
        note = r["dispute_note"] if "dispute_note" in r.keys() else None
        if not note:
            continue
        rep = rep_of(r)
        for f in rep.get("findings", []):
            if f.get("status") == "FLAG" or f.get("type") in ("BANNED_PHRASE", "UNSUPPORTED_CLAIM"):
                uphold_by_type[f.get("type") or "?"] += 1

    cards = []
    # Too strict: high overturn rate on a finding type
    for t, ov in overturn_by_type.most_common(8):
        up = uphold_by_type.get(t, 0)
        decided = ov + up
        if decided < 1:
            continue
        rate = ov / decided
        if rate >= 0.4 and ov >= 1:
            cards.append({
                "kind": "too_strict",
                "title": f'Rule may be too strict: {type_label.get(t, t)}',
                "evidence": f"{ov} overturn(s) vs {up} upheld · {int(rate * 100)}% overturn rate",
                "count": ov,
                "fix": "Narrow the rule or add preferred wording / context exceptions so creators are not blocked on harmless use.",
                "tone": "warn",
                "icon": "alert",
            })

    # Too vague: same wording flagged many times
    for phrase, n in wording.most_common(6):
        if n < 2 or not phrase:
            continue
        cards.append({
            "kind": "too_vague",
            "title": f'Repeated flag: “{phrase}”',
            "evidence": f"Fired {n} times across submissions",
            "count": n,
            "fix": "Add a concrete preferred alternative or example of allowed vs banned use in Brand Rules.",
            "tone": "warn",
            "icon": "message",
        })

    # Conflicting: both bans and preferred terminology covering similar space (heuristic)
    # Surface top finding types with high volume as training gaps
    for t, n in types.most_common(5):
        if n < 3:
            continue
        if any(c["title"].endswith(type_label.get(t, t)) for c in cards):
            continue
        cards.append({
            "kind": "training_gap",
            "title": f'Hotspot: {type_label.get(t, t)}',
            "evidence": f"{n} findings of this type",
            "count": n,
            "fix": "Publish a one-line creator tip or update the brand guide so this check stops surprising people.",
            "tone": "info",
            "icon": "history",
        })

    # Deduplicate by title, keep top 6
    seen, out = set(), []
    for c in cards:
        if c["title"] in seen:
            continue
        seen.add(c["title"])
        out.append(c)
        if len(out) >= 6:
            break
    return out


def guideline_health_html(cards, icon_fn=None):
    if not cards:
        ic = icon_fn("sparkles", 28) if icon_fn else ""
        return (f'<div class="empty">{ic}<p class="empty-title">Guidelines look healthy so far</p>'
                f'<p>After more reviews and disputes, BrandGuard surfaces rules that are too strict, vague, or conflicting.</p></div>')
    bits = []
    for c in cards:
        ic = icon_fn(c.get("icon") or "alert", 18) if icon_fn else ""
        bits.append(
            f'<div class="health-card {c.get("tone", "neutral")}">'
            f'<div class="health-top">{ic}<b>{e(c["title"])}</b>'
            f'<span class="chip {c.get("tone", "neutral")}">{c.get("count", 0)} evidence</span></div>'
            f'<p class="muted" style="margin:8px 0">{e(c["evidence"])}</p>'
            f'<p style="margin:0"><b>Recommended edit:</b> {e(c["fix"])}</p></div>')
    return f'<div class="health-grid">{"".join(bits)}</div>'
