// spec: AS-256 AS-283
import { mono } from './avatar.js';
import { byId, onMarket } from './search/index.js';
import { $ } from '../lib/dom.js';
import { esc, fd, n } from '../lib/format.js';
import { MK } from '../lib/market.js';
import { PRICES } from '../lib/profiles.js';
import { fromLink, replace, shareLink, stack, toggle, tracked } from '../lib/stack.js';
import { S } from './answer/model.js';

/* ---------- My stack on Overview: what AirStack knows about each tool you track, from the same data as its page ---------- */
let shared = null;
const pc = v => `${v > 0 ? '+' : ''}${v.toFixed(1)}%`;

function dossier(x) {
  /* each fact with its kind; nothing estimated */
  const out = [],
    profile = MK && MK.profiles && MK.profiles[x.id],
    movement = MK && MK.movers && MK.movers.rows.find(r => r.id === x.id),
    pricing = PRICES[x.id],
    item = byId(x.id);
  if (item && item.assess) out.push(['verdict', 'Renewal verdict available']);
  if (profile) out.push(['facts', `${n(profile.facts)} facts from its own pages`]);
  if (pricing && pricing.plans.length) out.push(['price', `List prices on its pricing page, read ${fd(pricing.checked)}`]);
  if (movement && movement.dl && movement.dl.vsBase != null)
    out.push([movement.dl.vsBase >= 0 ? 'up' : 'dn', `${pc(movement.dl.vsBase)} downloads against its own 4-week level`]);
  if (!out.length) out.push(['none', 'Listed, not researched yet']);
  return { x, facts: out, profile, movement, item };
}

function intelligence(rows) {
  const researched = rows.filter(r => r.profile).length,
    answered = rows.filter(r => r.item && r.item.assess).length,
    measured = rows
      .filter(r => r.movement && r.movement.dl && r.movement.dl.vsBase != null)
      .sort((a, b) => Math.abs(b.movement.dl.vsBase) - Math.abs(a.movement.dl.vsBase))[0],
    gap = rows.find(r => !r.profile) || rows.find(r => !(r.item && r.item.assess));
  const momentum = measured
    ? `<p class="stack-value ${measured.movement.dl.vsBase >= 0 ? 'up' : 'dn'}">${esc(measured.x.name)} · ${pc(measured.movement.dl.vsBase)}</p>
       <p class="meta">Downloads against its own 4-week level · measured ${fd(MK.movers.generated)}. Registry activity is not product usage.</p>`
    : '<p class="stack-value">No comparable signal</p><p class="meta">No tracked tool has a public registry trend against its own 4-week level.</p>';
  const review = gap
    ? `<p class="stack-value"><a href="#app=${esc(gap.x.id)}">${esc(gap.x.name)}</a></p>
       <p class="meta">${gap.profile ? 'Own-page research is recorded; open the record to check whether a renewal answer applies.' : 'Own-page research is not recorded yet.'}</p>`
    : '<p class="stack-value">Coverage complete</p><p class="meta">Every tracked tool has own-page research and a renewal answer. Compare them before the next review.</p>';
  return `<section class="stack-insight" aria-labelledby="stackMonitor"><p class="lab" id="stackMonitor">Monitoring</p>
      <p class="stack-value">${n(rows.length)} tracked locally</p><p class="meta">${n(researched)} researched · ${n(answered)} with a renewal answer. No account or server sync.</p></section>
    <section class="stack-insight" aria-labelledby="stackMomentum"><p class="lab" id="stackMomentum">Public momentum</p>${momentum}</section>
    <section class="stack-insight" aria-labelledby="stackReview"><p class="lab" id="stackReview">Review recommendation</p>${review}<p class="meta stack-caveat">Review order reflects evidence coverage, not product fit.</p></section>`;
}

function render() {
  const sec = $('#mystack');
  if (!sec) return;
  const list = shared || stack();
  sec.hidden = false;
  $('#stackHead').textContent = shared ? 'A shared software stack' : list.length ? 'My software stack' : 'Your software stack';
  $('#stackIntro').textContent =
    'Add the tools you pay for. This workspace shows renewal-answer coverage, own-page research, quoted prices and public momentum, and unlocks My stack filters for vendor updates and the calendar.';
  $('#stackList').hidden = !list.length;
  $('#stackNote').textContent = shared
    ? 'Opened from a link. Save it to this browser to make it yours; AirStack has no account or server copy.'
    : 'Device-local: saved in this browser only and never sent to AirStack. No account or server sync.';
  if (!list.length) {
    $('#stackSum').textContent = 'No tools added yet. Start with software your team already pays for.';
    $('#stackList').innerHTML = '';
    $('#stackIntel').hidden = true;
    $('#stackIntel').innerHTML = '';
    $('#stackActs').innerHTML = '<button class="cta" id="stackAdd" type="button">Add your first tool</button>';
    return;
  }
  const rows = list.map(dossier);
  const count = k => rows.filter(r => r.facts.some(([c]) => c === k)).length;
  $('#stackSum').textContent =
    `Scope: ${n(list.length)} tool${list.length === 1 ? '' : 's'} · Coverage: ${count('verdict')} with a renewal answer · ${count('facts')} researched · ${count('up')} rising · ${count('none')} not researched yet`;
  $('#stackList').innerHTML = rows
    .map(
      ({ x, facts }) => `<li><a class="who" href="#app=${esc(x.id)}">${mono(x, 's20')}<b>${esc(x.name)}</b></a>
      <span class="sfacts">${facts.map(([k, t]) => `<span class="sf ${k}">${esc(t)}</span>`).join('')}</span>
      ${shared ? '' : `<button class="lk srm" type="button" data-unstack="${esc(x.id)}" aria-label="Stop tracking ${esc(x.name)}">Remove</button>`}</li>`
    )
    .join('');
  $('#stackIntel').hidden = false;
  $('#stackIntel').innerHTML = intelligence(rows);
  const compare =
    list.length > 1
      ? `<a class="ghost" href="#compare=${esc(list
          .slice(0, 5)
          .map(x => x.id)
          .join(','))}">Compare ${Math.min(5, list.length)} stack tools</a>`
      : '';
  $('#stackActs').innerHTML = shared
    ? `<button class="ghost" type="button" id="stackSave">Save on this device</button>${compare}<button class="lk" type="button" id="stackDrop">Close</button>`
    : `<button class="ghost" type="button" id="stackAdd">Add another tool</button>${compare}<button class="ghost" type="button" id="stackShare">Copy a link to this stack</button>`;
}

function star() {
  /* the Track button beside the open product */
  const b = $('#starBtn');
  if (!b) return;
  const x = S.tool;
  b.hidden = !x;
  if (!x) return;
  const on = tracked(x.id);
  b.setAttribute('aria-pressed', String(on));
  b.textContent = on ? '★ In my stack' : '＋ Add to my stack';
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
  document.addEventListener('click', async e => {
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
      const b = e.target.closest('#stackShare');
      try {
        await navigator.clipboard.writeText(shareLink(stack()));
        b.textContent = 'Link copied';
      } catch {
        b.textContent = 'Copy failed';
      }
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
