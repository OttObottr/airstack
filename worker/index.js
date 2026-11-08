import schema from './schema.json' with { type: 'json' };

const BOT = /bot|crawl|spider|slurp|headless|lighthouse|preview|monitor|curl|wget|python|httpclient|okhttp|java\/|go-http|node-fetch|axios/i;
const QUERY = new RegExp(schema.query, 'u');
const ID = /^[a-z0-9][a-z0-9._-]{0,79}$/;
const HOST = /^(?=.{3,100}$)[a-z0-9-]+(\.[a-z0-9-]+)+$/;
const day = now => new Date(now).toISOString().slice(0, 10);

/* the event, or the reason it is refused */
export function check(text) {
  if (text.length > schema.maxBytes) return 'size';
  let e;
  try {
    e = JSON.parse(text);
  } catch {
    return 'json';
  }
  const spec = e && typeof e === 'object' && !Array.isArray(e) && Object.hasOwn(schema.events, e.t) && schema.events[e.t];
  if (!spec) return 'type';
  const want = Object.fromEntries(Object.entries(spec).map(([k, v]) => [k.replace('?', ''), [v, !k.endsWith('?')]]));
  for (const k of Object.keys(e)) if (k !== 't' && !want[k]) return 'field';
  for (const [k, [rule, needed]] of Object.entries(want)) {
    const v = e[k];
    if (v === undefined) {
      if (needed) return 'missing';
      continue;
    }
    const ok =
      rule === 'id' ? typeof v === 'string' && ID.test(v)
      : rule === 'host' ? typeof v === 'string' && HOST.test(v)
      : rule === 'query' ? typeof v === 'string' && QUERY.test(v) && (v.match(/\d/g) || []).length < 4
      : typeof rule[0] === 'number' ? Number.isInteger(v) && v >= rule[0] && v <= rule[1]
      : rule.includes(v);
    if (!ok) return 'value';
  }
  return e;
}

export const device = ua => (/ipad|tablet/i.test(ua) ? 'tablet' : /mobi|android/i.test(ua) ? 'mobile' : 'desktop');
export const browser = ua =>
  /edg\//i.test(ua) ? 'edge' : /firefox|fxios/i.test(ua) ? 'firefox' : /chrome|crios|chromium/i.test(ua) ? 'chrome' : /safari/i.test(ua) ? 'safari' : 'other';
export const os = ua =>
  /iphone|ipad|ios/i.test(ua) ? 'ios' : /android/i.test(ua) ? 'android' : /windows/i.test(ua) ? 'windows' : /mac os/i.test(ua) ? 'macos' : /linux|cros/i.test(ua) ? 'linux' : 'other';
export const bucket = (v, step) => Math.floor(v / step) * step;
const sizeBucket = (n, edges) => (n ? String(edges.filter(e => n >= e).pop()) : '0');

export async function key(salt, ip, ua, host, hex) {
  const d = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(`${salt}\n${ip}\n${ua}\n${host}`));
  return [...new Uint8Array(d)].map(b => b.toString(16).padStart(2, '0')).join('').slice(0, hex);
}

export function make(L) {
  let salt = null,
    known = null,
    knownAt = 0;
  const burst = new Map(),
    refused = new Map();

  async function saltFor(db, d) {
    if (salt && salt.d === d) return salt.v;
    const read = () => db.prepare('SELECT v FROM salt WHERE day = ?').bind(d).first('v');
    let v = await read();
    if (!v) {
      const r = crypto.getRandomValues(new Uint8Array(32));
      await db.prepare('INSERT OR IGNORE INTO salt(day, v) VALUES (?, ?)').bind(d, btoa(String.fromCharCode(...r))).run();
      v = await read();
    }
    salt = { d, v };
    return v;
  }

  async function ids(env, url, now) {
    if (known && now - knownAt < L.idsTtl * 1000) return known;
    try {
      const t = await (await env.ASSETS.fetch(new URL('/site-data.js', url))).text();
      known = new Map(JSON.parse(t.slice(t.indexOf('{'), t.lastIndexOf('}') + 1)).index.map(r => [r[0], r[2]]));
      knownAt = now;
    } catch {
      known ||= new Map();
    }
    return known;
  }

  const up = (db, d, dim, k) =>
    db.prepare('INSERT INTO agg(day, dim, key, n) VALUES (?, ?, ?, 1) ON CONFLICT(day, dim, key) DO UPDATE SET n = n + 1').bind(d, dim, String(k));

  function refuse(reason) {
    refused.set(reason, (refused.get(reason) || 0) + 1);
  }
  function drain(db, d) {
    const out = [...refused].map(([r, n]) =>
      db.prepare('INSERT INTO agg(day, dim, key, n) VALUES (?, ?, ?, ?) ON CONFLICT(day, dim, key) DO UPDATE SET n = n + excluded.n').bind(d, 'refused', r, n));
    refused.clear();
    return out;
  }
  const total = () => [...refused.values()].reduce((a, b) => a + b, 0);

  async function handle(request, env, now) {
    const url = new URL(request.url),
      h = request.headers,
      ua = h.get('user-agent') || '',
      d = day(now),
      db = env.DB;
    const site = h.get('sec-fetch-site');
    const reason =
      request.method !== 'POST' ? 'method'
      : h.get('origin') !== url.origin || (site && site !== 'same-origin') ? 'origin'
      : !ua || BOT.test(ua) ? 'bot'
      : null;
    if (reason) return refuse(reason);
    if (+(h.get('content-length') || 0) > schema.maxBytes) return refuse('size');
    const e = check(await request.text());
    if (typeof e === 'string') return refuse(e);

    const k = await key(await saltFor(db, d), h.get('cf-connecting-ip') || '', ua, url.host, L.keyHex);
    const minute = Math.floor(now / 60000),
      b = burst.get(k);
    if (b && b.m === minute && ++b.c > L.perMinute) return refuse('burst');
    if (!b || b.m !== minute) {
      if (burst.size > 10000) burst.clear();
      burst.set(k, { m: minute, c: 1 });
    }
    const n = await db
      .prepare('INSERT INTO uniq(day, k, n) VALUES (?, ?, 1) ON CONFLICT(day, k) DO UPDATE SET n = n + 1 RETURNING n')
      .bind(d, k)
      .first('n');
    if (n > L.perDay) return refuse('rate_limited');

    const map = e.t === 'product' || e.t === 'stack' ? await ids(env, url, now) : null,
      id = map && (map.has(e.id) ? e.id : '(other)'),
      w = [];
    if (n === 1) {
      const cc = (request.cf && request.cf.country) || '';
      w.push(up(db, d, 'visitors', 'all'), up(db, d, 'country', /^[A-Z][A-Z0-9]$/.test(cc) ? cc : 'XX'));
      w.push(up(db, d, 'device', device(ua)), up(db, d, 'browser', browser(ua)), up(db, d, 'os', os(ua)));
    }
    if (e.t === 'view') {
      w.push(up(db, d, 'view', e.route));
      if (e.ref) w.push(up(db, d, 'ref', e.ref));
      if (e.size !== undefined && n === 1) w.push(up(db, d, 'stack_size', sizeBucket(e.size, L.sizes)));
    } else if (e.t === 'product') {
      w.push(up(db, d, 'product', id));
      if (map.get(id)) w.push(up(db, d, 'category', map.get(id)));
    } else if (e.t === 'stack') w.push(up(db, d, `stack_${e.op}`, id), up(db, d, 'stack_after', sizeBucket(e.size, L.sizes)));
    else if (e.t === 'search')
      w.push(db.prepare('INSERT OR IGNORE INTO search(day, q, found, k) VALUES (?, ?, ?, ?)').bind(d, e.q.toLowerCase().replace(/\s+/g, ' ').trim(), e.found, k));
    else if (e.t === 'vitals') {
      for (const m of ['lcp', 'inp', 'cls']) if (e[m] !== undefined) w.push(up(db, d, m, bucket(Math.min(e[m], L.caps[m]), L.steps[m])));
    } else w.push(up(db, d, e.t === 'compare' ? 'compare' : e.t, e.t === 'compare' ? e.n : e.what || e.act));
    await db.batch(w.concat(drain(db, d)));
  }

  return {
    async fetch(request, env, ctx) {
      const now = Date.now();
      if (new URL(request.url).pathname !== '/e') return env.ASSETS.fetch(request);
      try {
        await handle(request, env, now);
        if (total() >= L.rejectFlush) ctx.waitUntil(env.DB.batch(drain(env.DB, day(now))));
      } catch {
        refuse('error');
      }
      return new Response(null, { status: 204 });
    },
  };
}

let worker;
export default {
  fetch(request, env, ctx) {
    worker ||= make(env.LIMITS);
    return worker.fetch(request, env, ctx);
  },
};
