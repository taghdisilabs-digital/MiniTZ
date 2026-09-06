const state = {
  config: null,
  session: null,
  lane: "Games",
  view: "control",
  projection: null,
  assets: [],
  events: [],
  eventSource: null,
  lastEventId: "",
  loading: false,
};

const LIVE_STATES = new Set(["ACTIVE", "WAITING", "STALE", "STOPPED", "ERROR"]);
const loginView = document.getElementById("login-view");
const appView = document.getElementById("app-view");
const loginForm = document.getElementById("login-form");
const loginMessage = document.getElementById("login-message");
const logoutButton = document.getElementById("logout-button");
const viewRoot = document.getElementById("view-root");
const errorBanner = document.getElementById("error-banner");
const liveState = document.getElementById("live-state");
const liveTask = document.getElementById("live-task");
const liveHeartbeat = document.getElementById("live-heartbeat");
const roleBadge = document.getElementById("role-badge");
const lastSync = document.getElementById("last-sync");

function esc(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;").replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;").replaceAll('"', "&quot;").replaceAll("'", "&#039;");
}

function apiPath(path) {
  const base = (state.config && state.config.api_base) || "/v1/control";
  return base.replace(/\/$/, "") + "/" + path.replace(/^\//, "");
}

async function request(path, options = {}) {
  const response = await fetch(apiPath(path), Object.assign({credentials: "same-origin"}, options));
  if (!response.ok) throw new Error("Gateway returned " + response.status);
  return response.status === 204 ? {} : response.json();
}

function control() { return state.projection?.control || {}; }
function work() { return state.projection?.work || {sections: [], tasks: []}; }
function system() { return state.projection?.system || {services: [], resources: [], workers: [], hardware: {}}; }

function normalizedLiveState() {
  const value = String(control().status || "ERROR").toUpperCase();
  return LIVE_STATES.has(value) ? value : "ERROR";
}

function updateLiveStrip() {
  const c = control();
  const status = normalizedLiveState();
  liveState.textContent = status;
  liveState.className = "live-state live-" + status.toLowerCase();
  liveTask.textContent = c.current_task ? `${state.lane} · ${c.current_task}` : `${state.lane} · no active task`;
  liveHeartbeat.textContent = c.heartbeat_at ? `Heartbeat ${formatTime(c.heartbeat_at)}` : "No active heartbeat";
}

function formatTime(value) {
  if (!value) return "not reported";
  const date = new Date(value);
  return Number.isNaN(date.valueOf()) ? String(value) : date.toLocaleString();
}
function short(value, size = 12) { return value ? String(value).slice(0, size) : "—"; }
function badge(value) {
  const raw = String(value ?? "UNKNOWN");
  const key = raw.toLowerCase().replace(/[^a-z0-9]+/g, "-");
  return `<span class="status-tag status-${esc(key)}">${esc(raw)}</span>`;
}
function empty(message) { return `<div class="empty-state">${esc(message)}</div>`; }
function progress(c) {
  const total = Number(c.total || 0), done = Number(c.completed || 0);
  const pct = total > 0 ? Math.max(0, Math.min(100, done * 100 / total)) : 0;
  return `<div class="progress-block"><div class="progress-copy"><b>${done} / ${total}</b><span>${pct.toFixed(0)}%</span></div><div class="progress-track"><span style="width:${pct}%"></span></div></div>`;
}

const DIALOG_EVENT_TYPES = new Set([
  "dialog.operator", "dialog.queued", "dialog.started", "dialog.agent", "dialog.failed",
  "agent.message", "agent.reasoning_summary", "tool.started", "tool.completed",
  "task.started", "task.continued", "task.continue", "task.completed", "task.runtime_recovery",
  "persistence.started", "persistence.retry", "persistence.completed",
  "turn.started", "turn.completed", "production.started", "production.completed"
]);

function currentTaskTitle() {
  const id = control().current_task;
  const item = (work().tasks || []).find((task) => task.id === id);
  return item?.title || id || "No task is currently executing";
}

function dialogRole(event) {
  if (event.type === "dialog.operator") return "YOU";
  if (String(event.type || "").startsWith("agent.") || event.type === "dialog.agent") return "BIELLA";
  if (String(event.type || "").startsWith("tool.")) return "TOOL";
  return "SYSTEM";
}

function dialogText(event) {
  if (event.text) return String(event.text);
  if (event.type === "turn.completed" && event.usage) {
    const cached = Number(event.usage.cached_input_tokens || 0);
    const input = Number(event.usage.input_tokens || 0);
    return `Turn complete · input ${input.toLocaleString()} · cached ${cached.toLocaleString()}`;
  }
  return event.status || event.type || "event";
}

function renderDialogEvents() {
  const entries = state.events.filter((event) => DIALOG_EVENT_TYPES.has(event.type)).slice(-120);
  if (!entries.length) return `<div class="empty-state">No live task events yet.</div>`;
  return entries.map((event) => `
    <div class="dialog-entry dialog-${esc(dialogRole(event).toLowerCase())}">
      <div class="dialog-meta"><b>${esc(dialogRole(event))}</b><time>${esc(formatTime(event.time || ""))}</time><span>${esc(event.task_id || "")}</span></div>
      <div class="dialog-text">${esc(dialogText(event))}</div>
    </div>`).join("");
}

function shouldRefreshProjection(event) {
  return new Set(["task.started", "task.completed", "persistence.completed", "production.completed"]).has(event.type);
}

function scrollDialogToEnd() {
  const stream = document.getElementById("dialog-stream");
  if (stream) stream.scrollTop = stream.scrollHeight;
}

function renderControl() {
  const c = control();
  const sections = c.sections || [];
  const currentIndex = (work().tasks || []).findIndex((task) => task.id === c.current_task);
  const next = currentIndex >= 0 ? work().tasks[currentIndex + 1] : null;
  const activity = state.events.length
    ? state.events.slice(-8).reverse().map((e) => `<li><time>${esc(e.time || "")}</time><span>${esc(e.text || e.status || JSON.stringify(e))}</span></li>`).join("")
    : `<li class="muted">No recent event stream entries.</li>`;
  return `
    <div class="section-heading"><div><span class="eyebrow">NOW</span><h2>${esc(state.lane)} production</h2></div>${badge(normalizedLiveState())}</div>
    <article class="current-work">
      <div class="task-identity"><span>${esc(c.current_section || "No section")}</span><strong>${esc(c.current_task || "IDLE")}</strong></div>
      <h3>${esc(currentTaskTitle())}</h3>
      ${progress(c)}
      <div class="fact-grid">
        <div><span>Model</span><b>${esc(c.active_model || "none")}</b></div>
        <div><span>Reasoning</span><b>${esc(c.active_reasoning || "none")}</b></div>
        <div><span>Next</span><b>${esc(next?.id || "not resolved")}</b></div>
        <div><span>Git</span><b class="mono">${esc(short(c.commit))}</b></div>
      </div>
    </article>
    <article class="panel live-dialog">
      <header><b>Live task activity</b><span>${esc(c.current_task || "idle")} · read only</span></header>
      <div id="dialog-stream" class="dialog-stream">${renderDialogEvents()}</div>
    </article>
    <div class="split-grid">
      <article class="panel"><header><b>Production map</b><span>${sections.length} sections</span></header><div class="section-list">${sections.map((s) => `<div class="section-row"><span>${esc(s.id)}</span><b>${Number(s.completed || 0)}/${Number(s.total || 0)}</b>${badge(s.status)}</div>`).join("") || empty("No section data")}</div></article>
      <article class="panel"><header><b>Recent activity</b><span>live stream</span></header><ul class="activity-list">${activity}</ul></article>
    </div>`;
}

function renderWork() {
  const w = work();
  const current = w.current_task;
  const tasks = w.tasks || [];
  const rows = tasks.map((task) => {
    const cls = task.id === current ? " task-current" : "";
    return `<article class="task-row${cls}"><span class="task-id mono">${esc(task.id)}</span><div><b>${esc(task.title)}</b><small>${esc(task.section)} · ${esc(task.class || "")}</small></div>${badge(task.status)}</article>`;
  }).join("");
  return `<div class="section-heading"><div><span class="eyebrow">WORK</span><h2>Canonical execution graph</h2><p>One executable row per canonical task. Completed work remains visible but secondary.</p></div></div><div class="task-list">${rows || empty("No tasks reported")}</div>`;
}

function assetFileUrl(item) {
  return apiPath("assets/file?lane=" + encodeURIComponent(state.lane) + "&root_id=" + encodeURIComponent(item.root_id || "") + "&path=" + encodeURIComponent(item.path || ""));
}
function assetPreview(item) {
  const url = assetFileUrl(item);
  if (item.kind === "image" && item.previewable) return `<img class="asset-preview" src="${url}" alt="${esc(item.name)}" loading="lazy">`;
  if (item.kind === "video" && item.previewable) return `<video class="asset-preview" src="${url}" controls preload="metadata"></video>`;
  if (item.kind === "audio" && item.previewable) return `<div class="asset-preview asset-audio"><audio src="${url}" controls preload="metadata"></audio></div>`;
  return `<div class="asset-preview asset-placeholder">${esc(String(item.kind || "artifact").toUpperCase())}</div>`;
}
function renderOutputs() {
  const assets = state.assets || [];
  const cards = assets.map((item) => `<article class="asset-card">${assetPreview(item)}<div class="asset-meta"><b>${esc(item.name)}</b><small>${esc(item.path)}</small><div>${badge(item.source_class)} ${badge(item.kind)}</div><span class="mono">${esc(item.sha256 ? short(item.sha256, 16) : "digest deferred")}</span></div></article>`).join("");
  const source = state.projection?.outputs?.items || [];
  return `<div class="section-heading"><div><span class="eyebrow">OUTPUTS</span><h2>Real production artifacts</h2><p>Visuals and playable/runtime outputs first; exact source and evidence identities remain inspectable.</p></div></div>
    <div class="asset-grid">${cards || empty("No media outputs reported")}</div>
    <details class="source-details"><summary>Current source files · ${source.length}</summary><div class="source-list">${source.slice(0, 80).map((item) => `<div><span class="mono">${esc(item.path)}</span><span>${esc(short(item.commit))}</span></div>`).join("")}</div></details>`;
}

function renderSystem() {
  const s = system();
  const resources = (s.resources || []).map((item) => `<article class="system-row"><div><b>${esc(item.display_name || item.id)}</b><small>${esc((item.capabilities || []).join(" · "))}</small></div>${badge(item.state)}</article>`).join("");
  const services = (s.services || []).map((item) => `<article class="system-row"><div><b>${esc(item.name)}</b><small>${esc(item.detail || "")}</small></div>${badge(item.status)}</article>`).join("");
  const workers = (s.workers || []).map((item) => `<article class="system-row"><div><b>${esc(item.name)}</b><small>${esc(item.detail || "")}</small></div>${badge(item.status)}</article>`).join("");
  const h = s.hardware || {};
  return `<div class="section-heading"><div><span class="eyebrow">SYSTEM</span><h2>Resources and runtime</h2><p>Exceptions first. Healthy infrastructure stays compact.</p></div></div>
    <div class="fact-grid system-facts"><div><span>GPU</span><b>${esc(h.gpu || "unavailable")}</b></div><div><span>VRAM</span><b>${esc(h.vram_used || "—")}</b></div><div><span>RAM</span><b>${esc(h.ram_used || "—")}</b></div><div><span>API</span><b>${esc(h.api_calls || "—")}</b></div></div>
    <div class="split-grid"><article class="panel"><header><b>External Resources</b><span>capability routing</span></header><div class="system-list">${resources || empty("Resource registry unavailable")}</div></article><article class="panel"><header><b>Services</b><span>live health</span></header><div class="system-list">${services || empty("No service health")}</div></article></div>
    <article class="panel workers-panel"><header><b>Workers</b><span>runtime</span></header><div class="system-list">${workers || empty("No workers reported")}</div></article>`;
}

function render() {
  document.querySelectorAll(".nav-button").forEach((b) => b.classList.toggle("active", b.dataset.view === state.view));
  document.querySelectorAll(".project-button").forEach((b) => b.classList.toggle("active", b.dataset.lane === state.lane));
  if (state.view === "control") viewRoot.innerHTML = renderControl();
  else if (state.view === "work") viewRoot.innerHTML = renderWork();
  else if (state.view === "outputs") viewRoot.innerHTML = renderOutputs();
  else viewRoot.innerHTML = renderSystem();
  updateLiveStrip();
  scrollDialogToEnd();
}

async function loadData() {
  if (!state.session || state.loading) return;
  state.loading = true;
  errorBanner.classList.add("hidden");
  try {
    const [projection, assets] = await Promise.all([
      request("/projection?lane=" + encodeURIComponent(state.lane)),
      request("assets?lane=" + encodeURIComponent(state.lane) + "&limit=100").catch(() => ({items: []})),
    ]);
    state.projection = projection;
    state.assets = assets.items || [];
    lastSync.textContent = "Synced " + new Date().toLocaleTimeString();
  } catch (error) {
    state.projection = {control: {status: "ERROR"}, work: {sections: [], tasks: []}, system: {services: [], resources: [], workers: []}};
    errorBanner.textContent = error.message;
    errorBanner.classList.remove("hidden");
  } finally {
    state.loading = false;
    render();
  }
}

function connectEvents() {
  if (state.eventSource) state.eventSource.close();
  const eventPath = state.config?.event_path || "/events";
  state.eventSource = new EventSource(apiPath(eventPath) + "?lane=" + encodeURIComponent(state.lane));
  state.eventSource.onmessage = (event) => {
    let parsed;
    try { parsed = JSON.parse(event.data); } catch { parsed = {text: event.data}; }
    state.lastEventId = event.lastEventId || state.lastEventId;
    state.events.push(Object.assign({time: new Date().toISOString()}, parsed));
    if (state.events.length > 500) state.events.shift();
    if (shouldRefreshProjection(parsed)) loadData();
    else if (state.view === "control") render();
  };
}

async function signOut() {
  try { await request("session/logout", {method: "POST"}); } catch {}
  state.eventSource?.close();
  state.session = null;
  appView.classList.add("hidden"); loginView.classList.remove("hidden"); logoutButton.classList.add("hidden");
}

async function openConsole(session) {
  state.session = session;
  loginView.classList.add("hidden"); appView.classList.remove("hidden"); logoutButton.classList.remove("hidden");
  roleBadge.textContent = "Read only";
  await loadData(); connectEvents();
}

loginForm.addEventListener("submit", async (event) => {
  event.preventDefault(); loginMessage.textContent = "Signing in…";
  try {
    const result = await request("/session", {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({username: document.getElementById("username").value.trim(), password: document.getElementById("password").value})});
    loginMessage.textContent = ""; await openConsole(result.session || result);
  } catch { loginMessage.textContent = "Sign-in failed."; }
});
logoutButton.addEventListener("click", signOut);
document.querySelectorAll(".nav-button").forEach((button) => button.addEventListener("click", () => { state.view = button.dataset.view; render(); }));
document.querySelectorAll(".project-button").forEach((button) => button.addEventListener("click", async () => { state.lane = button.dataset.lane; state.events = []; await loadData(); connectEvents(); }));

async function bootstrap() {
  try {
    state.config = await (await fetch("../data/control-runtime.json", {credentials: "same-origin"})).json();
    const existing = await request("/session");
    if (existing?.authenticated) await openConsole(existing.session || existing);
  } catch { /* login remains available while gateway is offline */ }
  render();
}
bootstrap();
