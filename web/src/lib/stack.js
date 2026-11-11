import { M } from './data.js';
import { send } from './beacon.js';
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
export function toggle(x) {
  const op = tracked(x.id) ? 'remove' : 'add';
  mem = op === 'remove'
    ? mem.filter(y => y.id !== x.id)
    : mem.concat([{ id: x.id, name: x.name, added: new Date().toISOString().slice(0, 10) }]);
  write(mem);
  send('stack', { op, id: x.id, size: Math.min(mem.length, 100) });
  dispatchEvent(new CustomEvent('airstack:stack'));
}
/* a remove never adds: clicking × twice, or two handlers on one click, leaves the item gone */
export function remove(id) {
  if (!tracked(id)) return;
  mem = mem.filter(y => y.id !== id);
  write(mem);
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
