// Cloudflare Worker that serves the planning agent to the static demo page.
// The Anthropic key stays here as a secret; the page never sees it.
//
//   GET  /api/health  -> { ok, ai, model, maps }
//   POST /api/plan    -> { ok, engine, model, reply, constraints, stopIds, legs, reasons, schedule, trace, usage }

import { runAgent } from "./agent.js";
import { makeClaude, ModelError } from "./anthropic.js";
import { makeGoogleWalk } from "./maps.js";

const MAX_BODY = 16000;
const memoryCounts = new Map(); // fallback when no KV namespace is bound (per isolate only)

function corsHeaders(request, env) {
  const origin = request.headers.get("Origin") || "";
  const allowed = String(env.ALLOWED_ORIGINS || "").split(",").map((s) => s.trim()).filter(Boolean);
  const ok = allowed.includes("*") || allowed.includes(origin);
  return {
    allowed: ok || !origin, // non-browser clients send no Origin header
    headers: {
      ...(ok ? { "Access-Control-Allow-Origin": allowed.includes("*") ? "*" : origin } : {}),
      "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
      "Access-Control-Allow-Headers": "content-type",
      "Access-Control-Max-Age": "600",
      Vary: "Origin",
    },
  };
}

function json(body, status, headers) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json; charset=utf-8", "cache-control": "no-store", ...headers },
  });
}

async function bump(env, key, ttl) {
  if (env.RATE_KV) {
    const n = Number((await env.RATE_KV.get(key)) || 0) + 1;
    await env.RATE_KV.put(key, String(n), { expirationTtl: ttl });
    return n;
  }
  const now = Date.now();
  const entry = memoryCounts.get(key);
  const n = entry && entry.until > now ? entry.n + 1 : 1;
  memoryCounts.set(key, { n, until: now + ttl * 1000 });
  return n;
}

async function withinLimits(request, env) {
  const ip = request.headers.get("CF-Connecting-IP") || "unknown";
  const iso = new Date().toISOString();
  const perHour = Number(env.PER_IP_PER_HOUR || 20);
  const perDay = Number(env.DAILY_LIMIT || 300);
  const ipCount = await bump(env, `ip:${ip}:${iso.slice(0, 13)}`, 3700);
  const dayCount = await bump(env, `day:${iso.slice(0, 10)}`, 90000);
  return ipCount <= perHour && dayCount <= perDay;
}

export async function handle(request, env, deps = {}) {
  const url = new URL(request.url);
  const cors = corsHeaders(request, env);
  if (request.method === "OPTIONS") return new Response(null, { status: 204, headers: cors.headers });
  if (!cors.allowed) return json({ ok: false, error: "origin_not_allowed" }, 403, cors.headers);

  const model = env.MODEL || "claude-haiku-5-5";
  if (url.pathname === "/api/health" && request.method === "GET") {
    return json({ ok: true, ai: Boolean(env.ANTHROPIC_API_KEY), model, maps: env.GOOGLE_MAPS_API_KEY ? "google" : "estimate" }, 200, cors.headers);
  }
  if (url.pathname !== "/api/plan" || request.method !== "POST") {
    return json({ ok: false, error: "not_found" }, 404, cors.headers);
  }
  if (!env.ANTHROPIC_API_KEY) return json({ ok: false, error: "ai_not_configured" }, 503, cors.headers);

  const raw = await request.text();
  if (raw.length > MAX_BODY) return json({ ok: false, error: "request_too_large" }, 413, cors.headers);
  let body;
  try { body = JSON.parse(raw); } catch { return json({ ok: false, error: "invalid_json" }, 400, cors.headers); }
  if (!body || typeof body.message !== "string" || !body.message.trim()) {
    return json({ ok: false, error: "message_required" }, 400, cors.headers);
  }
  if (!(await withinLimits(request, env))) return json({ ok: false, error: "rate_limited" }, 429, cors.headers);

  const callModel = deps.callModel || makeClaude({
    apiKey: env.ANTHROPIC_API_KEY,
    model,
    version: env.ANTHROPIC_VERSION || "2026-10-21",
    baseUrl: env.ANTHROPIC_BASE_URL || "https://api.anthropic.com",
  });
  const walkLive = deps.walkLive !== undefined
    ? deps.walkLive
    : (env.GOOGLE_MAPS_API_KEY ? makeGoogleWalk({ apiKey: env.GOOGLE_MAPS_API_KEY }) : null);

  try {
    const result = await runAgent(body, {
      callModel,
      walkLive,
      maxRounds: Math.max(2, Math.min(12, Number(env.MAX_ROUNDS || 8))),
      maxTokens: Math.max(256, Math.min(4096, Number(env.MAX_TOKENS || 1024))),
    });
    return json({ ok: true, engine: "claude", model, ...result }, 200, cors.headers);
  } catch (err) {
    const status = err instanceof ModelError && err.status === 429 ? 429 : 502;
    console.error("plan failed", err?.status || "", err?.message || err, err?.detail || "");
    return json({ ok: false, error: status === 429 ? "model_busy" : "agent_failed" }, status, cors.headers);
  }
}

export default {
  fetch(request, env) {
    return handle(request, env);
  },
};
