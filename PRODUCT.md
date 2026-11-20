# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users
One person, the owner of this repository. They study for exams and learn languages, and want their daily learning
done before entertainment. They meet the checklist in two moments: on the PC, when a blocked site or game is opened and
the browser shows the lock page instead; and on an Android phone, inside the Productivity Lock app, which shows the same
page after a blocked app or site was closed.

## Product Purpose
Productivity Lock blocks YouTube, Netflix, Instagram, LinkedIn, Reddit, League of Legends and World of Warcraft (PC and
phone) until the day's tasks are done. The checklist page shows what is still open, lets the user work it off (reading
timer and note, joker with a reason, chat buttons on the PC) and shows how consistent the last weeks were. Success is a
day where everything is done before evening, and a streak that keeps growing.

## Positioning
Not a timer or a willpower app: the lock is real (processes closed, sites redirected, phone apps sent home), and it only
lifts on evidence (Anki reviews read from the collection, accepted LeetCode submissions, finished timers with a note).
The day rolls over at 4 a.m., like Anki.

## Operating Context
- PC: Windows service on 127.0.0.1:47615; Edge/Chrome extension redirects blocked sites to the page; tray icon with
  reminders. The page polls the service every 3 seconds.
- Phone: Android app (WebView) loads the same page from the PC over Tailscale, with a token.
- The page is opened in an interrupted moment: the user wanted something else and lands here.

## Capabilities and Constraints
- Task kinds: Anki (cards or minutes), LeetCode (remote check), reading timer with note, Lernchat and Sprachchat (weekly
  count, start button only on PC), custom tasks (check, timer, github).
- Joker: one per task per calendar week, needs a short reason.
- History: streak, record, this week (done / joker / missed), month calendar with per-day completion and joker days.
- All features stay; their presentation is open.
- Plain static HTML/CSS/JS in `extension/`, served by the Python service and loaded inside the browser extension; no
  build step, no framework.
- Light and dark: follows the system by default; a toggle overrides it and remembers the choice.

## Brand Commitments
- Name: Productivity Lock. German UI copy, direct and short ("Erst lernen, dann der Rest.").
- The user asked for a clean, minimal, noble look in the spirit of Apple's design; a progress ring rather than bars;
  tasks may carry colour but restrained; no turquoise/teal.

## Evidence on Hand
Real data only comes from the running service (task status, history). No testimonials or marketing material exist or
are needed.

## Product Principles
1. The lock is honest: the page never pretends something is done or unlocked.
2. One glance answers "what is still open today?"; everything else is secondary.
3. Doing the task is never more than one tap away from its row.
4. Calm, not punishing: the user is interrupted already; the page should invite, not scold.

## Accessibility & Inclusion
No specific requirement beyond solid contrast in both themes, keyboard use on the PC and comfortable touch targets on
the phone.
