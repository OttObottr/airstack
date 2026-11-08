import { PARAMS } from './data.js';
import { sparkline } from './charts.js';

/* a weekly series through the one chart module; a series missing more than the published share is not drawn */
export const spark = (values, weeks, what, o = {}) =>
  sparkline(values, weeks, what, { maxMissing: PARAMS.movers.max_missing_share ?? 1, ...o });

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
