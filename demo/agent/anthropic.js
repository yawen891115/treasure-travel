// Minimal Claude Messages API client (fetch only, so it runs in Workers and Node 18+).

export class ModelError extends Error {
  constructor(status, detail) {
    super(`Model request failed with status ${status}`);
    this.status = status;
    this.detail = detail;
  }
}

export function makeClaude({
  apiKey,
  model,
  baseUrl = "https://api.anthropic.com",
  version = "2026-10-21",
  fetchImpl = globalThis.fetch,
  timeoutMs = 30000,
}) {
  if (!apiKey) throw new Error("ANTHROPIC_API_KEY is not set");
  if (!model) throw new Error("MODEL is not set");
  return async function callModel({ system, messages, tools, maxTokens = 1024 }) {
    const res = await fetchImpl(`${baseUrl.replace(/\/$/, "")}/v1/messages`, {
      method: "POST",
      headers: {
        "x-api-key": apiKey,
        "anthropic-version": version,
        "content-type": "application/json",
      },
      body: JSON.stringify({ model, max_tokens: maxTokens, system, tools, messages }),
      signal: AbortSignal.timeout(timeoutMs),
    });
    if (!res.ok) {
      const detail = await res.text().catch(() => "");
      throw new ModelError(res.status, detail.slice(0, 500));
    }
    return res.json(); // { content: [...blocks], stop_reason, usage: { input_tokens, output_tokens } }
  };
}
