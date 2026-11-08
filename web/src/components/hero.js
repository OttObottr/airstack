import { COUNTS, M } from '../lib/data.js';
import { $ } from '../lib/dom.js';
import { esc, fd, n, pct } from '../lib/format.js';

/* `only`: ids to show; returns false when none of them has a figure */
export function drawTape(only, all) {
  const rows = (all || (M.moversTop && M.moversTop.rows) || [])
    .filter(r => r.dl && r.dl.vsBase != null && (!only || only.has(r.id)))
    .sort((a, b) => b.dl.vsBase - a.dl.vsBase);
  const shown =
    rows.length > 30 && !only
      ? [...rows.slice(0, 15), ...rows.slice(-15)]
      : rows;
  const item = r =>
    `<a href="#app=${esc(r.id)}"><b>${esc(r.name)}</b><span class="${r.dl.vsBase < 0 ? 'dn' : 'up'}">${r.dl.vsBase < 0 ? '▼' : '▲'} ${pct(r.dl.vsBase)}</span></a>`;
  const as = `<span class="as">${only ? 'your tools · ' : ''}4-week momentum · registry downloads · ${fd(M.moversTop.fetched || M.meta.checked_at)}</span>`;
  if (rows.length) $('#tape').innerHTML = as + shown.map(item).join('') + as + shown.map(item).join('');
  else if (!only) $('#tapeW').hidden = true;
  return rows.length > 0;
}

export function mount() {
  drawTape();
  /* the same text tools/assemble.sh writes into the page, so nothing moves */
  $('#honest').textContent =
    `Scope: ${n(COUNTS.researched_products)} researched products · every fact quoted from its own page\nAs of ${fd(M.meta.checked_at)}`;
}
