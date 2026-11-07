// spec: AS-102 AS-256 AS-346
import { announce, renderAnswer } from './answer.js';
import { S, family } from './model.js';
import { $ } from '../../lib/dom.js';
import { esc } from '../../lib/format.js';
import { MK } from '../../lib/market.js';

/* what else you rely on the app for: chips from its OWN verified profile; the bundle only replaces it if it covers these too (review P0) */
function capabilities() {
  const v = MK && MK.vendors.find(x => x.name === S.app);
  if (!v) return [];
  const fam = family(S.plan),
    L = MK.platformLanguages[fam],
    n = v.languages && parseInt(String(v.languages.value), 10);
  const out = [];
  if (n && L && n > L.count)
    out.push({
      id: 'lang',
      label: `Languages beyond ${fam === 'Google' ? 'Meet' : fam}’s ${L.count}`,
      changesIf: `${fam === 'Google' ? 'Meet' : fam}’s notes add the languages you need.`,
      check: () => ({
        status: 'unmet',
        why: `${fam === 'Google' ? 'Meet' : fam}’s notes support ${L.count} languages; ${v.name} lists ${v.languages.value}.`,
        source: L.source,
      }),
    });
  for (const name of (v.integrations ? v.integrations.value.named : [])
    .filter(x => /salesforce|hubspot|slack|notion|zapier|asana|jira/i.test(x))
    .slice(0, 4))
    out.push({
      id: 'int:' + name,
      label: `Sync to ${name}`,
      check: () => ({ status: 'unknown', why: `Not verified whether your platform’s notes sync to ${name}.` }),
    });
  for (const app of (v.joins ? v.joins.value : [])
    .filter(x => !['Google Meet', 'Zoom', 'Microsoft Teams'].includes(x))
    .slice(0, 2))
    out.push({
      id: 'join:' + app,
      label: `Notes in ${app}`,
      check: () => ({ status: 'unknown', why: `Not verified whether your platform takes notes in ${app}.` }),
    });
  return out;
}
export function withNeeds(a) {
  /* the bundle covering the notes is a potential replacement, not a cancellation */
  if (a.action !== 'retire' || a.stale) return a;
  const caps = capabilities();
  if (!caps.length && !MK) return a;
  if (!S.needs.size)
    return {
      ...a,
      action: 'potential',
      line: `What you already have covers the notes. It may not cover everything you use ${S.app} for.`,
    };
  if (S.needs.has('none'))
    return { ...a, line: `You can stop paying for this, for what you told us you use ${S.app} for.` };
  const res = caps.filter(c => S.needs.has(c.id)).map(c => ({ ...c, ...c.check() }));
  if (a.needs) {
    const nd = [
      ...a.needs,
      ...res.map(r => ({ label: r.label, status: r.status, why: r.why, source: r.source, changesIf: r.changesIf })),
    ];
    a = { ...a, needs: nd, covered: nd.filter(x => x.status === 'covered').length };
  } /* every selected need is counted and shown, met or not */
  const unmet = res.find(r => r.status === 'unmet'),
    unk = res.filter(r => r.status === 'unknown');
  if (unmet)
    return {
      ...a,
      action: 'keep',
      line: 'What you already have doesn’t cover everything you use it for.',
      reason: unmet.why,
      changesIf: unmet.changesIf || `${unmet.label} is covered too.`,
      sources: unmet.source
        ? [{ label: unmet.source.host, date: unmet.source.checked, url: unmet.source.url }].concat(a.sources)
        : a.sources,
      basis: null,
    };
  if (unk.length)
    return {
      ...a,
      action: 'unknown',
      line: 'Not enough evidence yet.',
      reason: unk.map(r => r.why).join(' '),
      changesIf: 'A source confirms each one either way.',
      basis: null,
    };
  return a;
}
export function needChips() {
  const caps = capabilities(),
    w = $('#qNeedW');
  w.hidden = !caps.length;
  if (!caps.length) return;
  $('#qNeed').textContent = `What else do you use ${S.app} for?`;
  for (const id of [...S.needs]) if (id !== 'none' && !caps.some(c => c.id === id)) S.needs.delete(id);
  $('#needs').innerHTML = caps
    .concat([{ id: 'none', label: 'Nothing else' }])
    .map(
      c =>
        `<button class="chip" type="button" aria-pressed="${S.needs.has(c.id)}" data-n="${esc(c.id)}">${esc(c.label)}</button>`
    )
    .join('');
}

export function mount() {
  /* the choices behind the answer are one line, 'Your setup … Change'; it shows the chips on demand (the address keeps carrying them either way) */
  const bench = $('#bench'),
    bar = document.createElement('button');
  bar.id = 'setup';
  bar.type = 'button';
  bar.hidden = true;
  bar.setAttribute('aria-expanded', 'false');
  bar.setAttribute('aria-controls', 'qs');
  bar.innerHTML = '<span class="lab"></span><span class="sv"></span><span class="chg">Change</span>';
  $('#qs').before(bar);
  document.addEventListener('click', e => {
    const t = e.target.closest('#setup, [data-dev]');
    if (!t) return;
    if (t.dataset.dev) return $(`#devices .chip[data-v="${t.dataset.dev}"]`).click();
    bar.setAttribute('aria-expanded', String(bench.classList.toggle('open')));
  });
  document.addEventListener('click', e => {
    const b = e.target.closest('.chip[data-n]');
    if (!b) return;
    const id = b.dataset.n;
    S.assumed = false;
    if (id === 'none') {
      S.needs = new Set(S.needs.has('none') ? [] : ['none']);
    } else {
      S.needs.delete('none');
      S.needs.has(id) ? S.needs.delete(id) : S.needs.add(id);
    }
    needChips();
    renderAnswer();
    announce();
  });
}
