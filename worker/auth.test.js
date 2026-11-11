import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import { make } from './auth.js';
import { d1 } from './index.test.js';

const SQL = readFileSync(new URL('./users.sql', import.meta.url), 'utf8');
const L = { dayWrites: 1e6, emailsPerMonth: 2800, codesPer15Min: 3, codesPerAddressDay: 10, codesPerNetworkDay: 30, codeTries: 5, sessionDays: 30, stackMax: 100, from: 'AirStack <signin@airstack.bot>' };
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
  await call('/api/me');
  await call('/api/me');
  assert.equal((await call('/api/auth/email/start', { email: 'a@x.com' })).status, 429);
  assert.equal(sent.length, 0);
});

test('Google never takes over an account by matching its email; linking needs the person signed in', async () => {
  const fake = async (u, o) => ({ json: async () => (String(u).includes('token') ? { access_token: 't' } : { sub: 'g-1', email: 'ada@example.com', email_verified: true, name: 'Ada' }) });
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
