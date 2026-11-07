// spec: AS-140 AS-233 AS-256 AS-346 AS-366 AS-D01
import { here } from '../lib/router.js';
import { addr } from './search/directory.js';
import { S } from './answer/model.js';
import { $, reduce } from '../lib/dom.js';
import { esc, fd, ic, n, url } from '../lib/format.js';

/* ---------- the evidence chain: source -> retrieved -> extracted -> verified by code -> re-checked -> who else says it ---------- */
let CH = null,
  chainOpener = null,
  cmp = null;
/* the comparison is code and a section nobody needs until they ask: it loads when a compare button is used or the address names one */
const withCompare = f => (cmp ? Promise.resolve(cmp) : import('./compare.js').then(m => (cmp = m))).then(f);
const CMP = /[#&]compare=|^#\/compare/; /* the comparison's addresses */
export const METRIC = {
  what_it_does: 'What it does',
  open_source: 'Open source',
  license: 'License',
  deployment: 'Deployment',
  platforms: 'Platforms',
  sdk_languages: 'SDK languages',
  models_supported: 'Models supported',
  integrations: 'Integrations',
  integrations_count: 'Integrations stated',
  compliance: 'Compliance',
  free_plan: 'Free plan',
  plan_names: 'Plans',
  pricing_basis: 'Pricing basis',
  customers_claimed: 'Customers (their claim)',
  founded_year: 'Founded',
  joins_meeting_apps: 'Joins',
  devices: 'Devices',
  languages_count: 'Languages',
  bot_free: 'Bot-free',
  in_person_capture: 'In-person capture',
  store_users: 'Store users',
  store_rating: 'Store rating',
  notes_plans: 'Plans with notes',
  in_person_terms: 'In-person terms',
};
export const STR = new Set(['what_it_does', 'license', 'pricing_basis', 'customers_claimed', 'in_person_terms']);
/* their value IS the quote: show it once */
export const showVal = v =>
  Array.isArray(v)
    ? v.join(', ')
    : v === true
      ? 'Yes'
      : v === false
        ? 'No'
        : typeof v === 'number'
          ? n(v)
          : v && typeof v === 'object'
            ? `${v.rating}${v.count ? ` (${v.count})` : ''}`
            : String(v);
export async function chainData() {
  if (!CH) {
    const r = await fetch('chain-data.json');
    if (!r.ok) throw new Error(r.status);
    CH = await r.json();
  }
  return CH;
}
export async function openChain(id, opener) {
  chainOpener = opener || chainOpener;
  const sec = $('#chainSec');
  sec.hidden = false;
  $('#chainSub').textContent = 'Loading the chain…';
  $('#chainTbl tbody').innerHTML = '';
  $('#chainSum').textContent = '';
  $('#chainNote').textContent = '';
  if (location.hash !== `#chain=${id}`) history.replaceState(null, '', `#chain=${id}`);
  sec.scrollIntoView({ block: 'start', behavior: reduce ? 'auto' : 'smooth' });
  $('#chainT').focus({ preventScroll: true });
  let D, E;
  try {
    D = await chainData();
    E = D.entities[id];
  } catch (e) {
    $('#chainSub').textContent =
      'The evidence chain needs a connection: it is loaded on demand and isn’t available offline until it has been opened once.';
    return;
  }
  if (!E) {
    $('#chainSub').textContent = 'No verified facts are recorded for this tool yet.';
    return;
  }
  const F = E.facts,
    n = F.length,
    ver = F.filter(f => f.verified).length,
    rc = F.filter(f => f.recheck),
    un = rc.filter(f => f.recheck.outcome === 'unchanged' || f.recheck.outcome === 'changed_quotes_present').length;
  const pages = new Set(F.map(f => f.url)).size,
    indep = new Set(F.flatMap(f => f.agree_independent)).size,
    multi = F.filter(f => f.agree.length).length;
  $('#chainT').textContent = `Evidence chain · ${E.name}`;
  $('#chainSub').textContent =
    `${n} facts from ${pages} pages, each with the path it took from the page to this screen`;
  $('#chainSum').textContent =
    `${ver} of ${n} verified on their pages by code · ${rc.length} re-checked live (${un} still supported) · ${multi} stated on more than one page · independent sources: ${indep || 'none yet'}`;
  const cls = c => D.classes[c] || c;
  $('#chainTbl tbody').innerHTML = F.slice()
    .sort((a, b) => (a.metric > b.metric) - (a.metric < b.metric) || (a.host > b.host) - (a.host < b.host))
    .map(
      f => `<tr>
    <td data-l="Fact"><b>${esc(METRIC[f.metric] || f.metric)}</b>${STR.has(f.metric) ? '' : ' ' + esc(showVal(f.value))}<div class="meta">“${esc(f.quote)}”</div></td>
    <td data-l="Source"><a class="ext" href="${url(f.url)}" target="_blank" rel="noopener noreferrer">${esc(f.host)}${ic('out')}</a><div class="meta">${esc(cls(f.class))}</div></td>
    <td data-l="Retrieved" class="num">${fd(f.retrieved)}<div class="meta">HTTP ${f.status || '?'} · <span class="mono">${esc(f.hash.slice(0, 8))}</span></div></td>
    <td data-l="Extracted" class="num">${fd(f.extracted)}</td>
    <td data-l="Verified">${f.verified ? `${ic('check')} quote found on the page<div class="meta num">${fd(f.verified)}</div>` : '<span class="nobs">Not verified</span>'}</td>
    <td data-l="Re-checked">${f.recheck ? `${fd(f.recheck.at)}<div class="meta">${esc(f.recheck.note)}</div>` : '<span class="nobs">Not re-checked yet</span>'}</td>
    <td data-l="Also on">${f.agree.length ? `${f.agree.length} other page${f.agree.length > 1 ? 's' : ''}: ${esc(f.agree.join(', '))}` : '<span class="nobs">Only this page</span>'}${f.agree_independent.length ? `<div class="meta">Independent: ${esc(f.agree_independent.join(', '))}</div>` : ''}</td></tr>`
    )
    .join('');
  $('#chainNote').textContent = indep
    ? 'Some facts are also stated by independent sources, listed per fact.'
    : 'Every source here is the vendor’s own site, a store listing it controls, or the platform maker’s own documentation. None is an independent party, so these are vendor-origin claims that code has confirmed the pages really make.';
}
function closeChain() {
  $('#chainSec').hidden = true;
  if (/#chain=/.test(location.hash)) history.replaceState(null, '', S.tool ? `#app=${addr(S.tool)}` : here());
  if (chainOpener) {
    chainOpener.focus();
    chainOpener = null;
  }
}

export function mount() {
  for (const ev of ['pointerover', 'focusin'])
    document.addEventListener(
      ev,
      e => {
        if (!CH && e.target.closest && e.target.closest('[data-chain]')) chainData().catch(() => {});
      },
      { passive: true }
    );
  document.addEventListener('click', e => {
    const b = e.target.closest('[data-chain]');
    if (b) {
      openChain(b.dataset.chain, b);
      return;
    }
    if (e.target.closest('#chainX')) closeChain();
    const c = e.target.closest('[data-compare]');
    if (c) withCompare(m => m.openCompare([c.dataset.compare], c));
  });
  addEventListener('keydown', e => {
    if (e.key === 'Escape' && !$('#chainSec').hidden) closeChain();
  });
  addEventListener('hashchange', () => {
    const m = /[#&]chain=([\w.-]+)/.exec(location.hash);
    if (m) openChain(m[1]);
    else if (!$('#chainSec').hidden) $('#chainSec').hidden = true;
    if (cmp || CMP.test(location.hash)) withCompare(m => m.sync());
  });
  if (CMP.test(location.hash)) withCompare(m => m.sync());
}
