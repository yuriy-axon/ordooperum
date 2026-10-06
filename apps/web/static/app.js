const PRIORITIES = [
  { id: "P1", label: "Critical", meaning: "As soon as possible" },
  { id: "P2", label: "High", meaning: "Days" },
  { id: "P3", label: "Normal", meaning: "Weeks" },
  { id: "P4", label: "Low", meaning: "Months" },
  { id: "P5", label: "Not important", meaning: "Maybe next year" },
];

const state = { view: "priority", week: null, status: "open", tier: "all", tasks: [] };
const $ = id => document.getElementById(id);
const board = $("board");
const summary = $("summary");

// ---------- dates and ISO weeks (Monday start) ----------

const DAY = 86400000;
const pad = n => String(n).padStart(2, "0");
const ymd = d => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
const localDate = s => { const [y, m, d] = s.split("-").map(Number); return new Date(y, m - 1, d); };

function isoWeek(d) {
  const t = new Date(Date.UTC(d.getFullYear(), d.getMonth(), d.getDate()));
  t.setUTCDate(t.getUTCDate() + 4 - (t.getUTCDay() || 7)); // Thursday of this week
  const year = t.getUTCFullYear();
  const week = Math.ceil(((t - Date.UTC(year, 0, 1)) / DAY + 1) / 7);
  return `${year}-W${pad(week)}`;
}

function mondayOf(key) {
  const [year, week] = key.split("-W").map(Number);
  const jan4 = new Date(year, 0, 4);
  const monday = new Date(year, 0, 4 - ((jan4.getDay() || 7) - 1));
  monday.setDate(monday.getDate() + (week - 1) * 7);
  return monday;
}

function shiftWeek(key, n) {
  const d = mondayOf(key);
  d.setDate(d.getDate() + 7 * n);
  return isoWeek(d);
}

const weekNum = key => Number(key.split("-W")[1]);
const today = ymd(new Date());
const thisWeek = isoWeek(new Date());

function weekRange(key) {
  const start = mondayOf(key);
  const end = new Date(start); end.setDate(end.getDate() + 6);
  const fmt = (d, opts) => d.toLocaleDateString("en-GB", opts);
  return `${fmt(start, { day: "numeric", month: "short" })} – ${fmt(end, { day: "numeric", month: "short", year: "numeric" })}`;
}

// Which week a task belongs to — see docs/data-model.md.
function taskWeek(t) {
  if (t.is_closed) return t.closed ? isoWeek(new Date(t.closed)) : null;
  if (t.week) return t.week;
  if (t.due) return isoWeek(localDate(t.due));
  return null;
}

// ---------- rendering helpers ----------

function esc(s) {
  return String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

// Minimal Markdown: bullets, quotes, links, bold. Input is escaped first.
function md(text) {
  const inline = s => esc(s)
    .replace(/\[([^\]]+)\]\((https?:\/\/[^)\s]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>')
    .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
  const out = [];
  let list = null, quote = null;
  const flush = () => {
    if (list) { out.push(`<ul>${list.join("")}</ul>`); list = null; }
    if (quote) { out.push(`<blockquote>${quote.join("<br>")}</blockquote>`); quote = null; }
  };
  for (const line of (text || "").split("\n")) {
    if (/^\s*- /.test(line)) { if (quote) flush(); (list ||= []).push(`<li>${inline(line.replace(/^\s*- /, ""))}</li>`); }
    else if (/^>\s?/.test(line)) { if (list) flush(); (quote ||= []).push(inline(line.replace(/^>\s?/, ""))); }
    else if (line.trim()) { flush(); out.push(`<p>${inline(line)}</p>`); }
    else flush();
  }
  flush();
  return out.join("");
}

const plural = (n, word) => `${n} ${word}${n === 1 ? "" : "s"}`;
const priorityRank = t => PRIORITIES.findIndex(p => p.id === t.priority);

function byDueThenId(a, b) {
  if (a.due !== b.due) {
    if (!a.due) return 1;
    if (!b.due) return -1;
    return a.due < b.due ? -1 : 1;
  }
  return a.id < b.id ? -1 : 1;
}
const byPriorityThenDue = (a, b) => priorityRank(a) - priorityRank(b) || byDueThenId(a, b);

function taskCard(t, { badge = false } = {}) {
  const overdue = t.due && !t.is_closed && t.due < today;
  const due = t.due ? `<span class="${overdue ? "overdue" : ""}">Due ${esc(t.due)}${overdue ? " · overdue" : ""}</span>` : "";
  const week = t.week ? `<span>${t.pinned === "true" ? "📌 " : ""}Week ${weekNum(t.week)}</span>` : "";
  return `
    <details class="task ${t.priority.toLowerCase()} ${t.is_closed ? "closed" : ""}" data-id="${esc(t.id)}">
      <summary>
        ${badge ? `<span class="badge">${esc(t.priority)}</span>` : ""}
        <span class="title">${esc(t.title)}</span>
        <span class="meta">
          <span>${esc(t.id)}</span>
          <span>${esc(t.project_name)} · ${esc(t.tier)}</span>
          ${due}${week}
          <span class="status">${esc(t.status.replace("-", " "))}</span>
        </span>
      </summary>
      <div class="detail">
        <h3>Description</h3>${md(t.description)}
        <h3>Additional information</h3>${md(t.additional_info)}
        ${editor(t)}
      </div>
    </details>`;
}

function editor(t) {
  const actions = t.is_closed
    ? [["new", "Reopen"]]
    : [["done", "Mark done"], ...(t.status === "new" ? [["in-progress", "Start"]] : []), ["cancelled", "Cancel task"]];
  const weeks = [...new Set([thisWeek, ...Array.from({ length: 13 }, (_, i) => shiftWeek(thisWeek, i)), t.week].filter(Boolean))].sort();
  return `
    <div class="editor">
      <div class="actions">
        ${actions.map(([s, l]) => `<button data-set="status" data-value="${s}" class="${s === "done" ? "primary" : ""}">${l}</button>`).join("")}
      </div>
      <label>Priority
        <select data-set="priority">
          ${PRIORITIES.map(p => `<option value="${p.id}" ${p.id === t.priority ? "selected" : ""}>${p.id} · ${p.label}</option>`).join("")}
        </select>
      </label>
      <label>Due
        <input type="date" data-set="due" value="${esc(t.due || "")}">
      </label>
      <label>Week
        <select data-set="week">
          <option value="" ${t.week ? "" : "selected"}>Not planned</option>
          ${weeks.map(w => `<option value="${w}" ${w === t.week ? "selected" : ""}>Week ${weekNum(w)} · ${weekRange(w)}</option>`).join("")}
        </select>
      </label>
      <p class="edit-error" hidden></p>
    </div>`;
}

async function save(id, field, value, card) {
  const err = card.querySelector(".edit-error");
  try {
    const res = await fetch(`/api/tasks/${id}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ [field]: value || null }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || `HTTP ${res.status}`);
    await load();
  } catch (e) {
    err.textContent = `Not saved: ${e.message}`;
    err.hidden = false;
  }
}

board.addEventListener("click", e => {
  const btn = e.target.closest("button[data-set]");
  if (btn) save(btn.closest(".task").dataset.id, btn.dataset.set, btn.dataset.value, btn.closest(".task"));
});
board.addEventListener("change", e => {
  const el = e.target.closest("[data-set]");
  if (el && el.tagName !== "BUTTON") save(el.closest(".task").dataset.id, el.dataset.set, el.value, el.closest(".task"));
});

function section(title, tasks, { cls = "" } = {}) {
  if (!tasks.length) return "";
  return `
    <section class="group ${cls}">
      <div class="section-head"><h2>${title}</h2><span class="count">${tasks.length}</span></div>
      ${tasks.sort(byPriorityThenDue).map(t => taskCard(t, { badge: true })).join("")}
    </section>`;
}

// ---------- views ----------

const byTier = t => state.tier === "all" || t.tier === state.tier;

function renderPriority() {
  const tasks = state.tasks.filter(t =>
    byTier(t) && (state.status === "all" || (state.status === "closed") === t.is_closed));
  const label = state.status === "all" ? "" : ` ${state.status}`;
  summary.textContent = `${tasks.length}${label} task${tasks.length === 1 ? "" : "s"}`;
  if (!tasks.length) { board.innerHTML = `<p class="empty">No tasks here.</p>`; return; }
  board.innerHTML = PRIORITIES.map(p => {
    const group = tasks.filter(t => t.priority === p.id).sort(byDueThenId);
    if (!group.length) return "";
    return `
      <section class="group ${p.id.toLowerCase()}">
        <div class="group-head">
          <span class="badge">${p.id}</span>
          <h2>${p.label}</h2>
          <span class="meaning">${p.meaning}</span>
          <span class="count">${group.length}</span>
        </div>
        ${group.map(t => taskCard(t)).join("")}
      </section>`;
  }).join("");
}

function renderWeek() {
  const key = state.week;
  const isCurrent = key === thisWeek, isPast = key < thisWeek;
  $("week-title").textContent = `Week ${weekNum(key)}${isCurrent ? " · this week" : ""}`;
  $("week-range").textContent = weekRange(key);
  $("week-today").hidden = isCurrent;

  const tasks = state.tasks.filter(byTier);
  const inWeek = tasks.filter(t => taskWeek(t) === key);
  const open = inWeek.filter(t => !t.is_closed);
  const done = inWeek.filter(t => t.is_closed);
  const carried = isCurrent ? tasks.filter(t => !t.is_closed && taskWeek(t) && taskWeek(t) < key) : [];
  const unscheduled = isCurrent ? tasks.filter(t => !t.is_closed && !taskWeek(t)) : [];

  const parts = [];
  if (carried.length) parts.push(`${carried.length} carried over`);
  parts.push(`${open.length} ${isPast ? "not done" : isCurrent ? "to do" : "planned"}`);
  parts.push(`${done.length} done`);
  summary.textContent = parts.join(" · ");

  const html = [
    section("Carried over from earlier weeks", carried, { cls: "carried" }),
    section(isPast ? "Not done" : isCurrent ? "To do" : "Planned", open),
    section("Done", done),
  ].join("");

  const unscheduledHtml = unscheduled.length ? `
    <details class="group unscheduled">
      <summary>${plural(unscheduled.length, "open task")} not planned for any week</summary>
      ${unscheduled.sort(byPriorityThenDue).map(t => taskCard(t, { badge: true })).join("")}
    </details>` : "";

  board.innerHTML = (html || `<p class="empty">Nothing ${isPast ? "was" : "is"} planned for week ${weekNum(key)}.</p>`) + unscheduledHtml;
}

function render() {
  const openIds = new Set([...board.querySelectorAll("details.task[open]")].map(d => d.dataset.id));
  const unscheduledOpen = board.querySelector(".unscheduled")?.open;
  document.querySelectorAll(".tabs a").forEach(a => {
    if (a.dataset.view === state.view) a.setAttribute("aria-current", "page");
    else a.removeAttribute("aria-current");
  });
  document.querySelector("[data-filter='status']").hidden = state.view === "week";
  $("week-nav").hidden = state.view !== "week";
  state.view === "week" ? renderWeek() : renderPriority();
  board.querySelectorAll("details.task").forEach(d => { if (openIds.has(d.dataset.id)) d.open = true; });
  const u = board.querySelector(".unscheduled");
  if (u && unscheduledOpen) u.open = true;
}

// ---------- navigation (URL hash: #priority, #week, #week/2026-W41) ----------

function readHash() {
  const [view, week] = location.hash.replace(/^#/, "").split("/");
  state.view = view === "week" ? "week" : "priority";
  state.week = /^\d{4}-W\d{2}$/.test(week || "") ? week : thisWeek;
  render();
}

const goWeek = key => { location.hash = key === thisWeek ? "week" : `week/${key}`; };
$("week-prev").onclick = () => goWeek(shiftWeek(state.week, -1));
$("week-next").onclick = () => goWeek(shiftWeek(state.week, 1));
$("week-today").onclick = () => goWeek(thisWeek);
$("week-tab").textContent = `Week ${weekNum(thisWeek)}`;

document.querySelectorAll(".seg").forEach(seg => {
  seg.addEventListener("click", e => {
    const btn = e.target.closest("button");
    if (!btn) return;
    seg.querySelectorAll("button").forEach(b => b.setAttribute("aria-pressed", String(b === btn)));
    state[seg.dataset.filter] = btn.dataset.value;
    render();
  });
});

document.addEventListener("keydown", e => {
  if (state.view !== "week" || e.target.closest("input, textarea")) return;
  if (e.key === "ArrowLeft") $("week-prev").click();
  if (e.key === "ArrowRight") $("week-next").click();
});

async function load() {
  try {
    const res = await fetch("/api/tasks", { cache: "no-store" });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    state.tasks = (await res.json()).tasks;
    render();
  } catch (err) {
    board.innerHTML = `<p class="error">Could not load tasks: ${esc(err.message)}</p>`;
  }
}

window.addEventListener("hashchange", readHash);
window.addEventListener("focus", load); // pick up tasks added by agents while the page was in the background
readHash();
load();
