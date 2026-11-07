// spec: AS-137 AS-233 AS-256 AS-D01
import { S } from './answer/model.js';
import { $ } from '../lib/dom.js';
import { esc, fd, ic, nobs, url } from '../lib/format.js';
import { MK } from '../lib/market.js';

export const srcs = c => {
  const x = c.sources[0],
    more = c.sources.length - 1;
  return `<a class="src" href="${url(x.url)}" target="_blank" rel="noopener noreferrer" aria-label="Source: ${esc(x.host)}, checked ${fd(x.checked)}">${ic('out')}</a>${
    more
      ? `<span class="src" title="${esc(
          c.sources
            .slice(1)
            .map(s => s.host)
            .join(', ')
        )}">+${more}</span>`
      : ''
  }`;
};
export const list = c => (c ? `${esc(c.value.join(', '))}${srcs(c)}` : nobs);
export const integ = c =>
  c
    ? `${esc(c.value.named.join(', '))}${c.value.more ? ` +${c.value.more}` : ''}${c.value.stated ? `${c.value.named.length ? ' · ' : ''}${esc(c.value.stated)} listed` : ''}${srcs(c)}`
    : nobs;
export const one = (c, f = x => x) => (c ? `${esc(f(c.value))}${srcs(c)}` : nobs);
export function renderProfile() {
  const v = MK && MK.vendors.find(x => x.name === S.app);
  $('#profile').innerHTML = v
    ? `<dl class="kv"><div><dt>${esc(v.name)} lists</dt><dd>${v.what ? `${esc(v.what.value)}${srcs(v.what)}` : nobs}</dd></div>
    <div><dt>Languages</dt><dd>${one(v.languages)}</dd></div><div><dt>Joins</dt><dd>${list(v.joins)}</dd></div>
    <div><dt>Integrations</dt><dd>${integ(v.integrations)}</dd></div><div><dt>Compliance</dt><dd>${list(v.compliance)}</dd></div></dl><button class="ext" type="button" data-chain="${esc(v.id)}">Evidence chain · ${v.facts} facts</button>`
    : '';
}
const PF = [
  ['what_it_does', 'What it says it does'],
  ['open_source', 'Open source'],
  ['license', 'License'],
  ['deployment', 'Deployment'],
  ['platforms', 'Platforms'],
  ['sdk_languages', 'SDK languages'],
  ['models_supported', 'Models supported'],
  ['integrations', 'Integrations'],
  ['integrations_count', 'Integrations stated'],
  ['compliance', 'Compliance'],
  ['free_plan', 'Free plan'],
  ['plan_names', 'Plans'],
  ['pricing_basis', 'Pricing basis'],
  ['customers_claimed', 'Customers (their claim)'],
  ['founded_year', 'Founded'],
];
export function profileView(r, p) {
  const val = c => (Array.isArray(c.value) ? c.value.join(', ') : c.value === true ? 'Yes' : String(c.value));
  const rows = PF.filter(([k]) => p[k])
    .map(([k, l]) => `<div><dt>${l}</dt><dd>${esc(val(p[k]))}${srcs(p[k])}</dd></div>`)
    .join('');
  const missing = PF.filter(([k]) => !p[k]).map(([, l]) => l.toLowerCase());
  return `<dl class="kv">${rows}${missing.length ? `<div><dt>Not observed</dt><dd><details class="nobsd"><summary class="nobs">${missing.length} field${missing.length > 1 ? 's' : ''} not on the pages read</summary><span class="nobs">${esc(missing.join(', '))}</span></details></dd></div>` : ''}</dl><p class="mt8 meta">${p.facts} facts extracted with Muse Spark from ${esc(r.name)}’s own pages in ${p.calls} pass${p.calls > 1 ? 'es' : ''}; each quote found on its page by code. A text match is not independent confirmation. “Not observed” means the pages read didn’t say.</p><button class="ext" type="button" data-chain="${esc(r.id)}">Evidence chain · ${p.facts} facts</button>`;
}
