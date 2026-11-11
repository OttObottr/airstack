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
  const m = /^(\d{4})(?:-(\d{2}))?(?:-(\d{2}))?/.exec(iso || ''); // a date says no more than its source: a year or a month stays one
  return m ? [m[3] && +m[3], m[2] && MON[+m[2] - 1], m[1]].filter(Boolean).join(' ') : '';
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
export const cn = v =>
  (CF ||= new Intl.NumberFormat('en', { notation: 'compact', maximumFractionDigits: 2 })).format(v);
/* how long before `now` (a published built_for or read date, so a page reads the same whenever it is opened): "today", "5d ago",
   "3w ago", then the month past about 60 days; a later date reads as itself. `stamp` wraps it in <time> with the exact date. */
export const ago = (iso, now) => {
  const d = Math.round((Date.parse(now.slice(0, 10)) - Date.parse(iso.slice(0, 10))) / 864e5);
  if (!(d >= 0)) return fd(iso);
  return d === 0 ? 'today' : d < 14 ? `${d}d ago` : d <= 60 ? `${Math.round(d / 7)}w ago` : `${MON[+iso.slice(5, 7) - 1]} ${iso.slice(0, 4)}`;
};
export const stamp = (iso, now) => (iso ? `<time datetime="${esc(iso.slice(0, 10))}" title="${fd(iso)}">${ago(iso, now)}</time>` : '');
/* Links that let a reader check one fact; backend/airstack/evidence.py builds the same ones for the static pages. */
const term = s => encodeURIComponent(s).replace(/[!'()*-]/g, c => `%${c.charCodeAt(0).toString(16).toUpperCase()}`);
export const textFragment = (u, quote) => {
  const lines = String(quote).split(/\r\n|\r|\n/).map(l => l.split(/\s+/).filter(Boolean)).filter(w => w.length);
  if (!lines.length) return u;
  const first = lines[0],
    last = lines[lines.length - 1],
    d = lines.length === 1 && first.length <= 8 ? term(first.join(' ')) : `${term(first.slice(0, 4).join(' '))},${term(last.slice(-4).join(' '))}`;
  return `${u}${u.includes('#') ? '' : '#'}:~:text=${d}`;
};
export const reportUrl = (product, field, u, quote) =>
  `https://github.com/OttObottr/airstack/issues/new?title=${term(`Problem with a fact: ${product}, ${field}`)}&body=${term(`Product: ${product}\nFact: ${field}\nPage: ${u}\nQuote: “${quote}”\n\nWhat is wrong:\n`)}`;
/* a change against a baseline: direction as a glyph and a colour, one decimal; under half a point it is flat */
export const delta = x =>
  x == null
    ? '<span class="text-subtle-foreground" title="not recorded">–</span>'
    : `<span class="${x > 0.5 ? 'text-up' : x < -0.5 ? 'text-down' : 'text-muted-foreground'}">${x > 0.5 ? '▲ ' : x < -0.5 ? '▼ ' : ''}${Math.abs(x).toFixed(1)}%</span>`;
