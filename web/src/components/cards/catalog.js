// spec: AS-237 AS-251 AS-252 AS-256 AS-295
import { guideView, modelsView } from './guide.js';
import { renderAll } from '../app.js';
import { mono } from '../avatar.js';
import { priceView, startAt } from '../prices.js';
import { IDX, onMarket } from '../search/index.js';
import { $ } from '../../lib/dom.js';
import { cn, esc, fd, host, ic, nobs, url } from '../../lib/format.js';
import { MK, MKERR } from '../../lib/market.js';
import { COMMUNITY, NEWS, OSS, PROF, pview } from '../../lib/profiles.js';

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
  return `<section class="community mt48" aria-labelledby="community-${esc(x.id)}"><p class="lab">Attention, kept separate from adoption</p><h3 class="h2" id="community-${esc(x.id)}">Community footprint</h3>
    <p class="meta">${esc(attention)}Public channel links and dated audience counts are Wikidata’s record, not a live scrape. A channel’s presence is not proof that people are discussing or using the product.</p>
    ${channels ? `<ul class="community-links mt16">${channels}</ul>` : ''}
    <p class="source-note mt16"><b>How to read this</b> Discussion appears only when a dated source record exists. Channel links and repository activity never substitute for conversation or adoption.</p></section>`;
}

function altView(x) {
  /* the same category's researched products side by side: incumbents and AI challengers, each value from its own pages */
  if (!PROF)
    return (
      pview({ id: x.id, name: x.name }, '__none__', () => renderAll()) || '<p class="meta">Loading the comparison…</p>'
    );
  const peers = IDX.filter(p => p.cat && p.lane === x.lane && PROF[p.id])
    .sort((a, b) => (b.id === x.id) - (a.id === x.id) || PROF[b.id].facts - PROF[a.id].facts)
    .slice(0, 10);
  if (peers.length < 2) return '';
  const v = (p, k) => PROF[p.id][k];
  const list = (c, m) =>
    c && Array.isArray(c.value)
      ? esc(c.value.slice(0, m).join(', ')) +
        (c.value.length > m ? ` <span class="meta">+${c.value.length - m}</span>` : '')
      : nobs;
  return `<h3 class="h2 mt48">${esc(x.name)} and its alternatives</h3><p class="meta">Researched products in ${esc(x.laneName)}, from each one’s own pages: every value is a quote found on its page. “Not observed” means its pages didn’t say.</p>
    <div class="scroll mt16"><table class="t alt"><thead><tr><th scope="col">Product</th><th scope="col">What it says it does</th><th scope="col">Free plan</th><th scope="col">Starting at</th><th scope="col">Plans</th><th scope="col">Compliance</th><th scope="col">Integrations</th></tr></thead><tbody>
    ${peers
      .map(
        p => `<tr${p.id === x.id ? ' class="cur"' : ''}><td><span class="who">${mono(p, 's20')}<button class="lk" type="button" data-pick="${esc(p.id)}">${esc(p.name)}</button></span></td><td>${v(p, 'what_it_does') ? esc(String(v(p, 'what_it_does').value).slice(0, 90)) : nobs}</td>
      <td>${v(p, 'free_plan') ? 'Yes' : nobs}</td><td>${startAt(p.id)}</td><td>${list(v(p, 'plan_names'), 3)}</td><td>${list(v(p, 'compliance'), 3)}</td><td>${v(p, 'integrations') ? `${v(p, 'integrations').value.length} listed` : nobs}</td></tr>`
      )
      .join('')}</tbody></table></div>`;
}
function repGraph(r, order) {
  /* the reputation graph: one bar per OpenSSF Scorecard check, 0 to 10; not applicable is a dotted stub */
  const c = r.scorecard && r.scorecard.checks;
  if (!c) return '';
  return `<span class="rep" role="img" aria-label="${esc(order.map((n, i) => `${n}: ${c[i] == null ? 'not applicable' : c[i] + ' of 10'}`).join('; '))}">${c.map((v, i) => `<i class="${v == null ? 'na' : v === 0 ? 'zero' : ''}" style="--v:${v == null ? 0 : v / 10}" title="${esc(order[i])}: ${v == null ? 'not applicable' : v + '/10'}"></i>`).join('')}</span>`;
}
function ossView(x) {
  /* open-source candidates for the same job: found by GitHub topic, checked by OpenSSF Scorecard; stars are popularity, not trust */
  const L = OSS && OSS.categories[x.lane];
  if (!L || !L.length) return '';
  const ck = OSS.source.checks || {},
    order = ck.order || [];
  const discussion = r => {
    const h = r.community && r.community.hacker_news;
    if (!h || h.status !== 'observed') return '';
    return `<span class="osd"><b>Discussed on Hacker News</b> · ${h.count} repository-linked ${h.count === 1 ? 'story' : 'stories'} · ${h.items.map(i => `<a class="ext" href="${url(i.discussion)}" target="_blank" rel="noopener noreferrer">${esc(i.title)} <span class="meta">${i.points} points · ${i.comments} comments · ${fd(i.date)}</span>${ic('out')}</a>`).join('')}</span>`;
  };
  const lic = r => (r.license && r.license !== 'NOASSERTION' ? esc(r.license) : 'licence not stated');
  const row =
    r => `<li${r.vetted ? ' class="vetted"' : ' class="unvetted"'}><a class="ext" href="${url(r.url)}" target="_blank" rel="noopener noreferrer"><b>${esc(r.repo)}</b>${ic('out')}</a><span class="meta">${esc(r.description)}</span>
      <span class="osm">${r.vetted ? '<span class="pass">Passes the checks</span> · ' : ''}${lic(r)} · pushed ${fd(r.pushed)} · ★ ${cn(r.stars)} · ${r.forks == null ? 'forks not recorded' : `${cn(r.forks)} forks`} · ${r.open_issues_and_pull_requests == null ? 'issues and pull requests not recorded' : `${cn(r.open_issues_and_pull_requests)} open issues and pull requests`} · discussions ${r.discussions_enabled ? 'enabled' : 'not enabled'} <span class="meta">(repository attention and capability, not use)</span></span>
      <span class="osr">${r.scorecard ? `<a class="ext sc" href="${url(r.scorecard.url)}" target="_blank" rel="noopener noreferrer">Scorecard ${r.scorecard.score.toFixed(1)}/10${ic('out')}</a>${repGraph(r, order)}<span class="meta">${r.scorecard.commit ? `commit ${esc(r.scorecard.commit.slice(0, 7))} · ` : ''}${fd(r.scorecard.date)}</span>` : ''}</span>
      ${discussion(r)}
      ${r.flags && r.flags.length ? `<span class="osf">${r.flags.map(f => `<span>⚠ ${esc(f)}</span>`).join('')}</span>` : ''}</li>`;
  const ok = L.filter(r => !r.gate).slice(0, 8),
    below = L.filter(r => r.gate);
  return `<h3 class="h2 mt48">Open-source candidates</h3><p class="meta">Found through ${esc(x.laneName)} topics on GitHub (read ${fd(OSS.source.fetched_at)}). Stars, forks and open issues describe repository attention—not use, sentiment or trust. Projects that pass OpenSSF Scorecard’s automated security checks${ck.fetched_at ? ` (read ${fd(ck.fetched_at)})` : ''}, pinned to the commit checked, come first; the rest follow with what the checks found. Automated checks, not an audit: read the code and the licence before you run anything.</p>
    <ol class="oss mt16">${ok.map(row).join('')}</ol>
    ${below.length ? `<details class="mt16"><summary class="meta">Not vetted: ${below.length} more, below the bar (${[...new Set(below.map(r => r.gate))].join(', ')})</summary><ol class="oss mt12">${below.map(r => row(r).replace('<span class="osf">', `<span class="osf"><span>✕ ${esc(r.gate)}</span>`)).join('')}</ol></details>` : ''}`;
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
/* its static, shareable page */
export function catalogCard(x) {
  /* a cataloged product: what is known (name, category, the links we reached) and, once researched, its own-page facts */
  const tc = $('#toolcard');
  tc.hidden = false;
  if (!MK) {
    tc.innerHTML = MKERR
      ? '<p class="meta">This product’s details could not be loaded. Check your connection and reload.</p>'
      : '<p class="meta">Loading…</p>';
    if (!MKERR) onMarket(() => renderAll());
    return;
  }
  const C = (MK.catalog && MK.catalog[x.id]) || {},
    P = MK.profiles && MK.profiles[x.id];
  const covered = P
    ? `<ul class="cover" aria-label="Available AirStack coverage for ${esc(x.name)}"><li class="cv2 on">Own-page facts · ${P.facts} quotes found</li></ul>`
    : '';
  const link = u =>
    `<a class="ext" href="${url(u)}" target="_blank" rel="noopener noreferrer">${esc(host(u))}${ic('out')}</a> <span class="meta">reached ${fd(C.checked)}</span>`;
  tc.innerHTML = `${covered}<dl class="kv mt24"><div><dt>Vendor</dt><dd>${C.vendor ? esc(C.vendor) : nobs}</dd></div><div><dt>Category</dt><dd>${esc(x.laneName)} <span class="meta">AirStack’s classification</span></dd></div>
      <div><dt>Homepage</dt><dd>${C.homepage ? link(C.homepage) : nobs}</dd></div><div><dt>Share</dt><dd><a class="ext" href="${pageOf(x)}">airstack.bot${pageOf(x)}</a></dd></div><div><dt>Pricing page</dt><dd>${C.pricing ? link(C.pricing) : '<span class="nobs">Not confirmed</span>'}</dd></div></dl>
    ${PROF ? guideView(x) : ''}
    ${PROF ? priceView(x) : ''}
    ${altView(x)}
    ${PROF ? communityView(x) : ''}
    ${PROF ? ossView(x) : ''}
    ${PROF ? modelsView(x) : ''}
    ${P ? `<h3 class="h2 mt48">What its own pages say</h3>${pview({ id: x.id, name: x.name }, x.id, () => renderAll())}` : `<p class="note">AirStack lists ${esc(x.name)} by category with the links checked above. Its own pages haven’t been researched yet, so nothing else is claimed about it.</p>`}`;
}
