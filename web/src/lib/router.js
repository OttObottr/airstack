// spec: AS-256 AS-260 AS-298 AS-343 AS-366
/* ---------- the app's views: one at a time, each a route in the hash (#/markets), with the tab for it marked current ----------
   Deep links keep working: #app=<id> opens the product in Overview, #tool=<id> opens a profile in Markets, #chain=<id> opens the evidence
   chain where you are. Old section anchors (#movers, #leaders, ...) land on the view that holds them. Back and forward move between views. */
export const VIEWS = {
  overview: 'Overview',
  compare: 'Compare',
  markets: 'Markets',
  insights: 'Insights',
  calendar: 'Calendar',
  makers: 'Makers',
  agents: 'Agents',
  how: 'How it works',
};
const LEGACY = {
  top: 'overview',
  check: 'overview',
  movers: 'markets',
  leaders: 'makers',
  brief: 'overview',
  insights: 'insights',
  agents: 'agents',
  market: 'how',
  life: 'how',
  detail: 'how',
  method: 'how',
  fineprint: 'how',
  news: 'overview',
};
const TITLE = 'AirStack — See the software market move.';
let view = null;

function viewOf(hash) {
  const h = hash || '';
  const m = /^#\/([a-z]*)/.exec(h);
  if (m) return VIEWS[m[1]] ? m[1] : 'overview';
  if (/^#compare=/.test(h)) return 'compare';
  if (/[#&](app|q|stack)=/.test(h)) return 'overview';
  if (/[#&]tool=/.test(h)) return 'markets';
  if (/[#&]chain=/.test(h)) return null; /* the chain opens over whatever view you are on */
  const a = /^#([\w-]+)$/.exec(h);
  return a ? LEGACY[a[1]] || null : 'overview';
}

export function show(v, { scroll = true } = {}) {
  if (!VIEWS[v] || v === view) return; /* already there: nothing to do (selecting a tool calls this every time) */
  const changed = true,
    was = view;
  view = v;
  document.body.dataset.view = v;
  for (const s of document.querySelectorAll('[data-views]'))
    s.classList.toggle('view-away', !s.dataset.views.split(' ').includes(v));
  let active = null;
  for (const a of document.querySelectorAll('.nav a[data-view]')) {
    if (a.dataset.view === v) {
      a.setAttribute('aria-current', 'page');
      active = a;
    } else a.removeAttribute('aria-current');
  }
  /* On a narrow screen the tabs scroll horizontally. Keep the route's current tab in view, including on a direct link. */
  if (active)
    requestAnimationFrame(() => {
      const nav = active.closest('.nav');
      if (nav) nav.scrollTo({ left: Math.max(0, active.offsetLeft - (nav.clientWidth - active.offsetWidth) / 2) });
    });
  document.title = v === 'overview' ? TITLE : `${VIEWS[v]} · ${TITLE}`;
  if (was) {
    const top = document.querySelector('[data-views]:not(.view-away)');
    if (top) {
      top.classList.remove('view-enter');
      requestAnimationFrame(() => !top.classList.contains('view-away') && top.classList.add('view-enter'));
    }
  }
  if (changed && scroll) scrollTo(0, 0);
  if (changed)
    dispatchEvent(
      new CustomEvent('airstack:view', { detail: v })
    ); /* views drawn while hidden (canvas, treemap) redraw at their real size */
}

export const here = () =>
  view && view !== 'overview' ? `#/${view}` : location.pathname + location.search; /* the current view's own address */

export function mount() {
  const go = () => {
    const v = viewOf(location.hash);
    if (v) show(v);
  };
  addEventListener('hashchange', go);
  go();
  if (!view) show('overview', { scroll: false });
}
