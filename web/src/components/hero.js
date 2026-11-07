// spec: AS-100 AS-256 AS-341 AS-D03
import { LIVE, M } from '../lib/data.js';
import { $ } from '../lib/dom.js';
import { esc, fd, n } from '../lib/format.js';

/* the tape: momentum against each tool's own 4-week level, dated. `only`: a set of ids, to show just those tools, picked from `all` (every tool with a figure; the first screen's few when not given); false when none of them has a figure */
export function drawTape(only, all) {
  const pc = x => `${x > 0 ? '+' : ''}${x.toFixed(1)}%`;
  const rows = (all || (M.moversTop && M.moversTop.rows) || [])
    .filter(r => r.dl && r.dl.vsBase != null && (!only || only.has(r.id)))
    .sort((a, b) => b.dl.vsBase - a.dl.vsBase);
  const shown =
    rows.length > 30 && !only
      ? [...rows.slice(0, 15), ...rows.slice(-15)]
      : rows; /* the biggest risers and fallers: a ticker, not a table (Markets has every tool) */
  const item = r =>
    `<a href="#app=${esc(r.id)}"><b>${esc(r.name)}</b><span class="${r.dl.vsBase < 0 ? 'dn' : 'up'}">${r.dl.vsBase < 0 ? '▼' : '▲'} ${pc(r.dl.vsBase)}</span></a>`;
  const as = `<span class="as">${only ? 'your tools · ' : ''}4-week momentum · registry downloads · ${fd(M.moversTop.fetched || M.meta.checked_at)}</span>`;
  if (rows.length) $('#tape').innerHTML = as + shown.map(item).join('') + as + shown.map(item).join('');
  else if (!only) $('#tapeW').hidden = true;
  return rows.length > 0;
}

export function mount() {
  drawTape();
  /* the proof line's number is from the first data file, so the market file can wait; tools/assemble.sh writes the same text into the page */
  $('#honest').textContent =
    `Scope: ${n((M.dir || {}).researched || 0)} researched products · every fact quoted from its own page\nAs of ${fd(M.meta.checked_at)} · ${LIVE ? 'researched with Muse Spark' : 'verified from stored evidence'}`;
  $('#built').textContent = LIVE ? 'Built with Muse Spark' : 'Built for Muse Spark';
}
