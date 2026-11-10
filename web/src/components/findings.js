/* Category insights (insights.json findings): each item carries its base, its baseline and its spread, and the producer has already
   dropped what fails insights.* (rule 10). Two workspace panels: `panel` (the four comparisons) and `brief` (one line each). */
import { json } from '../lib/data.js';
import { esc, n, url } from '../lib/format.js';
import { versus } from '../lib/charts.js';
import { inScope, nodeOf, scopeControl, scopeName } from '../lib/scope.js';
import { ui } from '../ui/recipes.js';

const p1 = x => `${(x * 100).toFixed(x < 0.1 ? 1 : 0)}%`;
const k = x => (x >= 1e6 ? `${(x / 1e6).toFixed(1)}M` : x >= 1e4 ? `${Math.round(x / 1e3)}k` : n(x));
const LINK = 'underline underline-offset-4 decoration-border hover:text-foreground';
const cat = i => `<a class="text-sm font-medium text-foreground ${LINK}" href="/t/${esc(i.node)}/">${esc(i.name)}</a>`;
const ext = (href, text) => `<a class="${LINK}" href="${url(href)}" target="_blank" rel="noopener noreferrer">${esc(text)}</a>`;
const bar = (i, max) => versus(i.value, i.baseline, max, `${i.name}: ${p1(i.value)} against a baseline of ${p1(i.baseline)}`);
const SECTIONS = [
  {
    key: 'rising',
    title: 'Rising attention',
    ask: 'Which categories take a larger share of what people read?',
    value: i => `<b class="${ui.num} text-foreground">${p1(i.value)}</b> of all measured views · was ${p1(i.baseline)} · ×${i.ratio.toFixed(2)}`,
    more: i => `Driven by ${ext(i.driver.url, i.driver.name)}, ${k(i.driver.views[0])} → ${k(i.driver.views[1])} views · ${n(i.base)} products measured`,
    base: F => `Method: ${esc(F.rule)}: ${F.weeks[0]} to ${F.weeks[1]} against ${F.weeks[2]} to ${F.weeks[3]}. ${n(F.base.products)} products; all their views ${k(F.base.views[0])} → ${k(F.base.views[1])}. ${esc(F.source)}. Attention, not adoption.`,
    one: i => `<b class="text-foreground">${esc(i.name)}</b> ${p1(i.value)} of all measured views, was ${p1(i.baseline)}; driven by ${esc(i.driver.name)}`,
  },
  {
    key: 'ai',
    title: 'Where AI is moving in',
    ask: 'Which categories state AI in their one-line descriptions more than the average?',
    value: i => `<b class="${ui.num} text-foreground">${p1(i.value)}</b> state AI · average ${p1(i.baseline)}`,
    more: i => `${n(i.found)} of ${n(i.base)} products read · ${i.z} standard errors above the average`,
    base: F => `Method: ${esc(F.rule)}. Average: ${n(F.base.found)} of ${n(F.base.products)} products read.`,
    one: i => `<b class="text-foreground">${esc(i.name)}</b> ${p1(i.value)} state AI vs ${p1(i.baseline)} average, ${n(i.found)} of ${n(i.base)}`,
  },
  {
    key: 'entrants',
    title: 'New entrants',
    ask: 'Which categories have the most recently started products?',
    value: i => `<b class="${ui.num} text-foreground">${p1(i.value)}</b> started recently · average ${p1(i.baseline)}`,
    more: i => `${n(i.found)} of ${n(i.base)} with an inception year: ${i.examples.map(x => `${ext(x.url, x.name)} ${x.year}`).join(', ')}`,
    base: F => `Method: ${esc(F.rule)}. Across every category: ${n(F.base.found)} of ${n(F.base.products)} (${p1(F.base.found / F.base.products || 0)}). ${esc(F.source)}.`,
    one: (i, F) => `<b class="text-foreground">${esc(i.name)}</b> ${p1(i.value)} started in ${F.since} or later vs ${p1(i.baseline)} average`,
  },
  {
    key: 'standout',
    title: 'Standout trait',
    ask: 'What does a category state far more often than the rest?',
    value: i => `<b class="${ui.num} text-foreground">${p1(i.value)}</b> ${esc(i.label)} · average ${p1(i.baseline)}`,
    more: i => `${n(i.found)} of ${n(i.base)} products read · ${i.z} standard errors above the average`,
    base: F => `Method: ${esc(F.rule)}. ${n(F.base.products)} products read.`,
    one: i => `<b class="text-foreground">${esc(i.name)}</b> ${p1(i.value)} ${esc(i.label)} vs ${p1(i.baseline)} average, ${n(i.found)} of ${n(i.base)}`,
  },
];

let I = null,
  ofNode = null;
const load = scope =>
  Promise.all([json('insights.json').then(d => (I = d)), scope.kind === 'stack' || scope.kind === 'maker' ? nodeOf().then(f => (ofNode = f)) : null]);
/* an item is in scope when its category is the scope's node or under it, or holds one of the scope's products */
const pick = (scope, F, s) =>
  F[s.key].items.filter(i =>
    scope.ids ? ofNode && scope.ids.some(id => inScope({ kind: 'node', id: i.node }, { node: ofNode(id) }, F.tree)) : inScope(scope, { node: i.node }, F.tree)
  );
const none = (scope, F) => `<p class="${ui.panelNote}">No category${scope.kind === 'all' ? '' : ` in ${esc(scopeName(scope, F.tree))}`} stands out.</p>`;

function full(scope, el) {
  const F = I.findings;
  el.innerHTML = `<div class="flex flex-col gap-6">${SECTIONS.map(s => {
    const xs = pick(scope, F, s).slice(0, F.params.top),
      m = Math.max(1e-9, ...xs.flatMap(i => [i.value, i.baseline]));
    return `<section class="flex flex-col gap-2"><p class="${ui.panelTitle}">${esc(s.title)}</p><p class="${ui.panelNote}">${esc(s.ask)}</p>
      ${xs.length ? `<ol class="flex flex-col">${xs.map(i => `<li class="grid gap-1.5 py-2 border-b border-border last:border-b-0 md:grid-cols-[minmax(0,14rem)_minmax(0,9rem)_minmax(0,1fr)] md:items-center md:gap-x-4">${cat(i)}${bar(i, m)}<span class="flex flex-col gap-1 text-xs text-muted-foreground"><span>${s.value(i)}</span><span>${s.more(i)}</span></span></li>`).join('')}</ol>` : none(scope, F)}
      <p class="${ui.panelNote}">${s.base(F[s.key])}</p></section>`;
  }).join('')}
    <p class="${ui.panelNote}">Bar: the category; tick: its baseline.</p></div>`;
}

function brief(scope, el) {
  const F = I.findings;
  el.innerHTML = `<ol class="flex flex-col">${SECTIONS.map(s => {
    const xs = pick(scope, F, s);
    return `<li class="flex flex-col gap-1 py-2 border-b border-border last:border-b-0"><p class="${ui.meta}">${esc(s.title)}</p><p class="text-sm text-muted-foreground leading-snug">${xs.length ? s.one(xs[0], F[s.key]) : 'No category stands out.'}</p></li>`;
  }).join('')}</ol>`;
}

const render = draw => (scope, el) => {
  const go = () => draw(scope, el);
  if (I && (ofNode || !scope.ids)) return go();
  if (!el.firstChild) el.innerHTML = '<div class="skeleton skeleton-list" role="status" aria-label="Loading category insights"></div>';
  return load(scope)
    .then(go)
    .catch(e => {
      console.error('findings:', e);
      el.innerHTML = `<p class="${ui.panelNote}" role="status">Category insights could not be loaded. Check the connection and reload.</p>`;
    });
};
const NOTE = 'Each compares a category with the average or its own earlier weeks, with its base.';
export const panel = { id: 'findings', title: 'Category insights', note: NOTE, controls: scope => scopeControl(scope, 'categories'), render: render(full) };
export const briefPanel = {
  id: 'findings-brief',
  title: 'Category insights',
  note: 'The leading comparison of each kind, with its base.',
  controls: () => `<a class="${ui.button.ghost} shrink-0 whitespace-nowrap" href="#/insights">All insights</a>`,
  render: render(brief),
};
