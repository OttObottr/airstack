// spec: AS-256 AS-257
import { $ } from '../lib/dom.js';
import { esc, n } from '../lib/format.js';
import { squarify } from '../lib/treemap.js';

/* ---------- every kind of software: the same treemap, for any category of the taxonomy (t/map.json, written by build_pages.py). Area is how widely a product
   is documented (Wikidata's count of Wikipedia and sister-site pages): measured for every product, and not market share. No change over time is drawn: none is
   measured for these. A tile exists only if its count does; the rest of the category is counted under the map. ---------- */
let D = null,
  now = 'consumer';
const kids = id => Object.entries(D.nodes).filter(([, v]) => v[1] === id);

function options() {
  /* every category once, under its area, sub-categories indented */
  const opt = (id, label, count, depth) =>
    `<option value="${esc(id)}">${'\u00a0\u00a0'.repeat(depth)}${esc(label)} · ${n(count)}</option>`;
  const tree = (id, depth) =>
    kids(id)
      .sort((a, b) => b[1][2] - a[1][2])
      .map(([k, c]) => opt(k, c[0], c[2], depth) + tree(k, depth + 1))
      .join('');
  $('#tyPick').innerHTML = kids(null)
    .sort((a, b) => b[1][2] - a[1][2])
    .map(([id, v]) => `<optgroup label="${esc(v[0])}">${opt(id, 'All ' + v[0], v[2], 0)}${tree(id, 1)}</optgroup>`)
    .join('');
  $('#tyPick').value = now;
}

export function draw() {
  const box = $('#tyMap');
  if (!D || !box || !D.nodes[now]) return;
  const [name, , listed, read, top] = D.nodes[now],
    W = box.clientWidth,
    H = box.clientHeight;
  if (!W || !H) return;
  const at = squarify(
    top.map(r => r[2]),
    W,
    H
  );
  const tiles = top.map((r, i) => {
    const [x0, y0, x1, y1] = at[i],
      w = x1 - x0,
      h = y1 - y0,
      say = `${r[1]}: documented on ${n(r[2])} Wikipedia and sister-site pages`,
      tile = document.createElement(w < 24 || h < 24 ? 'i' : 'a');
    tile.className = 'tile flat';
    Object.assign(tile.style, { left: `${x0}px`, top: `${y0}px`, width: `${w}px`, height: `${h}px` });
    tile.style.setProperty('--i', i);
    tile.title = say;
    if (tile.tagName === 'I') tile.setAttribute('aria-hidden', 'true');
    else {
      tile.href = `#app=${encodeURIComponent(r[0])}`;
      tile.setAttribute('aria-label', say);
      if (w >= 72 && h >= 26) {
        const label = document.createElement('b');
        label.textContent = r[1];
        tile.append(label);
      }
    }
    return tile;
  });
  if (!tiles.length) {
    const empty = document.createElement('p');
    empty.className = 'meta';
    empty.textContent = 'No product here has a documentation count.';
    tiles.push(empty);
  }
  box.replaceChildren(...tiles);
  $('#tyPage').href = `/t/${now}/`;
  $('#tyNote').textContent =
    `${name}: ${n(listed)} listed, ${n(read)} read from their own pages; the ${n(top.length)} most widely documented are drawn. ${n(D.total - D.placed)} of ${n(D.total)} listed products carry no category yet and are not on any map. Area is documentation breadth, not market share.`;
}

export function mount() {
  const sel = $('#tyPick');
  if (!sel) return;
  fetch('t/map.json')
    .then(r => {
      if (!r.ok) throw new Error(r.status);
      return r.json();
    })
    .then(d => {
      D = d;
      if (!D.nodes[now]) now = Object.keys(D.nodes)[0];
      options();
      draw();
    })
    .catch(e => {
      console.error('type map:', e);
      $('#types').hidden = true;
    });
  sel.addEventListener('change', () => {
    now = sel.value;
    draw();
  });
  $('#tyMap').addEventListener('pointerover', e => {
    const t = e.target.closest('.tile');
    if (t) $('#tyInfo').textContent = t.getAttribute('title');
  });
  let t;
  if (window.ResizeObserver)
    new ResizeObserver(() => {
      clearTimeout(t);
      t = setTimeout(draw, 120);
    }).observe($('#tyMap'));
}
