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
});

// Main thread can also trigger a check by posting { type: 'CHECK_BUNDLE' }
self.addEventListener('message', e => {
  if (e.data?.type === 'CHECK_BUNDLE') checkForNewBundle();
});

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
