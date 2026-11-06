// 诗词 service worker: cache-first for immutable data/fonts, network-first for the app shell.
const SHELL = 'shici-shell-v40', DATA = 'shici-data-v17', MAX = 900;
self.addEventListener('install', e => { e.waitUntil(caches.open(SHELL).then(c => c.addAll(['/', '/app.js?v=39', '/app.css?v=19', '/fonts/fonts.css'])).catch(() => {})); self.skipWaiting(); });
self.addEventListener('activate', e => { e.waitUntil(caches.keys().then(ks => Promise.all(ks.filter(k => k !== SHELL && k !== DATA).map(k => caches.delete(k)))).then(() => self.clients.claim())); });
async function trim() { const c = await caches.open(DATA); const ks = await c.keys(); for (let i = 0; i < ks.length - MAX; i++) await c.delete(ks[i]); }
self.addEventListener('fetch', e => {
  const u = new URL(e.request.url);
  if (e.request.method !== 'GET' || u.origin !== location.origin || u.pathname.startsWith('/api/')) return;
  if (/^\/(data|fonts|vendor)\//.test(u.pathname)) {
    e.respondWith(caches.open(DATA).then(async c => {
      const hit = await c.match(e.request); if (hit) return hit;
      const r = await fetch(e.request); if (r.ok) { c.put(e.request, r.clone()); if (Math.random() < 0.05) trim(); } return r;
    }));
    return;
  }
  e.respondWith(fetch(e.request).then(r => { if (r.ok) { const cl = r.clone(); caches.open(SHELL).then(c => c.put(e.request, cl)); } return r; })
    .catch(() => caches.match(e.request).then(m => m || caches.match('/'))));
});
