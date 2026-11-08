import { PARAMS } from './data.js';
import { esc, fd, n } from './format.js';

/* one series, one de-emphasised 1.5 px line; a missing week breaks the line, never drops to zero; the latest week is the dot */
export function spark(values, weeks, what, { w = 104, h = 28 } = {}) {
  const got = values.map((v, i) => [i, v]).filter(([, v]) => v != null);
  if (got.length < 2) return '';
  const lo = Math.min(...got.map(p => p[1])),
    hi = Math.max(...got.map(p => p[1])),
    X = i => 2 + (i / (values.length - 1)) * (w - 6),
    Y = v => (hi === lo ? h / 2 : h - 3 - ((v - lo) / (hi - lo)) * (h - 6));
  let d = '',
    pen = false;
  values.forEach((v, i) => {
    if (v == null) return void (pen = false);
    d += `${pen ? 'L' : 'M'}${X(i).toFixed(1)} ${Y(v).toFixed(1)}`;
    pen = true;
  });
  const [li, lv] = got[got.length - 1],
    gaps = values.length - got.length,
    say = `${what}, ${values.length} weeks from ${fd(weeks[0])} to ${fd(weeks[weeks.length - 1])}: ${n(lo)} to ${n(hi)} a week, latest ${n(lv)}${gaps ? `; ${gaps} week${gaps > 1 ? 's' : ''} not recorded` : ''}`;
  return `<svg class="spark" width="${w}" height="${h}" viewBox="0 0 ${w} ${h}" role="img" aria-label="${esc(say)}"><title>${esc(say)}</title><path d="${d}"/><circle cx="${X(li).toFixed(1)}" cy="${Y(lv).toFixed(1)}" r="2.5"/></svg>`;
}

/* the registry series a movers row carries, as [values, weeks] */
export const series = r => {
  const s = r && r.series && (r.series[r.dl.registry] || Object.values(r.series)[0]);
  return s && s.length ? [s.map(p => p[1]), s.map(p => p[0])] : null;
};

/* momentum: the latest week against the average of the `weeks` before it, only when all of them are recorded */
export function vsOwnBase(values, weeks = PARAMS.movers.base_weeks) {
  const last = values[values.length - 1],
    prior = values.slice(-weeks - 1, -1);
  if (!weeks || last == null || prior.length < weeks || prior.some(v => v == null)) return null;
  const base = prior.reduce((s, v) => s + v, 0) / weeks;
  return base > 0 ? Math.round((last / base - 1) * 1000) / 10 : null;
}

/* rows without a published base_weeks level get one from their own weekly series, and say so */
export function fillBase(rows) {
  for (const r of rows || []) {
    if (!r.dl || r.dl.vsBase != null) continue;
    const s = series(r),
      v = s && vsOwnBase(s[0]);
    if (v != null) Object.assign(r.dl, { vsBase: v, baseWeeks: PARAMS.movers.base_weeks, from: 'weekly series' });
  }
}
