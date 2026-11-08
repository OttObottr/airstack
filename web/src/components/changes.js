/* What changed: recorded differences between two reads of a product's own page (changes.json: [{id, type, metric, before, after}],
   each side {value, quote, url, read}), worded as what each read found, never as a cause. In a stack or maker scope, attention
   (registry downloads, Wikipedia views) follows as a secondary line. Workspace panels: `panel`, and `stackPanel` for your stack. */
import { json, PARAMS } from '../lib/data.js';
import { esc, host, pct, stamp, url } from '../lib/format.js';
import { MK } from '../lib/market.js';
import { inScope, nodeOf } from '../lib/scope.js';
import { stack } from '../lib/stack.js';
import { ui } from '../ui/recipes.js';

const LINK = 'underline underline-offset-4 decoration-border hover:text-foreground';
const val = v => (v == null || v === '' ? 'not stated' : Array.isArray(v) ? v.join(', ') : typeof v === 'object' ? JSON.stringify(v) : String(v));
const side = (s, label) =>
  s && s.url
    ? `<span>${label}: ${s.quote ? `“${esc(s.quote)}”` : 'not stated'} on <a class="${LINK}" href="${url(s.url)}" target="_blank" rel="noopener noreferrer">${esc(host(s.url))}</a>, read ${stamp(s.read, now)}</span>`
    : `<span>${label}: not recorded</span>`;
const names = () => new Map([...((window.AIRSTACK_DATA || {}).index || []).map(r => [r[0], r[1]]), ...stack().map(x => [x.id, x.name])]);

let C = null,
  now = '',
  A = null,
  ofNode = null,
  loading = null;
const load = scope =>
  Promise.all([
    (loading ||= json('changes.json')
      .then(d => {
        C = Array.isArray(d) ? d : d.changes || [];
        now = (d.source && d.source.built_for) || C.reduce((m, c) => (c.after && c.after.read > m ? c.after.read : m), ''); /* the build's day, never the viewer's clock */
      })
      .catch(() => (C = []))) /* not published yet: nothing recorded */,
    scope.ids && !A ? json('attention.json').then(d => (A = d), () => (A = { products: {} })) : null,
    scope.kind === 'node' && !ofNode ? nodeOf().then(f => (ofNode = f)) : null,
  ]);

function attention(ids) {
  const nm = names(),
    rows = [];
  for (const id of ids) {
    const m = MK && MK.movers && MK.movers.rows.find(r => r.id === id),
      a = A && A.products[id];
    if (m && m.dl && m.dl.vsBase != null) rows.push([Math.abs(m.dl.vsBase), `${esc(nm.get(id) || id)} ${pct(m.dl.vsBase)} downloads vs its own ${PARAMS.movers.base_weeks}-week level`]);
    if (a && a.change != null) rows.push([Math.abs(a.change * 100), `${esc(nm.get(id) || id)} ${pct(a.change * 100)} Wikipedia views, last 4 weeks vs the 4 before`]);
  }
  rows.sort((x, y) => y[0] - x[0]);
  return `<p class="${ui.panelNote} border-t border-border pt-3"><span class="text-foreground">Attention</span> · ${rows.length ? rows.slice(0, 3).map(r => r[1]).join(' · ') : 'no download or page-view trend with a baseline for these tools'}. Attention, not adoption.</p>`;
}

function draw(scope, el) {
  const nm = names(),
    xs = C.filter(c => inScope(scope, { id: c.id, node: ofNode && ofNode(c.id) })).sort((a, b) => String(b.after?.read).localeCompare(String(a.after?.read)));
  el.innerHTML = `<div class="flex flex-col gap-3">${
    xs.length
      ? `<ol class="flex flex-col">${xs
          .slice(0, 12)
          .map(
            c => `<li class="flex flex-col gap-1 py-2 border-b border-border last:border-b-0"><span class="flex flex-wrap items-center gap-2 text-sm"><a class="font-medium text-foreground ${LINK}" href="#app=${esc(c.id)}">${esc(nm.get(c.id) || c.id)}</a><span class="${ui.badge.neutral}">${esc(c.metric || c.type)}</span><span class="text-muted-foreground">${esc(val(c.before?.value))} → <span class="text-foreground">${esc(val(c.after?.value))}</span></span></span>
          <span class="flex flex-col gap-0.5 text-xs text-muted-foreground">${side(c.after, 'Now')}${side(c.before, 'Before')}</span></li>`
          )
          .join('')}</ol>`
      : `<p class="text-sm text-muted-foreground">No recorded changes yet.</p>`
  }${scope.ids ? attention(scope.ids) : ''}</div>`;
}

const render = (scope, el) => {
  if (C && (!scope.ids || A) && (scope.kind !== 'node' || ofNode)) return draw(scope, el);
  if (!el.firstChild) el.innerHTML = '<div class="skeleton skeleton-list" role="status" aria-label="Loading what changed"></div>';
  return load(scope).then(() => draw(scope, el));
};
const NOTE = 'What a product’s own page said at one read and at the next, both quoted and linked.';
export const panel = { id: 'changes', title: 'What changed', note: NOTE, render };
export const stackPanel = { id: 'stack-changes', title: 'What changed in your stack', note: NOTE, render };
