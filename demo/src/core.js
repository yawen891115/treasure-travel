// Treasure Travel planning core, shared by the browser page and the serverless agent.
// Places are real Boston landmarks. Coordinates are approximate; opening hours,
// visit lengths and prices are estimates written for this demo, not live data.

export const INTERESTS = [
  "history", "art", "nature", "food", "coffee",
  "views", "architecture", "family", "science", "shopping",
];

export const ORIGINS = [
  { id: "park-street", name: "Park Street (Boston Common)", lat: 42.3564, lng: -71.0624 },
  { id: "faneuil", name: "Faneuil Hall", lat: 42.3600, lng: -71.0560 },
  { id: "north-end", name: "Haymarket (North End)", lat: 42.3630, lng: -71.0583 },
  { id: "south-station", name: "South Station", lat: 42.3523, lng: -71.0553 },
  { id: "copley", name: "Copley Square", lat: 42.3500, lng: -71.0773 },
];

// cost = estimated price per person in USD; visit = typical minutes on site.
export const PLACES = [
  { id: "boston-common", name: "Boston Common", area: "Downtown", lat: 42.3551, lng: -71.0657, tags: ["nature", "history"], open: "06:00", close: "23:00", visit: 35, cost: 0, icon: true, blurb: "The oldest public park in the US and the start of the Freedom Trail." },
  { id: "public-garden", name: "Public Garden", area: "Back Bay", lat: 42.3541, lng: -71.0703, tags: ["nature", "views"], open: "06:00", close: "23:00", visit: 35, cost: 0, icon: true, blurb: "Victorian garden with a lagoon, weeping willows and the seasonal Swan Boats." },
  { id: "state-house", name: "Massachusetts State House", area: "Beacon Hill", lat: 42.3588, lng: -71.0638, tags: ["history", "architecture"], open: "10:00", close: "15:30", visit: 30, cost: 0, icon: true, blurb: "Gold-domed seat of state government, with free guided tours on weekdays." },
  { id: "granary", name: "Granary Burying Ground", area: "Downtown", lat: 42.3574, lng: -71.0616, tags: ["history"], open: "09:00", close: "16:30", visit: 20, cost: 0, blurb: "Burying ground where Samuel Adams, John Hancock and Paul Revere rest." },
  { id: "kings-chapel", name: "King's Chapel", area: "Downtown", lat: 42.3581, lng: -71.0601, tags: ["history", "architecture"], open: "10:00", close: "16:30", visit: 25, cost: 0, blurb: "1754 granite chapel beside the city's oldest burying ground." },
  { id: "old-south", name: "Old South Meeting House", area: "Downtown", lat: 42.3570, lng: -71.0587, tags: ["history"], open: "10:00", close: "17:00", visit: 35, cost: 15, blurb: "Meeting house where the debate that led to the Boston Tea Party took place." },
  { id: "old-state-house", name: "Old State House", area: "Downtown", lat: 42.3587, lng: -71.0575, tags: ["history", "architecture"], open: "10:00", close: "17:00", visit: 45, cost: 15, blurb: "Boston's oldest public building, with the Boston Massacre site outside." },
  { id: "faneuil-hall", name: "Faneuil Hall and Quincy Market", area: "Downtown", lat: 42.3599, lng: -71.0555, tags: ["food", "history", "shopping"], open: "10:00", close: "21:00", visit: 45, cost: 15, icon: true, blurb: "Historic market hall with Quincy Market's food stalls right behind it." },
  { id: "paul-revere", name: "Paul Revere House", area: "North End", lat: 42.3637, lng: -71.0537, tags: ["history"], open: "10:00", close: "17:00", visit: 30, cost: 6, icon: true, blurb: "Paul Revere's 17th-century home, the oldest house in downtown Boston." },
  { id: "old-north", name: "Old North Church", area: "North End", lat: 42.3663, lng: -71.0544, tags: ["history", "architecture"], open: "10:00", close: "17:00", visit: 30, cost: 10, icon: true, blurb: "The steeple where two lanterns signaled the British were coming by sea." },
  { id: "copps-hill", name: "Copp's Hill Burying Ground", area: "North End", lat: 42.3672, lng: -71.0561, tags: ["history", "views"], open: "09:00", close: "17:00", visit: 15, cost: 0, blurb: "Hilltop burying ground looking across the harbor to Charlestown." },
  { id: "uss-constitution", name: "USS Constitution", area: "Charlestown", lat: 42.3724, lng: -71.0566, tags: ["history", "family"], open: "10:00", close: "16:00", visit: 45, cost: 0, icon: true, blurb: "The oldest commissioned warship afloat, docked at the Charlestown Navy Yard." },
  { id: "bunker-hill", name: "Bunker Hill Monument", area: "Charlestown", lat: 42.3763, lng: -71.0608, tags: ["history", "views"], open: "10:00", close: "17:00", visit: 40, cost: 0, icon: true, blurb: "A 221-foot granite obelisk; climb 294 steps for a view over the city." },
  { id: "hanover-street", name: "Hanover Street bakeries", area: "North End", lat: 42.3634, lng: -71.0544, tags: ["food", "coffee"], open: "08:00", close: "22:00", visit: 40, cost: 12, blurb: "The North End's main street for cannoli, espresso and Italian bakeries." },
  { id: "greenway", name: "Rose Kennedy Greenway", area: "Waterfront", lat: 42.3593, lng: -71.0530, tags: ["nature", "art", "family"], open: "07:00", close: "23:00", visit: 30, cost: 0, blurb: "Mile-and-a-half park with fountains, rotating public art and a carousel." },
  { id: "aquarium", name: "New England Aquarium", area: "Waterfront", lat: 42.3591, lng: -71.0498, tags: ["family", "science", "nature"], open: "09:00", close: "17:00", visit: 90, cost: 38, icon: true, blurb: "Giant ocean tank, penguins and sea turtles on Central Wharf." },
  { id: "columbus-park", name: "Christopher Columbus Waterfront Park", area: "Waterfront", lat: 42.3613, lng: -71.0508, tags: ["nature", "views"], open: "06:00", close: "23:00", visit: 25, cost: 0, blurb: "Harborside park with a rose garden and a long wisteria trellis." },
  { id: "tea-party", name: "Boston Tea Party Ships and Museum", area: "Fort Point", lat: 42.3522, lng: -71.0512, tags: ["history", "family"], open: "10:00", close: "17:00", visit: 70, cost: 35, icon: true, blurb: "Replica ships and a museum where you throw tea into the harbor yourself." },
  { id: "childrens-museum", name: "Boston Children's Museum", area: "Fort Point", lat: 42.3518, lng: -71.0497, tags: ["family", "science"], open: "09:00", close: "17:00", visit: 90, cost: 22, blurb: "Hands-on museum on Fort Point Channel, best for kids under ten." },
  { id: "ica", name: "Institute of Contemporary Art", area: "Seaport", lat: 42.3527, lng: -71.0429, tags: ["art", "views"], open: "10:00", close: "17:00", visit: 75, cost: 20, blurb: "Contemporary art in a glass building cantilevered over the harbor." },
  { id: "fan-pier", name: "Seaport Harborwalk", area: "Seaport", lat: 42.3538, lng: -71.0450, tags: ["views", "nature"], open: "06:00", close: "23:00", visit: 25, cost: 0, blurb: "Open harbor views from Fan Pier, with planes landing across the water." },
  { id: "chinatown", name: "Chinatown gate and dim sum", area: "Chinatown", lat: 42.3511, lng: -71.0600, tags: ["food"], open: "10:00", close: "22:00", visit: 60, cost: 20, blurb: "The paifang gate and blocks of dim sum, bakeries and noodle shops." },
  { id: "acorn-street", name: "Acorn Street", area: "Beacon Hill", lat: 42.3577, lng: -71.0683, tags: ["architecture", "views", "history"], open: "07:00", close: "21:00", visit: 25, cost: 0, icon: true, blurb: "Narrow cobblestone lane of rowhouses, among the most photographed in the US." },
  { id: "charles-street", name: "Charles Street cafés", area: "Beacon Hill", lat: 42.3575, lng: -71.0705, tags: ["coffee", "shopping", "food"], open: "08:00", close: "20:00", visit: 40, cost: 10, blurb: "Beacon Hill's gaslit main street of antique shops and small cafés." },
  { id: "esplanade", name: "Charles River Esplanade", area: "Back Bay", lat: 42.3570, lng: -71.0745, tags: ["nature", "views"], open: "06:00", close: "22:00", visit: 40, cost: 0, blurb: "Riverside path along the Charles with sailboats and the Hatch Shell." },
  { id: "museum-of-science", name: "Museum of Science", area: "West End", lat: 42.3676, lng: -71.0710, tags: ["science", "family"], open: "09:00", close: "17:00", visit: 120, cost: 32, blurb: "Hands-on science museum on the Charles River Dam, with a planetarium." },
  { id: "bpl", name: "Boston Public Library", area: "Back Bay", lat: 42.3493, lng: -71.0781, tags: ["architecture", "art", "history"], open: "09:00", close: "17:00", visit: 40, cost: 0, icon: true, blurb: "The McKim Building's courtyard, murals and grand Bates Hall reading room." },
  { id: "trinity-church", name: "Trinity Church", area: "Back Bay", lat: 42.3499, lng: -71.0752, tags: ["architecture", "art"], open: "10:00", close: "16:30", visit: 30, cost: 10, blurb: "Romanesque landmark on Copley Square, reflected in the Hancock tower." },
  { id: "newbury-street", name: "Newbury Street", area: "Back Bay", lat: 42.3506, lng: -71.0795, tags: ["shopping", "coffee"], open: "10:00", close: "20:00", visit: 60, cost: 15, blurb: "Eight blocks of brownstone boutiques, galleries and cafés." },
  { id: "view-boston", name: "View Boston observation deck", area: "Back Bay", lat: 42.3471, lng: -71.0825, tags: ["views", "family"], open: "10:00", close: "21:00", visit: 60, cost: 35, blurb: "360-degree views from the top of the Prudential Tower." },
  { id: "mfa", name: "Museum of Fine Arts", area: "Fenway", lat: 42.3394, lng: -71.0940, tags: ["art"], open: "10:00", close: "17:00", visit: 120, cost: 27, icon: true, blurb: "Nearly 500,000 works, from Egyptian antiquities to American paintings." },
  { id: "gardner", name: "Isabella Stewart Gardner Museum", area: "Fenway", lat: 42.3382, lng: -71.0990, tags: ["art", "architecture"], open: "11:00", close: "17:00", visit: 75, cost: 22, icon: true, blurb: "A Venetian-style palazzo of art built around a flowering courtyard." },
  { id: "fens", name: "Back Bay Fens rose garden", area: "Fenway", lat: 42.3423, lng: -71.0950, tags: ["nature"], open: "07:00", close: "20:00", visit: 30, cost: 0, blurb: "Olmsted-designed parkland with the Kelleher Rose Garden." },
  { id: "fenway-park", name: "Fenway Park tour", area: "Fenway", lat: 42.3467, lng: -71.0972, tags: ["family", "history"], open: "10:00", close: "17:00", visit: 60, cost: 25, icon: true, blurb: "Home of the Red Sox since 1912, with ballpark tours most days." },
  { id: "south-end", name: "South End brownstones", area: "South End", lat: 42.3427, lng: -71.0716, tags: ["architecture", "coffee", "food"], open: "08:00", close: "20:00", visit: 40, cost: 8, blurb: "Victorian squares, neighborhood cafés and the SoWa art district nearby." },
  { id: "public-market", name: "Boston Public Market", area: "Downtown", lat: 42.3618, lng: -71.0576, tags: ["food", "shopping"], open: "08:00", close: "19:00", visit: 40, cost: 15, blurb: "Indoor market of New England food vendors next to Haymarket." },
  { id: "maah", name: "Museum of African American History", area: "Beacon Hill", lat: 42.3597, lng: -71.0653, tags: ["history", "architecture"], open: "10:00", close: "16:00", visit: 50, cost: 10, blurb: "Exhibits in the 1806 African Meeting House on Beacon Hill." },
  { id: "comm-ave-mall", name: "Commonwealth Avenue Mall", area: "Back Bay", lat: 42.3518, lng: -71.0790, tags: ["nature", "architecture"], open: "06:00", close: "23:00", visit: 25, cost: 0, blurb: "Tree-lined promenade through Back Bay, dotted with statues." },
];

export const PLACE_BY_ID = Object.fromEntries(PLACES.map((p) => [p.id, p]));
export const ORIGIN_BY_ID = Object.fromEntries(ORIGINS.map((o) => [o.id, o]));

export const DEFAULTS = Object.freeze({
  start: "10:00", end: "16:00", budget: 60, group: 2,
  maxWalk: 20, stops: 4, interests: ["history", "food"], origin: "park-street",
});

// ---------------------------------------------------------------- time helpers

export function toMin(hhmm) {
  const m = /^(\d{1,2}):(\d{2})$/.exec(String(hhmm ?? "").trim());
  if (!m) return null;
  const h = Number(m[1]), mi = Number(m[2]);
  if (h > 23 || mi > 59) return null;
  return h * 60 + mi;
}

export function toClock(min) {
  const t = Math.max(0, Math.min(1439, Math.round(min)));
  return String(Math.floor(t / 60)).padStart(2, "0") + ":" + String(t % 60).padStart(2, "0");
}

export function to12h(min) {
  const t = Math.max(0, Math.min(1439, Math.round(min)));
  const h = Math.floor(t / 60), m = t % 60;
  const suffix = h < 12 ? "am" : "pm";
  const h12 = ((h + 11) % 12) + 1;
  return m === 0 ? `${h12} ${suffix}` : `${h12}:${String(m).padStart(2, "0")} ${suffix}`;
}

export function formatDuration(min) {
  const m = Math.max(0, Math.round(min));
  if (m < 60) return `${m} min`;
  const h = Math.floor(m / 60), r = m % 60;
  return r ? `${h} h ${r} min` : `${h} h`;
}

// ---------------------------------------------------------------- walking estimate

const WALK_KMH = 4.5;      // average walking speed
const DETOUR = 1.3;        // street grid vs straight line

export function distanceKm(a, b) {
  const r = Math.PI / 180;
  const dLat = (b.lat - a.lat) * r, dLng = (b.lng - a.lng) * r;
  const h = Math.sin(dLat / 2) ** 2 + Math.cos(a.lat * r) * Math.cos(b.lat * r) * Math.sin(dLng / 2) ** 2;
  return 6371 * 2 * Math.atan2(Math.sqrt(h), Math.sqrt(1 - h));
}

export function walkMinutes(a, b) {
  if (!a || !b) return null;
  return Math.max(1, Math.ceil((distanceKm(a, b) / WALK_KMH) * 60 * DETOUR));
}

export function locationOf(id) {
  return PLACE_BY_ID[id] || ORIGIN_BY_ID[id] || null;
}

// ---------------------------------------------------------------- constraints

function clampInt(v, lo, hi, fallback) {
  const n = Number(v);
  if (!Number.isFinite(n)) return fallback;
  return Math.max(lo, Math.min(hi, Math.round(n)));
}

export function normalizeConstraints(input = {}) {
  const c = { ...DEFAULTS, ...(input || {}) };
  let start = toMin(c.start), end = toMin(c.end);
  if (start === null) start = toMin(DEFAULTS.start);
  if (end === null) end = toMin(DEFAULTS.end);
  if (end <= start) end = Math.min(23 * 60 + 59, start + 60);
  const interests = Array.isArray(c.interests)
    ? [...new Set(c.interests.map((s) => String(s).toLowerCase().trim()).filter((s) => INTERESTS.includes(s)))]
    : [...DEFAULTS.interests];
  return {
    start: toClock(start),
    end: toClock(end),
    budget: clampInt(c.budget, 0, 2000, DEFAULTS.budget),
    group: clampInt(c.group, 1, 12, DEFAULTS.group),
    maxWalk: clampInt(c.maxWalk, 3, 60, DEFAULTS.maxWalk),
    stops: clampInt(c.stops, 1, 6, DEFAULTS.stops),
    interests,
    origin: ORIGIN_BY_ID[c.origin] ? c.origin : DEFAULTS.origin,
  };
}

// ---------------------------------------------------------------- schedule + validator

export const legKey = (fromId, toId) => `${fromId}>${toId}`;

// Hard violations make a plan invalid; notes are informational.
// opts.legs can override walking minutes per leg, e.g. with live route times.
export function schedule(stopIds, constraints, opts = {}) {
  const c = normalizeConstraints(constraints);
  const start = toMin(c.start), end = toMin(c.end);
  const legs = opts.legs || {};
  const violations = [], notes = [], stops = [];
  const seen = new Set();
  let now = start, here = ORIGIN_BY_ID[c.origin], hereId = c.origin, cost = 0, walkTotal = 0, longestWalk = 0;

  for (const id of Array.isArray(stopIds) ? stopIds : []) {
    const p = PLACE_BY_ID[id];
    if (!p) { violations.push({ type: "unknown_place", id: String(id), message: `"${String(id).slice(0, 40)}" is not in the catalog.` }); continue; }
    if (seen.has(id)) { violations.push({ type: "duplicate", id, message: `${p.name} appears twice.` }); continue; }
    seen.add(id);
    const override = Number(legs[legKey(hereId, id)]);
    const walk = Number.isFinite(override) && override > 0 ? Math.ceil(override) : walkMinutes(here, p);
    const arrive = now + walk;
    const open = toMin(p.open), close = toMin(p.close);
    const begin = Math.max(arrive, open);
    const leave = begin + p.visit;
    const groupCost = p.cost * c.group;
    if (walk > c.maxWalk) violations.push({ type: "leg_too_long", id, message: `${walk} min walk to ${p.name} is over the ${c.maxWalk} min limit.` });
    if (leave > close) violations.push({ type: "closed", id, message: `${p.name} closes at ${to12h(close)}, before a ${p.visit} min visit can finish.` });
    if (leave > end) violations.push({ type: "past_end", id, message: `${p.name} would end at ${to12h(leave)}, after your ${to12h(end)} finish.` });
    if (begin - arrive >= 20) notes.push({ type: "wait", id, message: `You'd wait ${begin - arrive} min for ${p.name} to open.` });
    stops.push({ id, name: p.name, walk, arrive, begin, wait: begin - arrive, leave, cost: groupCost });
    cost += groupCost; walkTotal += walk; longestWalk = Math.max(longestWalk, walk);
    now = leave; here = p; hereId = id;
  }
  if (cost > c.budget) violations.push({ type: "over_budget", message: `Estimated cost $${cost} is over your $${c.budget} budget.` });
  return {
    constraints: c, stops, cost, walkTotal, longestWalk,
    finish: stops.length ? stops[stops.length - 1].leave : start,
    violations, notes, ok: violations.length === 0,
  };
}

// ---------------------------------------------------------------- text relevance (TF-IDF)

const STOPWORDS = new Set("a an and are as at be but by for from have i in is it its like me my of on or our so that the this to us we with want would love some something good great nice really very please day trip afternoon morning want".split(" "));

const SYNONYMS = {
  kid: "family", kids: "family", children: "family", child: "family", toddler: "family",
  park: "nature", parks: "nature", outdoors: "nature", outdoor: "nature", garden: "nature", gardens: "nature", green: "nature", walk: "nature",
  eat: "food", eating: "food", lunch: "food", dinner: "food", snack: "food", pastry: "food", pastries: "food", cannoli: "food", dumplings: "food", bakery: "food",
  cafe: "coffee", cafes: "coffee", espresso: "coffee", latte: "coffee",
  church: "architecture", churches: "architecture", building: "architecture", buildings: "architecture",
  revolution: "history", revolutionary: "history", colonial: "history", freedom: "history", historic: "history", historical: "history",
  harbor: "views", waterfront: "views", water: "views", ocean: "views", sea: "views", skyline: "views", photo: "views", photos: "views",
  painting: "art", paintings: "art", gallery: "art", galleries: "art", museum: "art", museums: "art",
  shop: "shopping", shops: "shopping", boutique: "shopping", boutiques: "shopping",
  baseball: "family", sox: "family",
};

export function tokenize(text) {
  const out = [];
  for (const raw of String(text || "").toLowerCase().match(/[a-z0-9]+/g) || []) {
    if (STOPWORDS.has(raw) || raw.length < 2) continue;
    let t = raw;
    if (t.length > 4 && t.endsWith("ies")) t = t.slice(0, -3) + "y";
    else if (t.length > 3 && t.endsWith("s") && !t.endsWith("ss")) t = t.slice(0, -1);
    out.push(t);
    if (SYNONYMS[raw]) out.push(SYNONYMS[raw]);
  }
  return out;
}

function placeDoc(p) {
  return [p.name, p.area, p.blurb, p.tags.join(" "), p.tags.join(" ")].join(" ");
}

const TFIDF = (() => {
  const docs = PLACES.map((p) => tokenize(placeDoc(p)));
  const df = new Map();
  for (const d of docs) for (const t of new Set(d)) df.set(t, (df.get(t) || 0) + 1);
  const n = docs.length;
  const idf = (t) => Math.log((1 + n) / (1 + (df.get(t) || 0))) + 1;
  const vec = (toks) => {
    const tf = new Map();
    for (const t of toks) tf.set(t, (tf.get(t) || 0) + 1);
    const v = new Map();
    let norm = 0;
    for (const [t, f] of tf) { const w = (1 + Math.log(f)) * idf(t); v.set(t, w); norm += w * w; }
    norm = Math.sqrt(norm) || 1;
    for (const [t, w] of v) v.set(t, w / norm);
    return v;
  };
  return { idf, vec, placeVecs: Object.fromEntries(PLACES.map((p, i) => [p.id, vec(docs[i])])) };
})();

export function textSimilarity(query) {
  const q = TFIDF.vec(tokenize(query));
  const out = {};
  for (const p of PLACES) {
    let s = 0;
    for (const [t, w] of q) s += w * (TFIDF.placeVecs[p.id].get(t) || 0);
    out[p.id] = s;
  }
  return out;
}

// Relevance of each place to the constraints and the free-text request.
export function relevance(constraints, query = "") {
  const c = normalizeConstraints(constraints);
  const sim = query ? textSimilarity(query) : {};
  const out = {};
  for (const p of PLACES) {
    const matched = p.tags.filter((t) => c.interests.includes(t));
    const s = 3 * matched.length + 4 * (sim[p.id] || 0) + (p.icon ? 0.6 : 0);
    out[p.id] = { score: s, matched, text: sim[p.id] || 0 };
  }
  return out;
}

// ---------------------------------------------------------------- planner (beam search)

const BEAM_WIDTH = 80;

export function explainStop(p, info, walk, c) {
  const why = [];
  if (info?.matched?.length) why.push(`matches ${info.matched.join(" and ")}`);
  else if ((info?.text || 0) > 0.12) why.push("matches your request");
  why.push(walk <= 1 ? "right where you are" : `${walk} min walk from the last stop`);
  if (p.cost === 0) why.push("free");
  return why.join(", ");
}

export function plan(constraints, opts = {}) {
  const c = normalizeConstraints(constraints);
  const locked = (opts.locked || []).filter((id) => PLACE_BY_ID[id]);
  const excluded = new Set((opts.excluded || []).filter((id) => !locked.includes(id)));
  const rel = relevance(c, opts.query || "");
  const start = toMin(c.start), end = toMin(c.end);
  const origin = ORIGIN_BY_ID[c.origin];
  const candidates = PLACES.filter((p) => !excluded.has(p.id));
  const lockedSet = new Set(locked);

  let beam = [{ seq: [], time: start, here: origin, cost: 0, score: 0, kinds: {} }];
  const finished = [];
  for (let depth = 0; depth < c.stops; depth++) {
    const next = [];
    for (const st of beam) {
      for (const p of candidates) {
        if (st.seq.includes(p.id)) continue;
        const walk = walkMinutes(st.here, p);
        if (walk > c.maxWalk) continue;
        const arrive = st.time + walk;
        const begin = Math.max(arrive, toMin(p.open));
        const leave = begin + p.visit;
        if (leave > toMin(p.close) || leave > end) continue;
        const cost = st.cost + p.cost * c.group;
        if (cost > c.budget) continue;
        const kind = p.tags[0];
        const repeat = st.kinds[kind] || 0;
        const gain = rel[p.id].score
          + (lockedSet.has(p.id) ? 50 : 0)
          - (c.interests.includes(kind) ? 0.4 : 1.2) * repeat
          - 0.1 * walk
          - 0.03 * (begin - arrive);
        next.push({
          seq: [...st.seq, p.id], time: leave, here: p, cost,
          score: st.score + gain, kinds: { ...st.kinds, [kind]: repeat + 1 },
        });
      }
    }
    if (!next.length) break;
    next.sort((a, b) => b.score - a.score || a.seq.join().localeCompare(b.seq.join()));
    beam = next.slice(0, BEAM_WIDTH);
    finished.push(...beam);
  }

  const covers = (s) => locked.every((id) => s.seq.includes(id));
  let pool = finished.filter(covers);
  const missingLocked = pool.length ? [] : locked;
  if (!pool.length) pool = finished;
  pool.sort((a, b) => b.seq.length - a.seq.length || b.score - a.score || a.seq.join().localeCompare(b.seq.join()));
  const best = pool[0] || { seq: [] };
  const sched = schedule(best.seq, c);

  let prev = origin;
  const reasons = {};
  for (const s of sched.stops) {
    const p = PLACE_BY_ID[s.id];
    reasons[s.id] = explainStop(p, rel[s.id], walkMinutes(prev, p), c);
    prev = p;
  }
  const notes = [];
  if (sched.stops.length < c.stops) notes.push(`Only ${sched.stops.length} of ${c.stops} stops fit your time, budget and walking limit.`);
  for (const id of missingLocked) notes.push(`${PLACE_BY_ID[id].name} could not fit with your other limits.`);
  return { stopIds: best.seq, schedule: sched, reasons, notes, constraints: c };
}

// ---------------------------------------------------------------- offline request parser

const WORD_NUM = { one: 1, two: 2, three: 3, four: 4, five: 5, six: 6, seven: 7, eight: 8, nine: 9, ten: 10 };
const num = (s) => (WORD_NUM[s] ?? Number(s));

const INTEREST_WORDS = {
  history: ["history", "historic", "historical", "revolution", "revolutionary", "colonial", "freedom trail"],
  art: ["art", "arts", "museum", "museums", "gallery", "galleries", "painting", "paintings"],
  nature: ["nature", "park", "parks", "outdoor", "outdoors", "garden", "gardens", "green"],
  food: ["food", "eat", "lunch", "dinner", "snack", "pastry", "pastries", "cannoli", "dim sum", "foodie"],
  coffee: ["coffee", "cafe", "cafes", "café", "cafés", "espresso"],
  views: ["view", "views", "harbor", "waterfront", "skyline", "photos", "scenic"],
  architecture: ["architecture", "church", "churches", "buildings", "brownstone", "brownstones"],
  family: ["kids", "kid", "children", "family", "families", "toddler"],
  science: ["science", "aquarium", "planetarium"],
  shopping: ["shopping", "shop", "shops", "boutique", "boutiques", "market"],
};

function parseClock(h, m, ap, fallbackPm) {
  let hour = Number(h);
  const min = m ? Number(m) : 0;
  if (hour > 23 || min > 59) return null;
  if (ap) {
    ap = ap.toLowerCase();
    if (ap.startsWith("p") && hour < 12) hour += 12;
    if (ap.startsWith("a") && hour === 12) hour = 0;
  } else if (fallbackPm && hour >= 1 && hour <= 7) hour += 12; // "back by 5" means 5 pm
  return hour * 60 + min;
}

function hasWord(text, w) {
  return new RegExp(`(^|[^a-z])${w.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}([^a-z]|$)`).test(text);
}

function matchPlaces(fragment) {
  const f = String(fragment || "").toLowerCase().replace(/[^a-z0-9' ]+/g, " ").trim();
  if (f.length < 3) return [];
  const words = f.split(/\s+/).filter((w) => w.length > 2 && !STOPWORDS.has(w) && !["stop", "the"].includes(w));
  if (!words.length) return [];
  const scored = PLACES.map((p) => {
    const name = p.name.toLowerCase();
    const hits = words.filter((w) => name.includes(w)).length;
    return { p, hits, ratio: hits / words.length };
  }).filter((x) => x.hits > 0 && x.ratio >= 0.5);
  scored.sort((a, b) => b.hits - a.hits || b.ratio - a.ratio);
  if (!scored.length) return [];
  return scored.filter((x) => x.hits === scored[0].hits).map((x) => x.p.id);
}

// Returns the updated constraints plus a list of human-readable changes.
// This is a rule-based parser for the offline mode, not a language model.
export function parseRequest(text, current) {
  const c = normalizeConstraints(current);
  const t = ` ${String(text || "").toLowerCase().replace(/\s+/g, " ")} `;
  const changes = [];
  const include = [], exclude = [];
  let reset = false;

  if (/\b(reset|start over|clear everything)\b/.test(t)) {
    reset = true;
    return { constraints: normalizeConstraints(DEFAULTS), changes: ["reset to the default day"], include, exclude, reset, query: "" };
  }

  // budget
  if (/\b(free|no cost|zero budget|no money|\$0)\b/.test(t) || /\$0\b/.test(t)) {
    c.budget = 0; changes.push("budget $0");
  } else {
    const b = /(?:under|below|less than|max(?:imum)?|budget(?: of| is)?|up to|spend(?: up to)?|around)\s*\$?\s*(\d{1,4})\b/.exec(t) || /\$\s*(\d{1,4})\b/.exec(t);
    if (b) { c.budget = Number(b[1]); changes.push(`budget $${c.budget}`); }
    else if (/\b(cheaper|less expensive|lower budget|save money)\b/.test(t)) { c.budget = Math.floor(c.budget / 2); changes.push(`budget $${c.budget}`); }
  }

  // group size
  const g = /\b(\d{1,2}|one|two|three|four|five|six|seven|eight)\s+(people|persons|adults|friends|of us|travelers|travellers)\b/.exec(t)
    || /\bfamily of (\d{1,2}|three|four|five|six)\b/.exec(t) || /\bgroup of (\d{1,2}|two|three|four|five|six)\b/.exec(t);
  if (g) { c.group = Math.max(1, Math.min(12, num(g[1]))); changes.push(`${c.group} people`); }
  else if (/\b(solo|just me|by myself|alone)\b/.test(t)) { c.group = 1; changes.push("1 person"); }
  else if (/\b(couple|my partner|the two of us|two of us)\b/.test(t)) { c.group = 2; changes.push("2 people"); }

  // stop count
  const s = /\b(\d|one|two|three|four|five|six)\s+(stops|places|sights|spots|stop)\b/.exec(t);
  if (s) { c.stops = Math.max(1, Math.min(6, num(s[1]))); changes.push(`${c.stops} stops`); }
  else if (/\b(fewer|less) stops\b/.test(t)) { c.stops = Math.max(1, c.stops - 1); changes.push(`${c.stops} stops`); }
  else if (/\badd (?:a|an|one|another) [a-z]+ (?:stop|break)\b/.test(t)) { c.stops = Math.min(6, c.stops + 1); changes.push(`${c.stops} stops`); }
  else if (/\bmore stops\b/.test(t)) { c.stops = Math.min(6, c.stops + 1); changes.push(`${c.stops} stops`); }

  // times
  let start = toMin(c.start), end = toMin(c.end);
  const st = /\b(?:start|starting|begin|leave|from|after)\s*(?:at|around|by)?\s*(\d{1,2})(?::(\d{2}))?\s*(am|pm|a\.m\.|p\.m\.)?/.exec(t);
  const en = /\b(?:back by|done by|finish(?:ed)? by|end(?:ing)? (?:at|by)|until|till|by)\s*(\d{1,2})(?::(\d{2}))?\s*(am|pm|a\.m\.|p\.m\.)?/.exec(t);
  if (/\bmorning\b/.test(t) && !st) { start = 9 * 60; end = Math.min(end, 13 * 60); changes.push("morning"); }
  if (/\bafternoon\b/.test(t) && !st) { start = 13 * 60; end = Math.max(end, 17 * 60 + 30); changes.push("afternoon"); }
  if (/\bevening\b/.test(t) && !st) { start = 17 * 60; end = 21 * 60 + 30; changes.push("evening"); }
  if (st) { const v = parseClock(st[1], st[2], st[3], true); if (v !== null) { start = v; changes.push(`start ${to12h(v)}`); } }
  if (en) { const v = parseClock(en[1], en[2], en[3], true); if (v !== null) { end = v; changes.push(`finish by ${to12h(v)}`); } }
  if (/\bstart (an hour |one hour )?later\b/.test(t)) { start += 60; changes.push(`start ${to12h(start)}`); }
  if (/\bstart (an hour |one hour )?earlier\b/.test(t)) { start = Math.max(6 * 60, start - 60); changes.push(`start ${to12h(start)}`); }
  if (end <= start) end = Math.min(23 * 60 + 59, start + 180);
  c.start = toClock(start); c.end = toClock(end);

  // walking
  const w = /\b(?:walk(?:ing)?|legs?)\s*(?:of\s*)?(?:up to|max(?:imum)?|under|less than|no more than)?\s*(\d{1,2})\s*(?:min|minutes)\b/.exec(t)
    || /\b(\d{1,2})\s*(?:min|minutes)\s*(?:max\s*)?(?:walk|walking)\b/.exec(t);
  if (w) { c.maxWalk = Math.max(3, Math.min(60, Number(w[1]))); changes.push(`walks up to ${c.maxWalk} min`); }
  else if (/\b(less walking|shorter walks|walk less|tired|short walks)\b/.test(t)) { c.maxWalk = Math.max(5, c.maxWalk - 5); changes.push(`walks up to ${c.maxWalk} min`); }

  // remove / add specific places
  const rm = /\b(?:remove|skip|drop|no more|without|replace|swap(?: out)?)\s+(?:the\s+)?([a-z0-9' ]{3,40}?)(?=\s+(?:and|for|with|then)\b|[,.!?]|$)/.exec(t.trim());
  if (rm) for (const id of matchPlaces(rm[1])) { exclude.push(id); changes.push(`skip ${PLACE_BY_ID[id].name}`); }
  const add = /\b(?:add|include|visit|see|go to|stop at)\s+(?:the\s+|a\s+)?([a-z0-9' ]{3,40}?)(?=\s+(?:and|for|with|then)\b|[,.!?]|$)/.exec(t.trim());
  if (add) for (const id of matchPlaces(add[1])) { if (!exclude.includes(id)) { include.push(id); changes.push(`include ${PLACE_BY_ID[id].name}`); } }

  // start point
  for (const o of ORIGINS) {
    const key = o.name.toLowerCase().split(" (")[0];
    if (t.includes(`from ${key}`) || t.includes(`at ${key}`) || t.includes(`near ${key}`)) {
      if (c.origin !== o.id) { c.origin = o.id; changes.push(`start at ${o.name}`); }
      break;
    }
  }

  // interests
  const found = INTERESTS.filter((k) => INTEREST_WORDS[k].some((w2) => hasWord(t, w2)));
  const negated = INTERESTS.filter((k) => INTEREST_WORDS[k].some((w2) => new RegExp(`\\b(no|not|without|skip|less)\\s+(?:more\\s+)?${w2}\\b`).test(t)));
  const positive = found.filter((k) => !negated.includes(k));
  if (positive.length) {
    const additive = /\b(more|add|also|plus|another|extra)\b/.test(t);
    const before = c.interests.join(",");
    c.interests = additive ? [...new Set([...c.interests, ...positive])] : positive;
    if (c.interests.join(",") !== before) changes.push(`interests: ${c.interests.join(", ")}`);
  }
  if (negated.length) {
    const before = c.interests.length;
    c.interests = c.interests.filter((k) => !negated.includes(k));
    if (c.interests.length !== before) changes.push(`dropped ${negated.join(", ")}`);
  }

  return { constraints: normalizeConstraints(c), changes, include, exclude, reset, query: String(text || "") };
}

// Short summary of a plan for chat replies.
export function describePlan(result) {
  const s = result.schedule;
  if (!s.stops.length) return "Nothing fits those limits yet. Try a longer day, a bigger budget or a longer walking limit.";
  const total = s.finish - toMin(s.constraints.start);
  const parts = [
    `${s.stops.length} stop${s.stops.length > 1 ? "s" : ""} from ${to12h(toMin(s.constraints.start))} to ${to12h(s.finish)}`,
    `${s.walkTotal} min of walking`,
    s.cost === 0 ? "all free" : `about $${s.cost} for ${s.constraints.group}`,
  ];
  return `Planned ${parts.join(", ")} (${formatDuration(total)} in total).`;
}
