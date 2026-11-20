---
name: Productivity Lock
description: A calm daily checklist that keeps distractions locked until the learning is done.
colors:
  ground: "#f5f5f7"
  surface: "#ffffff"
  ink: "#1d1d1f"
  ink-secondary: "#6e6e73"
  ink-tertiary: "#8e8e93"
  ground-dark: "#000000"
  surface-dark: "#1c1c1e"
  ink-dark: "#f5f5f7"
  ink-secondary-dark: "#a1a1a6"
  danger: "#c4161c"
  danger-dark: "#ff6b63"
  go: "#248a3d"
  go-dark: "#4cd471"
  task-indigo: "#5754d0"
  task-amber: "#b26a00"
  task-green: "#2f8a4f"
  task-violet: "#8a4fbf"
  task-rose: "#c63a5d"
  task-blue: "#2b6fd6"
  task-sand: "#94744a"
  task-indigo-dark: "#8f8cf5"
  task-amber-dark: "#e7a542"
  task-green-dark: "#5ec27f"
  task-violet-dark: "#bb8deb"
  task-rose-dark: "#f27792"
  task-blue-dark: "#69a3fa"
  task-sand-dark: "#c9a678"
typography:
  display:
    fontFamily: "Host Grotesk, Segoe UI Variable Text, system-ui, sans-serif"
    fontSize: "clamp(30px, 3.4vw, 42px)"
    fontWeight: 650
    lineHeight: 1.06
    letterSpacing: "-0.03em"
  ring-count:
    fontFamily: "Host Grotesk, system-ui, sans-serif"
    fontSize: "52px"
    fontWeight: 600
    lineHeight: 1
    letterSpacing: "-0.035em"
  headline:
    fontFamily: "Host Grotesk, system-ui, sans-serif"
    fontSize: "20px"
    fontWeight: 650
    letterSpacing: "-0.02em"
  title:
    fontFamily: "Host Grotesk, system-ui, sans-serif"
    fontSize: "16px"
    fontWeight: 600
    letterSpacing: "-0.01em"
  body:
    fontFamily: "Host Grotesk, system-ui, sans-serif"
    fontSize: "15px"
    fontWeight: 400
    lineHeight: 1.45
    fontFeature: "\"tnum\""
  label:
    fontFamily: "Host Grotesk, system-ui, sans-serif"
    fontSize: "13px"
    fontWeight: 400
rounded:
  field: "10px"
  icon: "11px"
  group: "16px"
  pill: "999px"
spacing:
  row-y: "16px"
  row-x: "18px"
  section: "44px"
  column-gap: "40px"
components:
  button-primary:
    backgroundColor: "{colors.ink}"
    textColor: "{colors.surface}"
    rounded: "{rounded.pill}"
    padding: "0 16px"
    height: "34px"
  button-quiet:
    textColor: "{colors.ink-secondary}"
    rounded: "{rounded.pill}"
    padding: "0 12px"
    height: "34px"
  task-group:
    backgroundColor: "{colors.surface}"
    rounded: "{rounded.group}"
    padding: "16px 18px"
  field:
    rounded: "{rounded.field}"
    padding: "10px 12px"
---

# Design System: Productivity Lock

## Overview

**Creative North Star: "The quiet ledger"** (proposed by the build, not yet confirmed by the owner)

The lock page is met in an interrupted moment: a blocked site or app was just closed and the page takes its place. It
answers one question first, how much of today is still open, and makes the next task one tap away. The look follows
the restraint of Apple's own apps: neutral grounds, white or graphite grouped lists, ink-coloured actions, and colour
spent only where it identifies a task. Light and dark are equal citizens: the page follows the system, and a switch in
the top bar pins either one on that device.

**Key Characteristics:**
- One segmented progress ring, one segment per task, filled in the task's own colour.
- Tasks live in one grouped list with hairline separators, never as separate cards.
- Primary actions are ink pills (black on light, white on dark); secondary actions are quiet text buttons.
- History is monochrome: completion is drawn as ink density, not colour.

## Colors

Neutral greys carry the page; muted jewel tints identify tasks and nothing else.

### Primary
- **Ink** (#1d1d1f light / #f5f5f7 dark): text, primary buttons, today's calendar ring, completed calendar days.

### Neutral
- **Ground** (#f5f5f7 / #000000): page background.
- **Surface** (#ffffff / #1c1c1e): grouped lists and panels.
- **Secondary ink** (#6e6e73 / #a1a1a6): details, hints, labels, quiet buttons.
- **Fills** (rgb(118 118 128) at 10–32%): pill backgrounds, inputs, ring track, hover states.

### Task tints
Indigo (Anki), amber (LeetCode), green (Lesen), violet (Lernchat), rose (Sprachchat); blue, sand and graphite for
custom tasks. Each tint appears as a 14% chip behind the task icon, the icon itself, the filled check, the running
timer, the input caret and focus ring, and the task's ring segment. Dark mode uses lighter variants of the same hues.

### State
- **Danger** (#c4161c / #ff6b63): errors and the "Gesperrt" dot. **Go** (#248a3d / #4cd471): the "Frei" dot.

### Named Rules
**The Task Owns Its Colour Rule.** A tint only ever marks its own task. Navigation, buttons, history and chrome stay
neutral.

**The No Teal Rule.** Turquoise and teal are out; the owner rejected them explicitly.

## Typography

**Font:** Host Grotesk (self-hosted variable WOFF2 in `extension/fonts/`), falling back to Segoe UI Variable and
system-ui. Tabular numerals everywhere, so timers and counts never jitter.

### Hierarchy
- **Display** (650, clamp(30px, 3.4vw, 42px), 1.06, -0.03em): the page heading next to the ring; 26px on phones.
- **Ring count** (600, 52px, -0.035em): the finished-task count in the ring centre; 36px on phones.
- **Headline** (650, 20px, -0.02em): section titles ("Heute", "Verlauf").
- **Title** (600, 16px, -0.01em): task names.
- **Body** (400, 15px, 1.45): base text; lede at 17px in secondary ink.
- **Label** (400, 13–14px): details, hints, stats labels, legend.

## Layout

A centred column up to 1120px. On wide screens two columns: today's work (ring, list) and a 340px sticky history panel;
below 920px one column with history under the tasks; below 640px the ring shrinks to 128px, the brand name and date
hide, task actions span the row's full width and buttons grow to 40px for touch. Safe-area insets are respected for the
phone's WebView.

## Elevation & Depth

Mostly tonal: white surfaces on a light grey ground. In light mode lists and panels carry one soft ambient shadow
(`0 1px 2px rgb(0 0 0 / .04), 0 6px 20px -8px rgb(0 0 0 / .08)`); in dark mode none, the graphite surface on black is
enough. Never a border and a shadow together.

## Shapes

16px for grouped lists and panels, 11px for task icon chips, 10px for fields, full pills for buttons, state badge,
site links and the theme switch. Circles for checks and calendar days.

## Components

- **Top bar:** lock glyph, name, state pill with a coloured dot, date, a three-way theme switch (System / Hell /
  Dunkel, icons with labels for assistive tech) and a round refresh button.
- **Progress ring:** 200-unit SVG, radius 90, 16px stroke, round caps, 24-unit gaps; segments animate with an
  exponential ease-out over 1.1s; empty segments fade out so no cap dots remain.
- **Task row:** icon chip, title and detail, optional timer, check circle. Expanded content (hints, link, actions, joker
  and note forms) aligns with the title on wide screens and spans the row on phones.
- **Check:** 26px circle with a 1.75px inset ring; done fills with the tint and pops once; excused (joker) fills with
  35% tint.
- **History panel:** three stats (Serie, Rekord, Woche), a week footnote, then the month calendar with completion as
  ink density, joker days as an outlined circle with a dot, today as an ink ring.

## Do's and Don'ts

- Do keep colour inside the task: chip, check, ring segment, timer.
- Do keep every feature reachable from its row: timer, note, joker and chat buttons sit with their task.
- Do test both themes and a 390px width before shipping a change.
- Don't add cards around individual tasks or nest panels.
- Don't put a label or badge above the main heading.
- Don't reintroduce teal or a coloured page background.
