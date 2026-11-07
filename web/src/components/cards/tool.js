// spec: AS-105 AS-239 AS-256
import { S } from '../answer/model.js';
import { renderAll } from '../app.js';
import { byGrowth, lb, rowMap } from '../browse.js';
import { catalogCard } from './catalog.js';
import { dirCard, orgCard } from './directory.js';
import { IDX, hideTA, onMarket } from '../search/index.js';
import { $, sr } from '../../lib/dom.js';
import { MON, cn, esc, ic, n, pct, sgn, url } from '../../lib/format.js';
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
  const src = (u, l) =>
    u
      ? `<a class="src" href="${url(u)}" target="_blank" rel="noopener noreferrer" aria-label="${esc(l)}">${ic('out')}</a>`
      : '';
  const tile = (lab, big, sub, link = '') =>
    `<div class="tile"><p class="lab">${lab}</p><p class="big">${big}</p><p class="meta">${sub}${link}</p></div>`;
  const NO = '<span class="nobs">Not observed</span>',
    rel = row && row.gh.released ? `${+row.gh.released.slice(8, 10)} ${MON[+row.gh.released.slice(5, 7) - 1]}` : null;
  const tiles = row
    ? `<div class="tiles">
    ${tile('Downloads · 7 days', row.dl.value !== null ? cn(row.dl.value) : '—', row.dl.value !== null ? `${esc(row.dl.registry)} · ${pct(row.dl.delta) !== null ? pct(row.dl.delta) + ' on the week before' : 'no prior week'}${row.dl.vsBase != null ? ` · ${pct(row.dl.vsBase)} vs its 4-week level` : ''}` : NO, row.dl.value !== null ? src(row.dl.url, `${row.dl.registry} page for ${row.name}`) : '')}
    ${tile('Hacker News · 7 days', row.hn.value !== null ? n(row.hn.value) : '—', row.hn.value !== null ? `stories · ${sgn(row.hn.delta)} on the week before` : NO, row.hn.value !== null ? src(`https://hn.algolia.com/?q=${encodeURIComponent((row.hn.query || '').replace(/"/g, ''))}`, `Hacker News search for ${row.name}`) : '')}
    ${tile('GitHub stars', row.gh.stars != null ? cn(row.gh.stars) : '—', row.gh.stars != null ? `${esc((row.gh.url || '').replace(/^https:\/\/github\.com\//, ''))} · today’s count` : NO, row.gh.stars != null ? src(row.gh.url, `GitHub repository for ${row.name}`) : '')}
    ${tile('Last release', rel || '—', rel ? `${esc(row.gh.release)} · ${row.gh.released.slice(0, 4)}` : NO)}</div>`
    : `<p class="meta mt24">No public signals observed for ${esc(x.name)} yet.</p>`;
  const chart =
    peers.length > 1
      ? `<h3 class="h2 mt48">Where ${esc(x.name)} sits in ${esc(x.laneName)}</h3><p class="meta">Weekly registry downloads against each tool’s own 4-week level. Bars share one scale, the largest change shown.</p>${lb(peers, { cur: x.id, lane: false })}`
      : '';
  const facts = P
    ? pview({ id: x.id, name: x.name }, x.id, () => renderAll())
    : MK
      ? `<p class="meta">No verified facts yet for ${esc(x.name)}. It is on the watch list; the public signals above are all we have.</p>`
      : MKERR
        ? '<p class="meta">Verified facts could not be loaded. Check your connection and reload.</p>'
        : '<p class="meta">Loading verified facts…</p>';
  const coverage = [
    row ? '<li class="cv2 on">Market signals · current snapshot</li>' : '',
    P ? `<li class="cv2 on">Own-page facts · ${P.facts} quotes found</li>` : '',
  ].filter(Boolean).join('');
  const covered = coverage ? `<ul class="cover" aria-label="Available AirStack coverage for ${esc(x.name)}">${coverage}</ul>` : '';
  $('#toolcard').hidden = false;
  $('#toolcard').innerHTML =
    `${covered}${tiles}${PROF ? guideView(x) : ''}${chart}<h3 class="h2 mt48">What its own pages say</h3>${facts}${PROF ? modelsView(x) : ''}`;
  if (!MK && !MKERR) onMarket(() => renderAll());
}
export function notFound(name) {
  S.tool = null;
  S.app = null;
  if (/#app=/.test(location.hash)) history.replaceState(null, '', location.pathname + location.search);
  renderAll(); /* no unrelated answer stays on screen */
  hideTA();
  $('#nf').hidden = false;
  $('#nfText').textContent =
    `We don’t track “${name.slice(0, 40)}” yet. Browse the categories below, or save it and we’ll know you asked.`;
  const b = $('#save');
  b.disabled = false;
  b.textContent = 'Save on this device';
  b.onclick = () => {
    let l = [];
    try {
      l = JSON.parse(localStorage.getItem('airstack.saved') || '[]');
    } catch (e) {}
    if (!l.includes(name)) l.push(name);
    try {
      localStorage.setItem('airstack.saved', JSON.stringify(l));
    } catch (e) {}
    b.disabled = true;
    b.textContent = 'Saved on this device';
    sr(name + ' saved on this device');
  };
}
