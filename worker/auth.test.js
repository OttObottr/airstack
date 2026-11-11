import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import { make } from './auth.js';
import { d1 } from './index.test.js';

const SQL = readFileSync(new URL('./users.sql', import.meta.url), 'utf8');
const L = { dayWrites: 1e6, requestsPerNetworkDay: 1e6, emailsPerMonth: 2800, codesPer15Min: 3, codesPerAddressDay: 10, codesPerNetworkDay: 30, codeTries: 5, sessionDays: 30, stackMax: 100, from: 'AirStack <signin@airstack.bot>' };
const ORIGIN = 'https://airstack.bot';

function setup(limits = {}) {
  const sent = [],
    env = { USERS: d1(SQL), AUTH_SECRET: 'test-secret', EMAIL: { send: async m => (sent.push(m), { messageId: 'm1' }) } },
    w = make({ ...L, ...limits });
  let jar = '';
  const call = async (path, body, { method = body ? 'POST' : 'GET', origin = ORIGIN, ip = '192.0.2.1' } = {}) => {
    const r = await w.handle(
      new Request(ORIGIN + path, { method, body: body ? JSON.stringify(body) : undefined, headers: { origin, cookie: jar, 'content-type': 'application/json', 'cf-connecting-ip': ip } }),
      env,
      Date.parse('2026-11-11T12:00:00Z')
    );
    const c = r.headers.get('set-cookie');
    if (c && c.startsWith('__Host-as=')) jar = c.split(';')[0].endsWith('=') ? '' : c.split(';')[0];
    return r;
  };
  const code = () => sent.at(-1).text.match(/\d{6}/)[0];
  return { env, call, sent, code };
}

test('an emailed code signs a new person in once, and their stack is theirs', async () => {
  const { call, code, sent, env } = setup();
  assert.equal((await call('/api/auth/email/start', { email: 'Ada@Example.com' })).status, 200);
  assert.equal(sent.length, 1);
  assert.equal(sent[0].to, 'ada@example.com');
  const c = code();
  assert.equal((await call('/api/auth/email/verify', { email: 'ada@example.com', code: c })).status, 200);
  assert.equal((await call('/api/auth/email/verify', { email: 'ada@example.com', code: c })).status, 400); /* a code works once */
  await call('/api/stack', { op: 'add', id: 'notion', name: 'Notion' });
  const me = await (await call('/api/me')).json();
  assert.deepEqual(me.methods, ['email']);
  assert.deepEqual(me.stack.map(x => x.id), ['notion']);
  const stored = JSON.stringify(env.USERS.sql.prepare('SELECT * FROM verification').all()) + JSON.stringify(env.USERS.sql.prepare('SELECT token FROM session').all());
  assert.ok(!stored.includes(c)); /* neither the code nor the cookie is stored as is */
});

test('a wrong code is refused, and after five wrong tries the right one is too', async () => {
  const { call, code } = setup();
  await call('/api/auth/email/start', { email: 'b@example.com' });
  const c = code();
  for (let i = 0; i < 5; i++) assert.equal((await call('/api/auth/email/verify', { email: 'b@example.com', code: '000000' === c ? '111111' : '000000' })).status, 400);
  assert.equal((await call('/api/auth/email/verify', { email: 'b@example.com', code: c })).status, 400);
});

test('emails stop at the monthly cap and per address, with a calm busy answer', async () => {
  const { call, sent } = setup({ emailsPerMonth: 2 });
  for (const e of ['a@x.com', 'b@x.com', 'c@x.com']) await call('/api/auth/email/start', { email: e });
  assert.equal(sent.length, 2);
  const r = await call('/api/auth/email/start', { email: 'd@x.com' });
  assert.equal(r.status, 429);
  assert.match((await r.json()).message, /busy/i);
  const s2 = setup();
  for (let i = 0; i < 5; i++) await s2.call('/api/auth/email/start', { email: 'same@x.com' });
  assert.equal(s2.sent.length, 3); /* three codes per address per 15 minutes */
});

test('a request from another site, or a stack change while signed out, is refused', async () => {
  const { call } = setup();
  assert.equal((await call('/api/auth/email/start', { email: 'a@x.com' }, { origin: 'https://evil.example' })).status, 403);
  assert.equal((await call('/api/stack', { op: 'add', id: 'notion' })).status, 401);
});

test('the last way in cannot be removed, and deleting the account removes everything', async () => {
  const { call, code, env } = setup();
  await call('/api/auth/email/start', { email: 'e@x.com' });
  await call('/api/auth/email/verify', { email: 'e@x.com', code: code() });
  assert.equal((await call('/api/auth/unlink', { provider: 'email' })).status, 400);
  await call('/api/stack', { op: 'add', id: 'slack', name: 'Slack' });
  assert.equal((await call('/api/account/delete', {})).status, 200);
  for (const t of ['"user"', 'account', 'session', 'stack']) assert.equal(env.USERS.sql.prepare(`SELECT COUNT(*) AS c FROM ${t}`).get().c, 0, t);
});

test('past the daily write ceiling every request is refused before it writes', async () => {
  const { call, sent } = setup({ dayWrites: 2 });
  await call('/api/auth/email/start', { email: 'a@x.com' }, { ip: '192.0.2.1' });
  await call('/api/auth/email/start', { email: 'b@x.com' }, { ip: '192.0.2.2' });
  assert.equal((await call('/api/auth/email/start', { email: 'c@x.com' }, { ip: '192.0.2.3' })).status, 429);
  assert.equal(sent.length, 2);
});

test('a signed-out page load touches no database and spends nothing', async () => {
  const { call, sent, env } = setup({ dayWrites: 1, requestsPerNetworkDay: 1 });
  for (let i = 0; i < 20; i++) assert.deepEqual(await (await call('/api/me')).json(), { user: null, enabled: true, ways: { email: true, google: false, github: false } });
  assert.equal(env.USERS.sql.prepare('SELECT COUNT(*) AS c FROM quota').get().c, 0);
  assert.equal((await call('/api/auth/email/start', { email: 'a@x.com' })).status, 200);
  assert.equal(sent.length, 1);
});

test('one network cannot use up the day for everyone', async () => {
  const { call, sent } = setup({ dayWrites: 10, requestsPerNetworkDay: 3 });
  for (let i = 0; i < 50; i++) await call('/api/me', null, { ip: '198.51.100.7' }).then(() => call('/api/stack', { op: 'add', id: 'x' }, { ip: '198.51.100.7' }));
  assert.equal((await call('/api/auth/email/start', { email: 'ok@x.com' }, { ip: '192.0.2.9' })).status, 200);
  assert.equal(sent.length, 1);
});

test('signing out and deleting the account still work once the daily ceiling is reached', async () => {
  const { call, code, env } = setup({ dayWrites: 2 });
  await call('/api/auth/email/start', { email: 'f@x.com' });
  await call('/api/auth/email/verify', { email: 'f@x.com', code: code() });
  assert.equal((await call('/api/stack', { op: 'add', id: 'slack' })).status, 429); /* the ceiling is reached */
  assert.equal((await call('/api/account/delete', {})).status, 200);
  assert.equal(env.USERS.sql.prepare('SELECT COUNT(*) AS c FROM "user"').get().c, 0);
});

test('guesses sent all at once still get five tries in total', async () => {
  const { call, code, env } = setup();
  await call('/api/auth/email/start', { email: 'g@x.com' });
  const c = code();
  const guesses = Array.from({ length: 60 }, (_, i) => String((+c + 1 + i) % 1e6).padStart(6, '0'));
  guesses[59] = c; /* the right code, last in the burst */
  const out = await Promise.all(guesses.map(g => call('/api/auth/email/verify', { email: 'g@x.com', code: g })));
  assert.ok(out.every(r => r.status === 400));
  assert.equal(env.USERS.sql.prepare('SELECT COUNT(*) AS c FROM "user"').get().c, 0);
  assert.equal((await call('/api/auth/email/verify', { email: 'g@x.com', code: c })).status, 400);
});

test('email addresses are not stored in pending codes or counters, and old ones are cleared', async () => {
  const { call, code, env } = setup();
  const db = env.USERS.sql;
  db.prepare("INSERT INTO verification(id, identifier, value, expiresAt, createdAt, updatedAt) VALUES ('old', 'email:old@x.com', 'h.0', '2026-11-10T00:10:00Z', '2026-11-10T00:00:00Z', NULL)").run();
  db.prepare("INSERT INTO quota(name, period, n) VALUES ('code:old@x.com', '2026-11-10', 1), ('emails', '2026-10', 5)").run();
  await call('/api/auth/email/start', { email: 'Hana@Example.com' });
  const stored = () => JSON.stringify([db.prepare('SELECT * FROM verification').all(), db.prepare('SELECT * FROM quota').all()]);
  assert.ok(!/@/.test(stored()), stored());
  await call('/api/auth/email/verify', { email: 'hana@example.com', code: code() });
  await call('/api/auth/email/start', { email: 'hana@example.com', link: true });
  assert.equal((await call('/api/account/delete', {})).status, 200);
  assert.equal(db.prepare('SELECT COUNT(*) AS c FROM verification').get().c, 0);
  assert.ok(!/code:/.test(stored()), stored());
});

test('a failed GitHub or Google profile answer never signs anyone in', async () => {
  for (const provider of ['github', 'google']) {
    const fake = async u => (String(u).includes('token') ? { ok: true, json: async () => ({ access_token: 't' }) } : { ok: false, json: async () => ({ message: 'Bad credentials' }) });
    const w = make(L, fake);
    const env = { USERS: d1(SQL), AUTH_SECRET: 's', GOOGLE_CLIENT_ID: 'id', GOOGLE_CLIENT_SECRET: 'sec', GITHUB_CLIENT_ID: 'id', GITHUB_CLIENT_SECRET: 'sec' };
    const go = (path, cookie = '') => w.handle(new Request(ORIGIN + path, { headers: { origin: ORIGIN, cookie } }), env, Date.parse('2026-11-11T12:00:00Z'));
    for (let i = 0; i < 2; i++) {
      const flow = (await go(`/api/auth/${provider}/start`)).headers.get('set-cookie').split(';')[0];
      const cb = await go(`/api/auth/${provider}/callback?state=${flow.split('=')[1].split('.')[0]}&code=c`, flow);
      assert.match(cb.headers.get('location'), /signin=failed/, provider);
    }
    assert.equal(env.USERS.sql.prepare('SELECT COUNT(*) AS c FROM account').get().c, 0, provider);
  }
});

test('Google never takes over an account by matching its email; linking needs the person signed in', async () => {
  const fake = async (u, o) => ({ ok: true, json: async () => (String(u).includes('token') ? { access_token: 't' } : { sub: 'g-1', email: 'ada@example.com', email_verified: true, name: 'Ada' }) });
  const w = make(L, fake);
  const sent = [],
    env = { USERS: d1(SQL), AUTH_SECRET: 's', GOOGLE_CLIENT_ID: 'id', GOOGLE_CLIENT_SECRET: 'sec', EMAIL: { send: async m => sent.push(m) } };
  let jar = '';
  const go = async (path, body, extra = '') => {
    const r = await w.handle(new Request(ORIGIN + path, { method: body ? 'POST' : 'GET', body: body ? JSON.stringify(body) : undefined, headers: { origin: ORIGIN, cookie: [jar, extra].filter(Boolean).join('; '), 'content-type': 'application/json' } }), env, Date.parse('2026-11-11T12:00:00Z'));
    for (const c of r.headers.getSetCookie ? r.headers.getSetCookie() : [r.headers.get('set-cookie')].filter(Boolean)) if (c.startsWith('__Host-as=') && !c.startsWith('__Host-as=;')) jar = c.split(';')[0];
    return r;
  };
  await go('/api/auth/email/start', { email: 'ada@example.com' });
  await go('/api/auth/email/verify', { email: 'ada@example.com', code: sent[0].text.match(/\d{6}/)[0] });
  const signedIn = jar;
  jar = '';
  const start = await go('/api/auth/google/start');
  const flow = start.headers.get('set-cookie').split(';')[0], state = flow.split('=')[1].split('.')[0];
  const cb = await go(`/api/auth/google/callback?state=${state}&code=c`, null, flow);
  assert.match(cb.headers.get('location'), /signin=exists/); /* same email, signed out: refused, not merged */
  jar = signedIn;
  const s2 = await go('/api/auth/google/start?link=1');
  const flow2 = s2.headers.get('set-cookie').split(';')[0], state2 = flow2.split('=')[1].split('.')[0];
  const cb2 = await go(`/api/auth/google/callback?state=${state2}&code=c`, null, flow2);
  assert.match(cb2.headers.get('location'), /settings=linked/);
  assert.deepEqual((await (await go('/api/me')).json()).methods, ['email', 'google']);
});
