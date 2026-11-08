/* Every chart on the site: a series line (sparkline), stacked columns (the pulse) and a bar against its baseline. Scales and paths
   come from d3-scale and d3-shape, served first-party (web/src/vendor, pinned in config/vendor.json).
   Gap policy: a path is never broken. A series starts at its first recorded point; a missing stretch inside it is bridged by a thin dashed segment and counted in the label; a series
   missing more than the published share (max_missing_share) is not drawn, and says why. Every chart carries its own label. */
import { scaleLinear } from '../vendor/d3-scale.js';
import { line } from '../vendor/d3-shape.js';
import { esc, fd, n } from './format.js';

const f = v => +v.toFixed(2);

/* one series as a sparkline: values (null = not recorded) over labels (ISO dates), named `what` */
export function sparkline(all, dates, what, { w = 104, h = 28, unit = 'week', maxMissing = 1 } = {}) {
  /* the series starts at its first recorded point and ends at its last: before it there was nothing to record */
  const a = all.findIndex(v => v != null),
    b = all.length - [...all].reverse().findIndex(v => v != null),
    values = a < 0 ? [] : all.slice(a, b),
    labels = a < 0 ? [] : dates.slice(a, b);
  const pts = values.map((v, i) => [i, v]).filter(([, v]) => v != null);
  if (pts.length < 2) return '';
  const missing = values.length - pts.length,
    span = `${values.length} ${unit}s from ${fd(labels[0])} to ${fd(labels[labels.length - 1])}`;
  if (missing / values.length > maxMissing)
    return `<span class="text-xs text-muted-foreground" title="${esc(`${what}: ${missing} of ${values.length} ${unit}s not recorded`)}">Not drawn: ${n(missing)} of ${n(values.length)} ${unit}s missing</span>`;
  const vs = pts.map(p => p[1]),
    lo = Math.min(...vs),
    hi = Math.max(...vs),
    x = scaleLinear([0, values.length - 1], [2, w - 4]),
    y = lo === hi ? () => h / 2 : scaleLinear([lo, hi], [h - 3, 3]),
    path = line(
      p => f(x(p[0])),
      p => f(y(p[1]))
    );
  /* the solid line joins recorded points; each missing stretch becomes one dashed bridge between its neighbours */
  const bridges = [];
  for (let k = 1; k < pts.length; k++) if (pts[k][0] - pts[k - 1][0] > 1) bridges.push([pts[k - 1], pts[k]]);
  const solid = [];
  let run = [pts[0]];
  for (let k = 1; k < pts.length; k++) {
    if (pts[k][0] - pts[k - 1][0] > 1) {
      solid.push(run);
      run = [];
    }
    run.push(pts[k]);
  }
  solid.push(run);
  const [li, lv] = pts[pts.length - 1],
    say = `${what}, ${span}: ${n(lo)} to ${n(hi)} a ${unit}, latest ${n(lv)}${missing ? `; ${n(missing)} ${unit}${missing > 1 ? 's' : ''} missing, bridged by a dashed line` : ''}`;
  return `<svg class="block overflow-visible" width="${w}" height="${h}" viewBox="0 0 ${w} ${h}" role="img" aria-label="${esc(say)}" data-chart="line" data-gaps="${bridges.length}"><title>${esc(say)}</title>${solid
    .filter(r => r.length > 1)
    .map(r => `<path class="fill-none stroke-muted-foreground" stroke-width="1.5" stroke-linejoin="round" stroke-linecap="round" d="${path(r)}"/>`)
    .join('')}${bridges.map(b => `<path class="fill-none stroke-muted-foreground" stroke-width="1" stroke-dasharray="2 2" data-gap="1" d="${path(b)}"/>`).join('')}${solid
    .filter(r => r.length === 1)
    .map(r => `<circle cx="${f(x(r[0][0]))}" cy="${f(y(r[0][1]))}" r="1" class="fill-muted-foreground"/>`)
    .join('')}<circle cx="${f(x(li))}" cy="${f(y(lv))}" r="2.5" class="fill-foreground"/></svg>`;
}

/* stacked columns: cols = [{s: [value per band]}], fills = one complete class per band; returns rects and a clip mark per column
   taller than `max` (drawn to the top, marked). The caller owns axes and labels. */
export function columns(cols, fills, { width, top, height, max }) {
  const x = scaleLinear([0, cols.length], [0, width]),
    y = scaleLinear([0, max], [0, height]).clamp(true),
    cw = x(1) - x(0),
    bw = Math.max(1, cw - (cw >= 3 ? 1 : 0));
  let out = '';
  cols.forEach((c, k) => {
    let base = top + height;
    const x0 = f(x(k));
    c.s.forEach((v, j) => {
      const h = Math.min(base - top, y(v || 0));
      if (h <= 0) return;
      base -= h;
      out += `<rect x="${x0}" y="${f(base)}" width="${f(bw)}" height="${f(h)}" class="${fills[j]}"/>`;
    });
    if (c.v > max) out += `<path d="M${x0} ${top - 1}h${f(bw)}l${f(-bw / 2)} -4z" class="fill-foreground"/>`;
  });
  return { svg: out, colW: cw };
}

/* a value as a bar with its baseline as a tick, on a 0-to-max scale */
export function versus(v, b, max, label) {
  const x = scaleLinear([0, max], [0, 100]).clamp(true);
  return `<span class="relative block h-1.5 w-full rounded-full bg-muted" role="img" aria-label="${esc(label)}"><span class="absolute inset-y-0 left-0 rounded-full bg-info" style="width:${f(x(v))}%"></span><span class="absolute -inset-y-1 w-0.5 bg-foreground" style="left:${f(x(b))}%"></span></span>`;
}
