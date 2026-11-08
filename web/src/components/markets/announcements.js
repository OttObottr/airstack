import { ui } from '../../ui/recipes.js';
import { esc, fd, n } from '../../lib/format.js';
import { findings, latest, loading, peerName, rows, share, sourceLine } from './scope.js';

/* Who announced something, and who was talked about: vendors' own channels and Hacker News, per node, with the comparisons
   the producer published (each node against its parent, a sector against all sectors) */
const MEASURE = {
  announced: (o, p, days) =>
    `${n(o.announced)} of ${n(o.watched)} watched products announced something in ${days} days (${share(o.announced, o.watched)}%), against ${share(p.announced, p.watched)}% ${peerName(p)} (${n(p.announced)} of ${n(p.watched)}).`,
  talked: (o, p, days) =>
    `Hacker News stories in ${days} days linked to ${n(o.talked)} of ${n(o.watched)} watched products (${share(o.talked, o.watched)}%), against ${share(p.talked, p.watched)}% ${peerName(p)} (${n(p.talked)} of ${n(p.watched)}).`,
};

export const panel = {
  id: 'announcements',
  title: 'Announcements and conversation',
  note: 'Products that posted to their own feed, changelog or releases, and products a Hacker News story linked to. Recorded days, not a weekly trend.',
  async render(scope, el) {
    const fresh = latest(el);
    el.className = 'flex flex-col gap-3 min-w-0';
    loading(el);
    const R = await rows(scope);
    if (!fresh()) return;
    const D = R.D,
      days = Math.round((Date.parse(D.window[1]) - Date.parse(D.window[0])) / 864e5);
    el.removeAttribute('aria-busy');
    const src = sourceLine(
      `Feeds read ${fd(D.window[1])}, ${fd(D.window[0])} to ${fd(D.window[1])}; feeds keep only their latest posts, so at most a few per product and kind are counted. ${D.source.rule}`,
      'events.json'
    );
    if (R.products) {
      const w = R.products.filter(p => p.rec && p.rec[3]),
        a = w.filter(p => p.rec[0]).length;
      el.innerHTML = `<p class="text-sm">${w.length ? `${n(a)} of ${n(w.length)} watched products here announced something in ${days} days.` : 'None of these products is watched for announcements.'} <span class="text-muted-foreground">${n(R.products.length - w.length)} not watched: unknown, not zero.</span></p>${src}`;
      return;
    }
    const unwatched = R.nodes.filter(id => !D.nodes[id].watched).map(id => D.nodes[id].name);
    const f = findings(D, R.nodes, R.peer, MEASURE, days);
    el.innerHTML = `${f.length ? `<ul class="flex flex-col gap-3">${f.join('')}</ul>` : `<p class="${ui.panelNote}">No difference here clears the rule below. Each row's counts are in Sectors.</p>`}
      ${unwatched.length ? `<p class="${ui.panelNote}">No watched products in ${esc(unwatched.join(', '))}: announcements there are unknown.</p>` : ''}
      ${src}`;
  },
};
