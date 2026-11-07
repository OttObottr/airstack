// spec: AS-102 AS-256 AS-328
import { WORD, ans, expired, fromRule } from './answer/model.js';
import { integ, list, one, srcs } from './profile.js';
import { M } from '../lib/data.js';
import { $ } from '../lib/dom.js';
import { esc, fd, host, ic, n, nobs, url } from '../lib/format.js';
import { MK } from '../lib/market.js';

/* ---------- the market: every cell is a verified fact with its pages, or "Not observed" ---------- */
function coverCell(r) {
  if (!r) return nobs;
  const a = fromRule(r);
  if (expired(a)) return `<span class="cv unknown">Recheck due</span> · since ${fd(a.freshUntil)}`;
  const w =
    a.action === 'retire'
      ? 'potential'
      : a.action; /* without the team's other needs, a covering bundle is a Potential replacement: the card's word */
  return `<span class="cv ${w}">${WORD[w]}</span> · ${esc(r.why)}${r.source ? `<a class="src" href="${url(r.source.url)}" target="_blank" rel="noopener noreferrer" aria-label="Source: ${esc(r.source.host)}">${ic('out')}</a>` : ''}`;
}
function googleInPerson(p) {
  /* from the engine's own precomputed answers, for every device */
  const all = M.devices.map(d => ans('fireflies', p, d)).filter(Boolean);
  if (!all.length) return null;
  const a = all[0],
    same = all.every(x => x.action === a.action);
  const s = a.sources[1] || a.sources[0];
  if (!same)
    return {
      status: 'unknown',
      why: 'Depends on the device: pick yours in Check yours.',
      changesIf: a.changesIf,
      source: null,
      evaluatedAt: a.evaluatedAt,
      freshUntil: a.freshUntil,
    };
  const on = M.devices.map(d => (d === 'Computer' ? 'a computer' : d)),
    devs = on.length > 1 ? `${on.slice(0, -1).join(', ')} and ${on.at(-1)}` : on[0];
  const why =
    a.action === 'retire'
      ? `Google Meet takes notes in in-person meetings on ${devs}, and ${p} includes it.`
      : a.reason;
  return {
    status: { retire: 'covered', keep: 'unmet' }[a.action] || 'unknown',
    why,
    changesIf: a.changesIf,
    source: s ? { url: s.url, host: host(s.url), checked: s.date, quote: '', call: null } : null,
    evaluatedAt: a.evaluatedAt,
    freshUntil: a.freshUntil,
  };
}
export function renderMarket() {
  if (!MK) {
    $('#market').hidden = true;
    return;
  }
  const F = MK.fleet;
  $('#marketSub').textContent =
    `${MK.title} · ${MK.vendors.length} apps · from each app’s own pages and store listings`;
  $('#fleet').textContent =
    `${F.readable} pages read · ${F.calls} Muse Spark extraction calls · ${F.checked} claims checked · ${F.passed} quotes found on their pages (${Math.round(F.pass_rate * 100)}%)${F.withheld ? ` · ${F.withheld} withheld under newer rules` : ''} · checked ${fd(F.checked_on)}`;
  $('#vendors tbody').innerHTML = MK.vendors
    .map(v => {
      const rating = [
        v.chrome_rating ? `${v.chrome_rating.value} Chrome${srcs(v.chrome_rating)}` : '',
        v.appstore_rating ? `${v.appstore_rating.value} App Store${srcs(v.appstore_rating)}` : '',
      ]
        .filter(Boolean)
        .join('<br>');
      return `<tr><td data-l="App"><b>${esc(v.name)}</b><br><button class="ext" type="button" data-chain="${esc(v.id)}">Evidence chain</button></td><td data-l="Joins">${list(v.joins)}</td><td data-l="Devices">${list(v.devices)}</td>
    <td data-l="Languages">${one(v.languages)}</td><td data-l="Integrations">${integ(v.integrations)}</td><td data-l="Compliance">${list(v.compliance)}</td>
    <td data-l="Chrome users" class="r">${one(v.chrome_users, x => n(x))}</td><td data-l="Rating" class="r">${rating || nobs}</td></tr>`;
    })
    .join('');
  const rows = [];
  for (const p of ['Business Standard', 'Business Starter', 'No Google plan'])
    rows.push(['Google', p, MK.platforms.Google[p].online, googleInPerson(p)]);
  for (const f of Object.keys(MK.platforms).filter(f => f !== 'Google'))
    for (const p of Object.keys(MK.platforms[f]))
      rows.push([f, p, MK.platforms[f][p].online, MK.platforms[f][p].in_person]);
  $('#cover tbody').innerHTML = rows
    .map(
      ([f, p, on, ip]) =>
        `<tr><td data-l="You have">${f === 'Google' ? 'Google · ' : ''}${esc(p)}</td><td data-l="Online">${coverCell(on)}</td><td data-l="In person">${coverCell(ip)}</td></tr>`
    )
    .join('');
}
