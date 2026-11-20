// The trip-planning agent: Claude calls tools in a loop, and every plan it submits
// is re-checked by the same deterministic validator the page uses (src/core.js).

import {
  PLACES, PLACE_BY_ID, ORIGINS, ORIGIN_BY_ID, INTERESTS,
  normalizeConstraints, schedule, relevance, walkMinutes, locationOf, legKey,
  toMin, to12h, plan as rulePlan, explainStop,
} from "../src/core.js";

const MAX_MESSAGE = 600;
const MAX_REPLY = 400;
const MAX_REASON = 160;
const MAX_HISTORY_TURNS = 6;

export const TOOLS = [
  {
    name: "search_places",
    description: "Rank catalog places for a request. Returns ids with tags, estimated hours, visit minutes, price per person and walking minutes from a reference point. Use it to find candidates; it does not check a whole itinerary.",
    input_schema: {
      type: "object",
      properties: {
        query: { type: "string", description: "Free-text wishes, e.g. 'old churches and harbor views'." },
        interests: { type: "array", items: { type: "string", enum: INTERESTS } },
        near: { type: "string", description: "Place id or start point id to measure walking time from." },
        max_walk_min: { type: "integer", minimum: 1, maximum: 60 },
        max_price_per_person: { type: "number", minimum: 0 },
        limit: { type: "integer", minimum: 1, maximum: 12 },
      },
    },
  },
  {
    name: "walk_time",
    description: "Walking minutes between two catalog places or start points, given by id.",
    input_schema: {
      type: "object",
      properties: { from: { type: "string" }, to: { type: "string" } },
      required: ["from", "to"],
    },
  },
  {
    name: "update_constraints",
    description: "Change the traveler's constraints when their message asks for it. Omit fields that do not change. budget is the total for the whole group in USD.",
    input_schema: {
      type: "object",
      properties: {
        start: { type: "string", description: "HH:MM, 24-hour clock" },
        end: { type: "string", description: "HH:MM, 24-hour clock" },
        budget: { type: "number", minimum: 0 },
        group: { type: "integer", minimum: 1, maximum: 12 },
        max_walk: { type: "integer", minimum: 3, maximum: 60, description: "Maximum walking minutes per leg" },
        stops: { type: "integer", minimum: 1, maximum: 6 },
        interests: { type: "array", items: { type: "string", enum: INTERESTS } },
        origin: { type: "string", enum: ORIGINS.map((o) => o.id) },
      },
    },
  },
  {
    name: "check_itinerary",
    description: "Simulate an ordered list of stop ids against the current constraints: walking per leg, arrival and departure times, opening hours, finish time and total cost. Returns every violation. Call this before submitting.",
    input_schema: {
      type: "object",
      properties: { stop_ids: { type: "array", items: { type: "string" }, maxItems: 8 } },
      required: ["stop_ids"],
    },
  },
  {
    name: "submit_itinerary",
    description: "Submit the final plan in visiting order. It is checked again; if it breaks a constraint you get the violations back and must fix them.",
    input_schema: {
      type: "object",
      properties: {
        stop_ids: { type: "array", items: { type: "string" }, maxItems: 8 },
        reply: { type: "string", description: "One or two plain sentences to the traveler. No markdown." },
        reasons: {
          type: "array",
          items: {
            type: "object",
            properties: { id: { type: "string" }, why: { type: "string" } },
            required: ["id", "why"],
          },
        },
      },
      required: ["stop_ids", "reply"],
    },
  },
];

const CATALOG_TEXT = PLACES.map((p) =>
  `${p.id} | ${p.name} | ${p.area} | ${p.tags.join(", ")} | ${p.open}-${p.close} | ${p.visit} min | $${p.cost}`,
).join("\n");

const ORIGINS_TEXT = ORIGINS.map((o) => `${o.id} | ${o.name}`).join("\n");

export const SYSTEM_PROMPT = `You are the planning agent for Treasure Travel, a demo that plans walkable days in Boston.

Rules:
- Use only places from the catalog below, by id. Never invent places, prices or opening hours.
- Respect every constraint: start and finish time, total budget for the whole group (price per person times group size), group size, maximum walking minutes per leg, number of stops, interests and start point.
- If the traveler's message changes a constraint, call update_constraints before planning.
- Before submitting, call check_itinerary on the stop order you propose and fix every violation it reports. Waiting for a place to open is allowed, but avoid long waits.
- Finish by calling submit_itinerary once, with stop ids in visiting order, a reply of at most two plain sentences, and a short reason for each stop.
- If fewer stops than requested fit, submit the best valid plan and say so in the reply.
- If the message is not about planning a day in Boston, resubmit the current stops unchanged and reply that you can only help plan Boston days.

Start points (id | name):
${ORIGINS_TEXT}

Catalog (id | name | area | tags | estimated hours | visit length | estimated price per person):
${CATALOG_TEXT}`;

// ---------------------------------------------------------------- input hygiene

function cleanIds(list) {
  if (!Array.isArray(list)) return [];
  return [...new Set(list.filter((x) => typeof x === "string" && x.length <= 40))].slice(0, 10);
}

function cleanText(s, max) {
  return String(s ?? "").replace(/[\u0000-\u001f]+/g, " ").trim().slice(0, max);
}

// The Messages API needs alternating roles that start with the user.
export function cleanHistory(history) {
  const turns = (Array.isArray(history) ? history : [])
    .filter((t) => t && (t.role === "user" || t.role === "assistant") && typeof t.text === "string")
    .slice(-MAX_HISTORY_TURNS * 2)
    .map((t) => ({ role: t.role, content: cleanText(t.text, MAX_MESSAGE) }))
    .filter((t) => t.content);
  const merged = [];
  for (const t of turns) {
    if (merged.length && merged[merged.length - 1].role === t.role) merged[merged.length - 1].content += `\n${t.content}`;
    else merged.push({ ...t });
  }
  while (merged.length && merged[0].role !== "user") merged.shift();
  return merged;
}

function describeConstraints(c) {
  return `start ${c.start}, finish ${c.end}, group of ${c.group}, total budget $${c.budget}, at most ${c.maxWalk} min walking per leg, ${c.stops} stops, interests: ${c.interests.join(", ") || "none"}, start point: ${c.origin}`;
}

function stateText(ctx, current) {
  return [
    `Current constraints: ${describeConstraints(ctx.constraints)}.`,
    `Current itinerary: ${current.length ? current.join(", ") : "none yet"}.`,
    ctx.locked.length ? `The traveler wants to keep: ${ctx.locked.join(", ")}.` : "",
    ctx.excluded.length ? `The traveler removed: ${ctx.excluded.join(", ")}. Do not use them.` : "",
  ].filter(Boolean).join("\n");
}

// ---------------------------------------------------------------- tools

async function walkBetween(fromId, toId, ctx) {
  const a = locationOf(fromId), b = locationOf(toId);
  if (!a || !b) return null;
  const k = legKey(fromId, toId);
  if (ctx.legs[k]) return ctx.legs[k];
  if (ctx.walkLive) {
    const live = await ctx.walkLive(a, b);
    if (live) { ctx.legs[k] = live; return live; }
  }
  return walkMinutes(a, b);
}

async function fillLegs(stopIds, ctx) {
  if (!ctx.walkLive) return;
  let prev = ctx.constraints.origin;
  for (const id of stopIds) {
    if (!PLACE_BY_ID[id]) break;
    await walkBetween(prev, id, ctx);
    prev = id;
  }
}

async function fullCheck(stopIds, ctx) {
  await fillLegs(stopIds, ctx);
  const s = schedule(stopIds, ctx.constraints, { legs: ctx.legs });
  const extra = [];
  for (const id of stopIds) if (ctx.excluded.includes(id)) extra.push({ type: "removed", id, message: `${PLACE_BY_ID[id]?.name || id} was removed by the traveler.` });
  for (const id of ctx.locked) if (!stopIds.includes(id)) extra.push({ type: "missing_kept", id, message: `${PLACE_BY_ID[id]?.name || id} must stay in the plan.` });
  if (stopIds.length > ctx.constraints.stops) extra.push({ type: "too_many", message: `${stopIds.length} stops is more than the ${ctx.constraints.stops} requested.` });
  return { ...s, violations: [...s.violations, ...extra], ok: s.ok && extra.length === 0 };
}

function scheduleLines(s) {
  return s.stops.map((x, i) =>
    `${i + 1}. ${x.id}: walk ${x.walk} min, arrive ${to12h(x.arrive)}, visit ${to12h(x.begin)}-${to12h(x.leave)}, $${x.cost}`,
  ).join("\n");
}

const CONSTRAINT_FIELDS = { start: "start", end: "end", budget: "budget", group: "group", max_walk: "maxWalk", stops: "stops", interests: "interests", origin: "origin" };

async function execTool(name, input, ctx) {
  input = input && typeof input === "object" ? input : {};
  switch (name) {
    case "search_places": {
      const c = { ...ctx.constraints };
      if (Array.isArray(input.interests)) c.interests = input.interests;
      const rel = relevance(c, cleanText(input.query, 200));
      const near = locationOf(input.near) ? input.near : ctx.constraints.origin;
      const limit = Math.max(1, Math.min(12, Number(input.limit) || 8));
      const rows = [];
      for (const p of PLACES) {
        if (ctx.excluded.includes(p.id)) continue;
        if (Number.isFinite(input.max_price_per_person) && p.cost > input.max_price_per_person) continue;
        const walk = walkMinutes(locationOf(near), p);
        if (Number.isFinite(input.max_walk_min) && walk > input.max_walk_min) continue;
        rows.push({ p, walk, score: rel[p.id].score - 0.05 * walk });
      }
      rows.sort((a, b) => b.score - a.score || a.p.id.localeCompare(b.p.id));
      const top = rows.slice(0, limit);
      ctx.trace.push({ tool: name, ok: true, summary: `Searched ${input.query ? `"${cleanText(input.query, 60)}"` : "the catalog"}: ${top.length} candidates` });
      return {
        text: top.length
          ? top.map(({ p, walk }) => `${p.id} | ${p.name} | ${p.tags.join(", ")} | ${p.open}-${p.close} | ${p.visit} min | $${p.cost} | ${walk} min walk from ${near}`).join("\n")
          : "No places match those filters.",
      };
    }
    case "walk_time": {
      const m = await walkBetween(input.from, input.to, ctx);
      if (m === null) return { text: "Unknown id. Use catalog place ids or start point ids.", isError: true };
      const live = Boolean(ctx.legs[legKey(input.from, input.to)]);
      ctx.trace.push({ tool: name, ok: true, summary: `Walk ${input.from} to ${input.to}: ${m} min` });
      return { text: `${m} min (${live ? "Google Maps walking route" : "straight-line estimate"})` };
    }
    case "update_constraints": {
      const patch = {};
      for (const [k, v] of Object.entries(CONSTRAINT_FIELDS)) if (input[k] !== undefined) patch[v] = input[k];
      const before = ctx.constraints;
      ctx.constraints = normalizeConstraints({ ...before, ...patch });
      const changed = Object.keys(ctx.constraints).filter((k) => JSON.stringify(ctx.constraints[k]) !== JSON.stringify(before[k]));
      ctx.trace.push({ tool: name, ok: true, summary: changed.length ? `Updated ${changed.join(", ")}` : "No constraint changes" });
      return { text: `Constraints now: ${describeConstraints(ctx.constraints)}.` };
    }
    case "check_itinerary": {
      const ids = cleanIds(input.stop_ids);
      const s = await fullCheck(ids, ctx);
      ctx.trace.push({ tool: name, ok: s.ok, summary: `Checked ${ids.length} stops: ${s.ok ? "no problems" : `${s.violations.length} problem${s.violations.length > 1 ? "s" : ""}`}` });
      return {
        text: [
          scheduleLines(s) || "No stops.",
          `Total cost $${s.cost} of $${s.constraints.budget}. Finish ${to12h(s.finish)} (limit ${to12h(toMin(s.constraints.end))}).`,
          s.violations.length ? `Violations:\n- ${s.violations.map((v) => v.message).join("\n- ")}` : "No violations.",
          s.notes.length ? `Notes:\n- ${s.notes.map((n) => n.message).join("\n- ")}` : "",
        ].filter(Boolean).join("\n"),
      };
    }
    case "submit_itinerary": {
      const ids = cleanIds(input.stop_ids);
      const s = await fullCheck(ids, ctx);
      if (!s.ok) {
        ctx.trace.push({ tool: name, ok: false, summary: `Plan rejected: ${s.violations.length} problem${s.violations.length > 1 ? "s" : ""}` });
        return { text: `Not accepted. Fix these and submit again:\n- ${s.violations.map((v) => v.message).join("\n- ")}`, isError: true };
      }
      const reasons = {};
      for (const r of Array.isArray(input.reasons) ? input.reasons : []) {
        if (r && ids.includes(r.id)) reasons[r.id] = cleanText(r.why, MAX_REASON);
      }
      ctx.final = { stopIds: ids, reply: cleanText(input.reply, MAX_REPLY), reasons };
      ctx.trace.push({ tool: name, ok: true, summary: `Plan accepted: ${ids.length} stops passed every check` });
      return { text: "Accepted." };
    }
    default:
      ctx.trace.push({ tool: String(name).slice(0, 40), ok: false, summary: "Unknown tool" });
      return { text: `Unknown tool ${String(name).slice(0, 40)}.`, isError: true };
  }
}

// ---------------------------------------------------------------- loop

function fallbackReasons(stopIds, ctx, query) {
  const rel = relevance(ctx.constraints, query);
  const out = {};
  let prev = locationOf(ctx.constraints.origin);
  for (const id of stopIds) {
    const p = PLACE_BY_ID[id];
    out[id] = explainStop(p, rel[id], walkMinutes(prev, p), ctx.constraints);
    prev = p;
  }
  return out;
}

export async function runAgent(input, deps) {
  const { callModel, walkLive = null, maxRounds = 8, maxTokens = 1024 } = deps;
  const message = cleanText(input?.message, MAX_MESSAGE);
  if (!message) throw new Error("message is required");
  const ctx = {
    constraints: normalizeConstraints(input?.constraints),
    locked: cleanIds(input?.locked).filter((id) => PLACE_BY_ID[id]),
    excluded: cleanIds(input?.excluded).filter((id) => PLACE_BY_ID[id]),
    legs: {}, walkLive, final: null, trace: [],
  };
  const current = cleanIds(input?.current).filter((id) => PLACE_BY_ID[id]);

  const messages = cleanHistory(input?.history);
  const userTurn = `${stateText(ctx, current)}\n\nTraveler: ${message}`;
  if (messages.length && messages[messages.length - 1].role === "user") messages[messages.length - 1].content += `\n\n${userTurn}`;
  else messages.push({ role: "user", content: userTurn });

  const usage = { input_tokens: 0, output_tokens: 0 };
  let reply = "", rounds = 0;
  while (rounds < maxRounds && !ctx.final) {
    rounds += 1;
    const resp = await callModel({ system: SYSTEM_PROMPT, messages, tools: TOOLS, maxTokens });
    usage.input_tokens += resp?.usage?.input_tokens || 0;
    usage.output_tokens += resp?.usage?.output_tokens || 0;
    const content = Array.isArray(resp?.content) ? resp.content : [];
    messages.push({ role: "assistant", content });
    const calls = content.filter((b) => b.type === "tool_use");
    if (!calls.length) {
      reply = cleanText(content.filter((b) => b.type === "text").map((b) => b.text).join(" "), MAX_REPLY);
      break;
    }
    const results = [];
    for (const call of calls) {
      const r = await execTool(call.name, call.input, ctx);
      results.push({ type: "tool_result", tool_use_id: call.id, content: r.text, ...(r.isError ? { is_error: true } : {}) });
    }
    messages.push({ role: "user", content: results });
  }

  let stopIds, reasons, fallback = false;
  if (ctx.final) {
    stopIds = ctx.final.stopIds;
    reasons = { ...fallbackReasons(stopIds, ctx, message), ...ctx.final.reasons };
    reply = ctx.final.reply || reply;
  } else if (reply) {
    // The model answered in words, for example a question. Keep the current plan.
    const s = await fullCheck(current, ctx);
    stopIds = s.ok ? current : [];
    reasons = fallbackReasons(stopIds, ctx, message);
  } else {
    // No accepted plan within the round limit: use the rule-based planner instead.
    const r = rulePlan(ctx.constraints, { locked: ctx.locked, excluded: ctx.excluded, query: message });
    stopIds = r.stopIds;
    reasons = r.reasons;
    fallback = true;
    reply = "I couldn't finish checking a plan in time, so this one comes from the rule-based planner.";
    ctx.trace.push({ tool: "fallback", ok: true, summary: "Used the rule-based planner" });
  }

  await fillLegs(stopIds, ctx);
  const legs = {};
  let prev = ctx.constraints.origin;
  for (const id of stopIds) { const k = legKey(prev, id); if (ctx.legs[k]) legs[k] = ctx.legs[k]; prev = id; }
  const sched = schedule(stopIds, ctx.constraints, { legs });
  return {
    reply, constraints: ctx.constraints, stopIds, legs, reasons,
    schedule: sched, trace: ctx.trace, usage, rounds, fallback,
    walkSource: walkLive ? "google" : "estimate",
  };
}
