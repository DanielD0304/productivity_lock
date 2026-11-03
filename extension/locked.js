const API = "http://127.0.0.1:47615";
const POLL_MS = 3000;
const MONTHS = ["Januar", "Februar", "März", "April", "Mai", "Juni", "Juli", "August", "September", "Oktober", "November", "Dezember"];
const WEEKDAYS = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"];
const $ = (id) => document.getElementById(id);
const inExtension = Boolean(globalThis.chrome?.runtime?.id);

const timerEnds = new Map();
let wasUnlocked = false;
let shownMonth = null;
let lastHistory = null;
let lastCalendarKey = null;

function formatTime(seconds) {
  const safe = Math.max(0, seconds);
  return `${Math.floor(safe / 60)}:${String(safe % 60).padStart(2, "0")}`;
}

function createRow(id) {
  const row = $("task-template").content.firstElementChild.cloneNode(true);
  row.id = `task-${id}`;
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

function renderTask(id, check) {
  const row = $(`task-${id}`) || createRow(id);
  row.classList.toggle("done", check.done);
  row.querySelector(".task-title").textContent = check.title;
  const detail = row.querySelector(".detail");
  detail.textContent = check.detail;
  detail.hidden = check.state === "note"; // The form label already asks the same question.

  const error = row.querySelector(".check-error");
  error.hidden = !check.error;
  error.textContent = check.error || "";

  const hint = row.querySelector(".hint-text");
  hint.hidden = !check.hint;
  hint.textContent = check.hint || "";

  const link = row.querySelector(".hint-link");
  link.hidden = !check.link;
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

function title(allDone) {
  return allDone ? "Geschafft. Viel Spaß!" : "Erst lernen, dann der Rest.";
}

function days(count) {
  return count === 1 ? "1 Tag" : `${count} Tage`;
}

function isoDay(year, month, day) {
  return `${year}-${String(month + 1).padStart(2, "0")}-${String(day).padStart(2, "0")}`;
}

// 0 = nothing (red) up to 4 = everything (green). Untracked days and an untouched today stay plain.
function dayLevel(data, iso, detail) {
  if (detail) return detail.done === detail.total ? 4 : Math.max(1, Math.round((4 * detail.done) / detail.total));
  return data.first && iso >= data.first && iso < data.today ? 0 : null;
}

function appendDay(year, month, day, data) {
  const iso = isoDay(year, month, day);
  const cell = document.createElement("div");
  const detail = data.details[iso];
  const level = dayLevel(data, iso, detail);
  const used = detail?.jokers.length > 0;
  cell.className = `day ${level === null ? "" : `lv${level}`} ${used ? "joker-day" : ""} ${iso === data.today ? "today" : ""}`;
  cell.textContent = day;
  if (detail) cell.title = `${detail.done} von ${detail.total}${used ? ` · Joker: ${detail.jokers.join(", ")}` : ""}`;
  else if (level === 0) cell.title = "Nichts geschafft";
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
  $("streak").textContent = `Serie: ${days(history.streak)}`;
  $("best").textContent = `· Rekord: ${days(history.best)}`;
  const { done, joker, missed } = history.week;
  $("week").textContent = `Diese Woche: ${done} geschafft · ${joker} Joker · ${missed} verpasst`;
  renderCalendar(lastHistory);
}

function moveMonth(step) {
  const moved = new Date(shownMonth.year, shownMonth.month + step, 1);
  shownMonth = { year: moved.getFullYear(), month: moved.getMonth() };
  renderCalendar(lastHistory);
}

async function render(status) {
  const checks = Object.values(status.checks);
  const finished = checks.filter((check) => check.done).length;
  const allDone = finished === checks.length;
  $("offline").hidden = true;
  $("progress").textContent = `${finished} von ${checks.length} erledigt`;
  $("title").textContent = title(allDone);
  for (const [id, check] of Object.entries(status.checks)) renderTask(id, check);
  renderHistory(status.history, status.day);
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
    $("progress").textContent = "Keine Verbindung";
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

$("refresh").addEventListener("click", () => refresh(true));
$("month-prev").addEventListener("click", () => moveMonth(-1));
$("month-next").addEventListener("click", () => moveMonth(1));

setInterval(tickTimers, 1000);
setInterval(refresh, POLL_MS);
refresh();
