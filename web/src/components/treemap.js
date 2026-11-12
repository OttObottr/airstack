/* This week by category: last week's dated events (pulse.json) as a treemap, sector -> product, each block's area its weight (launches
   and major releases weigh most), coloured by the same sector fills as the pulse; hover names the product, its category and its biggest
   update, a click opens the product, and the same figures are one tap away as a list. */
import { esc, fd, n } from '../lib/format.js';
import { json } from '../lib/data.js';
import { ui } from '../ui/recipes.js';

const FILL = ['fill-sector-1', 'fill-sector-2', 'fill-sector-3', 'fill-sector-4', 'fill-sector-5', 'fill-sector-6', 'fill-sector-7', 'fill-sector-other', 'fill-sector-other/40'];
const SW = [...ui.sector, 'bg-sector-other/40'];
const W = 1000, H = 420, GAP = 2;
/* a label that fits its block (about 8.6 units a character at this size), shortened with an ellipsis, or none on a block too small */
const fit = (name, w) => {
  const room = Math.floor((w - 18) / 8.6);
  return room < 4 ? '' : name.length <= room ? name : name.slice(0, room - 1) + '…';
};

/* squarified layout (Bruls, Huizing and van Wijk): rows of blocks whose aspect ratios stay near square */
function squarify(items, x, y, w, h) {
  const total = items.reduce((s, i) => s + i.v, 0), out = [];
  let rest = items.map(i => ({ ...i, a: (i.v / total) * w * h }));
  while (rest.length) {
    const short = Math.min(w, h);
    let row = [rest[0]], worst = Infinity;
    for (let k = 1; k <= rest.length; k++) {
      const r = rest.slice(0, k), s = r.reduce((t, i) => t + i.a, 0), mx = Math.max(...r.map(i => i.a)), mn = Math.min(...r.map(i => i.a));
      const ratio = Math.max((short * short * mx) / (s * s), (s * s) / (short * short * mn));
      if (ratio > worst) break;
      worst = ratio; row = r;
    }
    const s = row.reduce((t, i) => t + i.a, 0), thick = s / short;
    let off = 0;
    for (const i of row) {
      const len = i.a / thick;
      out.push(w >= h ? { ...i, x, y: y + off, w: thick, h: len } : { ...i, x: x + off, y, w: len, h: thick });
      off += len;
    }
    if (w >= h) { x += thick; w -= thick; } else { y += thick; h -= thick; }
    rest = rest.slice(row.length);
  }
  return out;
}

function blocks(P) {
  const week = P.weeks[P.weeks.length - 1], by = new Map();
  for (const [ix, w] of week.e) {
    const e = P.events[ix];
    if (!e || !e.id || !(w > 0)) continue;
    const b = by.get(e.id) || { id: e.id, name: e.name || e.id, j: e.sector, node: e.node, v: 0, events: [] };
    b.v += w; b.events.push(e);
    by.set(e.id, b);
  }
  const products = [...by.values()].sort((a, b) => b.v - a.v);
  const sectors = new Map();
  for (const p of products) (sectors.get(p.j) || sectors.set(p.j, []).get(p.j)).push(p);
  return { week: week.w, sectors: [...sectors].map(([j, ps]) => ({ j, v: ps.reduce((s, p) => s + p.v, 0), ps })).sort((a, b) => b.v - a.v) };
}

function draw(el, P, T) {
  const { week, sectors } = blocks(P);
  if (!sectors.length) return void (el.innerHTML = `<p class="${ui.panelNote}">Nothing dated this week yet.</p>`);
  const cat = node => (T && T.nodes[node] ? T.nodes[node].name : '');
  const rects = squarify(sectors, 0, 0, W, H).flatMap(s => squarify(s.ps, s.x, s.y, s.w, s.h).map(p => ({ ...p, j: s.j })));
  const top = e => [...e.events].sort((a, b) => (b.w || 0) - (a.w || 0))[0];
  el.innerHTML = `
    <header class="flex flex-col gap-1"><h2 class="h-section">This week by category</h2><p class="${ui.panelNote}">Week of ${fd(week)}: each block is a product, sized by what it announced or released (launches and major releases count most), coloured by sector.</p></header>
    <div class="relative mt-3"><svg class="block h-auto w-full" viewBox="0 0 ${W} ${H}" role="img" aria-label="This week's updates by sector and product">${rects
      .map(
        (r, k) => `<g class="cursor-pointer" data-k="${k}" tabindex="0" role="link" aria-label="${esc(`${r.name}: ${r.events.length} update${r.events.length > 1 ? 's' : ''}`)}">
          <rect x="${r.x + GAP / 2}" y="${r.y + GAP / 2}" width="${Math.max(0, r.w - GAP)}" height="${Math.max(0, r.h - GAP)}" rx="4" class="${FILL[r.j] || FILL[7]} hover:opacity-80"/>
          ${r.h > 34 && fit(r.name, r.w) ? `<text x="${r.x + 10}" y="${r.y + 24}" class="fill-foreground text-[15px] font-semibold" style="paint-order:stroke;stroke:var(--color-bg);stroke-width:3px">${esc(fit(r.name, r.w))}</text>` : ''}
        </g>`
      )
      .join('')}</svg><div class="pointer-events-none absolute z-10 hidden max-w-xs rounded-md border border-border bg-popover p-2 text-xs shadow-md" data-tip></div></div>
    <ul class="mt-3 flex flex-wrap gap-x-4 gap-y-2 text-xs text-muted-foreground" aria-label="Sectors">${sectors
      .map(s => `<li class="inline-flex items-center gap-1.5"><i class="inline-block size-2.5 rounded-[2px] ${SW[s.j] || SW[7]}" aria-hidden="true"></i>${esc(P.sectors[s.j] ? P.sectors[s.j].name : 'Other')}</li>`)
      .join('')}</ul>
    <details class="mt-2"><summary class="${ui.panelNote}">See as a list</summary><table class="${ui.table} mt-2"><thead><tr><th class="${ui.th}">Product</th><th class="${ui.th}">Category</th><th class="${ui.th} text-right">Updates</th><th class="${ui.th} text-right">Weight</th></tr></thead><tbody>${rects
      .map(r => `<tr><td class="${ui.td}"><a href="#app=${esc(r.id)}">${esc(r.name)}</a></td><td class="${ui.td}">${esc(cat(r.node))}</td><td class="${ui.td} text-right">${n(r.events.length)}</td><td class="${ui.td} text-right">${r.v.toFixed(2)}</td></tr>`)
      .join('')}</tbody></table></details>`;
  const tip = el.querySelector('[data-tip]'), svg = el.querySelector('svg');
  const show = (g, ev) => {
    const r = rects[+g.dataset.k], t = top(r);
    tip.innerHTML = `<b class="block text-foreground">${esc(r.name)}</b><span class="block text-muted-foreground">${esc([P.sectors[r.j] && P.sectors[r.j].name, cat(r.node)].filter(Boolean).join(' · '))}</span><span class="mt-1 block">${n(r.events.length)} update${r.events.length > 1 ? 's' : ''} this week${t && t.title && t.title !== 'Release' ? `: ${esc(t.title)}` : ''}</span>`;
    const box = svg.getBoundingClientRect(), x = ev ? ev.clientX - box.left : (r.x / W) * box.width, y = ev ? ev.clientY - box.top : (r.y / H) * box.height;
    tip.style.left = `${Math.min(x + 12, box.width - 260)}px`; tip.style.top = `${y + 12}px`; tip.classList.remove('hidden');
  };
  svg.addEventListener('pointermove', e => { const g = e.target.closest('g[data-k]'); g ? show(g, e) : tip.classList.add('hidden'); });
  svg.addEventListener('pointerleave', () => tip.classList.add('hidden'));
  svg.addEventListener('focusin', e => { const g = e.target.closest('g[data-k]'); if (g) show(g); });
  svg.addEventListener('focusout', () => tip.classList.add('hidden'));
  const open = e => { const g = e.target.closest('g[data-k]'); if (g) location.hash = `#app=${rects[+g.dataset.k].id}`; };
  svg.addEventListener('click', open);
  svg.addEventListener('keydown', e => (e.key === 'Enter' || e.key === ' ') && (e.preventDefault(), open(e)));
}

export function mount(el) {
  if (!el) return;
  Promise.all([json('pulse.json'), json('taxonomy-index.json').catch(() => null)])
    .then(([P, T]) => draw(el, P, T))
    .catch(() => (el.innerHTML = `<p class="${ui.panelNote}">This week's map could not be loaded.</p>`));
}
