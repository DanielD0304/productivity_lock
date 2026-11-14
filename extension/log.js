const API = "http://127.0.0.1:47615";
const WEEKDAYS = ["So", "Mo", "Di", "Mi", "Do", "Fr", "Sa"];
const $ = (id) => document.getElementById(id);
const KEYS = ["done", "result", "next"];

let data = null;

function germanDate(iso, withWeekday = true) {
  const [year, month, day] = iso.split("-").map(Number);
  const weekday = WEEKDAYS[new Date(year, month - 1, day).getDay()];
  const text = `${String(day).padStart(2, "0")}.${String(month).padStart(2, "0")}.${year}`;
  return withWeekday ? `${weekday} ${text}` : text;
}

function minimum(key) {
  return key === "done" ? data.min_done_chars : data.min_other_chars;
}

function updateCount(key) {
  const length = $(`f-${key}`).value.trim().replace(/\s+/g, " ").length;
  const count = $(`c-${key}`);
  const need = minimum(key);
  count.textContent = length >= need ? `${length} Zeichen ✓` : `${length}/${need} Zeichen`;
  count.classList.toggle("ok", length >= need);
}

function render() {
  const todayEntry = data.entries.find((entry) => entry.day === data.today);
  const file = data.file ? ` · Datei: ${data.file}` : "";
  $("summary").textContent = `${data.entries.length} Einträge · Heute: ${todayEntry ? "✓ geschrieben" : "noch offen"}${file}`;
  $("form-title").textContent = `Heute, ${germanDate(data.today)}`;
  $("submit").textContent = todayEntry ? "Eintrag aktualisieren" : "Eintrag speichern";
  $("empty").hidden = data.entries.length > 0;
  $("entries").replaceChildren(...data.entries.map((entry) => {
    const item = document.createElement("li");
    item.className = "entry";
    const heading = document.createElement("h3");
    heading.textContent = germanDate(entry.day);
    const list = document.createElement("dl");
    for (const key of KEYS) {
      const term = document.createElement("dt");
      term.textContent = data.fields[key];
      const value = document.createElement("dd");
      value.textContent = entry[key];
      list.append(term, value);
    }
    item.append(heading, list);
    return item;
  }));
}

function fillForm() {
  const todayEntry = data.entries.find((entry) => entry.day === data.today);
  for (const key of KEYS) {
    $(`f-${key}`).value = todayEntry ? todayEntry[key] : "";
    updateCount(key);
  }
}

function exportText(since) {
  const entries = data.entries.filter((entry) => !since || entry.day >= since).reverse();
  return entries.map((entry) => [
    `${germanDate(entry.day)}`,
    ...KEYS.map((key) => `- ${data.fields[key]}: ${entry[key]}`),
  ].join("\n")).join("\n\n");
}

async function load() {
  try {
    const response = await fetch(`${API}/log/data`, { cache: "no-store" });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.error);
    data = payload;
  } catch (error) {
    $("summary").textContent = "";
    $("load-error").textContent = `Forschungslog nicht erreichbar: ${error.message}`;
    $("load-error").hidden = false;
    return;
  }
  $("content").hidden = false;
  const weekAgo = new Date();
  weekAgo.setDate(weekAgo.getDate() - 7);
  $("since").value = weekAgo.toISOString().slice(0, 10);
  fillForm();
  render();
}

for (const key of KEYS) $(`f-${key}`).addEventListener("input", () => updateCount(key));

$("form").addEventListener("submit", async (event) => {
  event.preventDefault();
  $("form-error").hidden = true;
  $("saved").hidden = true;
  try {
    const body = Object.fromEntries(KEYS.map((key) => [key, $(`f-${key}`).value]));
    const response = await fetch(`${API}/log`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.error);
    data = payload;
    render();
    $("saved").textContent = data.file ? "Gespeichert, auch in der Markdown-Datei." : "Gespeichert.";
    $("saved").hidden = false;
  } catch (error) {
    $("form-error").textContent = error.message;
    $("form-error").hidden = false;
  }
});

$("copy").addEventListener("click", async () => {
  const text = exportText($("since").value);
  if (!text) {
    $("copied").textContent = "Keine Einträge in diesem Zeitraum.";
    return;
  }
  try {
    await navigator.clipboard.writeText(text);
    $("copied").textContent = "Kopiert.";
  } catch {
    $("copied").textContent = "Kopieren ging nicht.";
  }
});

load();
