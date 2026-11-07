// spec: AS-256 AS-268
import { M } from '../lib/data.js';
import { $ } from '../lib/dom.js';
import { esc, fd, ic, n, url } from '../lib/format.js';

/* ---------- the methodology: how one real answer was made, step by step, from the worked example's own stored records ----------
   Every value below is read from site-data.js: the page, its exact words, the judge's receipt and the monitoring window. */
const https = u => (/^https?:\/\//.test(u) ? u : 'https://' + u);

export function mount() {
  const sec = $('#method');
  if (!sec) return;
  const launch = M.sources.find(s => s.source === 'Google Workspace Updates' && s.real) || M.sources[0];
  const plans = M.sources.find(s => /plans include it/.test(s.fact)) || launch;
  const key = 'fireflies|Business Standard|Android',
    ex = M.examples[key];
  const a = M.pool[M.answers.fireflies['Business Standard'].Android];
  const link = (s, label) =>
    `<a class="ext" href="${url(https(s.url))}" target="_blank" rel="noopener noreferrer">${esc(label || s.source)}${ic('out')}</a>`;
  const steps = [
    [
      'Read the vendor’s own page',
      'Google’s announcement and help pages are fetched and stored with a hash of what was read, so a change is detected, not assumed.',
      `${link(launch)} <span class="meta">published ${fd(launch.published)}</span>`,
    ],
    [
      'Code finds the quote',
      'A fact is kept only when its exact words are on the page. A model can propose a fact; code decides whether it stands.',
      `<q>${esc(launch.expect)}</q> <span class="meta">found on the page</span>`,
    ],
    [
      'Muse judges it against your plan',
      `Fireflies, for someone on Business Standard who records in person on Android. Below 0.7 confidence, nothing is published.`,
      ex
        ? `<b>${esc(a.action === 'retire' ? 'Retire' : a.action)}</b> <span class="meta">· judged by ${esc(M.meta.model)} · ${ex.calls} calls · ${n(ex.tokens)} tokens · ${fd(ex.on)}</span>`
        : '',
    ],
    [
      'Continuous monitoring protects the answer',
      'Every answer shows when it was verified and its next recheck. If a source page changes, the review moves forward.',
      `Verified through <b>${fd(a.freshUntil)}</b> <span class="meta">· monitored source: ${link(plans, 'Meet Help · plans')}</span>`,
    ],
  ];
  $('#pipe').innerHTML = steps
    .map(
      ([t, body, ev], i) =>
        `<li><span class="pn">${i + 1}</span><h3>${esc(t)}</h3><p>${esc(body)}</p><p class="pev">${ev}</p></li>`
    )
    .join('');
  $('#fine').innerHTML = [
    'The worked plan and device are explicit scenario inputs; every fact and source is real, linked and monitored.',
    `Two clocks: a source’s own date, and real time for every check and every model call. The replayed August steps were judged on ${fd(M.meta.checked_at)}, and the page labels replayed and real time.`,
    'A quote found on a vendor’s own page is a text match, not independent confirmation; a second record from the same vendor is labelled as such.',
    'The A/B compares an agent’s memory with AirStack’s retrieval on one question, not equal research access.',
    `Monitoring is active through ${fd(a.freshUntil)}. After that, the page and local MCP mark this answer as due for recheck until fresh verification completes.`,
  ]
    .map(t => `<li>${esc(t)}</li>`)
    .join('');
}
