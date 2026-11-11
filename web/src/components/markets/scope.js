import { Method } from '../../ui/method.js';
import { M, json } from '../../lib/data.js';
import { esc, fd, n, url } from '../../lib/format.js';
import { ui } from '../../ui/recipes.js';
import { stack } from '../../lib/stack.js';

/* What every Markets panel shares: markets.json, the rows a scope stands for, and the markup pieces the panels repeat.
   scope: { kind: 'all' | 'node' | 'stack' | 'maker', id?, ids? } (ui/panel.js) */
export const load = () => json('markets.json');
const place = () => json('taxonomy-index.json').then(t => t.products);
const NAME = new Map(M.index.map(r => [r[0], r[1]]));
export const nameOf = (id, D) => NAME.get(id) || (stack().find(x => x.id === id) || {}).name || (D && (D.entrants.find(r => r[0] === id) || [])[1]) || id;

async function members(scope) {
  if (scope.ids) return scope.ids;
  if (scope.kind === 'stack') return stack().map(x => x.id);
  const m = (await json('makers.json')).makers[scope.id];
  return m ? m.products : [];
}

/* nodes: the scope's rows when it is the taxonomy (all: the sectors; a node: its narrower nodes, or itself when it has none), with
   the peer they are compared with; products: the scope's own products when it is a stack or a maker */
export async function rows(scope) {
  const D = await load(),
    N = D.nodes;
  const kids = id => Object.keys(N).filter(k => N[k].parent === id);
  if (scope.kind === 'all') return { D, nodes: kids(null), peer: { ...D.all, name: 'all sectors' } };
  if (scope.kind === 'node' && N[scope.id]) {
    const k = kids(scope.id);
    return { D, nodes: k.length ? k : [scope.id], peer: k.length ? N[scope.id] : N[N[scope.id].parent] || { ...D.all, name: 'all sectors' } };
  }
  const [ids, P] = await Promise.all([members(scope), place()]);
  return { D, products: ids.map(id => ({ id, name: nameOf(id, D), node: P[id] ? P[id][0][0] : null, rec: D.products[id] || null })) };
}

/* is product p's node `id` or under it */
export const under = (D, node, id) => {
  for (let x = node; x; x = D.nodes[x] && D.nodes[x].parent) if (x === id) return true;
  return false;
};

export const share = (a, b) => (b ? Math.round((100 * a) / b) : null);
export const peerName = peer => (peer.parent !== undefined ? `in ${peer.name}` : 'across all sectors');

/* a cell that reads "a of b" and its share, or Not observed when there is no base */
export const ofCell = (a, b) =>
  b
    ? `<span class="text-foreground">${n(a)}</span><span class="text-muted-foreground"> of ${n(b)}</span>`
    : '<span class="text-muted-foreground">Not observed</span>';

export const loading = el => {
  el.setAttribute('aria-busy', 'true');
  el.innerHTML = '<div class="h-40 rounded-md bg-muted animate-pulse" role="status" aria-label="Loading"></div>';
};

/* guards a slow render against a newer scope */
export const latest = el => {
  const t = (el._t = (el._t || 0) + 1);
  return () => el._t === t;
};

export const sourceLine = (text, file, read) =>
  Method(`${text} · <a class="underline underline-offset-2 hover:text-foreground" href="${url(new URL(file, location.href).href)}">${esc(file)}</a>${read ? `, read ${fd(read)}` : ''}`);

/* the comparisons the producer published for these rows, each read against its peer: `say` words one measure */
const RATE = { announced: ['announced', 'watched'], talked: ['talked', 'watched'], entrants: ['entrants', 'dated'] };
export const findings = (D, ids, peer, say, days) =>
  ids.flatMap(id => {
    const o = D.nodes[id];
    return o.shown
      .filter(m => say[m])
      .map(m => {
        const [a, b] = RATE[m],
          up = o[a] / o[b] > peer[a] / peer[b];
        return `<li class="flex items-start gap-2 text-sm leading-snug"><span class="${ui.badge.neutral}">${up ? 'Higher' : 'Lower'}</span><span><b class="font-medium text-foreground">${esc(o.name)}:</b> <span class="text-muted-foreground">${say[m](o, peer, days)}</span></span></li>`;
      });
  });
