// Served by the service (PC or phone) the page asks its own origin; inside the extension it asks the PC.
const API = location.protocol.startsWith("http") ? location.origin : "http://127.0.0.1:47615";
const POLL_MS = 3000;
const MONTHS = ["Januar", "Februar", "März", "April", "Mai", "Juni", "Juli", "August", "September", "Oktober", "November", "Dezember"];
const WEEKDAYS = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"];
const SVG_NS = "http://www.w3.org/2000/svg";
const $ = (id) => document.getElementById(id);
const inExtension = Boolean(globalThis.chrome?.runtime?.id);

// Each task gets a colour and glyph; the colours are theme tokens, so light and dark each get their own shade.
// Unknown tasks fall back by kind, then by position.
const TASK_STYLE = {
  anki: { tint: "var(--t-indigo)", icon: "cards" },
  leetcode: { tint: "var(--t-amber)", icon: "code" },
  reading: { tint: "var(--t-green)", icon: "book" },
  lernchat: { tint: "var(--t-violet)", icon: "chat" },
  sprachchat: { tint: "var(--t-rose)", icon: "globe" },
};
const KIND_ICON = { remote: "branch", timer: "clock", check: "check", chat: "chat", anki: "cards" };
const FALLBACK_TINTS = ["var(--t-blue)", "var(--t-sand)", "var(--t-green)", "var(--t-amber)", "var(--t-violet)", "var(--t-graphite)"];
const THEME_KEY = "plock-theme";
const ICONS = {
  cards: '<rect x="4" y="7" width="12" height="13" rx="2.5"/><path d="M8 4h9.5A2.5 2.5 0 0 1 20 6.5V16"/>',
  code: '<path d="M8.5 7.5L4 12l4.5 4.5M15.5 7.5L20 12l-4.5 4.5M13.5 5l-3 14"/>',
  book: '<path d="M12 6.5C10 5 7 4.5 4 5v13c3-.5 6 0 8 1.5 2-1.5 5-2 8-1.5V5c-3-.5-6 0-8 1.5zM12 6.5v13"/>',
  chat: '<path d="M20 11.5c0 4-3.6 7-8 7-1.2 0-2.3-.2-3.3-.6L4.5 19.5l1.3-3.4C4.7 14.8 4 13.2 4 11.5c0-4 3.6-7 8-7s8 3 8 7z"/>',
  globe: '<circle cx="12" cy="12" r="8"/><path d="M4 12h16M12 4c2.2 2.3 3.2 5 3.2 8s-1 5.7-3.2 8c-2.2-2.3-3.2-5-3.2-8s1-5.7 3.2-8z"/>',
  branch: '<circle cx="7" cy="6" r="2"/><circle cx="7" cy="18" r="2"/><circle cx="17" cy="8" r="2"/><path d="M7 8v8M17 10c0 3-3 4-10 6"/>',
  clock: '<circle cx="12" cy="12" r="8"/><path d="M12 7.5V12l3 2"/>',
  check: '<path d="M5 12.5l4.5 4.5L19 7.5"/>',
};

const timerEnds = new Map();
let wasUnlocked = false;
let shownMonth = null;
let lastHistory = null;
let lastCalendarKey = null;
let ringKey = null;

function svg(tag, attrs = {}) {
  const node = document.createElementNS(SVG_NS, tag);
  for (const [key, value] of Object.entries(attrs)) node.setAttribute(key, value);
  return node;
}

function formatTime(seconds) {
  const safe = Math.max(0, seconds);
  return `${Math.floor(safe / 60)}:${String(safe % 60).padStart(2, "0")}`;
}

function styleFor(id, kind, index) {
  const known = TASK_STYLE[id];
  if (known) return known;
  return { tint: FALLBACK_TINTS[index % FALLBACK_TINTS.length], icon: KIND_ICON[kind] || "check" };
}

function createRow(id, check, index) {
  const row = $("task-template").content.firstElementChild.cloneNode(true);
  row.id = `task-${id}`;
  const { tint, icon } = styleFor(id, check.kind, index);
  row.style.setProperty("--tint", tint);
  row.dataset.tint = tint;
  row.querySelector(".icon").innerHTML = `<svg viewBox="0 0 24 24">${ICONS[icon]}</svg>`;

  const noteId = `note-${id}`;
  row.querySelector(".note").id = noteId;
  row.querySelector(".note-label").htmlFor = noteId;
  row.querySelector(".action").addEventListener("click", async () => {
    const error = row.querySelector(".action-error");
    error.hidden = true;
    try {
      await post(row.querySelector(".action").dataset.path);
    } catch (failure) {
      error.textContent = failure.message;
      error.hidden = false;
    }
  });
  const jokerForm = row.querySelector(".joker-form");
  const setJokerOpen = (open) => {
    row.dataset.jokerOpen = open ? "1" : "";
    row.querySelector(".joker-error").hidden = true;
    row.querySelector(".joker-open").hidden = open;
    jokerForm.hidden = !open;
    if (open) row.querySelector(".joker-reason").focus();
  };
  row.querySelector(".joker-open").addEventListener("click", () => setJokerOpen(true));
  row.querySelector(".joker-cancel").addEventListener("click", () => setJokerOpen(false));
  row.querySelector(".joker-reason").id = `joker-reason-${id}`;
  row.querySelector(".joker-label").htmlFor = `joker-reason-${id}`;
  jokerForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const error = row.querySelector(".joker-error");
    error.hidden = true;
    try {
      await post(`/tasks/${id}/joker`, { reason: row.querySelector(".joker-reason").value });
      row.dataset.jokerOpen = "";
      await refresh();
    } catch (failure) {
      error.textContent = failure.message;
      error.hidden = false;
    }
  });
  row.querySelector(".start").addEventListener("click", async () => {
    await post(`/tasks/${id}/start`);
    await refresh();
  });
  row.querySelector(".note-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const error = row.querySelector(".note-error");
    error.hidden = true;
    try {
      await post(`/tasks/${id}/finish`, { note: row.querySelector(".note").value });
      await refresh();
    } catch (failure) {
      error.textContent = failure.message;
      error.hidden = false;
    }
  });
  $("tasks").append(row);
  return row;
}

function renderTask(id, check, index) {
  const row = $(`task-${id}`) || createRow(id, check, index);
  row.classList.toggle("done", check.done);
  row.querySelector(".task-title").textContent = check.title;
  const detail = row.querySelector(".detail");
  detail.textContent = check.detail;
  detail.hidden = check.state === "note"; // The form label already asks the same question.

  const error = row.querySelector(".check-error");
  error.hidden = !check.error;
  error.textContent = check.error || "";

  const hint = row.querySelector(".hint-text");
  hint.hidden = !check.hint || check.done;
  hint.textContent = check.hint || "";

  const link = row.querySelector(".hint-link");
  link.hidden = !check.link || check.done;
  link.textContent = check.link_text || "";
  if (check.link) link.href = check.link;

  const action = row.querySelector(".action");
  action.hidden = !check.action_path;
  action.textContent = check.action_text || "";
  action.dataset.path = check.action_path || "";

  const jokerNote = check.joker.left > 0 ? "Joker frei diese Woche" : "Joker diese Woche verbraucht";
  const canJoker = !check.done && check.joker.left > 0 && check.joker.per_week > 0;
  const jokerOpen = canJoker && row.dataset.jokerOpen === "1";
  row.classList.toggle("excused", check.joker_used);
  row.querySelector(".joker-open").hidden = !canJoker || jokerOpen;
  row.querySelector(".joker-form").hidden = !jokerOpen;
  row.querySelector(".joker-open").title = jokerNote;

  row.querySelector(".start").hidden = check.state !== "idle";
  row.querySelector(".note-form").hidden = check.state !== "note";
  row.querySelector(".note-label").textContent = check.prompt || "";
  row.querySelector(".timer").hidden = check.state !== "running";
  if (check.state === "running") {
    timerEnds.set(id, Date.now() + check.remaining_seconds * 1000);
  } else {
    timerEnds.delete(id);
  }
}

function tickTimers() {
  for (const [id, endsAt] of timerEnds) {
    const left = Math.ceil((endsAt - Date.now()) / 1000);
    $(`task-${id}`).querySelector(".timer").textContent = formatTime(left);
  }
}

// One ring segment per task, in the task's colour, like the activity rings.
function renderRing(ids, checks) {
  const ring = $("ring");
  const key = ids.join("|");
  if (key !== ringKey) {
    ringKey = key;
    ring.replaceChildren();
    const radius = 90;
    const circumference = 2 * Math.PI * radius;
    const gap = ids.length > 1 ? 24 : 0; // Covers the round caps plus a visible gap.
    const length = Math.max(1, circumference / ids.length - gap);
    ids.forEach((id, index) => {
      const tint = $(`task-${id}`).dataset.tint;
      const rotate = -90 + (360 * index) / ids.length + (gap / 2 / circumference) * 360;
      const group = svg("g", { transform: `rotate(${rotate} 100 100)`, style: `--seg: ${tint}` });
      group.append(
        svg("circle", { class: "seg-track", cx: 100, cy: 100, r: radius, "stroke-dasharray": `${length} ${circumference}` }),
        svg("circle", { class: "seg-fill", id: `seg-${id}`, cx: 100, cy: 100, r: radius,
                        "stroke-dasharray": `${length} ${circumference}`, "stroke-dashoffset": length,
                        "data-length": length }),
      );
      ring.append(group);
    });
  }
  for (const id of ids) {
    const seg = $(`seg-${id}`);
    seg.setAttribute("stroke-dashoffset", checks[id].done ? 0 : seg.dataset.length);
    seg.classList.toggle("empty", !checks[id].done); // An empty dash would still draw its round caps.
  }
}

function clearRing() {
  for (const seg of document.querySelectorAll(".seg-fill")) {
    seg.setAttribute("stroke-dashoffset", seg.dataset.length);
    seg.classList.add("empty");
  }
}

function title(allDone) {
  return allDone ? "Geschafft. Viel Spaß!" : "Erst lernen, dann der Rest.";
}

function lede(open) {
  if (open === 0) return "Alles erledigt für heute.";
  return open === 1 ? "Noch eine Aufgabe, dann ist alles offen." : `Noch ${open} Aufgaben, dann ist alles offen.`;
}

function days(count) {
  return `${count}<small>${count === 1 ? "Tag" : "Tage"}</small>`;
}

function isoDay(year, month, day) {
  return `${year}-${String(month + 1).padStart(2, "0")}-${String(day).padStart(2, "0")}`;
}

// 0 = nothing up to 4 = everything; null for untracked days.
function dayLevel(share) {
  if (share === null) return null;
  if (share >= 1) return 4;
  return share === 0 ? 0 : Math.min(3, Math.max(1, Math.round(share * 4)));
}

// Share of the day's tasks that got done; 0 for a tracked day with nothing, null for untracked days.
function dayShare(data, iso, detail) {
  if (detail) return detail.total ? detail.done / detail.total : 0;
  return data.first && iso >= data.first && iso < data.today ? 0 : null;
}

function appendDay(year, month, day, data) {
  const iso = isoDay(year, month, day);
  const detail = data.details[iso];
  const share = dayShare(data, iso, detail);
  const used = detail?.jokers.length > 0;
  const cell = document.createElement("div");
  cell.className = "day";
  cell.classList.toggle("tracked", share !== null);
  cell.classList.toggle("today", iso === data.today);
  const level = dayLevel(share);
  if (level !== null && iso !== data.today) cell.classList.add(`lv${level}`);
  cell.classList.toggle("joker", used && share < 1);
  cell.textContent = day;

  if (detail) cell.title = `${detail.done} von ${detail.total}${used ? ` · Joker: ${detail.jokers.join(", ")}` : ""}`;
  else if (share === 0) cell.title = "Nichts geschafft";
  $("calendar").append(cell);
}

function renderCalendar(data) {
  const key = JSON.stringify([data, shownMonth]);
  if (key === lastCalendarKey) return;
  lastCalendarKey = key;

  const { year, month } = shownMonth;
  const [todayYear, todayMonth] = data.today.split("-").map(Number);
  $("month-label").textContent = `${MONTHS[month]} ${year}`;
  $("month-next").disabled = year === todayYear && month === todayMonth - 1;

  $("calendar").replaceChildren();
  for (const weekday of WEEKDAYS) {
    const head = document.createElement("div");
    head.className = "weekday";
    head.textContent = weekday;
    $("calendar").append(head);
  }
  const leadingBlanks = (new Date(year, month, 1).getDay() + 6) % 7;
  for (let blank = 0; blank < leadingBlanks; blank++) $("calendar").append(document.createElement("div"));
  const length = new Date(year, month + 1, 0).getDate();
  for (let day = 1; day <= length; day++) appendDay(year, month, day, data);
}

function renderHistory(history, today) {
  if (!shownMonth) {
    const [year, month] = today.split("-").map(Number);
    shownMonth = { year, month: month - 1 };
  }
  lastHistory = { ...history, today };
  $("history").hidden = false;
  $("streak").innerHTML = days(history.streak);
  $("best").innerHTML = days(history.best);
  const { done, joker, missed } = history.week;
  $("week-done").innerHTML = `${done}<small>/7</small>`;
  $("week").textContent = `Diese Woche ${done} geschafft · ${joker} Joker · ${missed} verpasst`;
  renderCalendar(lastHistory);
}

function moveMonth(step) {
  const moved = new Date(shownMonth.year, shownMonth.month + step, 1);
  shownMonth = { year: moved.getFullYear(), month: moved.getMonth() };
  renderCalendar(lastHistory);
}

function renderDate() {
  $("date").textContent = new Date().toLocaleDateString("de-DE", { weekday: "long", day: "numeric", month: "long" });
}

async function render(status) {
  const ids = Object.keys(status.checks);
  const checks = Object.values(status.checks);
  const finished = checks.filter((check) => check.done).length;
  const allDone = finished === checks.length;
  $("offline").hidden = true;
  $("count-done").textContent = finished;
  $("count-total").textContent = `von ${checks.length}`;
  $("progress").textContent = lede(checks.length - finished);
  $("state").textContent = status.unlocked ? "Frei" : "Gesperrt";
  $("title").textContent = title(allDone);
  document.body.classList.toggle("unlocked", allDone);
  ids.forEach((id, index) => renderTask(id, status.checks[id], index));
  renderRing(ids, status.checks);
  renderHistory(status.history, status.day);
  renderDate();
  tickTimers();
  if (status.unlocked && !wasUnlocked && inExtension) {
    // Lift the block before offering the links.
    await chrome.runtime.sendMessage({ type: "sync" });
  }
  wasUnlocked = status.unlocked;
  $("links").hidden = !status.unlocked;
}

async function refresh(force = false) {
  try {
    const response = await fetch(`${API}/status${force ? "?refresh=1" : ""}`, { cache: "no-store" });
    await render(await response.json());
  } catch {
    $("offline").hidden = false;
    $("count-done").textContent = "–";
    $("count-total").textContent = "";
    $("progress").textContent = "Keine Verbindung zum Lock-Dienst.";
    $("state").textContent = "Gesperrt";
    $("title").textContent = title(false);
    document.body.classList.remove("unlocked");
    clearRing();
    $("links").hidden = true;
    wasUnlocked = false;
  }
}

async function post(path, body = {}) {
  const response = await fetch(`${API}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const payload = await response.json();
  if (!response.ok) throw new Error(payload.error);
  return payload;
}

$("refresh").addEventListener("click", async () => {
  const button = $("refresh");
  button.classList.remove("spin");
  void button.offsetWidth; // Restart the turn on every click.
  button.classList.add("spin");
  await refresh(true);
  setTimeout(() => button.classList.remove("spin"), 500);
});
$("month-prev").addEventListener("click", () => moveMonth(-1));

// Light, dark or whatever the system says; the choice is remembered on this device.
function applyTheme(choice) {
  if (choice === "light" || choice === "dark") document.documentElement.dataset.theme = choice;
  else delete document.documentElement.dataset.theme;
  for (const button of document.querySelectorAll("[data-theme-choice]")) {
    button.setAttribute("aria-checked", String(button.dataset.themeChoice === (choice || "system")));
  }
}

function storedTheme() {
  try {
    return localStorage.getItem(THEME_KEY) || "system";
  } catch {
    return "system";
  }
}

for (const button of document.querySelectorAll("[data-theme-choice]")) {
  button.addEventListener("click", () => {
    const choice = button.dataset.themeChoice;
    try {
      if (choice === "system") localStorage.removeItem(THEME_KEY);
      else localStorage.setItem(THEME_KEY, choice);
    } catch {
      // Storage blocked: the choice holds until the page reloads.
    }
    applyTheme(choice);
  });
}
applyTheme(storedTheme());
$("month-next").addEventListener("click", () => moveMonth(1));

renderDate();
setInterval(tickTimers, 1000);
setInterval(refresh, POLL_MS);
refresh();
