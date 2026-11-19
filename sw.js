// Offline support. Bump VERSION on every release so phones pick up the update.
const VERSION = 'v23';
const CACHE = 'lava-leap-' + VERSION;
const CORE = ['./', './index.html', './manifest.webmanifest',
  './icons/apple-touch-icon.png', './icons/icon-192.png', './icons/icon-512.png'];

self.addEventListener('install', e => {
  e.waitUntil(caches.open(CACHE).then(c => c.addAll(CORE.map(u => new Request(u, { cache: 'no-cache' })))).then(() => self.skipWaiting()));
  // Voice clips for offline play (best effort: a missing clip is just skipped).
  e.waitUntil(caches.open(CACHE).then(c => fetch('./audio/voice.json').then(r => r.ok ? r.clone().json().then(j => {
    c.put('./audio/voice.json', r);
    return Promise.all([...new Set(Object.values(j.clips || {}))].map(f => caches.match('./audio/' + f).then(hit => hit ? c.put('./audio/' + f, hit) : c.add('./audio/' + f).catch(() => {}))));
  }) : null)).catch(() => {}));
});

self.addEventListener('activate', e => {
  e.waitUntil(caches.keys()
    .then(keys => Promise.all(keys.filter(k => k.startsWith('lava-leap-') && k !== CACHE).map(k => caches.delete(k))))
    .then(() => self.clients.claim()));
});

self.addEventListener('fetch', e => {
  const req = e.request;
  if (req.method !== 'GET') return;
  const url = new URL(req.url);
  // Page: network first (skipping the browser's HTTP cache) so updates show up, cache when offline.
  if (req.mode === 'navigate') {
    e.respondWith(fetch(req.url, { cache: 'no-cache' }).then(res => {
      if (res.ok) { const copy = res.clone(); caches.open(CACHE).then(c => c.put('./index.html', copy)); }
      return res;
    }).catch(() => caches.match('./index.html')));
    return;
  }
  // Voice list: network first so a new week's clips are picked up, cache when offline.
  if (url.origin === location.origin && url.pathname.endsWith('/audio/voice.json')) {
    e.respondWith(fetch(req, { cache: 'no-cache' }).then(res => {
      if (res.ok) { const copy = res.clone(); caches.open(CACHE).then(c => c.put(req, copy)); }
      return res;
    }).catch(() => caches.match(req, { ignoreSearch: true })));
    return;
  }
  // Fonts and own files (voice clips too: their names change when the audio does): cache first, fill cache on first use.
  if (url.origin === location.origin || /fonts\.(googleapis|gstatic)\.com$/.test(url.hostname)) {
    e.respondWith(caches.match(req).then(hit => hit || fetch(req).then(res => {
      if (res.ok || res.type === 'opaque') { const copy = res.clone(); caches.open(CACHE).then(c => c.put(req, copy)); }
      return res;
    })));
  }
});
