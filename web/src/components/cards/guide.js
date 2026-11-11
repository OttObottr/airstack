import { GUIDES, HF } from '../../lib/profiles.js';
import { esc, fd, ic, n, url } from '../../lib/format.js';

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

export function modelsView(x) {
  const T = HF && HF.tasks && (HF.categories[x.lane] || []).filter(t => HF.tasks[t] && HF.tasks[t].models.length);
  if (!T || !T.length) return '';
  return `<h3 class="h-section mt-12">Open models you can run</h3><p class="meta">The most downloaded models on the Hugging Face Hub for each job, by Hugging Face’s own 30-day count, read ${fd(HF.source.fetched_at)}. A lead, not an endorsement: check each licence and its terms.</p>
    ${T.map(
      t =>
        `<p class="eyebrow mt-6">${esc(HF.tasks[t].name)}</p><ol class="hfm">${HF.tasks[t].models
          .slice(0, 5)
          .map(
            m => `<li><a class="ext" href="${url(m.url)}" target="_blank" rel="noopener noreferrer"><b>${esc(m.id)}</b>${ic('out')}</a>
      <span class="meta">${n(m.downloads)} downloads · ${n(m.likes)} likes · ${m.license ? esc(m.license) : 'licence not stated'}${m.gated ? ' · gated: accept terms to download' : ''}${m.updated ? ` · updated ${fd(m.updated)}` : ''}</span></li>`
          )
          .join('')}</ol>`
    ).join('')}`;
}
