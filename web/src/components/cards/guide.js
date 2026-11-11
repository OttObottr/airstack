import { GUIDES } from '../../lib/profiles.js';
import { esc } from '../../lib/format.js';

export function guideView(x) {
  const G = GUIDES && GUIDES.categories[x.lane];
  if (!G) return '';
  const li = a => a.map(t => `<li>${esc(t)}</li>`).join('');
  return `<section class="guide mt-12" aria-labelledby="g-${esc(x.id)}"><h3 class="h-section" id="g-${esc(x.id)}">Why teams use ${esc(x.laneName)}</h3>
    <p class="meta">AirStack’s guide to the category, not a claim by ${esc(x.name)}.</p>
    <p class="gwhat">${esc(G.what)}</p>
    <div class="gcols"><div><p class="eyebrow">What it gets you</p><ul>${li(G.why)}</ul></div><div><p class="eyebrow">Jobs it does</p><ul>${li(G.jobs)}</ul></div>
      <div><p class="eyebrow">Who uses it</p><p class="roles">${G.who.map(r => `<span>${esc(r)}</span>`).join('')}</p>
        ${G.bundled_by.length ? `<p class="eyebrow mt-4">Often included in</p><p class="meta">${G.bundled_by.map(esc).join(' · ')}</p>` : ''}</div></div>
    <p class="gwatch"><b>Watch for</b> ${esc(G.watch_for)}</p></section>`;
}

