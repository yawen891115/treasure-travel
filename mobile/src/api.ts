export type Session = { authenticated: boolean; paid_access: boolean; csrf_token: string };
export type Stop = { place_id: string; name: string; arrive: string; leave: string; est_cost?: number };
export type Source = { backend: 'claude'|'offline'|'fake'; maps_mode: 'google'|'offline'; attribution: string|null; attribution_url: string|null; historical_catalog: boolean; cost_basis: string; travel_basis: string; history_persisted: boolean };
export type Plan = { reply: string; stops: Stop[]; warnings: string[]; data_source?: Source };
export function parseSource(value: unknown): Source {
  const s=value as Source;
  if (!s || !['claude','offline','fake'].includes(s.backend) || !['google','offline'].includes(s.maps_mode) || typeof s.historical_catalog !== 'boolean' || typeof s.history_persisted !== 'boolean' || typeof s.cost_basis !== 'string' || typeof s.travel_basis !== 'string') throw new Error('Invalid data-source metadata.');
  if (s.maps_mode==='google' && (s.attribution!=='Google Maps' || s.attribution_url!=='https://maps.google.com')) throw new Error('Required Google Maps attribution is missing.');
  return s;
}
export function validBase(raw: string, development = false): string {
  const u = new URL(raw);
  if (u.username || u.password || u.search || u.hash || u.pathname !== '/') throw new Error('Use only the server origin.');
  if (u.protocol !== 'https:' && !(development && u.protocol === 'http:' && ['localhost','127.0.0.1'].includes(u.hostname))) throw new Error('HTTPS is required.');
  return u.origin;
}
export function parsePlan(data: unknown): Plan {
  const p = data as Plan;
  if (!p || typeof p.reply !== 'string' || !Array.isArray(p.stops) || !Array.isArray(p.warnings)) throw new Error('Unexpected server response.');
  if (p.stops.some(s => !s || ['place_id','name','arrive','leave'].some(k => typeof (s as any)[k] !== 'string')) || p.warnings.some(w => typeof w !== 'string')) throw new Error('Invalid itinerary.');
  if (p.stops.some(s => s.est_cost !== undefined && (typeof s.est_cost !== 'number' || !Number.isFinite(s.est_cost) || s.est_cost < 0))) throw new Error('Invalid estimated cost.');
  if (p.data_source !== undefined) parseSource(p.data_source);
  return p;
}
export class TravelAPI {
  private csrf = '';
  readonly base: string;
  constructor(base: string, private transport: typeof fetch = fetch, development = false) { this.base = validBase(base, development); }
  async request(path: string, body?: unknown): Promise<any> {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 90000);
    try {
      const response = await this.transport(this.base + path, { method: body === undefined ? 'GET' : 'POST', credentials: 'include', signal: controller.signal,
        headers: { 'Content-Type': 'application/json', ...(body === undefined ? {} : { 'X-CSRFToken': this.csrf, 'Referer': this.base + '/' }) },
        body: body === undefined ? undefined : JSON.stringify(body) });
      if (!response.ok) throw new Error(response.status === 401 || response.status === 403 ? 'Please sign in again or ask for live access.' : response.status === 429 ? 'Too many requests. Please wait before trying again.' : 'The service is unavailable. Please try again.');
      return await response.json();
    } finally { clearTimeout(timer); }
  }
  async session(): Promise<Session> {
    const s = await this.request('/api/session');
    if (typeof s.csrf_token !== 'string' || typeof s.authenticated !== 'boolean' || typeof s.paid_access !== 'boolean') throw new Error('Invalid session.');
    this.csrf = s.csrf_token;
    return s;
  }
  async login(username: string, password: string): Promise<Session> { await this.session(); await this.request('/api/login', {username,password}); return this.session(); }
  async logout(): Promise<void> { await this.request('/api/logout', {}); this.csrf = ''; }
  async chat(message: string): Promise<Plan> { if (!message.trim() || message.length > 8000) throw new Error('Enter 1–8000 characters.'); const p=parsePlan(await this.request('/api/chat', {message})); if (!p.data_source) throw new Error('Server must include data-source metadata.'); return p; }
  async reset(): Promise<void> { await this.request('/api/reset', {}); await this.session(); }
}
