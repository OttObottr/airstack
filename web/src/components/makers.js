import { radios } from './chips.js';
import { json } from '../lib/data.js';
import { $, copy } from '../lib/dom.js';
import { esc, fd, host, ic, n, pct, url } from '../lib/format.js';
import { loadTaxonomy } from '../lib/profiles.js';

/* lenses from makers.json, each row naming its signal; the full list from o/makers.json; headcount is context, never the order */
const LENS = { Rising: 'rising', Leaders: 'leader', Incumbents: 'incumbent', 'All makers': 'all' },
  PAGE = 50,
  KIND = { downloads: 'weekly downloads', attention: 'Wikipedia views', documentation: 'Wikipedia and sister-site pages' };
let O = null,
  L = null,
  TAX = null,
  T = {},
  shown = PAGE;
const S = { lens: 'rising', q: '', cat: '', after: '' };

const fromHash = () => {
  const p = new URLSearchParams(location.hash.split('?')[1] || '');
  S.lens = Object.values(LENS).includes(p.get('lens')) ? p.get('lens') : L ? 'rising' : 'all';
  S.q = p.get('q') || '';
  S.cat = p.get('cat') || '';
  S.after = p.get('after') || '';
};
const toHash = () => {
  const p = new URLSearchParams();
  for (const [k, v] of Object.entries(S)) if (v && !(k === 'lens' && v === 'rising')) p.set(k, v);
  history.replaceState(null, '', '#/makers' + (p.size ? '?' + p : ''));
};

const catOf = ids => {
  for (const id of ids || []) {
    const node = TAX && TAX.products[id] && TAX.products[id][0] && TAX.products[id][0][0];
    if (node) return node;
  }
  return '';
};
/* the signal that puts a maker on its lens: the biggest rise for Rising, the biggest count otherwise */
const best = m => {
  const k = m && m.lens === 'rising' ? 'change' : 'value';
  return ((m && m.signals) || []).reduce((a, s) => (!a || (s[k] ?? -1e9) > (a[k] ?? -1e9) ? s : a), null);
};
const signal = s => {
  if (!s) return '';
  const src = s.source && typeof s.source === 'object' ? s.source : { url: s.source };
  return `<b class="num">${s.value != null ? n(s.value) : ''} ${esc(KIND[s.kind] || s.kind)}</b>${s.change != null ? ` <span class="num">${pct(s.change * 100)}</span>` : ''} <span class="meta">${esc(s.window || '')}</span>${
    src.url ? ` <a class="ext" href="${url(src.url)}" target="_blank" rel="noopener noreferrer">${esc(src.name || host(src.url))}${ic('out')}</a>${src.read ? ` <span class="meta">read ${fd(src.read)}</span>` : ''}` : ''
  }`;
};

function rows() {
  const byQ = new Map(O.rows.map(r => [r[10], r]));
  const all =
    S.lens === 'all'
      ? O.rows.map(r => ({ q: r[10], name: r[1], founded: r[3], o: r, m: L && L.makers[r[10]] }))
      : Object.entries(L.makers)
          .filter(([, m]) => m.lens === S.lens)
          .map(([q, m]) => ({ q, name: m.name, founded: m.founded, o: byQ.get(q), m }));
  for (const r of all) r.cat = catOf(r.m && r.m.products);
  const q = S.q.trim().toLowerCase(),
    R = all.filter(
      r => (!q || r.name.toLowerCase().includes(q)) && (!S.cat || r.cat === S.cat) && (!S.after || (r.founded && +String(r.founded).slice(0, 4) > +S.after))
    );
  const s0 = r => best(r.m) || {};
  const order = {
    rising: (a, b) => (s0(b).change ?? -1e9) - (s0(a).change ?? -1e9),
    leader: (a, b) => (s0(b).value ?? -1) - (s0(a).value ?? -1),
    incumbent: (a, b) => String(a.founded || 9999).localeCompare(String(b.founded || 9999)),
    all: () => 0,
  }[S.lens];
  return { all, R: R.sort((a, b) => order(a, b) || a.name.localeCompare(b.name)) };
}

function render() {
  const { all, R } = rows();
  if (L) radios($('#mkLens'), Object.keys(LENS), Object.keys(LENS).find(k => LENS[k] === S.lens), v => {
    S.lens = LENS[v];
    refresh();
  });
  $('#mkRule').textContent = S.lens === 'all' ? 'Every maker with a listed product, A to Z.' : L.rule[S.lens] || '';
  const cats = [...new Set(all.map(r => r.cat).filter(Boolean))].sort((a, b) => ((T[a] || [a])[0]).localeCompare((T[b] || [b])[0]));
  $('#mkCat').innerHTML = '<option value="">All categories</option>' + cats.map(c => `<option value="${esc(c)}"${c === S.cat ? ' selected' : ''}>${esc((T[c] || [c])[0])}</option>`).join('');
  $('#mkCat').hidden = !cats.length;
  $('#mkAfter').value = S.after;
  $('#mkQ').value = S.q;
  const nr = '<span class="nobs">Not recorded</span>';
  $('#mkList').setAttribute('aria-busy', 'false');
  $('#mkList').innerHTML =
    R.slice(0, shown)
      .map(
        (r, i) => `<tr><td class="num r">${S.lens === 'all' ? '' : i + 1}</td>
    <th scope="row">${r.o ? `<a href="/o/${esc(r.o[0])}/">${esc(r.name)}</a>` : /^Q\d+$/.test(r.q) ? `<a class="ext" href="https://www.wikidata.org/wiki/${r.q}" target="_blank" rel="noopener noreferrer">${esc(r.name)}${ic('out')}</a>` : esc(r.name)}</th>
    <td>${r.m && r.m.why ? `${esc(r.m.why)}<br>${signal(best(r.m))}` : '<span class="nobs">Not on a lens</span>'}</td>
    <td>${r.cat && T[r.cat] ? `<a href="/t/${esc(r.cat)}/">${esc(T[r.cat][0])}</a>` : r.cat ? esc(r.cat) : nr}</td>
    <td class="num r">${r.founded ? esc(String(r.founded).slice(0, 4)) : nr}</td>
    <td class="num r">${r.o && r.o[4] ? `${n(r.o[4])} <span class="meta">${esc(r.o[5])}</span>` : nr}</td>
    <td class="num r">${r.o ? n(r.o[6]) : n((r.m && r.m.products || []).length)}</td></tr>`
      )
      .join('') || '<tr><td colspan="7" class="meta">No maker matches these filters.</td></tr>';
  $('#mkMore').hidden = R.length <= shown;
  $('#mkMore').disabled = false;
  $('#mkCount').textContent = `${n(R.length)} of ${n(all.length)} makers on this lens`;
}

const refresh = () => {
  shown = PAGE;
  toHash();
  render();
};

export function mount() {
  const sec = $('#leaders');
  if (!sec) return;
  Promise.all([
    json('o/makers.json'),
    json('makers.json').catch(() => null) /* no lenses published: the full list alone */,
    loadTaxonomy().catch(() => null),
    json('t/map.json').catch(() => ({ nodes: {} })),
  ])
    .then(([o, l, tax, t]) => {
      O = o;
      L = l && l.makers ? l : null;
      TAX = tax;
      T = t.nodes || {};
      $('#mkLens').hidden = !L;
      fromHash();
      render();
    })
    .catch(e => {
      console.error('makers:', e);
      $('#mkCount').textContent = 'The makers list could not be loaded.';
      $('#mkMore').hidden = true;
      $('#mkList').setAttribute('aria-busy', 'false');
      $('#mkList').innerHTML = '<tr><td colspan="7"><p class="load-error" role="status">Check the connection and reload.</p></td></tr>';
    });
  $('#mkQ').addEventListener('input', e => {
    S.q = e.target.value;
    refresh();
  });
  for (const [id, key] of [
    ['#mkCat', 'cat'],
    ['#mkAfter', 'after'],
  ])
    $(id).addEventListener('change', e => {
      S[key] = e.target.value;
      refresh();
    });
  $('#mkMore').addEventListener('click', () => {
    shown += 100;
    render();
  });
  $('#mkReset').addEventListener('click', () => {
    Object.assign(S, { lens: L ? 'rising' : 'all', q: '', cat: '', after: '' });
    refresh();
  });
  $('#mkShare').addEventListener('click', e => copy(e.currentTarget, location.href, { ok: 'Link copied', fail: 'Copy the address' }));
  addEventListener('hashchange', () => {
    if (O && /^#\/makers/.test(location.hash)) {
      fromHash();
      render();
    }
  });
}
