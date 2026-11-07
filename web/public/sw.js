// spec: AS-121 AS-140 AS-248 AS-256
// Network-first: online you always get the latest page and data (never a stale fact); offline you get the last copy.
// Only an explicit allowlist of public static files is ever cached: API, auth and anything else on this origin is never stored.
const VERSION = 'airstack-v16';
const MODULES = [];                                                                // the page's ES modules: tools/assemble.sh writes the list in, so a first visit works offline
const CORE = ['./', 'site-data.js','market-data.js', 'manifest.webmanifest', 'fonts/Inter-latin.woff2', 'icons/icon-192.png', ...MODULES];
const CACHEABLE = p => p === '/' || /^\/(index\.html|src\/[\w\/.-]+\.js|site-data\.js|market-data\.js|chain-data\.json|directory\.json|profiles\.json|pricing\.json|oss\.json|insights\.json|hf\.json|category-guides\.json|freshness\.json|news\.json|events\.json|manifest\.webmanifest|robots\.txt|sitemap\.xml|llms\.txt|fonts\/[\w.-]+\.woff2|icons\/[\w.-]+\.(png|svg))$/.test(p);
self.addEventListener('install', e => e.waitUntil(caches.open(VERSION).then(c => c.addAll(CORE)).then(() => self.skipWaiting())));
self.addEventListener('activate', e => e.waitUntil(caches.keys().then(ks => Promise.all(ks.filter(k => k !== VERSION).map(k => caches.delete(k)))).then(() => self.clients.claim())));
self.addEventListener('fetch', e => {
  const r = e.request, u = new URL(r.url);
  if (r.method !== 'GET' || u.origin !== location.origin || !CACHEABLE(u.pathname)) return;
  e.respondWith(fetch(r).then(res => { if (res.ok) { const copy = res.clone(); caches.open(VERSION).then(c => c.put(r, copy)); } return res; })
    .catch(() => caches.match(r).then(m => m || caches.match('./'))));
});
