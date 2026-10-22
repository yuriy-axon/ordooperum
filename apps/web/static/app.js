const PRIORITIES = [
  { id: "P1", label: "Critical", meaning: "As soon as possible" },
  { id: "P2", label: "High", meaning: "Days" },
  { id: "P3", label: "Normal", meaning: "Weeks" },
  { id: "P4", label: "Low", meaning: "Months" },
];

const state = { view: "all", week: null, focus: null, status: "all", tier: "all", tasks: [], meetings: [], meetingsByTask: {}, drafts: {} };
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

const inProgress = t => t.status === "in-progress";

// Earlier weeks an open task was planned for and not finished in, oldest first.
// A weekly instance is never carried over: every week has its own instance.
// An in-progress task continues week after week on purpose, so it doesn't count as carried over either.
function carriedFrom(t) {
  if (t.is_closed || t.series || inProgress(t)) return [];
  return [...new Set((t.weeks || []).filter(w => w < thisWeek))];
}

// Weekly tasks: a series (repeat: weekly) is never planned; each week has its own instance (series: <id>).
const isSeries = t => t.repeat === "weekly";
const instancesOf = s => state.tasks.filter(t => t.series === s.id);
const shortDate = s => localDate(s).toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" });

// ---------- rendering helpers ----------

function esc(s) {
  return String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

// Minimal Markdown: bullets, quotes, links, bold. Input is escaped first.
function md(text) {
  const inline = s => esc(s)
    .replace(/\[([^\]]+)\]\((https?:\/\/[^)\s]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>')
    .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
    .replace(/\bT-\d{4}\b/g, id => `<a class="tref" href="#all/${id}">${id}</a>`);
  const out = [];
  let list = null, quote = null;
  const flush = () => {
    if (list) { out.push(`<ul>${list.join("")}</ul>`); list = null; }
    if (quote) { out.push(`<blockquote>${quote.join("<br>")}</blockquote>`); quote = null; }
  };
  for (const line of (text || "").split("\n")) {
    if (/^###\s+/.test(line)) { flush(); out.push(`<h4>${inline(line.replace(/^###\s+/, ""))}</h4>`); }
    else if (/^\s*- /.test(line)) { if (quote) flush(); (list ||= []).push(`<li>${inline(line.replace(/^\s*- /, ""))}</li>`); }
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

// First line of a description as plain text, for the collapsed view.
function preview(text, max = 110) {
  const line = (text || "").split("\n").find(l => l.trim()) || "";
  const plain = line.replace(/\[([^\]]+)\]\([^)]*\)/g, "$1").replace(/\*\*/g, "").replace(/^[->]\s*/, "").trim();
  return plain.length > max ? plain.slice(0, max).trimEnd() + "…" : plain;
}

function taskCard(t, { badge = false } = {}) {
  const overdue = t.due && !t.is_closed && t.due < today;
  const due = t.due ? `<span class="${overdue ? "overdue" : ""}">Due ${esc(t.due)}${overdue ? " · overdue" : ""}</span>` : "";
  const week = t.week ? `<span>${t.pinned === "true" ? "📌 " : ""}Week ${weekNum(t.week)}</span>` : "";
  const past = carriedFrom(t);
  const meetings = state.meetingsByTask[t.id] || [];
  const meetingChip = meetings.length ? `<span class="meeting-chip">🗓 ${esc(meetings[0].name)}${meetings.length > 1 ? ` +${meetings.length - 1}` : ""}</span>` : "";
  const carried = past.length ? `<span class="carried" title="Planned for ${past.join(", ")} and not done yet">↻ Carried over ${past.length}× · planned ${past.map(w => `W${weekNum(w)}`).join(", ")}</span>` : "";
  let repeat = "";
  if (isSeries(t)) {
    const done = instancesOf(t).filter(i => i.status === "done").length;
    repeat = `<span class="repeat" title="A separate task is created for every week until ${esc(t.repeat_until)}">🔁 Weekly until ${shortDate(t.repeat_until)}${done ? ` · ${plural(done, "week")} done` : ""}</span>`;
  } else if (t.series) {
    const s = state.tasks.find(x => x.id === t.series);
    repeat = `<a class="repeat" href="#all/${esc(t.series)}" title="Weekly instance of ${esc(t.series)}">🔁 ${esc(s ? s.title : t.series)}</a>`;
  }
  return `
    <details class="task ${t.priority.toLowerCase()} ${t.is_closed ? "closed" : ""} ${isSeries(t) ? "series" : ""} ${inProgress(t) ? "in-progress" : ""}" data-id="${esc(t.id)}">
      <summary>
        ${badge ? `<span class="badge">${esc(t.priority)}</span>` : ""}
        <span class="title">${esc(t.title)}</span>
        <span class="meta">
          <span>${esc(t.id)}</span>
          <span>${esc(t.project_name)} · ${esc(t.tier)}</span>
          ${repeat}${due}${week}${carried}${meetingChip}
          ${inProgress(t) ? `<span class="status progress-pill">▶ In progress</span>` : `<span class="status">${esc(t.status.replace("-", " "))}</span>`}
        </span>
      </summary>
      <div class="detail">
        <details class="desc">
          <summary><h3>Description</h3><span class="preview">${esc(preview(t.description))}</span></summary>
          ${md(t.description)}
        </details>
        <h3>Additional information</h3>${md(t.additional_info)}
        ${meetings.length ? `<h3>Meetings</h3><ul>${meetings.map(m => `<li><a href="#meetings/${esc(m.id)}">${esc(m.name)}</a> — ${esc(m.title)} · ${meetingWhen(m)}</li>`).join("")}</ul>` : ""}
        ${editor(t)}
      </div>
    </details>`;
}

// Priority as a row of small colored buttons; the current one is pressed.
function priorityPicker(t) {
  return `<div class="prio-picker" role="group" aria-label="Priority">${PRIORITIES.map(p =>
    `<button type="button" data-set="priority" data-value="${p.id}" class="prio ${p.id.toLowerCase()}" title="${p.id} · ${p.label}" aria-pressed="${p.id === t.priority}">${p.id}</button>`).join("")}</div>`;
}

function editor(t) {
  if (isSeries(t)) {  // a series is never planned or done itself: only its priority, or ending it
    return `
    <div class="editor">
      <div class="actions">
        ${t.is_closed ? "" : `<button data-set="status" data-value="cancelled">End series</button>`}
      </div>
      <div class="field">Priority for new weeks
        ${priorityPicker(t)}
      </div>
      <p class="edit-error" hidden></p>
    </div>`;
  }
  const actions = t.is_closed
    ? [["new", "Reopen"]]
    : [["done", "Mark done"], t.status === "new" ? ["in-progress", "Start · in progress"] : ["new", "Back to to do"], ["cancelled", "Cancel task"]];
  const weeks = [...new Set([thisWeek, ...Array.from({ length: 13 }, (_, i) => shiftWeek(thisWeek, i)), t.week].filter(Boolean))].sort();
  return `
    <div class="editor">
      <div class="actions">
        ${actions.map(([s, l]) => `<button data-set="status" data-value="${s}" class="${s === "done" ? "primary" : ""}">${l}</button>`).join("")}
        ${t.is_closed ? "" : `<button class="icon-btn" data-draft="${esc(t.id)}" title="Draft a message about this task" aria-label="Draft a message">✉</button>`}
      </div>
      ${draftPanel(t.id)}
      <div class="field">Priority
        ${priorityPicker(t)}
      </div>
      <label>Due
        <input type="date" data-set="due" value="${esc(t.due || "")}">
      </label>
      ${t.series ? "" : `<label>Week
        <select data-set="week">
          <option value="" ${t.week ? "" : "selected"}>Not planned</option>
          ${weeks.map(w => `<option value="${w}" ${w === t.week ? "selected" : ""}>Week ${weekNum(w)} · ${weekRange(w)}</option>`).join("")}
        </select>
      </label>`}
      <p class="edit-error" hidden></p>
    </div>`;
}

// ---------- message drafts (POST /api/tasks/<id>/draft, written by Claude on the server) ----------
// Kept in state so a draft survives the re-render when the page reloads data.

const LANGUAGES = ["English", "Italian", "Polish", "Russian", "Ukrainian"];

function draftPanel(id) {
  const d = state.drafts[id];
  if (!d) return "";
  if (d.loading) return `<div class="draft"><p class="muted">Drafting a message…</p></div>`;
  if (d.error) return `<div class="draft"><p class="edit-error">${esc(d.error)}</p><button data-draft="${esc(id)}">Try again</button></div>`;
  const langButtons = LANGUAGES.map(l => `<button data-draft="${esc(id)}" data-lang="${l}">${l}</button>`).join("");
  if (d.needs_language) return `
    <div class="draft">
      <p>Which language should the message be in?</p>
      <div class="lang-row">${langButtons}<input class="lang-other" placeholder="Other…" data-lang-for="${esc(id)}"></div>
    </div>`;
  const mailto = `mailto:?subject=${encodeURIComponent(d.subject || "")}&body=${encodeURIComponent(d.body || "")}`;
  return `
    <div class="draft">
      <p class="muted">${d.recipient ? `To ${esc(d.recipient)} · ` : ""}${esc(d.language)}</p>
      ${d.subject ? `<input class="draft-subject" value="${esc(d.subject)}" data-draft-field="subject" data-for="${esc(id)}">` : ""}
      <textarea class="draft-body" rows="${Math.min(14, (d.body || "").split("\n").length + 2)}" data-draft-field="body" data-for="${esc(id)}">${esc(d.body)}</textarea>
      <div class="actions">
        <button class="primary" data-copy="${esc(id)}">Copy</button>
        <a class="btn" href="${mailto}">Open in mail</a>
        <button data-draft="${esc(id)}" data-lang="${esc(d.language)}">Rewrite</button>
        <select data-draft-lang="${esc(id)}"><option value="">Other language…</option>${LANGUAGES.filter(l => l !== d.language).map(l => `<option>${l}</option>`).join("")}</select>
        <button data-draft-close="${esc(id)}">Close</button>
      </div>
    </div>`;
}

async function requestDraft(id, language) {
  state.drafts[id] = { loading: true };
  render();
  try {
    const res = await fetch(`/api/tasks/${id}/draft`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(language ? { language } : {}),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || `HTTP ${res.status}`);
    state.drafts[id] = data;
  } catch (e) {
    state.drafts[id] = { error: `No draft: ${e.message}` };
  }
  render();
}

board.addEventListener("click", async e => {
  const draftBtn = e.target.closest("button[data-draft]");
  if (draftBtn) return requestDraft(draftBtn.dataset.draft, draftBtn.dataset.lang);
  const copyBtn = e.target.closest("button[data-copy]");
  if (copyBtn) {
    const d = state.drafts[copyBtn.dataset.copy];
    const text = (d.subject ? `${d.subject}\n\n` : "") + d.body;
    try { await navigator.clipboard.writeText(text); copyBtn.textContent = "Copied"; } catch { copyBtn.textContent = "Copy failed"; }
    return;
  }
  const closeBtn = e.target.closest("button[data-draft-close]");
  if (closeBtn) { delete state.drafts[closeBtn.dataset.draftClose]; render(); }
});
board.addEventListener("input", e => {  // keep edits to the draft so Copy and a re-render use them
  const el = e.target.closest("[data-draft-field]");
  if (el && state.drafts[el.dataset.for]) state.drafts[el.dataset.for][el.dataset.draftField] = el.value;
});
board.addEventListener("change", e => {
  const sel = e.target.closest("select[data-draft-lang]");
  if (sel && sel.value) requestDraft(sel.dataset.draftLang, sel.value);
});
board.addEventListener("keydown", e => {
  const input = e.target.closest("input[data-lang-for]");
  if (input && e.key === "Enter" && input.value.trim()) requestDraft(input.dataset.langFor, input.value.trim());
});

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

function section(title, tasks, { cls = "", sort = byPriorityThenDue } = {}) {
  if (!tasks.length) return "";
  return `
    <section class="group ${cls}">
      <div class="section-head"><h2>${title}</h2><span class="count">${tasks.length}</span></div>
      ${tasks.sort(sort).map(t => taskCard(t, { badge: true })).join("")}
    </section>`;
}

// ---------- views ----------

const byTier = t => state.tier === "all" || t.tier === state.tier;

function renderAll() {
  const tasks = state.tasks.filter(t =>
    byTier(t) && (state.status === "all" || (state.status === "closed") === t.is_closed));
  const label = { all: "", open: " open", closed: " done" }[state.status];
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

const MEETING_STATUS = { planned: "Planned", done: "Protocol", cancelled: "Cancelled" };
const meetingWhen = m => `${localDate(m.date).toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" })}${m.time ? `, ${esc(m.time)}` : ""} · ${MEETING_STATUS[m.status] || esc(m.status)}`;

// Upcoming plans first (soonest first), then past meetings (latest first).
function byMeetingOrder(a, b) {
  const pa = a.status === "planned", pb = b.status === "planned";
  if (pa !== pb) return pa ? -1 : 1;
  const da = `${a.date} ${a.time || ""}`, db = `${b.date} ${b.time || ""}`;
  return pa ? (da < db ? -1 : da > db ? 1 : 0) : (da > db ? -1 : da < db ? 1 : 0);
}

function meetingCard(m) {
  const linked = m.tasks.map(id => state.tasks.find(t => t.id === id)).filter(Boolean);
  const hasProtocol = m.protocol && m.protocol !== "None yet.";
  return `
    <details class="meeting ${m.status}" data-id="${esc(m.id)}">
      <summary>
        <span class="title">${esc(m.name)}</span>
        <span class="topic">${esc(m.title)}</span>
        <span class="meta">
          <span>${esc(m.audience)}</span>
          <span>${meetingWhen(m)}</span>
          ${m.duration ? `<span>${esc(m.duration)} min</span>` : ""}
          ${m.project_name ? `<span>${esc(m.project_name)} · ${esc(m.tier)}</span>` : `<span>${esc(m.tier)}</span>`}
          ${linked.length ? `<span class="meeting-chip">🔗 ${plural(linked.length, "task")}</span>` : ""}
        </span>
      </summary>
      <div class="detail">
        ${hasProtocol ? `<h3>Protocol</h3>${md(m.protocol)}` : ""}
        <h3>Goal</h3>${md(m.goal)}
        <h3>Agenda</h3>${md(m.agenda)}
        <h3>Preparation</h3>${md(m.preparation)}
        ${linked.length ? `<h3>Linked tasks</h3><div class="linked">${linked.sort(byPriorityThenDue).map(t => taskCard(t, { badge: true })).join("")}</div>` : ""}
      </div>
    </details>`;
}

function renderMeetings() {
  const meetings = state.meetings.filter(byTier).sort(byMeetingOrder);
  const planned = meetings.filter(m => m.status === "planned").length;
  summary.textContent = `${plural(planned, "planned meeting")} · ${plural(meetings.length - planned, "past meeting")}`;
  board.innerHTML = meetings.length
    ? meetings.map(meetingCard).join("")
    : `<p class="empty">No meetings yet. Plan one with /ordo.</p>`;
}

// Only open critical tasks: what must be done now.
function renderCritical() {
  const tasks = state.tasks.filter(t => byTier(t) && !isSeries(t) && !t.is_closed && t.priority === "P1").sort(byDueThenId);
  summary.textContent = `${plural(tasks.length, "open critical task")}`;
  board.innerHTML = tasks.length
    ? `<section class="group p1">${tasks.map(t => taskCard(t)).join("")}</section>`
    : `<p class="empty">No critical tasks open.</p>`;
}

function renderWeek() {
  const key = state.week;
  const isCurrent = key === thisWeek, isPast = key < thisWeek;
  $("week-title").textContent = `Week ${weekNum(key)}${isCurrent ? " · this week" : ""}`;
  $("week-range").textContent = weekRange(key);
  $("week-today").hidden = isCurrent;

  const tasks = state.tasks.filter(byTier);
  const inWeek = tasks.filter(t => !isSeries(t) && taskWeek(t) === key);
  // Tasks dragged from earlier weeks, including ones /plan already moved into this week.
  // They are listed with the rest; their cards show the carried-over chip.
  const carried = isCurrent ? tasks.filter(t => !isSeries(t) && carriedFrom(t).length && taskWeek(t) && taskWeek(t) <= key) : [];
  const carriedIds = new Set(carried.map(t => t.id));
  // In-progress tasks get their own section at the top.
  const working = inWeek.filter(t => !t.is_closed && inProgress(t));
  const open = [...carried, ...inWeek.filter(t => !t.is_closed && !inProgress(t) && !carriedIds.has(t.id))];
  const done = inWeek.filter(t => t.is_closed);
  const unscheduled = isCurrent ? tasks.filter(t => !isSeries(t) && !t.is_closed && !taskWeek(t)) : [];

  const parts = working.length ? [`${working.length} in progress`] : [];
  parts.push(`${open.length} ${isPast ? "not done" : isCurrent ? "to do" : "planned"}`);
  if (carried.length) parts.push(`${carried.length} carried over`);
  parts.push(`${done.length} done`);
  summary.textContent = parts.join(" · ");

  const html = [
    section("In progress", working, { cls: "working" }),
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
  const openIds = new Set([...board.querySelectorAll("details[data-id][open]")].map(d => d.dataset.id));
  const unscheduledOpen = board.querySelector(".unscheduled")?.open;
  document.querySelectorAll(".tabs a").forEach(a => {
    if (a.dataset.view === state.view) a.setAttribute("aria-current", "page");
    else a.removeAttribute("aria-current");
  });
  document.querySelector("[data-filter='status']").hidden = state.view !== "all";
  $("week-nav").hidden = state.view !== "week";
  const critical = state.tasks.filter(t => !isSeries(t) && !t.is_closed && t.priority === "P1").length;
  $("priority-tab").textContent = state.tasks.length ? `Priority · ${critical}` : "Priority";
  ({ week: renderWeek, priority: renderCritical, meetings: renderMeetings }[state.view] || renderAll)();
  board.querySelectorAll("details[data-id]").forEach(d => { if (openIds.has(d.dataset.id)) d.open = true; });
  if (state.focus && state.tasks.length) {  // #all/T-0007 or #meetings/<id>: open and show that card once
    const el = board.querySelector(`details[data-id="${CSS.escape(state.focus)}"]`);
    if (el) { el.open = true; el.scrollIntoView({ block: "center" }); el.classList.add("focus"); }
    state.focus = null;
  }
  const u = board.querySelector(".unscheduled");
  if (u && unscheduledOpen) u.open = true;
}

// ---------- navigation (URL hash: #all, #all/T-0007, #priority, #week, #week/2026-W41, #meetings, #meetings/<id>) ----------

function readHash() {
  const [view, arg] = location.hash.replace(/^#/, "").split("/");
  state.view = ["week", "priority", "meetings"].includes(view) ? view : "all";
  state.week = /^\d{4}-W\d{2}$/.test(arg || "") ? arg : thisWeek;
  state.focus = view !== "week" && arg ? decodeURIComponent(arg) : null;
  if (state.focus && state.view === "all") {  // show the linked task even if a filter would hide it
    state.status = "all"; state.tier = "all";
    document.querySelectorAll(".seg button").forEach(b => b.setAttribute("aria-pressed", String(b.dataset.value === "all")));
  }
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
    const data = await res.json();
    state.tasks = data.tasks;
    state.meetings = data.meetings || [];
    state.meetingsByTask = {};
    for (const m of [...state.meetings].sort(byMeetingOrder)) {
      for (const id of m.tasks) (state.meetingsByTask[id] ||= []).push(m);
    }
    render();
  } catch (err) {
    board.innerHTML = `<p class="error">Could not load tasks: ${esc(err.message)}</p>`;
  }
}

window.addEventListener("hashchange", readHash);
window.addEventListener("focus", load); // pick up tasks added by agents while the page was in the background
readHash();
load();
