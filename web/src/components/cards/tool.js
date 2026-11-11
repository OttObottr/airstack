import { S } from '../../lib/state.js';
import { renderAll } from '../app.js';
import { byGrowth, lb, rowMap } from '../browse.js';
import { catalogCard } from './catalog.js';
import { dirCard, orgCard } from './directory.js';
import { IDX, hideTA, onMarket } from '../search/index.js';
import { PARAMS } from '../../lib/data.js';
import { $ } from '../../lib/dom.js';
import { esc } from '../../lib/format.js';
import { strip } from '../signals.js';
import { MK, MKERR } from '../../lib/market.js';
import { PROF, pview } from '../../lib/profiles.js';
import { guideView, modelsView } from './guide.js';

export function renderToolCard(x) {
  if (x.dir) return dirCard(x);
  if (x.org) return orgCard(x);
  if (x.cat) return catalogCard(x);
  const R = rowMap(),
    row = R[x.id],
    P = MK && MK.profiles && MK.profiles[x.id],
    peers = IDX.filter(p => p.lane === x.lane).sort(byGrowth(R));
  const tiles = strip(x) || `<p class="meta mt-6">No public signals observed for ${esc(x.name)} yet.</p>`;
  const chart =
    peers.length > 1
      ? `<h3 class="h-section mt-12">Where ${esc(x.name)} sits in ${esc(x.laneName)}</h3><p class="meta">Weekly registry downloads against each tool’s own ${PARAMS.movers.base_weeks}-week level. Bars share one scale, the largest change shown.</p>${lb(peers, { cur: x.id, lane: false })}`
      : '';
  const facts = P
    ? pview({ id: x.id, name: x.name }, x.id, () => renderAll())
    : MK
      ? `<p class="meta">No facts yet for ${esc(x.name)}.</p>`
      : MKERR
        ? '<p class="load-error">Facts could not be loaded. Check your connection and reload.</p>'
        : '<div class="skeleton skeleton-profile" role="status" aria-label="Loading facts"></div>';
  const coverage = [
    row ? '<li class="cv2 on">Market signals · current snapshot</li>' : '',
    P ? `<li class="cv2 on">${P.facts} sourced facts</li>` : '',
  ].filter(Boolean).join('');
  const covered = coverage ? `<ul class="cover" aria-label="Available AirStack coverage for ${esc(x.name)}">${coverage}</ul>` : '';
  $('#toolcard').innerHTML =
    `${covered}${tiles}${PROF ? guideView(x) : ''}${chart}<h3 class="h-section mt-12">What its own pages say</h3>${facts}${PROF ? modelsView(x) : ''}`;
  if (!MK && !MKERR) onMarket(() => renderAll());
}
export function notFound(name) {
  S.tool = null;
  if (/#app=/.test(location.hash)) history.replaceState(null, '', location.pathname + location.search);
  renderAll();
  hideTA();
  $('#nf').hidden = false;
  $('#nfText').textContent =
    `We don’t track “${name.slice(0, 40)}” yet. Browse the categories below.`;
}
