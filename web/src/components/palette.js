import { clearTool, selectTool } from './app.js';
import { drawTape } from './hero.js';
import { moverRows, q as searchBox, rank } from './search/index.js';
import { loadDir } from './search/directory.js';
import { M } from '../lib/data.js';
import { $ } from '../lib/dom.js';
import { esc, fd, sq as norm } from '../lib/format.js';
import { VIEWS, show } from '../lib/router.js';
import { stack } from '../lib/stack.js';

const GITHUB = 'https://github.com/OttObottr/airstack';
const click = sel => () => $(sel).click();
const shown = sel => {
  const el = $(sel);
  return !!el && !el.closest('[hidden]') && !el.hidden;
};
let onlyMine = false;
const COMMANDS = [
  {
    name: 'Change tool',
    when: () => shown('#change'),
    run: () => {
      clearTool();
    },
  },
  {
    name: 'Save this tool on this device',
    when: () => shown('#starBtn') && $('#starBtn').getAttribute('aria-pressed') !== 'true',
    run: click('#starBtn'),
  },
  {
    name: 'Remove this tool from this device',
    when: () => shown('#starBtn') && $('#starBtn').getAttribute('aria-pressed') === 'true',
    run: click('#starBtn'),
  },
  {
    name: 'Search products',
    when: () => true,
    run: () => {
      show('overview', { scroll: false });
      searchBox.focus();
    },
  },
  {
    name: 'Show only my tracked tools on the tape',
    when: () => !onlyMine,
    run: () => {
      onlyMine = drawTape(new Set(stack().map(x => x.id)), moverRows());
      if (!onlyMine) drawTape();
      $('#sr').textContent = onlyMine
        ? 'The tape shows your tracked tools.'
        : 'None of your tracked tools has a download figure yet; the tape is unchanged.';
    },
  },
  {
    name: 'Show every tool on the tape',
    when: () => onlyMine,
    run: () => {
      onlyMine = false;
      drawTape();
    },
  },
  { name: 'Open GitHub', when: () => true, run: () => window.open(GITHUB, '_blank', 'noopener,noreferrer') },
];
const GO = Object.entries(VIEWS).map(([v, name]) => ({
  name,
  run: () => (location.hash = v === 'overview' ? '#/' : `#/${v}`),
}));

const SOURCES = [
  ['Product pages read', () => M.meta && M.meta.checked_at],
  ['Download figures (built)', () => M.moversTop && M.moversTop.generated],
  ['Software directory (Wikidata)', () => M.dir && M.dir.fetched_at],
  ['Vendor news', () => json('news.json', j => j.source && j.source.read)],
  ['Calendar', () => json('events.json', j => j.source && j.source.built_for)],
  ['Open models (Hugging Face)', () => json('hf.json', j => j.source && j.source.fetched_at)],
  ['Open-source candidates (GitHub)', () => json('oss.json', j => j.source && j.source.fetched_at)],
];
const json = (file, pick) =>
  fetch(file)
    .then(r => (r.ok ? r.json() : null))
    .then(j => j && pick(j))
    .catch(() => null);

let dlg, input, list, items, act, opener, statusDone, chose;
const back = () => opener && opener.isConnected && opener.focus();

function build() {
  dlg = document.createElement('dialog');
  dlg.id = 'pal';
  dlg.setAttribute('aria-label', 'Jump to');
  dlg.setAttribute('aria-modal', 'true');
  dlg.innerHTML = `<div class="palin"><input id="palq" role="combobox" aria-label="Jump to a view, a product or a command" aria-expanded="true" aria-controls="pall" aria-autocomplete="list" autocomplete="off" spellcheck="false" autocapitalize="off" placeholder="Jump to a view, a product or a command"><button type="button" class="btn btn-secondary" id="palx">Close</button></div>
<ul id="pall" role="listbox" aria-label="Results"></ul>
<ul class="palbar" aria-label="Data sources, last read">${SOURCES.map(([name]) => `<li><span>${esc(name)}</span><span class="meta">…</span></li>`).join('')}</ul>`;
  document.body.append(dlg);
  input = $('#palq', dlg);
  list = $('#pall', dlg);
  input.addEventListener('input', () => {
    act = 0;
    draw();
  });
  input.addEventListener('keydown', e => {
    if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
      e.preventDefault();
      act = (act + (e.key === 'ArrowDown' ? 1 : -1) + items.length) % items.length;
      mark();
    } else if (e.key === 'Enter') {
      e.preventDefault();
      choose(act);
    }
  });
  list.addEventListener('click', e => {
    const li = e.target.closest('li[data-i]');
    if (li) choose(+li.dataset.i);
  });
  const x = $('#palx', dlg);
  x.addEventListener('click', () => dlg.close());
  dlg.addEventListener('keydown', e => {
    if (e.key === 'Tab') {
      e.preventDefault(); /* two controls: Tab and Shift-Tab swap between them */
      (document.activeElement === input ? x : input).focus();
    }
  });
  dlg.addEventListener('click', e => e.target === dlg && dlg.close()); /* a click on the dimmed page behind */
  dlg.addEventListener(
    'close',
    () => chose || back()
  );
}

function draw() {
  const k = norm(input.value),
    tag = (kind, xs) => xs.map(x => ({ ...x, kind })),
    match = name => !k || norm(name).includes(k),
    go = tag(
      'Views',
      GO.filter(x => match(x.name))
    ),
    cmd = tag(
      'Commands',
      COMMANDS.filter(x => x.when() && match(x.name))
    ),
    prods = k
      ? tag(
          'Products',
          rank(input.value).map(x => ({ name: x.name, hint: x.laneName, run: () => selectTool(x) }))
        )
      : [],
    named = [...go, ...cmd].filter(
      x => k && norm(x.name).includes(k)
    );
  items = [...named, ...prods, ...[...go, ...cmd].filter(x => !named.includes(x))];
  let kind = '';
  list.innerHTML = items.length
    ? items
        .map((x, i) => {
          const head = x.kind === kind ? '' : `<li role="presentation" class="tah">${(kind = x.kind)}</li>`;
          return `${head}<li role="option" id="pal${i}" data-i="${i}"><span>${esc(x.name)}</span>${x.hint ? `<span class="meta">${esc(x.hint)}</span>` : ''}</li>`;
        })
        .join('')
    : `<li class="none" role="option" aria-disabled="true">Nothing matches “${esc(input.value.trim().slice(0, 40))}”</li>`;
  mark();
}

function mark() {
  for (const li of list.querySelectorAll('li[data-i]')) li.setAttribute('aria-selected', String(+li.dataset.i === act));
  const cur = items.length && $(`#pal${act}`, list);
  if (cur) {
    input.setAttribute('aria-activedescendant', cur.id);
    cur.scrollIntoView({ block: 'nearest' });
  } else input.removeAttribute('aria-activedescendant');
}

function choose(i) {
  const x = items[i];
  if (!x) return;
  chose = true;
  dlg.close();
  back(); /* restore focus before the choice moves it */
  x.run();
}

function status() {
  if (statusDone) return;
  statusDone = true;
  SOURCES.forEach(([, read], i) =>
    Promise.resolve(read()).then(v => {
      const d = fd(v);
      $('.palbar', dlg).children[i].lastElementChild.textContent = d || 'Not observed';
    })
  );
}

export function open() {
  if (!dlg) build();
  if (dlg.open) return;
  opener = document.activeElement;
  chose = false;
  input.value = '';
  act = 0;
  draw();
  dlg.showModal();
  input.focus();
  loadDir().then(
    () => dlg.open && input.value && draw(),
    () => {}
  );
  status();
}
