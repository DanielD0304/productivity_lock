---
version: 1
slug: "extension-locked-html"
primary_target: "extension/locked.html"
related_targets: ["extension/locked.css","extension/locked.js"]
---

# Lock page

Scope: extension/locked.html (+ locked.css, locked.js, theme.js). Mode: Operate. One person, interrupted on the PC
(blocked site redirected here) or on the phone (Android WebView). Job: see at a glance what is still open today and do
it from its row; secondary: streak, week, month history. All features stay.

## Direction contract

THESIS: A calm daily checklist in the spirit of Apple's own apps; the day's progress is one segmented ring. Refuses the
dashboard-of-cards arrangement and the dark teal "app" look of the previous version.

OWN-WORLD: Neutral grounds (light #f5f5f7 / dark near-black), white or graphite grouped lists with hairline separators,
ink-coloured primary buttons (black in light, white in dark), Host Grotesk for all text with tabular numerals. Colour lives only
in the tasks: muted jewel tints (indigo, amber, green, violet, rose), never teal, each used for its icon chip, its check
and its ring segment.

STORY: The visitor sees how many tasks are left, which ones, and starts the next one in a tap; when all are done the
ring closes and the blocked sites are offered again. History confirms consistency without shouting.

FIRST VIEWPORT: Slim top bar (lock glyph + name, state pill, date, refresh, theme switch System/Hell/Dunkel). Left
column: the ring (~200px) with "2 von 5" in its centre beside the heading, then the grouped task list with each
row's action inline. Right column on wide screens: streak/record/week numbers above the month calendar; stacks below
the tasks on narrow screens.

FORM: Pinned by the user, apple-like grouped list with activity-style ring; seed: none (pinned) — "clean
minimalistisch", "zwischen white und black entscheiden", "den kreis finde ich besser", "Aufgaben mit Farben, aber edler",
"nicht das hässliche Türkisblau".

FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance
