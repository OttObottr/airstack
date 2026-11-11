import { TITLE, show } from '../lib/router.js';
import { S } from '../lib/state.js';
import { mono } from './avatar.js';
import { drawBrowse } from './browse.js';
import { renderToolCard } from './cards/tool.js';
import { hideTA, q } from './search/index.js';
import { addr } from './search/directory.js';
import { $, reduce } from '../lib/dom.js';
import { send } from '../lib/beacon.js';

addEventListener('click', e => {
  const a = e.target.closest('[data-sec]');
  if (!a) return;
  e.preventDefault(); /* the address keeps naming the product; the section scrolls into view */
  document.getElementById(a.dataset.sec)?.scrollIntoView({ block: 'start', behavior: reduce ? 'auto' : 'smooth' });
});
export function selectTool(x, o = {}) {
  show('product');
  S.tool = x;
  send('product', { id: x.id });
  q.value = '';
  hideTA();
  $('#nf').hidden = true;
  if (o.push !== false) history.replaceState(null, '', `#app=${addr(x)}`);
  document.title = `${x.name} · ${TITLE}`;
  renderAll();
}
export function clearTool() {
  S.tool = null;
  if (/#app=/.test(location.hash)) history.replaceState(null, '', location.pathname + location.search);
  show('overview');
  document.title = TITLE;
  renderAll();
  q.focus();
}
export function renderAll() {
  const x = S.tool;
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
  sections();
}
/* the product page's own contents list: one link per section the card rendered, so a long page is one tap from any part */
function sections() {
  const hs = [...$('#toolcard').querySelectorAll('h3.h-section')],
    nav = $('#pickedNav');
  hs.forEach((h, i) => (h.id ||= `sec${i}`));
  nav.hidden = hs.length < 2;
  nav.innerHTML = hs.map(h => `<a class="btn btn-ghost h-8 px-2.5 font-normal" href="#${h.id}" data-sec="${h.id}">${h.textContent}</a>`).join('');
}
