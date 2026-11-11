import { mono } from './avatar.js';
import { onMarket } from './search/index.js';
import { $, copy } from '../lib/dom.js';
import { LISTED, esc, fd, n, pct } from '../lib/format.js';
import { PARAMS } from '../lib/data.js';
import { MK } from '../lib/market.js';
import { PRICES } from '../lib/profiles.js';
import { fromLink, replace, shareLink, stack, toggle, tracked } from '../lib/stack.js';
import { S } from '../lib/state.js';
import { mount as mountPanel } from '../ui/panel.js';
import { ui } from '../ui/recipes.js';
import { stackPanel } from './changes.js';

let shared = null,
  changes = null;
/* each fact about a row as a badge: one height, its text centred, every badge on one centre line */
const BADGE = { facts: ui.badge.neutral, price: ui.badge.neutral, up: ui.badge.up, dn: ui.badge.down, none: ui.badge.neutral };

function dossier(x) {
  const out = [],
    profile = MK && MK.profiles && MK.profiles[x.id],
    movement = MK && MK.movers && MK.movers.rows.find(r => r.id === x.id),
    pricing = PRICES[x.id];
  if (profile) out.push(['facts', `${n(profile.facts)} facts from its own pages`]);
  if (pricing && pricing.plans.length) out.push(['price', `List prices on its pricing page, read ${fd(pricing.checked)}`]);
  if (movement && movement.dl && movement.dl.vsBase != null)
    out.push([movement.dl.vsBase >= 0 ? 'up' : 'dn', `${pct(movement.dl.vsBase)} downloads against its own ${PARAMS.movers.base_weeks}-week level`]);
  if (!out.length) out.push(['none', LISTED]);
  return { x, facts: out, profile, movement };
}

function intelligence(rows) {
  const researched = rows.filter(r => r.profile).length,
    gap = rows.find(r => !r.profile);
  const review = gap
    ? `<p class="stack-value"><a href="#app=${esc(gap.x.id)}">${esc(gap.x.name)}</a></p>
       <p class="meta">Own-page research is not recorded yet.</p>`
    : '<p class="stack-value">Coverage complete</p><p class="meta">Every tracked tool has own-page research. Compare them before the next review.</p>';
  return `<section class="stack-insight" aria-labelledby="stackMonitor"><p class="eyebrow" id="stackMonitor">Monitoring</p>
      <p class="stack-value">${n(rows.length)} in your stack</p><p class="meta">${n(researched)} researched on their own pages.</p></section>
    <section class="stack-insight" aria-labelledby="stackReview"><p class="eyebrow" id="stackReview">Next to research</p>${review}<p class="meta stack-caveat">Review order reflects evidence coverage, not product fit.</p></section>`;
}

function render() {
  const sec = $('#mystack');
  if (!sec) return;
  const list = shared || stack();
  sec.hidden = false;
  $('#stackHead').textContent = shared ? 'A shared software stack' : list.length ? 'Your software stack' : 'Build a software stack';
  $('#stackList').hidden = !list.length;
  $('#stackNote').textContent = shared ? 'Opened from a link. Save it to make it yours.' : 'Saved in this browser only. No account.';
  if (!list.length) {
    $('#stackSum').textContent = 'Start with software you already use.';
    $('#stackList').innerHTML = '';
    $('#stackIntel').hidden = true;
    $('#stackIntel').innerHTML = '';
    $('#stackChangesW').hidden = true;
    $('#stackActs').innerHTML = '<button class="btn btn-primary" id="stackAdd" type="button">Add software</button>';
    return;
  }
  const rows = list.map(dossier);
  const count = k => rows.filter(r => r.facts.some(([c]) => c === k)).length;
  $('#stackSum').textContent =
    `Scope: ${n(list.length)} tool${list.length === 1 ? '' : 's'} · Coverage: ${count('facts')} researched · ${count('up')} rising · ${count('none')} not researched yet`;
  $('#stackList').innerHTML = rows
    .map(
      ({ x, facts }) => `<li><a class="who" href="#app=${esc(x.id)}">${mono(x, 's20')}<b>${esc(x.name)}</b></a>
      <span class="flex flex-wrap items-center gap-2 max-[699px]:col-span-full">${facts.map(([k, t]) => `<span class="${BADGE[k]}">${esc(t)}</span>`).join('')}</span>
      ${shared ? '' : `<button class="lk srm" type="button" data-unstack="${esc(x.id)}" aria-label="Stop tracking ${esc(x.name)}">Remove</button>`}</li>`
    )
    .join('');
  $('#stackIntel').hidden = false;
  $('#stackIntel').innerHTML = intelligence(rows);
  const scope = { kind: 'stack', ids: list.map(x => x.id) };
  $('#stackChangesW').hidden = false;
  if (!changes) changes = mountPanel($('#stackChanges'), stackPanel, scope);
  else changes.update(scope);
  const compare =
    list.length > 1
      ? `<a class="btn btn-secondary" href="#compare=${esc(list
          .slice(0, 5)
          .map(x => x.id)
          .join(','))}">Compare ${Math.min(5, list.length)} stack tools</a>`
      : '';
  $('#stackActs').innerHTML = shared
    ? `<button class="btn btn-secondary" type="button" id="stackSave">Save on this device</button>${compare}<button class="lk" type="button" id="stackDrop">Close</button>`
    : `<button class="btn btn-secondary" type="button" id="stackAdd">Add software</button>${compare}<button class="btn btn-secondary" type="button" id="stackShare">Copy a share link</button>`;
}

function star() {
  const b = $('#starBtn');
  if (!b) return;
  const x = S.tool;
  b.hidden = !x;
  if (!x) return;
  const on = tracked(x.id);
  b.setAttribute('aria-pressed', String(on));
  b.textContent = on ? '✓ In your stack · Remove' : '+ Add to your stack';
}

export function mount() {
  shared = fromLink(location.hash);
  addEventListener('hashchange', () => {
    const s = fromLink(location.hash);
    if (s) {
      shared = s;
      render();
    }
  });
  addEventListener('airstack:stack', () => {
    render();
    star();
  });
  document.addEventListener('click', e => {
    if (e.target.closest('#stackStart')) {
      $('#mystack').scrollIntoView({ block: 'start' });
      return;
    }
    if (e.target.closest('#stackAdd')) {
      if (!$('#picked').hidden) $('#change').click();
      $('#check').scrollIntoView({ block: 'start' });
      requestAnimationFrame(() => $('#q').focus({ preventScroll: true }));
      return;
    }
    if (e.target.closest('#starBtn') && S.tool) {
      toggle({ id: S.tool.id, name: S.tool.name });
      return;
    }
    const rm = e.target.closest('[data-unstack]');
    if (rm) {
      toggle({ id: rm.dataset.unstack });
      return;
    }
    if (e.target.closest('#stackShare')) {
      copy(e.target.closest('#stackShare'), shareLink(stack()), { ok: 'Link copied' });
      return;
    }
    if (e.target.closest('#stackSave')) {
      replace(shared);
      shared = null;
      history.replaceState(null, '', location.pathname);
      render();
      return;
    }
    if (e.target.closest('#stackDrop')) {
      shared = null;
      history.replaceState(null, '', location.pathname);
      render();
    }
  });
  new MutationObserver(star).observe($('#pickedName'), { childList: true, characterData: true, subtree: true });
  onMarket(render); /* the facts behind each row arrive with the market data */
  render();
  star();
}
