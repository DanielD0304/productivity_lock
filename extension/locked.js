const API = "http://127.0.0.1:47615";
const POLL_MS = 3000;
const MONTHS = ["Januar", "Februar", "März", "April", "Mai", "Juni", "Juli", "August", "September", "Oktober", "November", "Dezember"];
const WEEKDAYS = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"];
const RESULT_CLASS = { done: "done", joker: "joker-day", partial: "partial" };
const RESULT_LABEL = { done: "Geschafft", joker: "Joker", partial: "Teilweise" };
const $ = (id) => document.getElementById(id);
const inExtension = Boolean(globalThis.chrome?.runtime?.id);

const timerEnds = new Map();
let wasUnlocked = false;
let jokerFormOpen = false;
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

function jokerText(joker) {
  if (joker.active) return `Joker für heute eingesetzt: ${joker.reason}`;
  if (joker.left > 0) return `Joker übrig diese Woche: ${joker.left} von ${joker.per_week}`;
  return "Joker für diese Woche verbraucht. Am Montag gibt es neue.";
}

function renderJoker(joker, allDone) {
  const canUse = !joker.active && !allDone && joker.left > 0;
  $("joker").hidden = joker.per_week === 0 || (allDone && !joker.active);
  $("joker-info").textContent = jokerText(joker);
  $("joker-open").hidden = !canUse || jokerFormOpen;
  $("joker-form").hidden = !canUse || !jokerFormOpen;
}

function title(status, allDone) {
  if (allDone) return "Geschafft. Viel Spaß!";
  return status.joker.active ? "Heute ist Pause. Morgen geht es weiter." : "Erst lernen, dann der Rest.";
}

function days(count) {
  return count === 1 ? "1 Tag" : `${count} Tage`;
}

function isoDay(year, month, day) {
  return `${year}-${String(month + 1).padStart(2, "0")}-${String(day).padStart(2, "0")}`;
}

function appendDay(year, month, day, data) {
  const iso = isoDay(year, month, day);
  const cell = document.createElement("div");
  const result = data.days[iso];
  cell.className = `day ${RESULT_CLASS[result] || ""} ${iso === data.today ? "today" : ""}`;
  cell.textContent = day;
  cell.title = RESULT_LABEL[result] || "";
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
  $("title").textContent = title(status, allDone);
  renderJoker(status.joker, allDone);
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

function setJokerFormOpen(open) {
  jokerFormOpen = open;
  $("joker-error").hidden = true;
  $("joker-open").hidden = open;
  $("joker-form").hidden = !open;
  if (open) $("joker-reason").focus();
}

$("joker-open").addEventListener("click", () => setJokerFormOpen(true));
$("joker-cancel").addEventListener("click", () => setJokerFormOpen(false));

$("joker-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  $("joker-error").hidden = true;
  try {
    await post("/joker", { reason: $("joker-reason").value });
    jokerFormOpen = false;
    await refresh();
  } catch (error) {
    $("joker-error").textContent = error.message;
    $("joker-error").hidden = false;
  }
});

setInterval(tickTimers, 1000);
setInterval(refresh, POLL_MS);
refresh();
