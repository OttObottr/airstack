export const ic = n => `<svg class="i" aria-hidden="true"><use href="#i-${n}"/></svg>`;
export const esc = s =>
  String(s ?? '').replace(
    /[&<>"']/g,
    c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]
  );
export const url = u => {
  try {
    const parsed = new URL(String(u));
    return esc(/^https?:$/.test(parsed.protocol) && !parsed.username && !parsed.password ? parsed.href : 'about:blank');
  } catch { return 'about:blank'; }
};
export const cap = s => (s ? esc(s[0].toUpperCase() + s.slice(1)) : '');
export const MON = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
/* the same rule as the static pages' addresses */
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
let CF; // built on first use: an Intl formatter is costly to make
export const n = x => {
  const v = Number(x);
  return Number.isFinite(v)
    ? String(Math.round(v * 1000) / 1000).replace(/^-?\d+/, m => m.replace(/\B(?=(\d{3})+$)/g, ','))
    : String(v);
};
export const host = u =>
  u
    .replace(/^https?:\/\//, '')
    .split('/')[0]
    .replace(/^www\./, '');
export const nobs = '<span class="nobs">Not observed</span>';
export const LISTED = 'Listed, not researched';
export const sq = s => s.toLowerCase().replace(/[^a-z0-9]/g, '');
export const known = (x, facts) =>
  x.org
    ? `${n(x.made)} product${x.made === 1 ? '' : 's'} listed`
    : facts
      ? `researched · ${facts} facts`
      : x.cat || x.dir
        ? LISTED
        : 'tracked';
export const pct = x => (x === null || x === undefined ? null : `${x > 0 ? '+' : ''}${x.toFixed(1)}%`);
export const sgn = x => (x === null || x === undefined ? null : `${x > 0 ? '+' : ''}${x}`);
export const cn = v =>
  (CF ||= new Intl.NumberFormat('en', { notation: 'compact', maximumFractionDigits: 2 })).format(v);
