const API = "http://127.0.0.1:47615";
const SVG_NS = "http://www.w3.org/2000/svg";
const WIDTH = 540;
const LANE_X0 = 40;
const LANE_GAP = 36;
const LABEL_X = 228;
const ROW_H = 50;
const STAGE_H = 40;
const NODE_R = 12;
const LANE_COLORS = 5;
const $ = (id) => document.getElementById(id);

let data = null;
let current = 0;      // index of the visible path
let selected = null;  // paper id
let editing = false;
let comparing = false; // review: recall written, old notes revealed

function svg(tag, attrs = {}, parent = null) {
  const element = document.createElementNS(SVG_NS, tag);
  for (const [key, value] of Object.entries(attrs)) element.setAttribute(key, value);
  if (parent) parent.append(element);
  return element;
}

function paths() {
  return data.plan.paths;
}

function path() {
  return paths()[current];
}

function laneColor(lanePath, lane) {
  const index = lanePath.lanes.findIndex((entry) => entry.id === lane);
  return `var(--lane-${Math.max(0, index) % LANE_COLORS})`;
}

function germanDate(iso) {
  const [year, month, day] = iso.split("-");
  return `${day}.${month}.${year}`;
}

function isDue(id) {
  return Boolean(data.review && data.review.due.includes(id));
}

function paperById(id) {
  for (const entry of paths()) {
    const paper = entry.papers.find((candidate) => candidate.id === id);
    if (paper) return paper;
  }
  return null;
}

function openPaper(id) {
  if (!path().papers.some((paper) => paper.id === id)) {
    const index = paths().findIndex((entry) => entry.papers.some((paper) => paper.id === id));
    if (index >= 0) goTo(index);
  }
  select(id);
  $("panel").scrollIntoView({ block: "nearest", behavior: "smooth" });
}

function renderReviewBox() {
  const due = data.review ? data.review.due : [];
  $("review-box").hidden = due.length === 0;
  $("review-list").replaceChildren(...due.map((id) => {
    const item = document.createElement("li");
    const button = document.createElement("button");
    button.type = "button";
    button.textContent = `↻ ${paperById(id)?.short || id}`;
    button.addEventListener("click", () => openPaper(id));
    item.append(button);
    return item;
  }));
}

function nextUnread(inPath) {
  return inPath.papers.find((paper) => !data.progress[paper.id]);
}

function relationsOf(inPath, id) {
  const out = [];
  for (const paper of inPath.papers) {
    for (const relation of paper.related || []) {
      if (paper.id === id) out.push({ other: relation.id, why: relation.why });
      else if (relation.id === id) out.push({ other: paper.id, why: relation.why });
    }
  }
  return out;
}

// Rows in reading order, with a header row before each stage.
function layout(inPath) {
  const lanes = Object.fromEntries(inPath.lanes.map((lane, index) => [lane.id, LANE_X0 + index * LANE_GAP]));
  const positions = {};
  const stages = [];
  let y = 8;
  let stage = null;
  inPath.papers.forEach((paper, index) => {
    if (paper.stage !== stage) {
      stage = paper.stage;
      stages.push({ stage, top: y });
      y += STAGE_H;
    }
    positions[paper.id] = { x: lanes[paper.lane] ?? LANE_X0, y: y + ROW_H / 2, index };
    y += ROW_H;
  });
  return { lanes, positions, stages, height: y + 8 };
}

function drawGraph(inPath, graph) {
  const { lanes, positions, stages, height } = layout(inPath);
  graph.replaceChildren();
  graph.setAttribute("viewBox", `0 0 ${WIDTH} ${height}`);
  svg("title", {}, graph).textContent = `Lesepfad „${inPath.title}“ mit Bezügen zwischen den Papern`;

  for (const entry of stages) {
    svg("rect", { class: "stage-band", x: 0, y: entry.top, width: WIDTH, height: STAGE_H - 6 }, graph);
  }
  for (const x of Object.values(lanes)) {
    svg("line", { class: "lane-guide", x1: x, x2: x, y1: stages[0].top + STAGE_H, y2: height - 8 }, graph);
  }

  const relationLayer = svg("g", {}, graph);
  for (const paper of inPath.papers) {
    for (const relation of paper.related || []) {
      const a = positions[paper.id];
      const b = positions[relation.id];
      if (!b) continue;
      const bend = Math.max(6, Math.min(a.x, b.x) - 22 - Math.abs(a.y - b.y) * 0.04);
      const active = selected === paper.id || selected === relation.id;
      svg("path", {
        class: `relation${active ? " active" : ""}`,
        d: `M ${a.x} ${a.y} C ${bend} ${a.y}, ${bend} ${b.y}, ${b.x} ${b.y}`,
      }, relationLayer);
    }
  }

  const papers = inPath.papers;
  for (let i = 1; i < papers.length; i++) {
    const a = positions[papers[i - 1].id];
    const b = positions[papers[i].id];
    const middle = (a.y + b.y) / 2;
    const done = data.progress[papers[i - 1].id] && data.progress[papers[i].id];
    svg("path", { class: `route${done ? " done" : ""}`, d: `M ${a.x} ${a.y} C ${a.x} ${middle}, ${b.x} ${middle}, ${b.x} ${b.y}` }, graph);
  }

  const next = nextUnread(inPath);
  papers.forEach((paper, index) => {
    const { x, y } = positions[paper.id];
    const read = data.progress[paper.id];
    const color = laneColor(inPath, paper.lane);
    const row = svg("g", { class: `row${read ? " read" : ""}${selected === paper.id ? " selected" : ""}`, tabindex: 0, role: "button" }, graph);
    row.setAttribute("aria-label", `${index + 1}. ${paper.short}${read ? ", gelesen" : ""}`);
    svg("rect", { class: "row-hit", x: 0, y: y - ROW_H / 2 + 2, width: WIDTH, height: ROW_H - 4, rx: 6 }, row);
    if (next && next.id === paper.id) svg("circle", { class: "node-next", cx: x, cy: y, r: NODE_R + 6 }, row);
    const ring = svg("circle", { class: "node-ring", cx: x, cy: y, r: NODE_R }, row);
    ring.style.stroke = color;
    if (read) {
      ring.style.fill = color;
      svg("path", { class: "node-check", d: `M ${x - 5} ${y} l 3.5 3.5 l 6.5 -7` }, row);
    }
    const title = svg("text", { class: "row-title", x: LABEL_X, y: y - 3 }, row);
    title.textContent = `${index + 1}. ${paper.short}`;
    const sub = svg("text", { class: "row-sub", x: LABEL_X, y: y + 14 }, row);
    const due = read && isDue(paper.id);
    sub.textContent = due ? `↻ heute wiederholen · ${paper.source}`
      : read ? `✓ gelesen am ${germanDate(read.read_on)} · ${paper.source}` : paper.source;
    if (due) sub.classList.add("due");
    const tip = svg("title", {}, row);
    // No peeking at the notes while a review is due.
    tip.textContent = read && !due ? `${paper.short}\n\n${read.summary}` : `${paper.short}: ${paper.why}`;
    row.addEventListener("click", () => select(paper.id));
    row.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        select(paper.id);
      }
    });
  });

  // Labels last, so relation curves pass behind them.
  for (const entry of stages) {
    const label = svg("text", { class: "stage-label", x: 16, y: entry.top + 22 }, graph);
    label.textContent = inPath.stages[String(entry.stage)] || `Stufe ${entry.stage}`;
  }
}

function buildTrack() {
  $("track").replaceChildren(...paths().map((entry) => {
    const slide = document.createElement("div");
    slide.className = "slide";
    const graph = svg("svg", { class: "graph", role: "img" });
    graph.dataset.path = entry.id;
    slide.append(graph);
    return slide;
  }));
  $("dots").replaceChildren(...paths().map((entry, index) => {
    const dot = document.createElement("button");
    dot.type = "button";
    dot.className = "dot-button";
    dot.setAttribute("aria-label", entry.title);
    dot.title = entry.title;
    dot.addEventListener("click", () => goTo(index));
    return dot;
  }));
}

function drawAll() {
  const graphs = $("track").querySelectorAll("svg.graph");
  paths().forEach((entry, index) => drawGraph(entry, graphs[index]));
}

function updateCount(input, countId, minimum) {
  const length = input.value.trim().replace(/\s+/g, " ").length;
  const count = $(countId);
  count.textContent = length >= minimum ? `${length} Zeichen ✓` : `${length}/${minimum} Zeichen`;
  count.classList.toggle("ok", length >= minimum);
}

function renderPanel() {
  const inPath = path();
  const paper = inPath.papers.find((entry) => entry.id === selected);
  if (!paper) return;
  const index = inPath.papers.indexOf(paper);
  const lane = inPath.lanes.find((entry) => entry.id === paper.lane);
  const read = data.progress[paper.id];
  const elsewhere = paths().filter((entry) => entry !== inPath && entry.papers.some((other) => other.id === paper.id));
  $("panel").hidden = false;
  $("p-meta").textContent = `#${index + 1} · ${inPath.stages[String(paper.stage)] || `Stufe ${paper.stage}`} · ${lane ? lane.title : paper.lane}`;
  $("p-meta").style.color = laneColor(inPath, paper.lane);
  $("p-title").textContent = paper.title;
  $("p-source").textContent = paper.source;
  $("p-link").href = paper.url;
  $("p-why").textContent = paper.why;
  $("p-elsewhere").hidden = elsewhere.length === 0;
  $("p-elsewhere").textContent = `Auch im Pfad: ${elsewhere.map((entry) => entry.title).join(", ")}`;

  const related = relationsOf(inPath, paper.id);
  $("p-related-box").hidden = related.length === 0;
  $("p-related").replaceChildren(...related.map(({ other, why }) => {
    const target = inPath.papers.find((entry) => entry.id === other);
    const item = document.createElement("li");
    const button = document.createElement("button");
    button.type = "button";
    button.textContent = `${inPath.papers.indexOf(target) + 1}. ${target.short}`;
    button.addEventListener("click", () => select(other));
    const reason = document.createElement("span");
    reason.textContent = `: ${why}`;
    item.append(button, reason);
    return item;
  }));

  const due = Boolean(read) && isDue(paper.id);
  $("p-notes").hidden = !read || editing || due;
  if (read) {
    $("p-read-on").textContent = `Gelesen am ${germanDate(read.read_on)}`;
    $("p-summary").textContent = read.summary;
    $("p-takeaway").textContent = read.takeaway;
    const reviews = (read.reviews || []).map((review) => `${germanDate(review.on)}: ${review.rating}`);
    const next = data.review && data.review.next[paper.id];
    const parts = [];
    if (reviews.length) parts.push(`Wiederholt: ${reviews.join(" · ")}`);
    if (data.review) parts.push(next ? `Nächste Wiederholung am ${germanDate(next)}` : "Alle Wiederholungen geschafft");
    $("p-reviews").textContent = parts.join(" — ");
    $("p-reviews").hidden = parts.length === 0;
  }
  $("r-form").hidden = !due;
  $("r-result").hidden = !comparing;
  $("r-compare").hidden = comparing;
  $("r-recall").readOnly = comparing;
  if (due && comparing) {
    $("r-old-summary").textContent = read.summary;
    $("r-old-takeaway").textContent = `Für Lean-CL-Eval: ${read.takeaway}`;
  }
  $("r-error").hidden = true;
  $("p-form").hidden = due || (Boolean(read) && !editing);
  $("p-cancel").hidden = !read;
  $("p-submit").textContent = read ? "Notizen speichern" : "Als gelesen abhaken";
  $("p-error").hidden = true;
}

function select(id) {
  if (selected !== id) {
    editing = false;
    const read = data.progress[id];
    $("p-summary-input").value = read ? read.summary : "";
    $("p-takeaway-input").value = read ? read.takeaway : "";
    comparing = false;
    $("r-recall").value = "";
  }
  selected = id;
  updateCount($("p-summary-input"), "p-summary-count", data.min_summary_chars);
  updateCount($("p-takeaway-input"), "p-takeaway-count", data.min_takeaway_chars);
  if (data.review) updateCount($("r-recall"), "r-count", data.review.min_recall_chars);
  drawAll();
  renderPanel();
}

function renderSummary() {
  const inPath = path();
  const total = inPath.papers.length;
  const done = inPath.papers.filter((paper) => data.progress[paper.id]).length;
  const today = Object.values(data.progress).some((entry) => entry.read_on === data.today);
  $("summary").textContent = `${done} von ${total} in diesem Pfad gelesen · Heute: ${today ? "✓ Paper gelesen" : "noch offen"}`;
  $("path-title").textContent = inPath.title;
  $("path-source").textContent = inPath.source ? `Quelle: ${inPath.source}` : "";
  $("prev").disabled = current === 0;
  $("next").disabled = current === paths().length - 1;
  $("dots").querySelectorAll("button").forEach((dot, index) => dot.setAttribute("aria-current", String(index === current)));
  $("legend").replaceChildren(...inPath.lanes.map((lane) => {
    const item = document.createElement("li");
    const dot = document.createElement("span");
    dot.className = "dot";
    dot.style.background = laneColor(inPath, lane.id);
    item.append(dot, lane.title);
    return item;
  }));
}

// Called whenever the visible path changes, by swipe, button, dot or key.
function showPath(index) {
  if (index === current && selected) return;
  current = index;
  try { history.replaceState(null, "", `#${path().id}`); } catch { /* ignore */ }
  renderSummary();
  if (!path().papers.some((paper) => paper.id === selected)) {
    select((nextUnread(path()) || path().papers[0]).id);
  } else {
    renderPanel();
  }
}

function goTo(index, smooth = true) {
  const clamped = Math.max(0, Math.min(paths().length - 1, index));
  const track = $("track");
  track.scrollTo({ left: clamped * track.clientWidth, behavior: smooth ? "smooth" : "auto" });
  showPath(clamped);
}

let scrollTimer = null;
function onScroll() {
  clearTimeout(scrollTimer);
  scrollTimer = setTimeout(() => {
    const track = $("track");
    const index = Math.round(track.scrollLeft / Math.max(1, track.clientWidth));
    if (index !== current) showPath(index);
  }, 90);
}

async function load() {
  try {
    const response = await fetch(`${API}/papers/data`, { cache: "no-store" });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.error);
    data = payload;
  } catch (error) {
    $("summary").textContent = "";
    $("load-error").textContent = `Lesepfad nicht erreichbar: ${error.message}`;
    $("load-error").hidden = false;
    return;
  }
  buildTrack();
  renderReviewBox();
  const wanted = decodeURIComponent(location.hash.slice(1)) || data.plan.default;
  const start = Math.max(0, paths().findIndex((entry) => entry.id === wanted));
  current = -1;
  goTo(start, false);
}

$("track").addEventListener("scroll", onScroll, { passive: true });
$("prev").addEventListener("click", () => goTo(current - 1));
$("next").addEventListener("click", () => goTo(current + 1));
document.addEventListener("keydown", (event) => {
  if (!data || (event.target instanceof Element && event.target.closest("textarea, input, button"))) return;
  if (event.key === "ArrowLeft") goTo(current - 1);
  if (event.key === "ArrowRight") goTo(current + 1);
});
window.addEventListener("resize", () => { if (data) $("track").scrollLeft = current * $("track").clientWidth; });

$("p-summary-input").addEventListener("input", (event) => updateCount(event.target, "p-summary-count", data.min_summary_chars));
$("p-takeaway-input").addEventListener("input", (event) => updateCount(event.target, "p-takeaway-count", data.min_takeaway_chars));
$("p-edit").addEventListener("click", () => {
  editing = true;
  renderPanel();
  $("p-summary-input").focus();
});
$("p-cancel").addEventListener("click", () => {
  editing = false;
  renderPanel();
});
$("p-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  $("p-error").hidden = true;
  try {
    const response = await fetch(`${API}/papers/${selected}/read`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ summary: $("p-summary-input").value, takeaway: $("p-takeaway-input").value }),
    });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.error);
    data = payload;
    editing = false;
    renderSummary();
    renderReviewBox();
    drawAll();
    renderPanel();
  } catch (error) {
    $("p-error").textContent = error.message;
    $("p-error").hidden = false;
  }
});

$("r-recall").addEventListener("input", (event) => updateCount(event.target, "r-count", data.review.min_recall_chars));
$("r-form").addEventListener("submit", (event) => {
  event.preventDefault();
  const length = $("r-recall").value.trim().replace(/\s+/g, " ").length;
  if (length < data.review.min_recall_chars) {
    $("r-error").textContent = `Schreib erst mindestens ${data.review.min_recall_chars} Zeichen aus dem Kopf.`;
    $("r-error").hidden = false;
    return;
  }
  comparing = true;
  renderPanel();
});
for (const button of document.querySelectorAll(".ratings button")) {
  button.addEventListener("click", async () => {
    try {
      const response = await fetch(`${API}/papers/${selected}/review`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ recall: $("r-recall").value, rating: button.dataset.rating }),
      });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.error);
      data = payload;
      comparing = false;
      $("r-recall").value = "";
      renderSummary();
      renderReviewBox();
      drawAll();
      renderPanel();
    } catch (error) {
      $("r-error").textContent = error.message;
      $("r-error").hidden = false;
    }
  });
}

load();
