import test from "node:test";
import assert from "node:assert/strict";
import {
  PLACES, ORIGINS, DEFAULTS, INTERESTS, toMin, to12h, walkMinutes, schedule, plan,
  normalizeConstraints, parseRequest, textSimilarity, legKey,
} from "../src/core.js";

test("catalog entries are well formed", () => {
  const ids = new Set();
  for (const p of PLACES) {
    assert.ok(!ids.has(p.id), `duplicate id ${p.id}`);
    ids.add(p.id);
    assert.ok(p.lat > 42.3 && p.lat < 42.4 && p.lng > -71.12 && p.lng < -71.0, `${p.id} outside Boston`);
    assert.ok(toMin(p.open) < toMin(p.close), `${p.id} hours`);
    assert.ok(p.visit > 0 && p.cost >= 0);
    assert.ok(p.tags.length && p.tags.every((t) => INTERESTS.includes(t)), `${p.id} tags`);
  }
  assert.ok(PLACES.length >= 35);
});

test("time helpers", () => {
  assert.equal(toMin("09:30"), 570);
  assert.equal(toMin("24:00"), null);
  assert.equal(to12h(570), "9:30 am");
  assert.equal(to12h(780), "1 pm");
  assert.equal(to12h(0), "12 am");
});

test("walking estimate is positive and symmetric", () => {
  const [a, b] = PLACES;
  assert.equal(walkMinutes(a, b), walkMinutes(b, a));
  assert.ok(walkMinutes(a, b) >= 1);
});

test("validator reports each kind of violation", () => {
  const c = { ...DEFAULTS, start: "15:30", end: "16:00", budget: 10, group: 2, maxWalk: 5 };
  const s = schedule(["mfa", "mfa", "nowhere"], c);
  const types = new Set(s.violations.map((v) => v.type));
  for (const t of ["leg_too_long", "closed", "past_end", "duplicate", "unknown_place", "over_budget"]) {
    assert.ok(types.has(t), `missing ${t}`);
  }
  assert.equal(s.ok, false);
});

test("leg overrides replace the estimate", () => {
  const c = normalizeConstraints({ ...DEFAULTS, origin: "park-street" });
  const s = schedule(["granary"], c, { legs: { [legKey("park-street", "granary")]: 9 } });
  assert.equal(s.stops[0].walk, 9);
});

test("every plan the planner returns passes the validator", () => {
  let seed = 7;
  const rand = () => ((seed = (seed * 1103515245 + 12345) % 2147483648) / 2147483648);
  for (let i = 0; i < 300; i++) {
    const startH = 8 + Math.floor(rand() * 9);
    const c = {
      start: `${String(startH).padStart(2, "0")}:00`,
      end: `${String(Math.min(23, startH + 2 + Math.floor(rand() * 7))).padStart(2, "0")}:30`,
      budget: Math.floor(rand() * 150),
      group: 1 + Math.floor(rand() * 4),
      maxWalk: 5 + Math.floor(rand() * 25),
      stops: 1 + Math.floor(rand() * 6),
      interests: INTERESTS.filter(() => rand() < 0.25),
      origin: ORIGINS[Math.floor(rand() * ORIGINS.length)].id,
    };
    const r = plan(c);
    assert.ok(r.schedule.ok, `invalid plan for ${JSON.stringify(c)}: ${JSON.stringify(r.schedule.violations)}`);
    assert.ok(r.stopIds.length <= r.constraints.stops);
  }
});

test("default day fills every requested stop", () => {
  const r = plan(DEFAULTS);
  assert.equal(r.stopIds.length, DEFAULTS.stops);
  assert.ok(r.schedule.ok);
});

test("kept stops are included and removed stops are not", () => {
  const r = plan(DEFAULTS, { locked: ["paul-revere"], excluded: ["faneuil-hall", "granary"] });
  assert.ok(r.stopIds.includes("paul-revere"));
  assert.ok(!r.stopIds.includes("faneuil-hall") && !r.stopIds.includes("granary"));
  assert.ok(r.schedule.ok);
});

test("a nature day picks nature stops when they fit", () => {
  const r = plan({ ...DEFAULTS, interests: ["nature"], budget: 0, stops: 3 });
  assert.ok(r.schedule.ok);
  assert.ok(r.stopIds.every((id) => PLACES.find((p) => p.id === id).tags.includes("nature")), r.stopIds.join());
});

test("text similarity finds the right place", () => {
  const sim = textSimilarity("the church with the lanterns");
  const best = Object.entries(sim).sort((a, b) => b[1] - a[1])[0][0];
  assert.equal(best, "old-north");
});

test("offline parser understands common requests", () => {
  const base = normalizeConstraints(DEFAULTS);
  assert.equal(parseRequest("make it free", base).constraints.budget, 0);
  assert.equal(parseRequest("keep it under $40", base).constraints.budget, 40);
  assert.equal(parseRequest("just the two of us", base).constraints.group, 2);
  assert.equal(parseRequest("family of four", base).constraints.group, 4);
  assert.equal(parseRequest("only three stops", base).constraints.stops, 3);
  assert.equal(parseRequest("start at 1pm and be back by 5", base).constraints.start, "13:00");
  assert.equal(parseRequest("start at 1pm and be back by 5", base).constraints.end, "17:00");
  assert.equal(parseRequest("less walking please", base).constraints.maxWalk, base.maxWalk - 5);
  assert.deepEqual(parseRequest("history and coffee", base).constraints.interests, ["history", "coffee"]);
  assert.deepEqual(parseRequest("more nature", base).constraints.interests, ["history", "food", "nature"]);
  assert.deepEqual(parseRequest("remove the aquarium", base).exclude, ["aquarium"]);
  assert.deepEqual(parseRequest("add fenway park", base).include, ["fenway-park"]);
  assert.equal(parseRequest("reset", base).reset, true);
});
