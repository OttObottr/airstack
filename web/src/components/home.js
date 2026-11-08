import { json } from '../lib/data.js';
import { $ } from '../lib/dom.js';
import { esc, fd, host, n, url } from '../lib/format.js';

const DAY = 864e5,
  WEEKS = 8,
  SHOWN = 6,
  MIN_READ = 5; /* a share over fewer products read is not shown */
const pct = (k, of) => (of ? Math.round((k / of) * 100) : null);
const STATUS = { scheduled: 'published date', unconfirmed: 'date passed, not confirmed' };

/* a category count: a {found, of} record, or a bare count out of the products read */
export const cnt = (v, c) => (v && typeof v === 'object' ? v : { found: v, of: c.researched });
/* the headline measures, shared with the full insights view */
export function measures(I) {
  const bands = I.map.populations.categories,
    cats = Object.entries(I.categories).filter(([, c]) => c.researched),
    researched = cats.reduce((s, [, c]) => s + c.researched, 0),
    totals = I.kpis.map(k => [k.label, cats.reduce((s, [, c]) => s + cnt(c[k.key], c).found, 0), k.key]).sort((a, b) => b[1] - a[1]);
  return { bands, placed: bands.reduce((a, b) => a + b, 0), ai: bands[1] + bands[2], cats, researched, totals, hub: I.hubs[0] };
}

function insightsPanel(I) {
  const m = measures(I),
    [label, count, key] = m.totals[0],
    top = m.cats
      .filter(([, c]) => c.researched >= MIN_READ)
      .map(([id, c]) => [id, c, pct(cnt(c[key], c).found, cnt(c[key], c).of)])
      .sort((a, b) => b[2] - a[2] || b[1].researched - a[1].researched)
      .slice(0, 5);
  $('#insNow').innerHTML = `<ol class="ins-mini">
      <li><b>${pct(m.ai, m.placed)}% mention AI</b> <span class="meta">${n(m.ai)} of ${n(m.placed)} placed products, on their own pages</span></li>
      <li><b>${esc(label)}</b> <span class="meta">the most stated disclosure: ${n(count)} of ${n(m.researched)} products read</span></li>
      ${m.hub ? `<li><b>${esc(m.hub[1])}</b> <span class="meta">the most named integration, in ${n(m.hub[2])} products’ own lists</span></li>` : ''}
    </ol>
    <p class="lab mt16">${esc(label)}, by category</p>
    ${
      top.length
        ? `<ol class="cbars">${top
            .map(
              ([id, c, v]) =>
                `<li><a href="/c/${esc(id)}/">${esc(c.name)}</a><span class="num r">${v}% <span class="meta">${n(cnt(c[key], c).found)} found of ${n(cnt(c[key], c).of)}</span></span><span class="hb" style="--v:${v / 100}" aria-hidden="true"></span></li>`
            )
            .join('')}</ol>`
        : `<p class="meta mt8">No category has ${MIN_READ} products read yet.</p>`
    }
    <p class="meta mt12">Share of products read whose own pages say so; scale 0 to 100%. Categories with fewer than ${MIN_READ} products read are left out. Sources: ${esc(I.source.facts_from)}; ${esc(I.source.documentation_from)}.</p>`;
}

function upcomingPanel(E) {
  const today = E.source.built_for,
    end = new Date(Date.parse(today) + WEEKS * 7 * DAY).toISOString().slice(0, 10),
    seen = new Set(),
    S = E.source.support_schedules;
  const ahead = E.events
    .filter(e => /^(release|changelog|end of)/.test(e.kind) && e.status !== 'observed' && (e.until || e.at) >= today && e.at <= end)
    .sort((a, b) => (a.at < b.at ? -1 : 1))
    .filter(e => !seen.has(e.id || e.name) && seen.add(e.id || e.name));
  $('#upList').innerHTML = ahead.length
    ? ahead
        .slice(0, SHOWN)
        .map(
          e => `<li><time datetime="${esc(e.at)}">${fd(e.at)}</time><a href="#app=${esc(e.id)}"><b>${esc(e.name)}</b></a>
      <span class="meta">${e.url ? `<a class="ext" href="${url(e.url)}" target="_blank" rel="noopener noreferrer">${esc(e.title)}</a>` : esc(e.title)} · ${esc(STATUS[e.status] || e.status)}${e.url ? ` · ${esc(host(e.url))}` : ''}</span></li>`
        )
        .join('')
    : `<li class="meta">Nothing dated in the next ${WEEKS} weeks.</li>`;
  $('#upSrc').innerHTML =
    `${n(Math.min(SHOWN, ahead.length))} of ${n(ahead.length)} tools with a date in the ${WEEKS} weeks from ${fd(today)}. Support dates: <a class="src" href="${url(S.url)}" target="_blank" rel="noopener noreferrer">${esc(S.name)}</a>, ${esc(S.license)}, read ${S.read ? fd(S.read) : 'not yet'}.`;
}

const fill = (sel, file, draw, what) =>
  json(file)
    .then(draw)
    .catch(e => {
      console.error(`home: ${file}`, e);
      const tag = $(sel).tagName === 'OL' ? 'li' : 'p';
      $(sel).innerHTML = `<${tag} class="load-error" role="status">${what} could not be loaded. Check your connection and reload.</${tag}>`;
    })
    .finally(() => $(sel).setAttribute('aria-busy', 'false'));

export function mount() {
  let done = false;
  addEventListener('airstack:view', e => {
    if (e.detail !== 'overview' || done) return;
    done = true;
    fill('#upList', 'events.json', upcomingPanel, 'Upcoming dates');
    fill('#insNow', 'insights.json', insightsPanel, 'Category insights');
  });
}
