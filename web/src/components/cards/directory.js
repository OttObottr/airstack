import { priceView } from '../prices.js';
import { renderAll } from '../app.js';
import { catList, vendorOf } from '../browse.js';
import { DIR, orgName, wdLink } from '../search/directory.js';
import { IDX, onMarket } from '../search/index.js';
import { $ } from '../../lib/dom.js';
import { cap, esc, host, ic, n, nobs, sq, url } from '../../lib/format.js';
import { MK, MKERR } from '../../lib/market.js';
import { pview, PROF } from '../../lib/profiles.js';

export function dirCard(x) {
  const P = MK && MK.profiles && MK.profiles[x.id],
    T = DIR.types,
    tc = $('#toolcard');
  const covered = P
    ? `<ul class="cover" aria-label="Available AirStack coverage for ${esc(x.name)}"><li class="cv2 on">Own-page facts · ${P.facts} quotes found</li></ul>`
    : '';
  const path = [];
  for (let j = x.t; j != null && path.length < 12; j = T[j][2].length ? T[j][2][0] : null) path.unshift(j);
  const devs = x.devs
    .filter(orgName)
    .map(d =>
      DIR.orgs[d][5] !== 'person'
        ? `<button class="lk" type="button" data-pick="${esc(d)}">${esc(orgName(d))}</button>`
        : esc(orgName(d))
    )
    .join(', ');
  tc.innerHTML = `${covered}<dl class="kv mt24"><div><dt>What it is</dt><dd>${x.desc ? cap(x.desc) : nobs} <span class="meta">Wikidata’s description</span></dd></div>
      <div><dt>Made by</dt><dd>${devs || nobs}</dd></div>
      <div><dt>Type</dt><dd class="crumb">${path.map(j => `<button type="button" data-type="${j}">${esc(T[j][1])}</button>`).join(' › ')}</dd></div>
      <div><dt>Website</dt><dd>${x.site ? `<a class="ext" href="${url(x.site)}" target="_blank" rel="noopener noreferrer">${esc(host(x.site))}${ic('out')}</a> <span class="meta">as Wikidata records it</span>` : nobs}</dd></div>
      <div><dt>Record</dt><dd>${wdLink(x.id)}</dd></div>
      <div><dt>Coverage</dt><dd>${n(x.links)} Wikipedia and sister-site page${x.links === 1 ? '' : 's'}</dd></div></dl>
    ${PROF ? priceView(x) : ''}
    ${P ? `<h3 class="h2 mt48">What its own pages say</h3>${pview({ id: x.id, name: x.name }, x.id, () => renderAll())}` : `<p class="note">Listed from Wikidata. AirStack hasn’t read ${esc(x.name)}’s own pages yet, so nothing else is claimed about it.</p>`}`;
  if (!MK && !MKERR) onMarket(() => renderAll());
}
export function orgCard(x) {
  const tc = $('#toolcard');
  const made = IDX.filter(p => (p.dir && p.devs.includes(x.id)) || (p.cat && sq(vendorOf(p)) === x.k)).sort(
    (a, b) => !!a.listed - !!b.listed || (b.links || 0) - (a.links || 0)
  );
  tc.innerHTML = `<dl class="kv mt24"><div><dt>Founded</dt><dd>${x.founded ? esc(x.founded) : nobs}</dd></div><div><dt>Country</dt><dd>${x.country ? esc(x.country) : nobs}</dd></div>
      <div><dt>Website</dt><dd>${x.site ? `<a class="ext" href="${url(x.site)}" target="_blank" rel="noopener noreferrer">${esc(host(x.site))}${ic('out')}</a>` : nobs}</dd></div>
      <div><dt>Record</dt><dd>${wdLink(x.id)}</dd></div></dl>
    <h3 class="h2 mt48">What it makes · ${n(made.length)} listed</h3>${made.length ? catList(made.slice(0, 60)) : '<p class="meta">None of its products are listed yet.</p>'}
    <p class="note">Listed from Wikidata. AirStack hasn’t researched ${esc(x.name)} itself, so nothing else is claimed about it.</p>`;
  if (!MK && !MKERR) onMarket(() => renderAll());
}
