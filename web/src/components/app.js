// spec: AS-104 AS-256 AS-343 AS-346 AS-366
import { show } from '../lib/router.js';
import { chipsUp, renderAnswer } from './answer/answer.js';
import { S } from './answer/model.js';
import { mono } from './avatar.js';
import { drawBrowse } from './browse.js';
import { renderToolCard } from './cards/tool.js';
import { byName, hideTA, onMarket, q } from './search/index.js';
import { addr } from './search/directory.js';
import { $, reduce } from '../lib/dom.js';
import { MK, MKERR } from '../lib/market.js';

export function selectTool(x, o = {}) {
  show('overview', { scroll: false }); /* a product always opens in Overview, whichever view picked it */
  S.tool = x;
  S.app = x.assess ? x.name : null;
  S.needs = new Set();
  S.assumed = true;
  S.device = null;
  S.use = 'Online';
  S.to = null;
  S.side = 'Current';
  {
    const h = new URLSearchParams(
      location.hash.slice(1)
    ); /* a shared answer: restore its scenario, and only for the same tool */
    if (x.assess && h.get('app') === x.id && h.get('plan')) {
      S.plan = h.get('plan');
      S.use = h.get('use') === 'in-person' ? 'In person' : 'Online';
      S.device = h.get('device') || null;
      S.needs = new Set((h.get('needs') || '').split(',').filter(Boolean).slice(0, 12));
      S.to = h.get('to') || null;
      S.side = h.get('side') === 'proposed' ? 'Proposed' : 'Current';
      S.assumed = false;
    }
  }
  q.value = '';
  hideTA();
  $('#nf').hidden = true;
  if (o.push !== false) history.replaceState(null, '', `#app=${addr(x)}`);
  document.title = `${x.name} · AirStack — See the software market move.`; /* the tab and a shared link name the product */
  renderAll();
  $('#picked').scrollIntoView({ block: 'nearest', behavior: reduce ? 'auto' : 'smooth' });
}
export const selectByName = nm => {
  const x = byName(nm);
  if (x) selectTool(x);
};
export function clearTool() {
  S.tool = null;
  S.app = null;
  if (/#app=/.test(location.hash)) history.replaceState(null, '', location.pathname + location.search);
  renderAll();
  q.focus();
}
export function renderAll() {
  const x = S.tool,
    as = !!(x && x.assess);
  document.body.classList.toggle(
    'tool-focus',
    !!x && x.lane !== 'meeting-notes'
  ); /* a tool's page shows that tool: the meeting-notes worked example belongs to the landing page and the meeting-notes tools */
  $('#strip').hidden = true; /* renderAnswer shows it again; no tool, no strip */
  $('#browse').hidden = !!x;
  $('#picked').hidden = !x;
  $('#bench').hidden = !x;
  $('#qs').hidden = !as;
  $('#setup').hidden = !as;
  $('#bench').classList.toggle('solo', !as);
  if (!x) {
    drawBrowse();
    return;
  }
  $('#pickedName').textContent = x.name;
  $('#cmpThis').dataset.compare = x.id;
  $('#cmpThis').hidden = as; /* an answer has its own Compare button */
  $('#pickedLane').textContent = x.laneName;
  $('#pickedMono').innerHTML = mono(x, 's44');
  if (as) {
    if (!MK) {
      $('#toolcard').hidden = true;
      $('#answer').hidden = false;
      $('#answer').innerHTML = MKERR
        ? '<p class="areason">The checks could not be loaded. Check your connection and reload.</p>'
        : '<p class="meta">Loading the checks…</p>';
      if (!MKERR) onMarket(renderAll);
      return;
    }
    $('#toolcard').hidden = true;
    chipsUp();
    renderAnswer();
  } else {
    $('#answer').hidden = true;
    $('#profile').hidden = true;
    renderToolCard(x);
  }
}
