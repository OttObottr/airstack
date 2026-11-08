// network-first; the shell, its modules, the published datasets and static assets are cached
const VERSION = 'airstack-v18';
const CORE = ['./', 'manifest.webmanifest', 'fonts/Inter-latin.woff2', 'icons/icon-192.png'];
const CACHEABLE = p => p === '/' || /^\/(index\.html|src\/[\w\/.-]+\.js|[\w-]+\.(js|json|webmanifest|txt|xml)|fonts\/[\w.-]+\.woff2|icons\/[\w.-]+\.(png|svg))$/.test(p);
self.addEventListener('install', e => e.waitUntil(caches.open(VERSION).then(c => c.addAll(CORE)).then(() => self.skipWaiting())));
self.addEventListener('activate', e => e.waitUntil(caches.keys().then(ks => Promise.all(ks.filter(k => k !== VERSION).map(k => caches.delete(k)))).then(() => self.clients.claim())));
self.addEventListener('fetch', e => {
  const r = e.request, u = new URL(r.url);
  if (r.method !== 'GET' || u.origin !== location.origin || !CACHEABLE(u.pathname)) return;
  e.respondWith(fetch(r).then(res => { if (res.ok) { const copy = res.clone(); caches.open(VERSION).then(c => c.put(r, copy)); } return res; })
    .catch(() => caches.match(r).then(m => m || caches.match('./'))));
});
