// spec: AS-256 AS-298
import { mono } from './avatar.js';
import { $ } from '../lib/dom.js';
import { esc, fd, n, url } from '../lib/format.js';
import { stack } from '../lib/stack.js';

/* ---------- the software calendar: recorded events behind the line, sourced dates ahead of it ----------
   Every mark comes from events.json: observed (filled, with its record), scheduled (a source-published date: outlined), or recheck
   (AirStack's own monitoring date). Forecasts never share this factual calendar. */
let E = null,
  mine = false,
  picked = null;
const KINDS = [
  ['release', 'Releases'],
  ['changelog', 'Changelogs'],
  ['support', 'End of life and support'],
  ['hacker news', 'Hacker News'],
  ['blog', 'Blogs'],
  ['answer recheck', 'Answer rechecks'],
];
const on = new Set(['release', 'changelog', 'support', 'answer recheck']);
const group = k => (/end of/.test(k) ? 'support' : k);
const DAY = 864e5,
  iso = t => new Date(t).toISOString().slice(0, 10);
const STATUS = {
  observed: 'Observed record',
  scheduled: 'Published support date',
  recheck: 'AirStack review date',
};
const source = e => {
  try {
    return new URL(e.url).hostname.replace(/^www\./, '');
  } catch (_) {
    return 'source';
  }
};

function pick() {
  const ids = mine ? new Set(stack().map(x => x.id)) : null;
  return E.events.filter(e => on.has(group(e.kind)) && (!ids || ids.has(e.id)));
}

function grid(list, today) {
  const t0 = Date.parse(today),
    start = t0 - (364 + new Date(t0).getUTCDay()) * DAY,
    weeks = 52 + 1 + 26;
  const by = new Map();
  for (const e of list) {
    const span =
      e.precision === 'window' && e.until
        ? Math.min(31, Math.round((Date.parse(e.until) - Date.parse(e.at)) / DAY))
        : 0;
    for (let k = 0; k <= span; k++) {
      const d = iso(Date.parse(e.at) + k * DAY);
      if (!by.has(d)) by.set(d, []);
      by.get(d).push(e);
    }
  }
  let cells = '',
    past = 0;
  for (let w = 0; w < weeks; w++)
    for (let r = 0; r < 7; r++) {
      const d = iso(start + (w * 7 + r) * DAY),
        ev = by.get(d) || [],
        obs = ev.filter(e => e.status === 'observed').length;
      const fut = d > today,
        cls = [fut ? 'f' : 'p'];
      if (!fut) {
        past += obs;
        if (obs) cls.push('o' + Math.min(4, Math.ceil(obs / 2)));
      }
      if (ev.some(e => e.status === 'scheduled')) cls.push('s');
      if (ev.some(e => e.status === 'recheck')) cls.push('a');
      if (d === today) cls.push('t');
      cells += `<i class="${cls.join(' ')}" data-d="${d}" style="grid-column:${w + 1};grid-row:${r + 1}" title="${fd(d)}: ${ev.length ? ev.length + ' event' + (ev.length > 1 ? 's' : '') : 'none recorded'}"></i>`;
    }
  return { html: cells, by, past };
}

const when = e => fd(e.at);
const title = e =>
  e.url
    ? `<a class="ext" href="${url(e.url)}" target="_blank" rel="noopener noreferrer">${esc(e.title)}</a>`
    : esc(e.title);
function row(e, more = []) {
  /* a product once: its next date leads, its later ones fold under it */
  return `<li class="crow ${esc(e.status)}"><a class="who" href="#app=${esc(e.id)}">${mono({ name: e.name }, 's20')}<b>${esc(e.name)}</b></a>
    <span class="ct">${title(e)}${more.length ? `<details class="nmore"><summary class="meta">and ${more.length} later date${more.length > 1 ? 's' : ''}</summary><ul>${more.map(m => `<li><span class="meta">${when(m)}</span> ${title(m)}</li>`).join('')}</ul></details>` : ''}</span>
    <span class="cs">${esc(STATUS[e.status] || e.status)} · ${esc(source(e))} · ${when(e)}</span></li>`;
}
function agenda(ahead) {
  /* sourced, dated items: one row per product, with later dates folded under it */
  const by = new Map();
  for (const e of ahead) {
    const k = e.id || e.name;
    if (!by.has(k)) by.set(k, []);
    by.get(k).push(e);
  }
  return [...by.values()]
    .slice(0, 50)
    .map(xs => row(xs[0], xs.slice(1)))
    .join('');
}

function render() {
  const today = E.source.built_for,
    list = pick(),
    G = grid(list, today);
  $('#calKinds').innerHTML =
    KINDS.map(
      ([k, l]) => `<button class="chip" type="button" aria-pressed="${on.has(k)}" data-kind="${esc(k)}">${l}</button>`
    ).join('') +
    (stack().length
      ? `<button class="chip mine" type="button" aria-pressed="${mine}" data-mine="1">My stack only · ${stack().length}</button>`
      : '');
  $('#calGrid').innerHTML = G.html;
  const ahead = list
    .filter(e => e.status !== 'observed' && (e.until || e.at) >= today && e.at <= iso(Date.parse(today) + 90 * DAY))
    .sort((a, b) => (a.at < b.at ? -1 : 1));
  const schedules = E.source.support_schedules;
  $('#calSum').innerHTML =
    `${n(G.past)} sourced events in the last 52 weeks · ${n(ahead.length)} published or review dates in the next 90 days${mine ? ' for your stack' : ''} · built ${fd(today)}. Support dates: <a class="ext" href="${url(schedules.url)}" target="_blank" rel="noopener noreferrer">${esc(schedules.name)}</a>, ${esc(schedules.license)}, read ${schedules.read ? fd(schedules.read) : 'not yet'}. <b>No release forecasts are mixed into this calendar.</b>`;
  $('#calAhead').innerHTML = ahead.length
    ? agenda(ahead)
    : `<li class="meta">Nothing dated in the next 90 days${mine ? ' for your stack' : ''}.</li>`;
  day(picked && G.by.has(picked) ? picked : null, G.by);
}

function day(d, by) {
  picked = d;
  const box = $('#calDay');
  box.hidden = !d;
  if (!d) return;
  const ev = (by.get(d) || []).sort((a, b) => (a.status < b.status ? -1 : 1));
  box.innerHTML = `<h3 class="lab">${fd(d)}</h3><ol class="clist">${ev.map(row).join('')}</ol>`;
}

export function mount() {
  const sec = $('#calendar');
  if (!sec) return;
  let loading = null;
  const load = () =>
    loading ||
    (loading = fetch('events.json')
      .then(r => {
        if (!r.ok) throw new Error(r.status);
        return r.json();
      })
      .then(d => {
        E = d;
        render();
      })
      .catch(() => {
        $('#calSum').textContent = 'The calendar could not be loaded. Check your connection and reload.';
      }));
  addEventListener('airstack:view', e => {
    if (e.detail === 'calendar') load();
  });
  if (document.body.dataset.view === 'calendar') load();
  addEventListener('airstack:stack', () => {
    if (E) render();
  });
  sec.addEventListener('click', e => {
    if (e.target.closest('#calKinds .chip[data-mine]')) {
      mine = !mine;
      render();
      return;
    }
    const k = e.target.closest('#calKinds .chip');
    if (k) {
      const v = k.dataset.kind;
      on.has(v) ? on.delete(v) : on.add(v);
      render();
      return;
    }
    const c = e.target.closest('#calGrid i[data-d]');
    if (c && E) {
      const G = grid(pick(), E.source.built_for);
      day(c.dataset.d === picked ? null : c.dataset.d, G.by);
    }
  });
}
