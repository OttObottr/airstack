import { $, copy } from '../lib/dom.js';
import { esc, n } from '../lib/format.js';

const SORTS = { size: 'Largest by headcount', products: 'Most products listed', name: 'Name, A to Z' };
const PAGE = 50;
let D = null,
  shown = PAGE;
const S = { q: '', country: '', kind: '', sort: 'size' };

const fromHash = () => {
  const p = new URLSearchParams(location.hash.split('?')[1] || '');
  S.q = p.get('q') || '';
  S.country = p.get('country') || '';
  S.kind = p.get('kind') || '';
  S.sort = p.get('sort') || 'size';
  if (!SORTS[S.sort]) S.sort = 'size';
};
const toHash = () => {
  const p = new URLSearchParams();
  for (const [k, v] of Object.entries(S)) if (v && !(k === 'sort' && v === 'size')) p.set(k, v);
  history.replaceState(null, '', '#/makers' + (p.size ? '?' + p : ''));
};

function rows() {
  const q = S.q.trim().toLowerCase();
  const R = D.rows.filter(
    r => (!S.country || r[2] === S.country) && (!S.kind || r[8] === S.kind) && (!q || r[1].toLowerCase().includes(q))
  );
  if (S.sort === 'products') R.sort((a, b) => b[6] - a[6] || a[1].localeCompare(b[1]));
  else if (S.sort === 'name') R.sort((a, b) => a[1].localeCompare(b[1]));
  else
    R.sort(
      (a, b) => b[7] - a[7] || (b[7] ? (b[4] || 0) - (a[4] || 0) : a[1].localeCompare(b[1]))
    );
  return R;
}

function render() {
  const R = rows();
  $('#mkList').setAttribute('aria-busy', 'false');
  $('#mkCountry').innerHTML =
    '<option value="">All countries</option>' +
    Object.entries(D.countries)
      .sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]))
      .map(([c, k]) => `<option value="${esc(c)}"${c === S.country ? ' selected' : ''}>${esc(c)} (${k})</option>`)
      .join('');
  $('#mkKind').value = S.kind;
  $('#mkSort').value = S.sort;
  $('#mkQ').value = S.q;
  $('#mkList').innerHTML =
    R.slice(0, shown)
      .map(
        (r, i) => `<tr><td class="num r">${S.sort === 'size' && r[7] ? i + 1 : ''}</td>
    <th scope="row"><a href="/o/${esc(r[0])}/">${esc(r[1])}</a></th><td>${r[9] ? `<a href="#/makers?country=${encodeURIComponent(r[2])}" data-country="${esc(r[2])}">${esc(r[2])}</a>` : esc(r[2]) || '<span class="nobs">Not recorded</span>'}</td>
    <td class="num r">${esc(r[3]) || '<span class="nobs">—</span>'}</td><td class="num r">${r[4] ? `${n(r[4])} <span class="meta">${esc(r[5])}</span>` : '<span class="nobs">Not recorded</span>'}</td><td class="num r">${n(r[6])}</td></tr>`
      )
      .join('') || '<tr><td colspan="6" class="meta">No maker matches these filters.</td></tr>';
  $('#mkMore').hidden = R.length <= shown;
  $('#mkMore').disabled = false;
  $('#mkCount').textContent =
    `${n(R.length)} of ${n(D.rows.length)} makers · ${n(D.ranked)} have a headcount dated 2015 or later and are ranked by it`;
}

const refresh = () => {
  shown = PAGE;
  toHash();
  render();
};

export function mount() {
  const sec = $('#leaders');
  if (!sec) return;
  const load = () =>
    fetch('o/makers.json')
      .then(r => {
        if (!r.ok) throw new Error(r.status);
        return r.json();
      })
      .then(d => {
        D = d;
        fromHash();
        render();
      })
      .catch(e => {
        console.error('makers:', e);
        $('#mkCount').textContent = 'The makers list could not be loaded.';
        $('#mkMore').hidden = true;
        $('#mkList').setAttribute('aria-busy', 'false');
        $('#mkList').innerHTML =
          '<tr><td colspan="6"><p class="load-error" role="status">Check the connection and reload.</p></td></tr>';
      });
  $('#mkSort').innerHTML = Object.entries(SORTS)
    .map(([k, l]) => `<option value="${k}">${l}</option>`)
    .join('');
  $('#mkQ').addEventListener('input', e => {
    S.q = e.target.value;
    refresh();
  });
  for (const [id, key] of [
    ['#mkCountry', 'country'],
    ['#mkKind', 'kind'],
    ['#mkSort', 'sort'],
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
    Object.assign(S, { q: '', country: '', kind: '', sort: 'size' });
    refresh();
  });
  $('#mkShare').addEventListener('click', e => copy(e.currentTarget, location.href, { ok: 'Link copied', fail: 'Copy the address' }));
  sec.addEventListener('click', e => {
    const a = e.target.closest('a[data-country]');
    if (a) {
      e.preventDefault();
      S.country = a.dataset.country;
      refresh();
    }
  });
  addEventListener('hashchange', () => {
    if (D && /^#\/makers/.test(location.hash)) {
      fromHash();
      render();
    }
  });
  load();
}
