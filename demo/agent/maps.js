// Optional live walking times from the Google Maps Routes API.
// Used only when GOOGLE_MAPS_API_KEY is set; otherwise the agent uses the
// straight-line estimate from core.js. Every Routes call is billed by Google.

const ROUTES_URL = "https://routes.googleapis.com/directions/v2:computeRoutes";

export function makeGoogleWalk({ apiKey, fetchImpl = globalThis.fetch, timeoutMs = 8000, maxCalls = 40 }) {
  if (!apiKey) throw new Error("GOOGLE_MAPS_API_KEY is not set");
  const cache = new Map();
  let calls = 0;
  return async function walkMinutesLive(a, b) {
    const key = `${a.lat.toFixed(5)},${a.lng.toFixed(5)}>${b.lat.toFixed(5)},${b.lng.toFixed(5)}`;
    if (cache.has(key)) return cache.get(key);
    if (calls >= maxCalls) return null; // per-request budget for paid calls
    calls += 1;
    try {
      const res = await fetchImpl(ROUTES_URL, {
        method: "POST",
        headers: {
          "content-type": "application/json",
          "X-Goog-Api-Key": apiKey,
          "X-Goog-FieldMask": "routes.duration",
        },
        body: JSON.stringify({
          origin: { location: { latLng: { latitude: a.lat, longitude: a.lng } } },
          destination: { location: { latLng: { latitude: b.lat, longitude: b.lng } } },
          travelMode: "WALK",
        }),
        signal: AbortSignal.timeout(timeoutMs),
      });
      if (!res.ok) return null;
      const data = await res.json();
      const m = /^(\d+(?:\.\d+)?)s$/.exec(data?.routes?.[0]?.duration || "");
      const minutes = m ? Math.max(1, Math.ceil(Number(m[1]) / 60)) : null;
      if (minutes !== null) cache.set(key, minutes);
      return minutes;
    } catch {
      return null; // fall back to the estimate for this leg
    }
  };
}
