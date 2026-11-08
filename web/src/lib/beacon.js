export const PLAIN = /^[\p{L}\p{N} .+#&'-]{2,40}$/u;
const HOST = /^(?=.{3,100}$)[a-z0-9-]+(\.[a-z0-9-]+)+$/;
const CLICKS = [
  ['[data-copy="#agCli"]', 'mcp', { act: 'copy_command' }],
  ['[data-copy="#agJson"]', 'mcp', { act: 'copy_config' }],
  ['a[href$="docs/MCP.md"]', 'mcp', { act: 'open_guide' }],
  ['#stackShare', 'export', { what: 'stack_link' }],
  ['a[href="/open-data/"]', 'export', { what: 'open_data' }],
];

export const quiet = () => navigator.globalPrivacyControl === true || navigator.doNotTrack === '1' || globalThis.doNotTrack === '1';

export function send(t, f = {}) {
  if (quiet() || typeof navigator.sendBeacon !== 'function') return false;
  if (t === 'search' && (!PLAIN.test(f.q) || (f.q.match(/\d/g) || []).length > 3)) return false;
  try {
    return navigator.sendBeacon('/e', JSON.stringify({ t, ...f }));
  } catch {
    return false;
  }
}

const watch = (type, fn, o = {}) => {
  try {
    new PerformanceObserver(l => l.getEntries().forEach(fn)).observe({ type, buffered: true, ...o });
  } catch {}
};

export function mount(size = () => 0) {
  let first = true;
  addEventListener('airstack:view', ({ detail: route }) => {
    const f = { route };
    if (first) {
      first = false;
      f.size = Math.min(size(), 100);
      try {
        const r = new URL(document.referrer).hostname.toLowerCase().replace(/^www\./, '');
        if (r !== location.hostname && HOST.test(r)) f.ref = r;
      } catch {}
    }
    send('view', f);
  });
  document.addEventListener('click', e => {
    const hit = e.target.closest && CLICKS.find(([s]) => e.target.closest(s));
    if (hit) send(hit[1], hit[2]);
  });
  let lcp, inp, cls = 0, win = 0, last = 0, start = 0, done = false;
  watch('largest-contentful-paint', e => (lcp = e.startTime));
  watch('event', e => e.interactionId && (inp = Math.max(inp || 0, e.duration)), { durationThreshold: 40 });
  watch('layout-shift', e => {
    if (e.hadRecentInput) return;
    if (e.startTime - last > 1000 || e.startTime - start > 5000) (win = 0), (start = e.startTime);
    win += e.value;
    last = e.startTime;
    cls = Math.max(cls, win);
  });
  addEventListener('visibilitychange', () => {
    if (done || document.visibilityState !== 'hidden' || lcp === undefined) return;
    done = true;
    const ms = v => Math.min(Math.round(v), 60000);
    send('vitals', { lcp: ms(lcp), ...(inp !== undefined && { inp: ms(inp) }), cls: Math.min(Math.round(cls * 1000), 10000) });
  });
}
