import {
  PLACES, PLACE_BY_ID, ORIGINS, ORIGIN_BY_ID, INTERESTS, DEFAULTS,
  normalizeConstraints, schedule, plan, parseRequest, describePlan, toMin, to12h, formatDuration,
} from "./core.js";
import { renderCharts } from "./charts.js";

const CONFIG = window.TT_CONFIG || {};
const API = /^https?:\/\//.test(CONFIG.apiBase || "") ? CONFIG.apiBase.replace(/\/$/, "") : "";
const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
const $ = (sel) => document.querySelector(sel);

function el(tag, attrs = {}, ...children) {
  const n = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (v === false || v == null) continue;
    if (k === "class") n.className = v;
    else if (k === "text") n.textContent = v;
    else if (k.startsWith("on")) n.addEventListener(k.slice(2), v);
    else n.setAttribute(k, v === true ? "" : v);
  }
  for (const c of children) if (c != null && c !== false) n.append(c);
  return n;
}

const state = {
  constraints: normalizeConstraints(DEFAULTS),
  stopIds: [], legs: {}, reasons: {}, notes: [],
  engine: "rules", model: "", trace: [], usage: null, rounds: 0, walkSource: "estimate",
  locked: [], excluded: [], history: [], query: "",
  ai: API ? "checking" : "off",
  busy: false,
};

const ENGINE_NOTES = {
  off: "AI planning isn't connected on this copy, so the rule planner answers.",
  checking: "Connecting to the AI planner…",
  ready: "Requests go to a Claude agent that checks every stop before it answers.",
  down: "The AI planner isn't reachable right now, so the rule planner answers.",
};
const AGENT_ERRORS = {
  rate_limited: "the demo's hourly limit was reached",
  model_busy: "the model is busy",
  ai_not_configured: "no API key is set on the server",
  agent_failed: "the agent hit an error",
  origin_not_allowed: "this site isn't on the agent's allowed list",
};

// ---------------------------------------------------------------- planning

function applyRules(result) {
  state.stopIds = result.stopIds;
  state.legs = {};
  state.reasons = result.reasons;
  state.notes = result.notes;
  state.engine = "rules";
  state.trace = []; state.usage = null; state.rounds = 0; state.walkSource = "estimate";
}

function replanWithRules() {
  applyRules(plan(state.constraints, { locked: state.locked, excluded: state.excluded, query: state.query }));
  render({ animate: true });
}

function offlineAnswer(text, prefix = "") {
  const p = parseRequest(text, state.constraints);
  if (p.reset) { state.locked = []; state.excluded = []; state.query = ""; }
  for (const id of p.exclude) {
    if (!state.excluded.includes(id)) state.excluded.push(id);
    state.locked = state.locked.filter((x) => x !== id);
  }
  for (const id of p.include) {
    if (!state.locked.includes(id)) state.locked.push(id);
    state.excluded = state.excluded.filter((x) => x !== id);
  }
  state.constraints = p.constraints;
  if (!p.reset) state.query = [state.query, text].filter(Boolean).join(" ").slice(-280);
  const result = plan(state.constraints, { locked: state.locked, excluded: state.excluded, query: state.query });
  applyRules(result);
  const changed = p.changes.length
    ? `Updated ${p.changes.join(", ")}. `
    : "I matched your words against the place descriptions. ";
  const reply = `${prefix ? `${prefix} ` : ""}${changed}${describePlan(result)}${result.notes.length ? ` ${result.notes.join(" ")}` : ""}`;
  addMessage("agent", reply, "rules");
  state.history.push({ role: "assistant", text: reply });
  render({ animate: true });
}

async function callAgent(text) {
  const res = await fetch(`${API}/api/plan`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({
      message: text,
      history: state.history.slice(-13, -1),
      constraints: state.constraints,
      current: state.stopIds,
      locked: state.locked,
      excluded: state.excluded,
    }),
    signal: AbortSignal.timeout(90000),
  });
  let data = null;
  try { data = await res.json(); } catch { /* not JSON */ }
  if (!res.ok || !data || !data.ok) throw new Error(AGENT_ERRORS[data?.error] || `the server answered ${res.status}`);
  return data;
}

function applyAgent(res) {
  state.constraints = normalizeConstraints(res.constraints);
  state.stopIds = (res.stopIds || []).filter((id) => PLACE_BY_ID[id]);
  state.legs = res.legs || {};
  state.reasons = res.reasons || {};
  state.notes = [];
  state.engine = res.fallback ? "fallback" : "claude";
  state.model = res.model || "";
  state.trace = Array.isArray(res.trace) ? res.trace : [];
  state.usage = res.usage || null;
  state.rounds = res.rounds || 0;
  state.walkSource = res.walkSource || "estimate";
  const reply = res.reply || describePlan({ schedule: currentSchedule() });
  addMessage("agent", reply, res.fallback ? "rules" : "claude");
  state.history.push({ role: "assistant", text: reply });
  render({ animate: true });
}

async function ask(raw) {
  const text = String(raw || "").trim().slice(0, 600);
  if (!text || state.busy) return;
  addMessage("user", text);
  state.history.push({ role: "user", text });
  $("#ask-input").value = "";
  if (state.ai !== "ready") { offlineAnswer(text); return; }
  setBusy(true);
  const pending = el("p", { class: "msg msg-pending", text: "Planning with Claude and checking each stop…" });
  $("#convo").append(pending);
  try {
    applyAgent(await callAgent(text));
  } catch (err) {
    offlineAnswer(text, `The AI planner didn't answer (${err.message}), so the rule planner did.`);
  } finally {
    pending.remove();
    setBusy(false);
  }
}

function setBusy(on) {
  state.busy = on;
  $("#ask-btn").disabled = on;
  $("#ask-btn").textContent = on ? "Planning…" : (state.history.length ? "Update plan" : "Plan my day");
  for (const b of document.querySelectorAll(".chip")) b.disabled = on;
}

// ---------------------------------------------------------------- conversation

function addMessage(who, text, engine) {
  const convo = $("#convo");
  if (who === "user") convo.append(el("p", { class: "msg msg-user", text }));
  else {
    convo.append(el("p", { class: `msg msg-agent ${engine === "claude" ? "" : "rules"}` },
      el("span", { class: "who", text: engine === "claude" ? "Claude agent" : "Rule planner" }), text));
  }
  while (convo.children.length > 8) convo.firstElementChild.remove();
}

// ---------------------------------------------------------------- limits form

function syncLimitsForm() {
  const f = $("#limits-form");
  const c = state.constraints;
  for (const k of ["start", "end", "group", "budget", "maxWalk", "stops", "origin"]) {
    if (document.activeElement !== f.elements[k]) f.elements[k].value = c[k];
  }
  for (const b of document.querySelectorAll("#interest-toggles .toggle")) {
    b.setAttribute("aria-pressed", String(c.interests.includes(b.dataset.interest)));
  }
}

function buildLimitsForm() {
  const f = $("#limits-form");
  for (const o of ORIGINS) f.elements.origin.append(el("option", { value: o.id, text: o.name }));
  const box = $("#interest-toggles");
  for (const i of INTERESTS) {
    box.append(el("button", {
      type: "button", class: "toggle", "data-interest": i, "aria-pressed": "false",
      text: i[0].toUpperCase() + i.slice(1),
      onclick: () => {
        const set = new Set(state.constraints.interests);
        if (set.has(i)) set.delete(i); else set.add(i);
        state.constraints = normalizeConstraints({ ...state.constraints, interests: [...set] });
        replanWithRules();
      },
    }));
  }
  f.addEventListener("change", () => {
    if (!f.reportValidity()) return;
    const v = Object.fromEntries(new FormData(f));
    state.constraints = normalizeConstraints({ ...state.constraints, ...v });
    replanWithRules();
  });
  f.addEventListener("submit", (e) => e.preventDefault());
}

// ---------------------------------------------------------------- route list

function currentSchedule() {
  return schedule(state.stopIds, state.constraints, { legs: state.legs });
}

function toggleKeep(id) {
  if (state.locked.includes(id)) state.locked = state.locked.filter((x) => x !== id);
  else state.locked.push(id);
  render({ animate: false });
}

function removeStop(id) {
  if (!state.excluded.includes(id)) state.excluded.push(id);
  state.locked = state.locked.filter((x) => x !== id);
  replanWithRules();
}

function addPlace(id) {
  if (!state.locked.includes(id)) state.locked.push(id);
  state.excluded = state.excluded.filter((x) => x !== id);
  if (state.stopIds.length >= state.constraints.stops && state.constraints.stops < 6) {
    state.constraints = normalizeConstraints({ ...state.constraints, stops: state.constraints.stops + 1 });
  }
  replanWithRules();
}

function costText(p, group) {
  if (!p.cost) return "free";
  return group > 1 ? `about $${p.cost * group} for ${group}` : `about $${p.cost}`;
}

function renderTrail(s, animate) {
  const ol = $("#trail");
  ol.textContent = "";
  const c = s.constraints;
  const origin = ORIGIN_BY_ID[c.origin];
  ol.append(el("li", { class: "origin" },
    el("span", { class: "t" }, el("b", { text: to12h(toMin(c.start)) })),
    el("span", { class: "rail" }, el("span", { class: "node origin", "aria-hidden": "true" })),
    el("div", { class: "body" }, el("h3", { text: `Start at ${origin.name}` }))));
  if (!s.stops.length) {
    ol.append(el("li", {}, el("p", { class: "empty", text: "No stop fits these limits. Try a later finish, a bigger budget or a longer walk." })));
    return;
  }
  const live = state.walkSource === "google";
  s.stops.forEach((st, i) => {
    const p = PLACE_BY_ID[st.id];
    const legText = `${st.walk} min walk${live ? " (Google Maps)" : ""}${st.wait >= 10 ? `, then ${st.wait} min until it opens` : ""}`;
    ol.append(el("li", { class: "leg" },
      el("span", { class: "t" }), el("span", { class: "rail" }),
      el("div", { class: "body", text: legText })));
    const kept = state.locked.includes(st.id);
    const li = el("li", { class: "station", "data-id": st.id },
      el("span", { class: "t" }, el("b", { text: to12h(st.begin) }), to12h(st.leave)),
      el("span", { class: "rail" }, el("span", { class: "node", text: String(i + 1), "aria-hidden": "true" })),
      el("div", { class: "body" },
        el("h3", { text: `${i + 1}. ${p.name}` }),
        el("p", { class: "meta", text: `${p.area}, ${p.visit} min, ${costText(p, c.group)}` }),
        state.reasons[st.id] ? el("p", { class: "why", text: state.reasons[st.id] }) : null,
        el("div", { class: "acts" },
          el("button", { type: "button", "aria-pressed": String(kept), text: kept ? "Kept" : "Keep", title: "Keep this stop when the plan changes", onclick: () => toggleKeep(st.id) }),
          el("button", { type: "button", text: "Remove", title: "Remove this stop and fill the gap", onclick: () => removeStop(st.id) }))));
    li.addEventListener("pointerenter", () => setActive(st.id));
    li.addEventListener("pointerleave", () => setActive(null));
    if (animate && !reduceMotion) li.animate([{ opacity: 0, transform: "translateY(6px)" }, { opacity: 1, transform: "none" }], { duration: 260, delay: 120 + i * 90, fill: "backwards", easing: "ease-out" });
    ol.append(li);
  });
  const end = toMin(c.end);
  const spare = end - s.finish;
  ol.append(el("li", { class: "end" },
    el("span", { class: "t" }, el("b", { text: to12h(s.finish) })),
    el("span", { class: "rail" }, el("span", { class: "node end", "aria-hidden": "true" })),
    el("div", { class: "body" }, el("h3", { text: spare >= 0 ? `Done with ${formatDuration(spare)} to spare` : "Over your finish time" }))));
}

function renderTotals(s) {
  const dl = $("#totals");
  dl.textContent = "";
  const total = s.stops.length ? s.finish - toMin(s.constraints.start) : 0;
  const items = [
    [String(s.stops.length), s.stops.length === 1 ? "stop" : "stops"],
    [formatDuration(total), "total time"],
    [`${s.walkTotal} min`, "walking"],
    [s.cost ? `$${s.cost}` : "Free", s.constraints.group > 1 ? `est. for ${s.constraints.group}` : "est. cost"],
  ];
  for (const [v, k] of items) dl.append(el("div", {}, el("dt", { text: k }), el("dd", { text: v })));
}

function renderChecks(s) {
  const ul = $("#checks");
  ul.textContent = "";
  const c = s.constraints;
  const has = (t) => s.violations.some((v) => v.type === t);
  const row = (kind, text) => ul.append(el("li", { class: kind },
    el("span", { class: "ico", "aria-hidden": "true", text: kind === "ok" ? "✓" : kind === "bad" ? "✕" : "i" }),
    el("span", { text: `${kind === "bad" ? "Problem: " : ""}${text}` })));
  if (s.stops.length) {
    row(has("closed") ? "bad" : "ok", has("closed") ? "a stop closes before your visit ends" : "Every stop is open while you're there");
    row(has("past_end") ? "bad" : "ok", `Done ${to12h(s.finish)}, your limit is ${to12h(toMin(c.end))}`);
    row(has("leg_too_long") ? "bad" : "ok", `Longest walk ${s.longestWalk} min, your limit is ${c.maxWalk}`);
    row(has("over_budget") ? "bad" : "ok", `About $${s.cost} of your $${c.budget} budget`);
  }
  for (const v of s.violations) if (!["closed", "past_end", "leg_too_long", "over_budget"].includes(v.type)) row("bad", v.message);
  for (const n of s.notes) row("info", n.message);
  for (const n of state.notes) row("info", n);
}

function renderTrace() {
  const box = $("#trace");
  const isAgent = state.engine !== "rules" && state.trace.length;
  box.hidden = !isAgent;
  if (!isAgent) return;
  $("#trace-summary").textContent = `How the agent built this plan (${state.trace.length} steps)`;
  const ol = $("#trace-list");
  ol.textContent = "";
  for (const t of state.trace) ol.append(el("li", { class: t.ok ? "" : "fail", text: t.summary }));
  const tokens = state.usage ? (state.usage.input_tokens || 0) + (state.usage.output_tokens || 0) : 0;
  $("#trace-meta").textContent = `${state.model || "Claude"}, ${state.rounds} model calls, ${tokens.toLocaleString()} tokens. Walking times: ${state.walkSource === "google" ? "Google Maps walking routes" : "straight-line estimates"}. Every submitted plan is re-checked by the same validator as the rule planner.`;
}

function renderEngine() {
  const note = $("#engine-note");
  note.textContent = ENGINE_NOTES[state.ai];
  note.className = `engine-note${state.ai === "ready" ? " ai" : ""}`;
  const badge = $("#engine-badge");
  badge.textContent = state.engine === "claude" ? "Planned by Claude" : state.engine === "fallback" ? "Rule planner (agent fallback)" : "Rule planner";
  badge.className = `engine-badge${state.engine === "claude" ? " ai" : ""}`;
}

function renderChips() {
  const c = state.constraints;
  const s = currentSchedule();
  const ideas = [];
  if (c.budget > 0) ideas.push("Make it free");
  if (!s.stops.some((x) => PLACE_BY_ID[x.id].tags.includes("coffee")) && c.stops < 6) ideas.push("Add a coffee stop");
  if (!c.interests.includes("nature")) ideas.push("More outdoors");
  if (c.maxWalk > 10) ideas.push("Less walking");
  ideas.push(toMin(c.start) < 13 * 60 ? "Start at 1 pm" : "Start at 10 am");
  if (c.stops > 2) ideas.push("Fewer stops");
  const box = $("#chips");
  box.textContent = "";
  for (const text of ideas.slice(0, 5)) box.append(el("button", { type: "button", class: "chip", text, disabled: state.busy, onclick: () => ask(text) }));
}

function render({ animate = false } = {}) {
  const s = currentSchedule();
  renderEngine();
  renderTotals(s);
  renderTrail(s, animate);
  renderChecks(s);
  renderTrace();
  renderChips();
  syncLimitsForm();
  drawMap(s, animate);
  $("#ask-btn").textContent = state.busy ? "Planning…" : (state.history.length ? "Update plan" : "Plan my day");
}

// ---------------------------------------------------------------- map

let map = null;
const layers = { casing: null, route: null, origin: null, stops: new Map(), dots: new Map() };

function popupFor(id) {
  const p = PLACE_BY_ID[id];
  const inPlan = state.stopIds.includes(id);
  const box = el("div", { class: "pop" },
    el("h3", { text: p.name }),
    el("p", { text: p.blurb }),
    el("p", { class: "pop-meta", text: `${p.area}. Open about ${to12h(toMin(p.open))} to ${to12h(toMin(p.close))}. ${p.cost ? `About $${p.cost} per person.` : "Free."} ${p.visit} min visit.` }));
  const btn = el("button", { type: "button", text: inPlan ? "In your route" : "Add to my day" });
  if (inPlan) btn.disabled = true;
  else btn.addEventListener("click", () => { map.closePopup(); addPlace(id); });
  box.append(btn);
  return box;
}

function initMap() {
  if (!window.L) { $("#map-fallback").hidden = false; return; }
  map = L.map("map", { scrollWheelZoom: false, zoomControl: true }).setView([42.356, -71.063], 14);
  map.attributionControl.setPrefix('<a href="https://leafletjs.com">Leaflet</a>');
  window.addEventListener("resize", () => map.invalidateSize());
  const tiles = L.tileLayer("https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png", {
    subdomains: "abcd", maxZoom: 19,
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>',
  });
  let loaded = false, errors = 0;
  tiles.on("tileload", () => { loaded = true; $("#map-fallback").hidden = true; });
  tiles.on("tileerror", () => { errors += 1; if (!loaded && errors >= 6) $("#map-fallback").hidden = false; });
  tiles.addTo(map);
  map.on("click", () => map.scrollWheelZoom.enable());
  map.on("mouseout", () => map.scrollWheelZoom.disable());
  for (const p of PLACES) {
    const dot = L.circleMarker([p.lat, p.lng], { radius: 5, weight: 2, color: "#ffffff", fillColor: "#8c9aa3", fillOpacity: 1 });
    dot.bindTooltip(p.name, { direction: "top", offset: [0, -6] });
    dot.bindPopup(() => popupFor(p.id));
    dot.addTo(map);
    layers.dots.set(p.id, dot);
  }
}

function animateRoute(line) {
  const path = line.getElement && line.getElement();
  if (!path || reduceMotion || !path.getTotalLength) return;
  const len = Math.ceil(path.getTotalLength());
  path.style.transition = "none";
  path.style.strokeDasharray = `${len}`;
  path.style.strokeDashoffset = `${len}`;
  path.getBoundingClientRect();
  path.style.transition = "stroke-dashoffset 1s ease-out";
  path.style.strokeDashoffset = "0";
  const done = () => { path.style.transition = ""; path.style.strokeDasharray = ""; path.style.strokeDashoffset = ""; };
  path.addEventListener("transitionend", done, { once: true });
  setTimeout(done, 1400);
}

function drawMap(s, animate) {
  if (!map) return;
  for (const k of ["casing", "route", "origin"]) if (layers[k]) { layers[k].remove(); layers[k] = null; }
  for (const m of layers.stops.values()) m.remove();
  layers.stops.clear();
  const origin = ORIGIN_BY_ID[s.constraints.origin];
  const pts = [[origin.lat, origin.lng], ...s.stops.map((x) => [PLACE_BY_ID[x.id].lat, PLACE_BY_ID[x.id].lng])];
  for (const [id, dot] of layers.dots) dot.setStyle({ opacity: state.stopIds.includes(id) ? 0 : 1, fillOpacity: state.stopIds.includes(id) ? 0 : 1 });
  layers.casing = L.polyline(pts, { color: "#ffffff", weight: 10, opacity: 0.95, lineCap: "round", lineJoin: "round", interactive: false }).addTo(map);
  layers.route = L.polyline(pts, { color: "#b4372a", weight: 5, opacity: 1, lineCap: "round", lineJoin: "round", interactive: false }).addTo(map);
  layers.origin = L.marker([origin.lat, origin.lng], {
    icon: L.divIcon({ className: "origin-pin", iconSize: [22, 22] }), title: `Start: ${origin.name}`, keyboard: false,
  }).addTo(map);
  s.stops.forEach((x, i) => {
    const p = PLACE_BY_ID[x.id];
    const m = L.marker([p.lat, p.lng], {
      icon: L.divIcon({ className: "stop-pin", html: String(i + 1), iconSize: [28, 28] }),
      title: `${i + 1}. ${p.name}`, alt: `${i + 1}. ${p.name}`, zIndexOffset: 1000,
    });
    m.bindPopup(() => popupFor(x.id));
    m.on("mouseover", () => setActive(x.id));
    m.on("mouseout", () => setActive(null));
    m.addTo(map);
    layers.stops.set(x.id, m);
  });
  map.invalidateSize();
  if (pts.length > 1) map.fitBounds(L.latLngBounds(pts).pad(0.25), { animate: !reduceMotion, maxZoom: 16 });
  else map.setView(pts[0], 15, { animate: !reduceMotion });
  if (animate) animateRoute(layers.route);
}

function setActive(id) {
  for (const li of document.querySelectorAll("#trail .station")) li.classList.toggle("active", li.dataset.id === id);
  for (const [sid, m] of layers.stops) {
    const node = m.getElement && m.getElement();
    if (node) node.classList.toggle("active", sid === id);
  }
}

// ---------------------------------------------------------------- start

async function checkAgent() {
  if (!API) return;
  try {
    const res = await fetch(`${API}/api/health`, { signal: AbortSignal.timeout(8000) });
    const data = await res.json();
    state.ai = res.ok && data.ok && data.ai ? "ready" : "down";
  } catch {
    state.ai = "down";
  }
  renderEngine();
}

function start() {
  buildLimitsForm();
  try { initMap(); } catch { $("#map-fallback").hidden = false; }
  applyRules(plan(state.constraints));
  render({ animate: true });
  $("#ask").addEventListener("submit", (e) => { e.preventDefault(); ask($("#ask-input").value); });
  $("#ask-input").addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); ask(e.target.value); }
  });
  renderCharts();
  let t = 0;
  window.addEventListener("resize", () => { clearTimeout(t); t = setTimeout(renderCharts, 150); });
  checkAgent();
}

start();
