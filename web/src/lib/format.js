// spec: AS-256 AS-280
export const ic = n => `<svg class="i" aria-hidden="true"><use href="#i-${n}"/></svg>`;
export const esc = s =>
  String(s ?? '').replace(
    /[&<>"']/g,
    c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]
  );
const unsafeHost = h => {
  const x = h.toLowerCase().replace(/\.$/, '');
  if (x === 'localhost' || /\.(?:localhost|local|internal|home\.arpa)$/.test(x)) return true;
  if (/^(?:127|10|0)\./.test(x) || /^169\.254\./.test(x) || /^192\.168\./.test(x)) return true;
  const m = /^172\.(\d+)\./.exec(x);
  return !!(m && +m[1] >= 16 && +m[1] <= 31) || x === '::1' || x === '[::1]';
};
export const url = u => {
  try {
    const parsed = new URL(String(u));
    return esc(/^https?:$/.test(parsed.protocol) && !parsed.username && !parsed.password && !unsafeHost(parsed.hostname) ? parsed.href : 'about:blank');
  } catch { return 'about:blank'; }
};
// scraped URLs: a link is only ever http(s), never javascript: or data:
export const cap = s => (s ? esc(s[0].toUpperCase() + s.slice(1)) : '');
// callers put the result straight into markup, so it is escaped here
export const MON = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
/* the readable form of a name used in addresses (the same rule as backend/tools/pages/layout.py) */
export const slug = s =>
  String(s)
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .slice(0, 60) || 'x';
export const fd = iso => {
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso || '');
  return m ? `${+m[3]} ${MON[+m[2] - 1]} ${m[1]}` : '';
};
let CF; // built on first use: an Intl formatter costs far more to make than to use, and start-up needs none
export const n = x => {
  const v = Number(x);
  return Number.isFinite(v)
    ? String(Math.round(v * 1000) / 1000).replace(/^-?\d+/, m => m.replace(/\B(?=(\d{3})+$)/g, ','))
    : String(v);
};
export const secs = ms => (ms / 1000).toFixed(1) + ' s';
export const host = u =>
  u
    .replace(/^https?:\/\//, '')
    .split('/')[0]
    .replace(/^www\./, '');
export const nobs = '<span class="nobs">Not observed</span>';
export const pct = x => (x === null || x === undefined ? null : `${x > 0 ? '+' : ''}${x.toFixed(1)}%`);
export const sgn = x => (x === null || x === undefined ? null : `${x > 0 ? '+' : ''}${x}`);
export const cn = v =>
  (CF ||= new Intl.NumberFormat('en', { notation: 'compact', maximumFractionDigits: 2 })).format(v);
