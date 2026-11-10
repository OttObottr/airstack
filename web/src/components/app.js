import { TITLE, show } from '../lib/router.js';
import { S } from '../lib/state.js';
import { mono } from './avatar.js';
import { drawBrowse } from './browse.js';
import { renderToolCard } from './cards/tool.js';
import { byName, hideTA, q } from './search/index.js';
import { addr } from './search/directory.js';
import { $, reduce } from '../lib/dom.js';
import { send } from '../lib/beacon.js';

export function selectTool(x, o = {}) {
  show('overview', { scroll: false });
  S.tool = x;
  send('product', { id: x.id });
  q.value = '';
  hideTA();
  $('#nf').hidden = true;
  if (o.push !== false) history.replaceState(null, '', `#app=${addr(x)}`);
  document.title = `${x.name} · ${TITLE}`;
  renderAll();
  $('#picked').scrollIntoView({ block: 'nearest', behavior: reduce ? 'auto' : 'smooth' });
}
export const selectByName = nm => {
  const x = byName(nm);
  if (x) selectTool(x);
};
export function clearTool() {
  S.tool = null;
  document.title = TITLE;
  if (/#app=/.test(location.hash)) history.replaceState(null, '', location.pathname + location.search);
  renderAll();
  q.focus();
}
export function renderAll() {
  const x = S.tool;
  $('#browse').hidden = !!x;
  $('#picked').hidden = !x;
  $('#toolcard').hidden = !x;
  if (!x) {
    drawBrowse();
    return;
  }
  $('#pickedName').textContent = x.name;
  $('#cmpThis').dataset.compare = x.id;
  $('#pickedLane').textContent = x.laneName;
  $('#pickedMono').innerHTML = mono(x, 's44');
  renderToolCard(x);
}
