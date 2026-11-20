import test from "node:test";
import assert from "node:assert/strict";
import { runAgent, cleanHistory, TOOLS, SYSTEM_PROMPT } from "../agent/agent.js";
import { handle } from "../agent/index.js";
import { makeClaude } from "../agent/anthropic.js";
import { makeGoogleWalk } from "../agent/maps.js";
import { DEFAULTS, legKey } from "../src/core.js";

// A scripted stand-in for Claude: each call returns the next canned response.
function scripted(responses) {
  const calls = [];
  const fn = async (req) => {
    calls.push(JSON.parse(JSON.stringify(req)));
    const next = responses[calls.length - 1];
    if (!next) throw new Error("model called too many times");
    return next;
  };
  fn.calls = calls;
  return fn;
}
const use = (id, name, input) => ({ type: "tool_use", id, name, input });
const reply = (content) => ({ content, stop_reason: "tool_use", usage: { input_tokens: 100, output_tokens: 20 } });

test("agent fixes a rejected plan and returns the accepted one", async () => {
  const model = scripted([
    reply([use("t1", "update_constraints", { budget: 0, interests: ["nature"] }), use("t2", "check_itinerary", { stop_ids: ["aquarium", "public-garden"] })]),
    reply([use("t3", "submit_itinerary", { stop_ids: ["aquarium"], reply: "x" })]),
    reply([use("t4", "submit_itinerary", { stop_ids: ["boston-common", "public-garden"], reply: "Two free green stops.", reasons: [{ id: "public-garden", why: "Lagoon walk" }] })]),
  ]);
  const r = await runAgent({ message: "make it free and outdoorsy", constraints: DEFAULTS }, { callModel: model });
  assert.deepEqual(r.stopIds, ["boston-common", "public-garden"]);
  assert.equal(r.constraints.budget, 0);
  assert.equal(r.reply, "Two free green stops.");
  assert.equal(r.reasons["public-garden"], "Lagoon walk");
  assert.ok(r.reasons["boston-common"].length > 0);
  assert.equal(r.schedule.ok, true);
  assert.equal(r.fallback, false);
  assert.equal(r.usage.input_tokens, 300);
  // The rejected submission went back to the model as an error tool_result.
  const third = model.calls[2].messages.at(-1).content[0];
  assert.equal(third.type, "tool_result");
  assert.equal(third.is_error, true);
  assert.match(third.content, /over your \$0 budget/);
  assert.deepEqual(r.trace.map((t) => t.tool), ["update_constraints", "check_itinerary", "submit_itinerary", "submit_itinerary"]);
});

test("a plain text answer keeps the current plan", async () => {
  const model = scripted([{ content: [{ type: "text", text: "Which neighborhood do you prefer?" }], stop_reason: "end_turn", usage: {} }]);
  const r = await runAgent({ message: "hmm", constraints: DEFAULTS, current: ["granary"] }, { callModel: model });
  assert.equal(r.reply, "Which neighborhood do you prefer?");
  assert.deepEqual(r.stopIds, ["granary"]);
});

test("falls back to the rule planner when no plan is accepted in time", async () => {
  const model = scripted([
    reply([use("a", "search_places", { query: "history" })]),
    reply([use("b", "walk_time", { from: "park-street", to: "granary" })]),
  ]);
  const r = await runAgent({ message: "history please", constraints: DEFAULTS }, { callModel: model, maxRounds: 2 });
  assert.equal(r.fallback, true);
  assert.ok(r.stopIds.length > 0);
  assert.equal(r.schedule.ok, true);
});

test("removed and kept stops are enforced on submit", async () => {
  const model = scripted([
    reply([use("a", "submit_itinerary", { stop_ids: ["granary"], reply: "x" })]),
    reply([use("b", "submit_itinerary", { stop_ids: ["paul-revere"], reply: "ok" })]),
  ]);
  const r = await runAgent(
    { message: "go", constraints: DEFAULTS, excluded: ["granary"], locked: ["paul-revere"] },
    { callModel: model },
  );
  assert.deepEqual(r.stopIds, ["paul-revere"]);
  const first = model.calls[1].messages.at(-1).content[0].content;
  assert.match(first, /removed by the traveler/);
  assert.match(first, /must stay in the plan/);
});

test("unknown tools get an error result", async () => {
  const model = scripted([
    reply([use("a", "book_hotel", {})]),
    reply([use("b", "submit_itinerary", { stop_ids: ["granary"], reply: "ok" })]),
  ]);
  const r = await runAgent({ message: "x", constraints: DEFAULTS }, { callModel: model });
  assert.equal(model.calls[1].messages.at(-1).content[0].is_error, true);
  assert.deepEqual(r.stopIds, ["granary"]);
});

test("live walking times are used for checks and returned as legs", async () => {
  const model = scripted([reply([use("a", "submit_itinerary", { stop_ids: ["granary"], reply: "ok" })])]);
  const r = await runAgent({ message: "x", constraints: DEFAULTS }, { callModel: model, walkLive: async () => 11 });
  assert.equal(r.legs[legKey("park-street", "granary")], 11);
  assert.equal(r.schedule.stops[0].walk, 11);
  assert.equal(r.walkSource, "google");
});

test("history is cleaned into alternating turns that start with the user", () => {
  const h = cleanHistory([
    { role: "assistant", text: "hi" },
    { role: "user", text: "a" }, { role: "user", text: "b" },
    { role: "system", text: "ignore me" },
    { role: "assistant", text: "c" },
  ]);
  assert.deepEqual(h.map((t) => t.role), ["user", "assistant"]);
  assert.equal(h[0].content, "a\nb");
});

test("tool schemas and prompt are well formed", () => {
  for (const t of TOOLS) {
    assert.ok(t.name && t.description && t.input_schema?.type === "object");
  }
  assert.match(SYSTEM_PROMPT, /old-north \| Old North Church/);
});

test("Claude client sends the expected request", async () => {
  let seen;
  const callModel = makeClaude({
    apiKey: "k", model: "claude-haiku-5-5",
    fetchImpl: async (url, init) => { seen = { url, init }; return new Response(JSON.stringify({ content: [], usage: {} }), { status: 200 }); },
  });
  await callModel({ system: "s", messages: [{ role: "user", content: "hi" }], tools: TOOLS });
  assert.equal(seen.url, "https://api.anthropic.com/v1/messages");
  assert.equal(seen.init.headers["anthropic-version"], "2026-10-21");
  const body = JSON.parse(seen.init.body);
  assert.equal(body.model, "claude-haiku-5-5");
  assert.ok(!("temperature" in body));
});

test("Google walking client parses durations and caches them", async () => {
  let n = 0;
  const walk = makeGoogleWalk({
    apiKey: "g",
    fetchImpl: async () => { n++; return new Response(JSON.stringify({ routes: [{ duration: "421s" }] }), { status: 200 }); },
  });
  const a = { lat: 42.35, lng: -71.06 }, b = { lat: 42.36, lng: -71.05 };
  assert.equal(await walk(a, b), 8);
  assert.equal(await walk(a, b), 8);
  assert.equal(n, 1);
});

// ---------------------------------------------------------------- HTTP layer

const env = { ANTHROPIC_API_KEY: "k", ALLOWED_ORIGINS: "https://demo.example", PER_IP_PER_HOUR: "2", DAILY_LIMIT: "100" };
const post = (body, origin = "https://demo.example", ip = "1.1.1.1") => new Request("https://w.example/api/plan", {
  method: "POST", headers: { Origin: origin, "content-type": "application/json", "CF-Connecting-IP": ip }, body: JSON.stringify(body),
});

test("health and CORS preflight", async () => {
  const h = await handle(new Request("https://w.example/api/health", { headers: { Origin: "https://demo.example" } }), env);
  assert.equal(h.status, 200);
  assert.equal(h.headers.get("Access-Control-Allow-Origin"), "https://demo.example");
  assert.equal((await h.json()).ai, true);
  const pre = await handle(new Request("https://w.example/api/plan", { method: "OPTIONS", headers: { Origin: "https://demo.example" } }), env);
  assert.equal(pre.status, 204);
});

test("other origins, missing keys and bad bodies are refused", async () => {
  assert.equal((await handle(post({ message: "hi" }, "https://evil.example"), env)).status, 403);
  assert.equal((await handle(post({ message: "hi" }), { ...env, ANTHROPIC_API_KEY: "" })).status, 503);
  assert.equal((await handle(post({}), env)).status, 400);
});

test("plan endpoint returns the agent result and enforces the hourly limit", async () => {
  const callModel = scripted([
    reply([use("a", "submit_itinerary", { stop_ids: ["granary"], reply: "ok" })]),
    reply([use("b", "submit_itinerary", { stop_ids: ["granary"], reply: "ok" })]),
  ]);
  const deps = { callModel, walkLive: null };
  const r1 = await handle(post({ message: "plan", constraints: DEFAULTS }, undefined, "9.9.9.9"), env, deps);
  assert.equal(r1.status, 200);
  const body = await r1.json();
  assert.equal(body.engine, "claude");
  assert.deepEqual(body.stopIds, ["granary"]);
  assert.equal((await handle(post({ message: "plan" }, undefined, "9.9.9.9"), env, deps)).status, 200);
  assert.equal((await handle(post({ message: "plan" }, undefined, "9.9.9.9"), env, deps)).status, 429);
});
