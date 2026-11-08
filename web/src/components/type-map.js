import { $ } from '../lib/dom.js';
import { esc, n } from '../lib/format.js';
import { squarify } from '../lib/treemap.js';

let D = null,
  now = 'consumer';
const kids = id => Object.entries(D.nodes).filter(([, v]) => v[1] === id);

function options() {
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
  box.setAttribute('aria-busy', 'false');
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
      $('#tyMap').setAttribute('aria-busy', 'false');
      $('#tyMap').innerHTML =
        '<p class="load-error" role="status">The category map could not be loaded. Check the connection and reload.</p>';
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
