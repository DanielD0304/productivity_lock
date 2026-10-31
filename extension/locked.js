const API = "http://127.0.0.1:47615";
const POLL_MS = 3000;
const $ = (id) => document.getElementById(id);
const inExtension = Boolean(globalThis.chrome?.runtime?.id);

let timerEndsAt = null;
let wasUnlocked = false;
let jokerFormOpen = false;

function formatTime(seconds) {
  const safe = Math.max(0, seconds);
  return `${Math.floor(safe / 60)}:${String(safe % 60).padStart(2, "0")}`;
}

function renderTask(id, check) {
  const task = $(id);
  task.classList.toggle("done", check.done);
  task.querySelector(".detail").textContent = check.detail;
  const error = task.querySelector(":scope > div > .error");
  if (error && error.id !== "note-error") {
    error.hidden = !check.error;
    error.textContent = check.error || "";
  }
}

function renderReading(reading) {
  renderTask("reading", reading);
  $("start").hidden = reading.state !== "idle";
  $("note-form").hidden = reading.state !== "note";
  $("timer").hidden = reading.state !== "running";
  timerEndsAt = reading.state === "running" ? Date.now() + reading.remaining_seconds * 1000 : null;
  tickTimer();
}

function tickTimer() {
  if (timerEndsAt === null) return;
  const left = Math.ceil((timerEndsAt - Date.now()) / 1000);
  $("timer").textContent = formatTime(left);
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

async function render(status) {
  const checks = Object.values(status.checks);
  const finished = checks.filter((check) => check.done).length;
  const allDone = finished === checks.length;
  $("offline").hidden = true;
  $("progress").textContent = `${finished} von ${checks.length} erledigt`;
  $("title").textContent = title(status, allDone);
  renderJoker(status.joker, allDone);
  renderTask("anki", status.checks.anki);
  renderTask("leetcode", status.checks.leetcode);
  renderReading(status.checks.reading);
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

$("start").addEventListener("click", async () => {
  await post("/reading/start");
  await refresh();
});

$("note-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  $("note-error").hidden = true;
  try {
    await post("/reading/finish", { note: $("note").value });
    await refresh();
  } catch (error) {
    $("note-error").textContent = error.message;
    $("note-error").hidden = false;
  }
});

$("refresh").addEventListener("click", () => refresh(true));

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

setInterval(tickTimer, 1000);
setInterval(refresh, POLL_MS);
refresh();
