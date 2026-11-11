import { M } from './data.js';
import { send } from './beacon.js';
import { A, refresh, saveStack } from './account.js';
const KEY = 'airstack.stack.v1';
const read = () => {
  try {
    const v = JSON.parse(localStorage.getItem(KEY) || '[]');
    return Array.isArray(v) ? v.filter(x => x && typeof x.id === 'string') : [];
  } catch {
    return [];
  }
};
const write = s => {
  try {
    localStorage.setItem(KEY, JSON.stringify(s));
  } catch {
    /* private mode: the stack lives for this page only */
  }
};
let mem = read();
export const stack = () => mem.slice();
export const tracked = id => mem.some(x => x.id === id);
/* with accounts on, the stack is the signed-in person's: a signed-out click asks them to sign in instead of saving */
const gate = () => {
  if (!A.enabled) return true;
  if (!A.user) {
    dispatchEvent(new CustomEvent('airstack:signin'));
    return false;
  }
  return true;
};
const persist = (op, x) => {
  if (A.enabled && A.user)
    saveStack(op, x.id, x.name).then(r => {
      if (!r.ok) refresh(); /* the server's stack is the truth: show it again */
    });
  else write(mem);
};
export function toggle(x) {
  if (!gate()) return;
  const op = tracked(x.id) ? 'remove' : 'add';
  mem = op === 'remove'
    ? mem.filter(y => y.id !== x.id)
    : mem.concat([{ id: x.id, name: x.name, added: new Date().toISOString().slice(0, 10) }]);
  persist(op, x);
  send('stack', { op, id: x.id, size: Math.min(mem.length, 100) });
  dispatchEvent(new CustomEvent('airstack:stack'));
}
/* a remove never adds: clicking × twice, or two handlers on one click, leaves the item gone */
export function remove(id) {
  if (!tracked(id) || !gate()) return;
  mem = mem.filter(y => y.id !== id);
  persist('remove', { id });
  send('stack', { op: 'remove', id, size: Math.min(mem.length, 100) });
  dispatchEvent(new CustomEvent('airstack:stack'));
}
export function replace(list) {
  mem = list.filter(x => x && typeof x.id === 'string').slice(0, 100);
  write(mem);
  dispatchEvent(new CustomEvent('airstack:stack'));
}
const b64 = s =>
  btoa(unescape(encodeURIComponent(s)))
    .replace(/\+/g, '-')
    .replace(/\//g, '_')
    .replace(/=+$/, '');
const unb64 = s => decodeURIComponent(escape(atob(s.replace(/-/g, '+').replace(/_/g, '/'))));
export const shareLink = list => `${location.origin}${location.pathname}#stack=${b64(JSON.stringify(list.map(x => x.id)))}`;
export function fromLink(hash) {
  const m = /[#&]stack=([\w-]+)/.exec(hash || '');
  if (!m) return null;
  const names = new Map(M.index.map(r => [r[0], r[1]]));
  try {
    const v = JSON.parse(unb64(m[1]));
    if (!Array.isArray(v)) return null;
    const ids = [...new Set(v.map(p => (Array.isArray(p) ? p[0] : p)))].filter(id => names.has(id));
    return ids.slice(0, 100).map(id => ({ id, name: names.get(id) }));
  } catch {
    return null;
  }
}

/* on sign-in, a stack kept in this browser moves into the account once, then the browser copy is cleared */
addEventListener('airstack:account', async () => {
  if (!A.enabled) return;
  if (A.user) {
    const local = read();
    if (local.length) {
      await Promise.all(local.filter(x => !A.stack.some(y => y.id === x.id)).map(x => saveStack('add', x.id, x.name)));
      write([]);
      return void refresh();
    }
    mem = A.stack.map(x => ({ id: x.id, name: x.name, added: x.added }));
  } else mem = [];
  dispatchEvent(new CustomEvent('airstack:stack'));
});
