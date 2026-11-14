const API = "http://127.0.0.1:47615";
const WEEKDAYS = ["So", "Mo", "Di", "Mi", "Do", "Fr", "Sa"];
const STRIP_DAYS = 84;
const $ = (id) => document.getElementById(id);

let data = null;

function parse(iso) {
  const [year, month, day] = iso.split("-").map(Number);
  return new Date(year, month - 1, day);
}

function germanDate(iso) {
  const date = parse(iso);
  return `${WEEKDAYS[date.getDay()]} ${String(date.getDate()).padStart(2, "0")}.${String(date.getMonth() + 1).padStart(2, "0")}.${date.getFullYear()}`;
}

function shortDate(iso) {
  const date = parse(iso);
  return `${date.getDate()}.${date.getMonth() + 1}.`;
}

function rangeText(event) {
  return event.end ? `${germanDate(event.date)} – ${germanDate(event.end)}` : germanDate(event.date);
}

function countdown(event) {
  if (event.state === "running") {
    if (!event.end) return "heute";
    return event.end_days === 0 ? "läuft, endet heute" : `läuft noch ${event.end_days} ${event.end_days === 1 ? "Tag" : "Tage"}`;
  }
  if (event.state === "past") {
    const ago = -event.end_days;
    return ago === 1 ? "gestern" : `vor ${ago} Tagen`;
  }
  if (event.days === 1) return "morgen";
  return `in ${event.days} Tagen`;
}

function kindColor(kind) {
  return `var(--kind-${kind}, var(--muted))`;
}

function eventItem(event) {
  const item = document.createElement("li");
  item.className = `event ${event.state}`;
  const when = document.createElement("div");
  when.className = "when";
  when.textContent = countdown(event);
  const small = document.createElement("small");
  small.textContent = event.end ? `${shortDate(event.date)}–${shortDate(event.end)}` : shortDate(event.date);
  when.append(small);

  const body = document.createElement("div");
  const chip = document.createElement("span");
  chip.className = "chip";
  chip.style.background = kindColor(event.kind);
  chip.textContent = data.kinds[event.kind] || event.kind;
  const title = document.createElement("h3");
  title.textContent = event.title;
  const date = document.createElement("p");
  date.className = "note";
  date.textContent = rangeText(event);
  body.append(chip, title, date);
  if (event.note) {
    const note = document.createElement("p");
    note.className = "note";
    note.textContent = event.note;
    body.append(note);
  }

  const actions = document.createElement("div");
  actions.className = "actions";
  if (event.id) {
    const remove = document.createElement("button");
    remove.type = "button";
    remove.className = "quiet danger";
    remove.textContent = "Löschen";
    remove.addEventListener("click", () => removeEvent(event));
    actions.append(remove);
  }
  item.append(when, body, actions);
  return item;
}

function renderHero(upcoming) {
  const next = upcoming[0];
  $("hero").hidden = !next;
  if (!next) return;
  const running = next.state === "running";
  $("hero-days").textContent = running ? (next.end ? next.end_days : 0) : next.days;
  $("hero-unit").textContent = running ? (next.end ? "Tage, bis es vorbei ist" : "heute") : next.days === 1 ? "Tag" : "Tage";
  $("hero-kind").textContent = data.kinds[next.kind] || next.kind;
  $("hero-kind").style.background = kindColor(next.kind);
  $("hero-title").textContent = next.title;
  $("hero-date").textContent = rangeText(next);
  $("hero-note").textContent = next.note || "";
}

function renderStrip() {
  const strip = $("strip");
  strip.replaceChildren();
  const today = parse(data.today);
  const position = (iso) => ((parse(iso) - today) / 86400000 / STRIP_DAYS) * 100;
  const axis = document.createElement("div");
  axis.className = "strip-axis";
  strip.append(axis);
  // A tick on every Monday.
  for (let offset = 0; offset <= STRIP_DAYS; offset++) {
    const day = new Date(today);
    day.setDate(day.getDate() + offset);
    if (day.getDay() !== 1) continue;
    const tick = document.createElement("div");
    tick.className = "strip-week";
    tick.style.left = `${(offset / STRIP_DAYS) * 100}%`;
    const label = document.createElement("span");
    label.textContent = `${day.getDate()}.${day.getMonth() + 1}.`;
    tick.append(label);
    strip.append(tick);
  }
  for (const event of data.events) {
    const start = Math.max(0, position(event.date));
    const end = Math.min(100, position(event.end || event.date));
    if (end < 0 || start > 100) continue;
    if (event.end) {
      const range = document.createElement("div");
      range.className = "strip-range";
      range.style.left = `${start}%`;
      range.style.width = `${Math.max(0.5, end - start)}%`;
      range.style.background = kindColor(event.kind);
      range.title = `${event.title}: ${rangeText(event)}`;
      strip.append(range);
    }
    const dot = document.createElement("div");
    dot.className = "strip-dot";
    dot.style.left = `${start}%`;
    dot.style.background = kindColor(event.kind);
    dot.title = `${event.title}: ${rangeText(event)} (${countdown(event)})`;
    strip.append(dot);
  }
  const marker = document.createElement("div");
  marker.className = "strip-today";
  marker.style.left = "0";
  const label = document.createElement("span");
  label.textContent = "heute";
  marker.append(label);
  strip.append(marker);
}

function render() {
  const upcoming = data.events.filter((event) => event.state !== "past");
  const past = data.events.filter((event) => event.state === "past").reverse();
  const next = upcoming[0];
  $("summary").textContent = next
    ? `${upcoming.length} anstehend · als Nächstes: ${next.title}, ${countdown(next)}`
    : "Keine anstehenden Termine.";
  renderHero(upcoming);
  renderStrip();
  $("upcoming").replaceChildren(...upcoming.map(eventItem));
  $("past-box").hidden = past.length === 0;
  $("past-summary").textContent = `${past.length} vergangene Termine`;
  $("past").replaceChildren(...past.map(eventItem));
}

async function call(path, body) {
  const response = await fetch(`${API}${path}`, body === undefined ? { cache: "no-store" } : {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const payload = await response.json();
  if (!response.ok) throw new Error(payload.error);
  return payload;
}

async function removeEvent(event) {
  if (!confirm(`„${event.title}“ löschen?`)) return;
  try {
    data = await call(`/termine/${event.id}/delete`, {});
    render();
  } catch (error) {
    alert(error.message);
  }
}

async function load() {
  try {
    data = await call("/termine/data");
  } catch (error) {
    $("summary").textContent = "";
    $("load-error").textContent = `Termine nicht erreichbar: ${error.message}`;
    $("load-error").hidden = false;
    return;
  }
  $("content").hidden = false;
  $("t-kind").replaceChildren(...Object.entries(data.kinds).map(([value, label]) => new Option(label, value)));
  render();
}

$("form").addEventListener("submit", async (event) => {
  event.preventDefault();
  $("form-error").hidden = true;
  try {
    data = await call("/termine", {
      title: $("t-title").value,
      date: $("t-date").value,
      end: $("t-end").value || null,
      kind: $("t-kind").value,
      note: $("t-note").value,
    });
    $("form").reset();
    render();
  } catch (error) {
    $("form-error").textContent = error.message;
    $("form-error").hidden = false;
  }
});

load();
