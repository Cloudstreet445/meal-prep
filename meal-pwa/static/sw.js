const SW_CACHE = 'meal-prep-sw';
const BUNDLE_KEY = '/sw/last-bundle-id';

self.addEventListener('install', () => self.skipWaiting());
self.addEventListener('activate', e => e.waitUntil(clients.claim()));

self.addEventListener('notificationclick', e => {
  e.notification.close();
  const target = e.notification.data?.url || '/';
  e.waitUntil(
    clients.matchAll({ type: 'window', includeUncontrolled: true }).then(list => {
      const existing = list.find(c => 'focus' in c);
      if (existing) return existing.focus();
      return clients.openWindow(target);
    })
  );
});

// Periodic Background Sync — fires when browser schedules it (installed PWA, Chrome/Android)
self.addEventListener('periodicsync', e => {
  if (e.tag === 'check-new-bundle') e.waitUntil(checkForNewBundle());
  if (e.tag === 'check-new-prices') e.waitUntil(checkForNewPrices());
});

// Main thread can also trigger checks by posting message types
self.addEventListener('message', e => {
  if (e.data?.type === 'CHECK_BUNDLE') checkForNewBundle();
  if (e.data?.type === 'CHECK_PRICES') checkForNewPrices();
});

// ── IndexedDB helpers ────────────────────────────────────────────

function _openIDB() {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open('meal-prep-idb', 1);
    req.onupgradeneeded = e => e.target.result.createObjectStore('kv', { keyPath: 'key' });
    req.onsuccess = e => resolve(e.target.result);
    req.onerror   = e => reject(e.target.error);
  });
}

async function _idbGet(key) {
  const db = await _openIDB();
  return new Promise((resolve, reject) => {
    const tx  = db.transaction('kv', 'readonly');
    const req = tx.objectStore('kv').get(key);
    req.onsuccess = e => resolve(e.target.result?.value ?? null);
    req.onerror   = e => reject(e.target.error);
  });
}

async function _idbSet(key, value) {
  const db = await _openIDB();
  return new Promise((resolve, reject) => {
    const tx = db.transaction('kv', 'readwrite');
    tx.objectStore('kv').put({ key, value });
    tx.oncomplete = () => resolve();
    tx.onerror    = e => reject(e.target.error);
  });
}

// ── Check for new bundle ─────────────────────────────────────────

async function checkForNewBundle() {
  try {
    const res = await fetch('/api/bundle/latest');
    if (!res.ok) return;
    const data = await res.json();
    const bundleId = data.bundleId;
    if (!bundleId) return;

    const cache = await caches.open(SW_CACHE);
    const stored = await cache.match(BUNDLE_KEY);
    const lastBundleId = stored ? await stored.text() : null;

    if (lastBundleId && bundleId !== lastBundleId) {
      await self.registration.showNotification('New meal plan ready', {
        body: `Your plan for week of ${data.week} is ready to view.`,
        icon: '/icon-192.png',
        data: { url: '/' },
        tag: 'new-bundle',
      });
    }

    await cache.put(BUNDLE_KEY, new Response(bundleId));
  } catch {
    // API unreachable — skip silently
  }
}

// ── Check for new prices (scrape timestamp) ──────────────────────

async function checkForNewPrices() {
  try {
    // Don't notify when app is in the foreground
    const allClients = await clients.matchAll({ type: 'window', includeUncontrolled: true });
    if (allClients.some(c => c.visibilityState === 'visible')) return;

    const res = await fetch('/api/shopping/latest');
    if (!res.ok) return;
    const data = await res.json();
    const scrapedAt = data.scrapedAt;
    if (!scrapedAt) return;

    const lastScrapedAt = await _idbGet('lastScrapedAt');

    if (lastScrapedAt && scrapedAt !== lastScrapedAt) {
      await self.registration.showNotification('New specials available', {
        body: 'Your shopping list has been updated with the latest prices.',
        icon: '/icon-192.png',
        data: { url: '/?tab=shopping' },
        tag: 'new-prices',
      });
    }

    await _idbSet('lastScrapedAt', scrapedAt);
  } catch {
    // API unreachable — skip silently
  }
}
