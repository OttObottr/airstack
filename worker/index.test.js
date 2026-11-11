import assert from 'node:assert/strict';
import { DatabaseSync } from 'node:sqlite';
import test from 'node:test';
import { browser, check, device, key, make, os } from './index.js';

const DDL = `CREATE TABLE salt(day TEXT PRIMARY KEY, v TEXT NOT NULL);
CREATE TABLE uniq(day TEXT, k TEXT, n INTEGER, PRIMARY KEY(day, k)) WITHOUT ROWID;
CREATE TABLE agg(day TEXT, dim TEXT, key TEXT, n INTEGER, PRIMARY KEY(day, dim, key)) WITHOUT ROWID;
CREATE TABLE search(day TEXT, q TEXT, found INTEGER, k TEXT, PRIMARY KEY(day, q, k)) WITHOUT ROWID;`;
const LIMITS = { keyHex: 16, dayCap: 1e9, perDay: 5, perMinute: 3, rejectFlush: 1000, idsTtl: 60, sizes: [1, 2, 3, 5, 10, 20], steps: { lcp: 100, inp: 10, cls: 10 }, caps: { lcp: 10000, inp: 2000, cls: 1000 } };
const CHROME = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36';
const SITE = 'window.AIRSTACK_DATA={"index":[["tool-a","Tool A","lane-x",[]],["tool-b","Tool B","lane-y",[]]]};';

export function d1(ddl = DDL) {
  const s = new DatabaseSync(':memory:');
  s.exec(ddl);
  const stmt = (sql, args = []) => ({
    sql,
    args,
    bind: (...a) => stmt(sql, a),
    first: async col => {
      const r = s.prepare(sql).get(...args);
      return r === undefined ? null : col ? r[col] : r;
    },
    all: async () => ({ results: s.prepare(sql).all(...args) }),
    run: async () => s.prepare(sql).run(...args),
  });
  return {
    sql: s,
    prepare: sql => stmt(sql),
    batch: async list => {
      s.exec('BEGIN');
      try {
        for (const x of list) s.prepare(x.sql).run(...(x.args || []));
        s.exec('COMMIT');
      } catch (e) {
        s.exec('ROLLBACK');
        throw e;
      }
    },
  };
}

function env(db = d1()) {
  return { DB: db, ASSETS: { fetch: async () => new Response(SITE) } };
}
const ctx = { waitUntil: () => {} };
const post = (body, { ip = '192.0.2.1', ua = CHROME, origin = 'https://airstack.bot' } = {}) =>
  new Request('https://airstack.bot/e', {
    method: 'POST',
    body: typeof body === 'string' ? body : JSON.stringify(body),
    headers: { origin, 'user-agent': ua, 'cf-connecting-ip': ip, 'sec-fetch-site': 'same-origin' },
  });
const rows = (db, dim) => Object.fromEntries(db.sql.prepare('SELECT key, n FROM agg WHERE dim = ?').all(dim).map(r => [r.key, r.n]));

test('the schema accepts only listed events, fields and values', () => {
  assert.equal(check('{"t":"view","route":"compare"}').route, 'compare');
  assert.equal(check('{"t":"view","route":"compare","ref":"news.example.org","size":3}').ref, 'news.example.org');
  assert.equal(check('{"t":"view","route":"admin"}'), 'value');
  assert.equal(check('{"t":"view","route":"compare","ip":"1.2.3.4"}'), 'field');
  assert.equal(check('{"t":"product"}'), 'missing');
  assert.equal(check('{"t":"nope"}'), 'type');
  assert.equal(check('{"t":"constructor"}'), 'type');
  assert.equal(check('[1]'), 'type');
  assert.equal(check('not json'), 'json');
  assert.equal(check(JSON.stringify({ t: 'search', q: 'x'.repeat(600), found: 0 })), 'size');
  assert.equal(check('{"t":"search","q":"vector database","found":0}').q, 'vector database');
  assert.equal(check('{"t":"search","q":"me@example.org","found":0}'), 'value');
  assert.equal(check('{"t":"search","q":"call 5551234","found":0}'), 'value');
  assert.equal(check('{"t":"compare","n":9}'), 'value');
  assert.equal(check('{"t":"compare","n":2.5}'), 'value');
});

test('the browser, system and device are reduced to a family', () => {
  assert.deepEqual([browser(CHROME), os(CHROME), device(CHROME)], ['chrome', 'macos', 'desktop']);
  const iphone = 'Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Mobile/15E148 Safari/604.1';
  assert.deepEqual([browser(iphone), os(iphone), device(iphone)], ['safari', 'ios', 'mobile']);
  assert.equal(browser('Mozilla/5.0 (Windows NT 10.0) Chrome/130.0 Safari/537.36 Edg/130.0'), 'edge');
});

test('the daily key is a truncated hash that changes with the salt', async () => {
  const a = await key('salt-1', '192.0.2.1', CHROME, 'airstack.bot', 16);
  assert.match(a, /^[0-9a-f]{16}$/);
  assert.equal(a, await key('salt-1', '192.0.2.1', CHROME, 'airstack.bot', 16));
  assert.notEqual(a, await key('salt-2', '192.0.2.1', CHROME, 'airstack.bot', 16));
  assert.notEqual(a, await key('salt-1', '192.0.2.2', CHROME, 'airstack.bot', 16));
});

test('an accepted view counts a visitor once and stores no address or user agent', async t => {
  const e = env(),
    w = make({ ...LIMITS, perMinute: 50, perDay: 50 });
  t.mock.timers.enable({ apis: ['Date'], now: Date.parse('2026-11-08T10:00:00Z') });
  for (const route of ['overview', 'compare', 'compare']) {
    const r = await w.fetch(post({ t: 'view', route, ref: 'news.example.org', size: 4 }), e, ctx);
    assert.equal(r.status, 204);
  }
  await w.fetch(post({ t: 'product', id: 'tool-b' }), e, ctx);
  await w.fetch(post({ t: 'product', id: 'unlisted' }), e, ctx);
  await w.fetch(post({ t: 'search', q: 'Vector  DB', found: 0 }), e, ctx);
  assert.deepEqual(rows(e.DB, 'view'), { overview: 1, compare: 2 });
  assert.deepEqual(rows(e.DB, 'visitors'), { all: 1 });
  assert.deepEqual(rows(e.DB, 'stack_size'), { 3: 1 });
  assert.deepEqual(rows(e.DB, 'product'), { 'tool-b': 1, '(other)': 1 });
  assert.deepEqual(rows(e.DB, 'category'), { 'lane-y': 1 });
  assert.deepEqual(rows(e.DB, 'browser'), { chrome: 1 });
  assert.equal(e.DB.sql.prepare('SELECT q FROM search').get().q, 'vector db');
  const dump = JSON.stringify(['salt', 'uniq', 'agg', 'search'].map(x => e.DB.sql.prepare(`SELECT * FROM ${x}`).all()));
  assert.ok(!dump.includes('192.0.2.1') && !dump.includes('Mozilla') && !dump.includes('Chrome/'));
});

test('a new day makes a new salt, so the same visitor gets an unlinkable key', async t => {
  const e = env(),
    w = make(LIMITS);
  t.mock.timers.enable({ apis: ['Date'], now: Date.parse('2026-11-08T23:59:00Z') });
  await w.fetch(post({ t: 'view', route: 'overview' }), e, ctx);
  t.mock.timers.setTime(Date.parse('2026-11-09T00:01:00Z'));
  await w.fetch(post({ t: 'view', route: 'overview' }), e, ctx);
  const salts = e.DB.sql.prepare('SELECT day, v FROM salt ORDER BY day').all();
  const keys = e.DB.sql.prepare('SELECT k FROM uniq ORDER BY day').all();
  assert.deepEqual(salts.map(s => s.day), ['2026-11-08', '2026-11-09']);
  assert.notEqual(salts[0].v, salts[1].v);
  assert.notEqual(keys[0].k, keys[1].k);
});

test('bots, foreign origins, bursts and heavy keys are refused and counted by reason', async t => {
  const e = env(),
    w = make(LIMITS);
  t.mock.timers.enable({ apis: ['Date'], now: Date.parse('2026-11-08T10:00:00Z') });
  await w.fetch(post({ t: 'view', route: 'overview' }, { ua: 'Googlebot/2.1' }), e, ctx);
  await w.fetch(post({ t: 'view', route: 'overview' }, { origin: 'https://elsewhere.example' }), e, ctx);
  await w.fetch(post('{"t":"view"}'), e, ctx);
  await w.fetch(post(JSON.stringify({ t: 'view', route: 'overview', pad: 'x'.repeat(4000) })), e, ctx);
  for (let i = 0; i < 4; i++) await w.fetch(post({ t: 'view', route: 'overview' }), e, ctx);
  for (let m = 1; m <= 3; m++) {
    t.mock.timers.setTime(Date.parse('2026-11-08T10:00:00Z') + m * 60000);
    for (let i = 0; i < 2; i++) await w.fetch(post({ t: 'view', route: 'overview' }), e, ctx);
  }
  await w.fetch(post({ t: 'view', route: 'markets' }, { ip: '192.0.2.9' }), e, ctx);
  assert.equal(rows(e.DB, 'view').overview, 5);
  assert.deepEqual(rows(e.DB, 'refused'), { bot: 1, origin: 1, missing: 1, size: 1, burst: 1, rate_limited: 4 });
  assert.equal(e.DB.sql.prepare('SELECT MAX(n) AS n FROM uniq').get().n, 9);
});

test('only /e reaches the counting code; anything else is the static site', async () => {
  const e = { ...env(), ASSETS: { fetch: async () => new Response('asset', { status: 404 }) } };
  const r = await make(LIMITS).fetch(new Request('https://airstack.bot/missing.json'), e, ctx);
  assert.equal(await r.text(), 'asset');
  assert.equal(e.DB.sql.prepare('SELECT COUNT(*) AS n FROM agg').get().n, 0);
});

test('past the whole site’s ceiling for the day, a flood from fresh addresses writes nothing more', async t => {
  const e = env(),
    w = make({ ...LIMITS, dayCap: 3, perMinute: 50, perDay: 50 });
  t.mock.timers.enable({ apis: ['Date'], now: Date.parse('2026-11-08T10:00:00Z') });
  for (let i = 0; i < 10; i++) await w.fetch(post({ t: 'view', route: 'compare' }, { ip: `198.51.100.${i}` }), e, ctx);
  assert.deepEqual(rows(e.DB, 'events'), { all: 3 });
  assert.equal(e.DB.sql.prepare('SELECT COUNT(*) AS c FROM uniq').get().c, 3); /* no write for a refused visitor */
});
