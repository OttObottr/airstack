// spec: AS-256 AS-350
import { MV, drawMovers } from './movers.js';
import { M } from '../lib/data.js';
import { $, reduce } from '../lib/dom.js';
import { esc, fd } from '../lib/format.js';

/* the top rows ship in site-data.js: complete at first paint */
function renderBrief() {
  /* written by Muse Wonder from the figures on this page; published only after code checked every number */
  const B = M.brief;
  if (!B || !B.items || !B.items.length) return;
  const nameOf = id => (M.index.find(r => r[0] === id) || [])[1] || id;
  $('#briefSub').textContent =
    `Written by Muse Wonder on ${fd(B.date)} from the figures on this page. Before it was published, code checked every number against the figure it cites.`;
  $('#briefHead').textContent = B.headline;
  $('#briefItems').innerHTML = B.items
    .map(it => {
      const tools = [...new Set(it.cites.map(c => B.facts[c] && B.facts[c].tool).filter(Boolean))];
      return `<li>${esc(it.text)}${tools.length ? `<span class="cites">${tools.map(t => `<a class="ext" href="#app=${esc(t)}">${esc(nameOf(t))}</a>`).join('')}</span>` : ''}</li>`;
    })
    .join('');
  $('#brief').hidden = false;
}

export function mount() {
  renderBrief();
  addEventListener('hashchange', () => {
    /* a pasted #tool=… link, or back/forward, restores the open profile */
    const id = (/[#&]tool=([\w.-]+)/.exec(location.hash) || [])[1] || null;
    if (id !== MV.open) {
      MV.open = id;
      drawMovers();
      if (id) {
        const r = $('.prow');
        if (r) r.scrollIntoView({ block: 'center', behavior: reduce ? 'auto' : 'smooth' });
      }
    }
  });
}
