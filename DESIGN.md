---
name: BrandGuard
description: A violet, card-based review workspace where every verdict is a number, a chip and a chart you can check.
colors:
  accent: "#6d3bd8"
  accent-hover: "#5a2dbd"
  accent-tint: "#f0eafd"
  canvas: "#f6f4fb"
  surface: "#ffffff"
  line: "#e8e4f3"
  line-soft: "#f1eef9"
  ink: "#1c1a2e"
  ink-soft: "#6b6784"
  field-line: "#8a85a3"
  side: "#fbfaff"
  ok: "#136c3a"
  ok-tint: "#e3f5ea"
  warn: "#8a5300"
  warn-tint: "#fff2d6"
  bad: "#a61b1b"
  bad-tint: "#fde8e8"
  chart-violet: "#6d3bd8"
  chart-lilac: "#a98bf0"
  chart-sky: "#5aa2ff"
  chart-ok: "#2db873"
  chart-warn: "#f0b429"
  chart-bad: "#e5484d"
typography:
  display:
    fontFamily: "Manrope, 'Segoe UI', 'Noto Sans', 'Noto Sans Devanagari', 'Nirmala UI', Mangal, system-ui, sans-serif"
    fontSize: "42px"
    fontWeight: 800
    lineHeight: 1.08
    letterSpacing: "-0.03em"
  headline:
    fontFamily: "Manrope, 'Segoe UI', 'Noto Sans', 'Noto Sans Devanagari', 'Nirmala UI', Mangal, system-ui, sans-serif"
    fontSize: "28px"
    fontWeight: 800
    lineHeight: 1.3
    letterSpacing: "-0.02em"
  title:
    fontFamily: "Manrope, 'Segoe UI', 'Noto Sans', 'Noto Sans Devanagari', 'Nirmala UI', Mangal, system-ui, sans-serif"
    fontSize: "17px"
    fontWeight: 700
    lineHeight: 1.3
  body:
    fontFamily: "Manrope, 'Segoe UI', 'Noto Sans', 'Noto Sans Devanagari', 'Nirmala UI', Mangal, system-ui, sans-serif"
    fontSize: "15px"
    fontWeight: 400
    lineHeight: 1.55
  label:
    fontFamily: "Manrope, 'Segoe UI', 'Noto Sans', 'Noto Sans Devanagari', 'Nirmala UI', Mangal, system-ui, sans-serif"
    fontSize: "12px"
    fontWeight: 600
    letterSpacing: "0.04em"
  mono:
    fontFamily: "Consolas, 'SFMono-Regular', monospace"
    fontSize: "13px"
rounded:
  xs: "6px"
  sm: "10px"
  lg: "16px"
  xl: "20px"
  pill: "999px"
spacing:
  xs: "6px"
  sm: "12px"
  md: "16px"
  lg: "22px"
  xl: "28px"
components:
  button-primary:
    backgroundColor: "{colors.accent}"
    textColor: "{colors.surface}"
    rounded: "{rounded.sm}"
    padding: "9px 16px"
    height: "44px"
  button-primary-hover:
    backgroundColor: "{colors.accent-hover}"
  button-secondary:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink}"
    rounded: "{rounded.sm}"
    padding: "9px 16px"
    height: "44px"
  card:
    backgroundColor: "{colors.surface}"
    rounded: "{rounded.lg}"
    padding: "22px"
  stat-hero:
    backgroundColor: "{colors.accent}"
    textColor: "{colors.surface}"
    rounded: "{rounded.lg}"
    padding: "18px 20px"
  input:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink}"
    rounded: "{rounded.sm}"
    padding: "9px 12px"
    height: "44px"
  chip-ok:
    backgroundColor: "{colors.ok-tint}"
    textColor: "{colors.ok}"
    rounded: "{rounded.pill}"
    padding: "2px 10px"
  nav-item-current:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.accent-hover}"
    rounded: "{rounded.sm}"
    padding: "10px 12px"
    height: "44px"
---

# Design System: BrandGuard

## Overview

**Creative North Star: "The Violet Ledger"**

BrandGuard reads like a clear page of accounts: every verdict is a number you can check, a chip that names it, and a chart that puts it in context. The workspace is a grid of rounded white cards on a pale lavender ground, with one saturated violet that appears in three places only: the main action, the current place, and the single headline figure on each dashboard. It is a reference-driven design: bento-style stat tiles, ring and bar charts, a light sidebar with a raised white current item, and a violet gradient used sparingly as the one bold surface.

The mood is confident and clear rather than severe. Numbers are large and bold, labels are small and quiet, and charts use only real counts from the company's own submissions. A full dark theme (deep violet-black surfaces) mirrors the light one.

**Key Characteristics:**
- Bento grid of 16px-radius cards; one gradient hero tile per dashboard.
- Big, tabular, heavy numerals (28px, weight 800) over small quiet labels.
- Rings, bars and columns drawn from real submission data; never decorative.
- Status shown by a chip with icon and word, and by tinted figures; never by colour alone.
- Light by default (lavender canvas), dark on request or by system setting.

## Colors

One violet accent over cool-lavender neutrals, with green, amber and red kept for verdicts and a small chart palette (violet, lilac, sky) for data.

### Primary
- **Violet** (#6d3bd8): primary buttons, links, the logo, the current-place marker on icons, the hero stat tile (as a gradient #7a4ae6 to #5a2dbd), chart bars. **Deep Violet** (#5a2dbd) is its hover and its ink on tint.
- **Violet Tint** (#f0eafd): the welcome card, role badges, empty-state tiles, selected tabs and the landing ground glow.

### Neutral
- **Lavender Canvas** (#f6f4fb): page ground. **White Sheet** (#ffffff): cards, tables, inputs.
- **Soft Rule** (#e8e4f3) and **Hair Rule** (#f1eef9): card borders and dividers. **Field Line** (#8a85a3): input, select and secondary-button borders (3.5:1 on white).
- **Ink** (#1c1a2e): text and headings. **Ink Soft** (#6b6784): secondary text (5.4:1 on white).
- **Side Wash** (#fbfaff): the sidebar surface.

### Status (tinted pairs)
- **Verified Green** (#136c3a) on #e3f5ea, **Caution Amber** (#8a5300) on #fff2d6, **Stop Red** (#a61b1b) on #fde8e8. Chart fills for the same meanings are brighter (#2db873, #f0b429, #e5484d).

### Dark theme
Follows the system and can be set from the sidebar (Auto, Light, Dark). Ground #0f0c1f, sheets #17132b, text #ece9f7, action violet #7a4ae0 with a light link violet (#b79cff). Status tints invert to light figures on dark tints. Every text pair is at least 4.5:1.

### Named Rules
**The One Violet Rule.** Violet marks the action, the place you are, and the one headline figure. It never decorates.
**The Status-Only Colour Rule.** Green, amber and red mean a verdict and nothing else.
**The Real-Data Rule.** A chart only ever shows counts from the company's own submissions; there is no sample or placeholder data in a chart.

## Typography

**Display / Body Font:** Manrope (with Segoe UI, Noto Sans, Noto Sans Devanagari, Nirmala UI, Mangal, system-ui)
**Mono Font:** Consolas (with SFMono-Regular) for approval IDs, fingerprints and quoted transcript.

**Character:** A rounded geometric sans in heavy weights for headings and figures, regular weight for reading. Devanagari falls back to Noto so Marathi and Hindi stay on the same baseline.

### Scale
Sizes: 12, 13, 14, 15, 17, 20, 24, 28px and a fluid hero (30 to 42px). Radii: 6, 10, 16, 20px, plus pills and circles.

### Hierarchy
- **Display** (800, clamp 30 to 42px, 1.08, -0.03em): landing headline only.
- **Headline** (800, 28px, -0.02em): page title, one per page.
- **Title** (700, 17px): card headings.
- **Body** (400, 15px, 1.55): all reading text.
- **Figure** (800, 28px, tabular numerals): stat tiles and ring centres.
- **Label** (600, 12px, uppercase, +0.04em): table column headers and sidebar group names.

### Named Rules
**The Plain Sentence Rule.** Findings and statuses are plain sentences in sentence case. Uppercase belongs to table headers and group names.

## Layout

A 248px light sidebar and a fluid main column (max 1240px, 28px padding). Dashboards use a 12-column bento grid with 16px gaps: a row of four stat tiles, then cards spanning 8 and 4, then rows of 4/4/4. Under 1100px every span collapses to one column; under 900px the sidebar becomes an off-canvas drawer behind a 44px menu button; under 640px tables restack into labelled rows and stats go single-column. Spacing steps cluster at 6, 12, 16, 22 and 28px.

## Elevation & Depth

Flat with a hairline. Cards sit on the lavender canvas with a 1px Soft Rule border and a faint violet-tinted hairline shadow (`0 1px 2px rgba(60,40,120,.05)`). The current sidebar item lifts slightly (`0 1px 3px`). Only overlays and the landing sample window carry real shadow.

### Shadow Vocabulary
- **Hairline** (`0 1px 2px rgba(60,40,120,.05)`): cards.
- **Lift** (`0 2px 10px rgba(60,40,120,.08)`, `0 10px 28px rgba(60,40,120,.12)`): findings and role cards on hover.
- **Overlay** (`0 12px 40px rgba(28,26,46,.3)`): dialogs, tour popover; the landing sample sits on a violet gradient stage with a deeper shadow.

### Named Rules
**The Flat-At-Rest Rule.** Surfaces carry no shadow beyond the hairline until they float or are hovered.

## Shapes

Generous and consistent: 16px cards and alerts, 10px buttons, inputs and nav items, 20px for the landing stage and role cards, pills for chips, tabs and progress bars, circles for status dots and ring charts. No thick coloured card edges: status shows through a tinted 1px border, a chip with icon and word, or the colour of a figure.

## Components

All controls are at least 44px tall.

### Buttons
- **Primary:** Violet fill, white text, 10px radius, weight 700; hover Deep Violet.
- **Secondary:** white fill, Ink text, 1px Field Line border; hover Canvas.
- **Danger / Success:** #b42323 and #15803d fills for reject and approve decisions.
- Focus: 3px violet outline with 2px offset.

### Stat tiles
Four across. The first tile is the **hero**: Violet gradient, white figure. The others are white cards whose figure is tinted by meaning (amber, green, red). A short quiet hint sits under the figure.

### Charts
- **Ring:** a 148px donut with the total in the centre and a legend (dot, label, count, percent) beside it.
- **Bars:** horizontal bars for ranked findings, vertical columns for the last 7 days, both with a violet-to-lilac fill. Each chart carries a text summary for assistive tech.

### Cards
White, 16px radius, 1px Soft Rule, 22px padding, hairline shadow.

### Chips
Pill, 12px 600, status tint with matching dark text; always with an icon or word.

### Inputs / Fields
White, 1px Field Line border, 10px radius, 44px tall; focus is a 3px violet outline and a violet border.

### Navigation
Light sidebar. Items are 44px tall with icon and label; the current item is a raised white pill with violet text and icon. The reviewer menu is grouped (Work open; Set up and Proof fold away until one of their pages is open). A count badge is a violet pill. Footer holds the demo-role switch, account, theme toggle and log out.

### Findings (signature component)
A white row with a status-tinted border, chips for status and severity, and a definition list answering where, what, why and what to change.

### Approval record
A green-tinted bordered block with the approval ID in Consolas and the SHA-256 fingerprint set out in ruled rows; the one place the ledger idea is literal.

### Landing sample
A real example result (a rejected claim) in a white window on a violet gradient stage, to the right of a heavy two-line headline.

## Do's and Don'ts

### Do:
- **Do** keep violet to the action, the current place and the hero figure.
- **Do** draw every chart from real counts, with a text equivalent.
- **Do** pair every status colour with an icon and a word.
- **Do** keep controls at 44px and focus outlines visible.
- **Do** keep sizes, radii and colours on the defined scales and tokens so the dark theme works.
- **Do** scope single-key shortcuts to focus inside the control group (WCAG 2.1.4).

### Don't:
- **Don't** use green, amber or red for decoration, or add a second accent hue.
- **Don't** put thick coloured edges on cards or nest a bordered card inside another card.
- **Don't** show sample or invented numbers in a chart or stat tile.
- **Don't** use heavy shadows on resting cards.
- **Don't** convey a verdict by colour alone.
