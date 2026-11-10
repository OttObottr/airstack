import assert from 'node:assert/strict';
import { readFileSync, readdirSync } from 'node:fs';
import test from 'node:test';
import { PLAIN, send } from '../web/src/lib/beacon.js';
import { VIEWS } from '../web/src/lib/router.js';
import schema from './schema.json' with { type: 'json' };

const browser = nav => {
  const sent = [];
  Object.defineProperty(globalThis, 'navigator', { configurable: true, value: { sendBeacon: (u, b) => sent.push([u, JSON.parse(b)]) || true, ...nav } });
  return sent;
};

test('Global Privacy Control or Do Not Track stops every event before it is sent', () => {
  for (const nav of [{ globalPrivacyControl: true }, { doNotTrack: '1' }]) {
    const sent = browser(nav);
    assert.equal(send('view', { route: 'overview' }), false);
    assert.deepEqual(sent, []);
  }
});

test('an event goes to /e on this origin, and only a short plain search is sent', () => {
  const sent = browser({});
  send('view', { route: 'overview' });
  send('search', { q: 'vector db', found: 0 });
  send('search', { q: 'someone@example.org', found: 0 });
  send('search', { q: 'order 123456', found: 0 });
  assert.deepEqual(sent, [['/e', { t: 'view', route: 'overview' }], ['/e', { t: 'search', q: 'vector db', found: 0 }]]);
});

test('the beacon, the views and the schema agree', () => {
  assert.equal(PLAIN.source, schema.query);
  assert.deepEqual(schema.events.view.route, Object.keys(VIEWS));
  const fields = Object.fromEntries(Object.entries(schema.events).map(([t, f]) => [t, Object.keys(f).map(k => k.replace('?', ''))]));
  const code = readdirSync(new URL('../web/src', import.meta.url), { recursive: true })
    .filter(f => f.endsWith('.js'))
    .map(f => readFileSync(new URL(`../web/src/${f}`, import.meta.url), 'utf8'))
    .join('\n');
  const calls = [...code.matchAll(/send\('(\w+)', \{([^}]*)\}/g), ...code.matchAll(/', '(\w+)', \{ (\w+:)/g)];
  assert.ok(calls.length >= 8);
  for (const [, t, body] of calls) {
    assert.ok(fields[t], t);
    for (const k of body.match(/\b\w+(?=:)/g) || []) assert.ok(fields[t].includes(k), `${t}.${k}`);
  }
});
