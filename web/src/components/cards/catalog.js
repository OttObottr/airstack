import { Method } from '../../ui/method.js';
import { RepoCard } from '../../ui/repo.js';
import { ui } from '../../ui/recipes.js';
import { strip } from '../signals.js';
import { guideView, modelsView } from './guide.js';
import { renderAll } from '../app.js';
import { mono } from '../avatar.js';
import { priceView } from '../prices.js';
import { IDX, onMarket } from '../search/index.js';
import { DIR, loadDir } from '../search/directory.js';
import { $ } from '../../lib/dom.js';
import { cn, esc, fd, host, ic, nobs, url } from '../../lib/format.js';
import { MK, MKERR } from '../../lib/market.js';
import { loadScale, rankOf, reach, reachCredit, since } from '../../lib/reach.js';
import { COMMUNITY, NEWS, OSS, PROF, TAX, pview } from '../../lib/profiles.js';

const CHANNELS = {
  subreddit: ['Reddit', v => `https://www.reddit.com/${v}/`],
  x: ['X', v => `https://x.com/${v}`],
  threads: ['Threads', v => `https://www.threads.net/@${v}`],
  bluesky: ['Bluesky', v => `https://bsky.app/profile/${v}`],
  mastodon: ['Mastodon', v => { const [, who, server] = /^@?([^@]+)@(.+)$/.exec(v) || []; return who && server ? `https://${server}/@${who}` : ''; }],
  youtube: ['YouTube', v => `https://www.youtube.com/channel/${v}`],
  github: ['GitHub', v => `https://github.com/${v}`],
  linkedin: ['LinkedIn', v => `https://www.linkedin.com/company/${v}/`],
  discord_invite: ['Discord', v => `https://discord.gg/${v}`],
  blog: ['Blog', v => v],
};

function communityView(x) {
  const qids = (COMMUNITY && COMMUNITY.catalog[x.id]) || [],
    seen = new Set();
  const channels = qids.flatMap((qid, index) => {
    const entity = COMMUNITY.entities[qid];
    if (!entity) return [];
    const followers = new Map((entity.followers || []).map(([platform, count, at]) => [platform, [count, at]]));
    return Object.entries(entity.links || {}).map(([k, v]) => {
      if (!CHANNELS[k]) return '';
      const [label, make] = CHANNELS[k],
        href = make(v),
        f = followers.get(k);
      if (!href || seen.has(href)) return '';
      seen.add(href);
      return `<li><a class="chip ext" href="${url(href)}" target="_blank" rel="noopener noreferrer">${esc(label)}${ic('out')}</a><span class="meta">${index ? 'Maker' : 'Product'} · ${f ? `${cn(f[0])} followers · stated ${f[1] ? fd(f[1]) : 'without a date'}` : 'channel recorded; audience not measured'}</span></li>`;
    });
  }).filter(Boolean).join('');
  const hn = NEWS ? NEWS.items.filter(i => i.id === x.id && i.kind === 'hacker news') : [],
    attention = hn.length
      ? `${hn.length} retained Hacker News ${hn.length === 1 ? 'story' : 'stories'} in the ${NEWS.source.window_days}-day update feed · ${hn.reduce((s, i) => s + (i.points || 0), 0)} points when read. `
      : '';
  if (!channels && !attention) return '';
  return `<section class="community mt-12" aria-labelledby="community-${esc(x.id)}"><p class="eyebrow">Attention, kept separate from adoption</p><h3 class="h-section" id="community-${esc(x.id)}">Community footprint</h3>
    <p class="meta">${esc(attention)}Channel links and audience counts are Wikidata’s dated record, not evidence of use.</p>
    ${channels ? `<ul class="community-links mt-4">${channels}</ul>` : ''}</section>`;
}

const DASH = '<span class="text-subtle-foreground">—</span>';
function altView(x) {
  if (!PROF || !TAX || !DIR)
    return (
      pview({ id: x.id, name: x.name }, '__none__', () => renderAll()) ||
      '<div class="skeleton skeleton-profile" role="status" aria-label="Loading comparable products"></div>'
    );
  const nodesOf = p => ((TAX.products[p.id] || []).map(row => row[0])),
    jobs = new Set(nodesOf(x)),
    sameJob = p => p.id !== x.id && nodesOf(p).some(id => jobs.has(id)),
    node = [...jobs][0],
    category = (TAX.nodes[node] || {}).name || x.laneName,
    peers = IDX.filter(p => sameJob(p) && PROF[p.id])
      .sort((a, b) => (rankOf(a.id) || 1e9) - (rankOf(b.id) || 1e9) || PROF[b.id].facts - PROF[a.id].facts || a.name.localeCompare(b.name)) /* the most widely linked first */
      .slice(0, 12),
    listed = IDX.filter(p => sameJob(p) && !PROF[p.id])
      .sort((a, b) => (b.links || 0) - (a.links || 0) || a.name.localeCompare(b.name))
      .slice(0, 24);
  if (!peers.length && !listed.length) return '';
  const v = (p, k) => PROF[p.id][k];
  const list = (c, m) =>
    c && Array.isArray(c.value)
      ? esc(c.value.slice(0, m).join(', ')) +
        (c.value.length > m ? ` <span class="meta">+${c.value.length - m}</span>` : '')
      : DASH;
  const TD = `${ui.td} h-auto py-2.5 align-top`;
  return `<h3 class="h-section mt-12">Also in ${esc(category)}</h3><p class="meta">Products filed in the same category, the most widely linked first. Plans and integrations are what each product’s own pages say.</p>${reachCredit() ? Method(reachCredit(), 'How reach and age are measured') : ''}
    ${peers.length ? `<div class="mt-4 overflow-x-auto"><table class="${ui.table} min-w-[44rem]"><thead><tr><th class="${ui.th}" scope="col">Product</th><th class="${ui.th}" scope="col">What it says it does</th><th class="${ui.th}" scope="col">Site reach</th><th class="${ui.th} text-right" scope="col">Since</th><th class="${ui.th}" scope="col">Free plan</th><th class="${ui.th}" scope="col">Plans</th><th class="${ui.th} text-right" scope="col">Integrations</th></tr></thead><tbody>
    ${peers
      .map(
        p => `<tr class="hover:bg-muted"><td class="${TD} w-56"><span class="flex items-center gap-2.5">${mono(p, 's20')}<button class="text-left font-medium text-foreground hover:underline underline-offset-4" type="button" data-pick="${esc(p.id)}">${esc(p.name)}</button></span></td><td class="${TD} text-muted-foreground">${v(p, 'what_it_does') ? esc(String(v(p, 'what_it_does').value).slice(0, 90)) : DASH}</td>
      <td class="${TD} w-32 whitespace-nowrap">${reach(p.id) || DASH}</td><td class="${TD} w-16 text-right ${ui.num}">${since(p.id) || DASH}</td>
      <td class="${TD} w-24">${v(p, 'free_plan') ? 'Yes' : DASH}</td><td class="${TD} w-56">${list(v(p, 'plan_names'), 3)}</td><td class="${TD} w-28 text-right ${ui.num}">${v(p, 'integrations') ? v(p, 'integrations').value.length : DASH}</td></tr>`
      )
      .join('')}</tbody></table></div>` : ''}
    ${listed.length ? `<p class="eyebrow mt-6">Listed, not yet read</p><ul class="mt-3 flex list-none flex-wrap gap-2">${listed.map(p => `<li><button class="chip" type="button" data-pick="${esc(p.id)}">${esc(p.name)}</button></li>`).join('')}</ul>` : ''}`;
}
function ossView(x) {
  const job = (TAX && TAX.products[x.id] && TAX.products[x.id][0][0]) || x.lane,
    L = OSS && (OSS.categories[job] || OSS.categories[x.lane]);
  if (!L || !L.length) return '';
  const month = iso => fd(iso).replace(/^\d+ /, ''),
    known = f => !/not (checked|scanned)/.test(f); /* an unknown is not a warning: say nothing */
  const card = r =>
    RepoCard({
      name: r.repo,
      href: url(r.url),
      stars: cn(r.stars),
      forks: r.forks == null ? null : cn(r.forks),
      issues: r.open_issues_and_pull_requests == null ? null : cn(r.open_issues_and_pull_requests),
      licence: r.license && r.license !== 'NOASSERTION' ? r.license : null,
      pushed: fd(r.pushed),
      created: r.created ? month(r.created) : null,
      score: r.scorecard ? { text: `Scorecard ${r.scorecard.score.toFixed(1)}/10`, href: url(r.scorecard.url) } : null,
      warn: r.gate || (r.flags || []).find(known) || null,
    });
  const ok = L.filter(r => !r.gate)
      .sort((a, b) => b.stars - a.stars)
      .slice(0, 9),
    below = L.filter(r => r.gate);
  const category = (TAX && TAX.nodes[job] && TAX.nodes[job].name) || x.laneName,
    GRID = 'grid list-none grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-3';
  return `<h3 class="h-section mt-12">Open source in ${esc(category)}</h3><p class="meta">Repositories GitHub returns for this category, most starred first.</p>
    <ol class="${GRID} mt-4">${ok.map(card).join('')}</ol>
    ${below.length ? `<details class="mt-4"><summary class="meta cursor-pointer">${below.length} more with no licence or no recent push</summary><ol class="${GRID} mt-3">${below.map(card).join('')}</ol></details>` : ''}
    <div class="mt-3">${Method(`GitHub search API, read ${fd([].concat(OSS.source.fetched_at).pop())}. Scorecard is OpenSSF’s automated security score, shown where a repository has been scanned. Stars, forks and issues measure attention, not use.`)}</div>`;
}
const pageOf = x =>
  x.dir
    ? `/p/${x.name
        .toLowerCase()
        .replace(/[^a-z0-9]+/g, '-')
        .replace(/^-|-$/g, '')
        .slice(0, 60)}-${x.id.toLowerCase()}/`
    : `/p/${x.id
        .toLowerCase()
        .replace(/[^a-z0-9]+/g, '-')
        .replace(/^-|-$/g, '')
        .slice(0, 60)}/`;
let scaled = false;
export function catalogCard(x) {
  const tc = $('#toolcard');
  if (!DIR) loadDir().then(renderAll, () => {});
  if (!scaled) loadScale().then(() => ((scaled = true), renderAll()));
  if (!MK) {
    tc.innerHTML = MKERR
      ? '<p class="load-error">This product’s details could not be loaded. Check your connection and reload.</p>'
      : '<div class="skeleton skeleton-profile" role="status" aria-label="Loading product details"></div>';
    if (!MKERR) onMarket(() => renderAll());
    return;
  }
  const C = (MK.catalog && MK.catalog[x.id]) || {},
    P = MK.profiles && MK.profiles[x.id];
  const covered = P
    ? `<ul class="cover" aria-label="Available AirStack coverage for ${esc(x.name)}"><li class="cv2 on">${P.facts} sourced facts</li></ul>`
    : '';
  const link = u =>
    `<a class="ext" href="${url(u)}" target="_blank" rel="noopener noreferrer">${esc(host(u))}${ic('out')}</a> <span class="meta">reached ${fd(C.checked)}</span>`;
  tc.innerHTML = `${covered}${strip(x)}<dl class="kv mt-6"><div><dt>Vendor</dt><dd>${C.vendor ? esc(C.vendor) : nobs}</dd></div><div><dt>Category</dt><dd>${esc(x.laneName)} <span class="meta">AirStack’s classification</span></dd></div>
      <div><dt>Homepage</dt><dd>${C.homepage ? link(C.homepage) : nobs}</dd></div><div><dt>Share</dt><dd><a class="ext" href="${pageOf(x)}">airstack.bot${pageOf(x)}</a></dd></div><div><dt>Pricing page</dt><dd>${C.pricing ? link(C.pricing) : '<span class="nobs">Not confirmed</span>'}</dd></div></dl>
    ${PROF ? guideView(x) : ''}
    ${PROF ? priceView(x) : ''}
    ${altView(x)}
    ${PROF ? communityView(x) : ''}
    ${PROF ? ossView(x) : ''}
    ${PROF ? modelsView(x) : ''}
    ${P ? `<h3 class="h-section mt-12">What its own pages say</h3>${pview({ id: x.id, name: x.name }, x.id, () => renderAll())}` : `<p class="note">AirStack lists ${esc(x.name)} by category with the links checked above. Its own pages haven’t been researched yet, so nothing else is claimed about it.</p>`}`;
}
