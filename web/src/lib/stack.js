// spec: AS-256 AS-283
/* ---------- your stack: the tools you track, kept in this browser only; nothing about it is ever sent ----------
   A shared link (#stack=) carries the ids in the address itself, so a colleague sees the same list without any server seeing it. */
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
  mem = tracked(x.id)
    ? mem.filter(y => y.id !== x.id)
    : mem.concat([{ id: x.id, name: x.name, added: new Date().toISOString().slice(0, 10) }]);
  write(mem);
  dispatchEvent(new CustomEvent('airstack:stack'));
}
export function replace(list) {
  mem = list.filter(x => x && typeof x.id === 'string').slice(0, 200);
  write(mem);
  dispatchEvent(new CustomEvent('airstack:stack'));
}
const b64 = s =>
  btoa(unescape(encodeURIComponent(s)))
    .replace(/\+/g, '-')
    .replace(/\//g, '_')
    .replace(/=+$/, '');
const unb64 = s => decodeURIComponent(escape(atob(s.replace(/-/g, '+').replace(/_/g, '/'))));
export const shareLink = list =>
  `${location.origin}${location.pathname}#stack=${b64(JSON.stringify(list.map(x => [x.id, x.name])))}`;
export function fromLink(hash) {
  /* the shared list, or null; names are shown only as text */
  const m = /[#&]stack=([\w-]+)/.exec(hash || '');
  if (!m) return null;
  try {
    const v = JSON.parse(unb64(m[1]));
    return Array.isArray(v)
      ? v
          .filter(p => Array.isArray(p) && typeof p[0] === 'string' && /^[\w.-]{1,80}$/.test(p[0]))
          .slice(0, 200)
          .map(([id, name]) => ({ id, name: String(name || id).slice(0, 120) }))
      : null;
  } catch {
    return null;
  }
}
