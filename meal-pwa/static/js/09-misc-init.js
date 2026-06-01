// ── Global keyboard / backdrop handlers ─────────────────────────

document.getElementById('rating-overlay').addEventListener('click', e => {
  if (e.target === document.getElementById('rating-overlay')) closeRatingOverlay();
});

document.addEventListener('keydown', e => {
  if (e.key !== 'Escape') return;
  if (document.getElementById('picker-overlay').classList.contains('active'))  { closePicker();          return; }
  if (document.getElementById('builder-overlay').classList.contains('active')) { closeBuilder();         return; }
  if (document.getElementById('cook-mode').classList.contains('active'))       { _exitCookMode();        return; }
  if (document.getElementById('rating-overlay').classList.contains('active'))  { closeRatingOverlay();   return; }
  if (document.getElementById('nav-menu-sheet').classList.contains('active'))  { closeNavMenu();         return; }
  if (document.getElementById('settings-sheet').classList.contains('active'))  { closeSettings();        return; }
  if (document.getElementById('bundle-sheet').classList.contains('active'))    { closeBundleSheet();     return; }
  if (document.getElementById('enhance-sheet').classList.contains('active'))   { closeEnhancements();    return; }
  const pantryConfirm = document.getElementById('pantry-confirm-sheet');
  if (pantryConfirm && pantryConfirm.classList.contains('active'))             { closePantryConfirm();   return; }
});

// ── Swipe-to-dismiss for bottom sheets ──────────────────────────
(function attachSheetSwipe() {
  const DISMISS_THRESHOLD = 80; // px downward drag to dismiss
  document.querySelectorAll('.bottom-sheet').forEach(sheet => {
    let startY = 0, currentY = 0, dragging = false;
    const onStart = e => {
      if (!sheet.classList.contains('active')) return;
      startY = (e.touches ? e.touches[0] : e).clientY;
      currentY = startY;
      dragging = true;
      sheet.style.transition = 'none';
    };
    const onMove = e => {
      if (!dragging) return;
      currentY = (e.touches ? e.touches[0] : e).clientY;
      const dy = Math.max(0, currentY - startY);
      sheet.style.transform = `translateY(${dy}px)`;
    };
    const onEnd = () => {
      if (!dragging) return;
      dragging = false;
      sheet.style.transition = '';
      sheet.style.transform = '';
      if (currentY - startY > DISMISS_THRESHOLD) {
        // Find and click the matching backdrop to trigger close
        const backdropId = sheet.id.replace('-sheet', '-backdrop');
        const backdrop = document.getElementById(backdropId);
        if (backdrop) backdrop.click();
        else if (sheet.id === 'settings-sheet') closeSettings();
        else if (sheet.id === 'bundle-sheet')   closeBundleSheet();
        else if (sheet.id === 'enhance-sheet')  closeEnhancements();
      }
    };
    sheet.addEventListener('touchstart', onStart, { passive: true });
    sheet.addEventListener('touchmove',  onMove,  { passive: true });
    sheet.addEventListener('touchend',   onEnd);
  });
})();

// ── Plan generation ──────────────────────────────────────────────

let _generating = false;

async function generatePlan() {
  if (_generating) return;
  // Once a week, confirm the pantry before building a plan so the shopping
  // list leaves out what's already at home. After it's been confirmed this
  // week, skip straight to generating.
  if (!_pantryConfirmedThisWeek()) {
    await openPantryConfirm();
    return;
  }
  await _runGeneration();
}

async function _runGeneration() {
  if (_generating) return;
  _generating = true;

  const fab = document.getElementById('tab-fab');
  if (fab) { fab.classList.add('fab--spinning'); fab.disabled = true; }

  const _steps = ['Checking prices', 'Selecting meals', 'Building plan'];
  const statusEl = document.getElementById('generate-status');
  let _stepIdx = 0;

  function _showStep(i) {
    if (!statusEl) return;
    statusEl.style.display = 'block';
    statusEl.innerHTML = _steps.map((s, j) =>
      `<span class="gen-step ${j < i ? 'gen-step--done' : j === i ? 'gen-step--active' : ''}">${s}</span>`
    ).join('<span class="gen-sep">›</span>');
  }

  _showStep(0);
  const t1 = setTimeout(() => _showStep(1), 1500);
  const t2 = setTimeout(() => _showStep(2), 3200);

  try {
    const result = await apiPost('/plan/generate');
    clearTimeout(t1); clearTimeout(t2);
    if (statusEl) statusEl.style.display = 'none';
    await notifyNewPlan({ week: result.week });
    await loadWeek();
    await loadRecipes();
    await loadShopping();
    showToast(`Plan ready · ${result.recipeCount || plan?.recipes?.length || 5} meals · ${fmt$(result.estimatedTotal || plan?.estimatedTotal || 0)} est.`, 3000);
  } catch (e) {
    clearTimeout(t1); clearTimeout(t2);
    if (statusEl) {
      statusEl.style.display = 'block';
      statusEl.innerHTML = `<span class="gen-error">Generation failed — <button class="gen-retry-btn" onclick="generatePlan()">Try again</button></span>`;
    }
    log('GENERATE', 'Error', { error: e.message });
  } finally {
    _generating = false;
    if (fab) { fab.classList.remove('fab--spinning'); fab.disabled = false; }
  }
}

// ── Weekly pantry confirmation ───────────────────────────────────
// Shown before the first generation of each ISO week. The pantry feeds the
// shopping total (owned items are dropped), so confirming it keeps the list
// honest without nagging on every generate.

let _pantryUnchecked = new Set();

function _isoWeekKey(d = new Date()) {
  // ISO-8601 week (YYYY-Www) — lines "once a week" up with the Mon-start plan week.
  const dt = new Date(Date.UTC(d.getFullYear(), d.getMonth(), d.getDate()));
  const day = dt.getUTCDay() || 7;
  dt.setUTCDate(dt.getUTCDate() + 4 - day);
  const yearStart = new Date(Date.UTC(dt.getUTCFullYear(), 0, 1));
  const week = Math.ceil((((dt - yearStart) / 86400000) + 1) / 7);
  return `${dt.getUTCFullYear()}-W${String(week).padStart(2, '0')}`;
}

function _pantryConfirmedThisWeek() {
  return localStorage.getItem('pantryConfirmedWeek') === _isoWeekKey();
}

async function openPantryConfirm() {
  // Pull the latest household pantry so the list is current before confirming.
  try { await loadPantry(); } catch { /* offline — use what we have */ }
  _pantryUnchecked = new Set();
  renderPantryConfirmList();
  renderPantrySuggestions();   // theme staples you haven't added yet
  const input = document.getElementById('pantry-confirm-input');
  if (input) input.value = '';
  document.getElementById('pantry-confirm-backdrop').classList.add('active');
  document.getElementById('pantry-confirm-sheet').classList.add('active');
}

// Theme-driven staples the household hasn't added yet — one-tap to add. Keeps
// the weekly check useful even when the pantry is sparse.
async function renderPantrySuggestions() {
  const el = document.getElementById('pantry-confirm-suggested');
  if (!el) return;
  el.innerHTML = '';
  let suggestions = [];
  try {
    const data = await apiFetch('/pantry/suggestions');   // uses saved themes
    suggestions = (data.suggestions || []).filter(s => !s.inPantry);
  } catch (_) { return; }
  if (!suggestions.length) return;
  el.innerHTML = `
    <div class="pantry-suggested-label">Suggested for your cuisines</div>
    <div class="pantry-suggested-chips">
      ${suggestions.map(s => `
        <button type="button" class="pantry-suggested-chip" data-canonical="${_esc(s.canonical)}"
                onclick="addSuggestedPantryItem(this, '${_esc(s.name).replace(/'/g, "\\'")}', '${_esc(s.canonical)}')">
          + ${_esc(s.name)}
        </button>`).join('')}
    </div>`;
}

function addSuggestedPantryItem(btn, name, canonical) {
  if (pantry.some(p => p.canonical === canonical)) return;
  pantry = [...pantry, { name, canonical }];
  savePantry();
  _pantryUnchecked.delete(canonical);
  btn.classList.add('added');
  btn.disabled = true;
  renderPantryConfirmList();
  apiFetch('/pantry/', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name, canonical }),
  }).catch(() => {});
}

function closePantryConfirm() {
  document.getElementById('pantry-confirm-backdrop').classList.remove('active');
  document.getElementById('pantry-confirm-sheet').classList.remove('active');
}

function renderPantryConfirmList() {
  const list = document.getElementById('pantry-confirm-list');
  if (!list) return;
  if (!pantry.length) {
    list.innerHTML = `<div class="pantry-confirm-empty">No pantry items yet. Add staples you always have (salt, oil, rice…) so they stay off your shopping list.</div>`;
    return;
  }
  list.innerHTML = pantry.map((item, i) => {
    const checked = !_pantryUnchecked.has(item.canonical);
    return `
      <label class="pantry-confirm-item${checked ? '' : ' pantry-confirm-item--off'}">
        <input type="checkbox" ${checked ? 'checked' : ''} onchange="togglePantryConfirmItem(${i})">
        <span class="pantry-confirm-box" aria-hidden="true"></span>
        <span class="pantry-confirm-name">${_esc(item.name)}</span>
      </label>`;
  }).join('');
}

function togglePantryConfirmItem(i) {
  const item = pantry[i];
  if (!item) return;
  if (_pantryUnchecked.has(item.canonical)) _pantryUnchecked.delete(item.canonical);
  else _pantryUnchecked.add(item.canonical);
  renderPantryConfirmList();
}

function addPantryConfirmItem() {
  const input     = document.getElementById('pantry-confirm-input');
  const val       = input.value.trim();
  const canonical = val.toLowerCase();
  if (!val || pantry.some(p => p.canonical === canonical)) { input.value = ''; return; }
  pantry = [...pantry, { name: val, canonical }];
  savePantry();
  input.value = '';
  _pantryUnchecked.delete(canonical);
  renderPantryConfirmList();
  apiFetch('/pantry/', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name: val, canonical }),
  }).catch(() => {});
}

async function confirmPantryAndGenerate() {
  // Apply any items the user unticked (they no longer have them), then build.
  const removals = pantry.filter(p => _pantryUnchecked.has(p.canonical));
  if (removals.length) {
    pantry = pantry.filter(p => !_pantryUnchecked.has(p.canonical));
    savePantry();
    renderPantryTags();
    for (const r of removals) {
      apiFetch(`/pantry/${encodeURIComponent(r.canonical)}`, { method: 'DELETE' }).catch(() => {});
    }
  }
  _pantryUnchecked = new Set();
  localStorage.setItem('pantryConfirmedWeek', _isoWeekKey());
  closePantryConfirm();
  await _runGeneration();
}

function skipPantryConfirm() {
  // Don't ask again this week; generate without touching the pantry.
  localStorage.setItem('pantryConfirmedWeek', _isoWeekKey());
  closePantryConfirm();
  _runGeneration();
}

(function _wirePantryConfirm() {
  const btn = document.getElementById('pantry-confirm-add-btn');
  const input = document.getElementById('pantry-confirm-input');
  if (btn) btn.onclick = addPantryConfirmItem;
  if (input) input.addEventListener('keydown', e => {
    if (e.key === 'Enter') addPantryConfirmItem();
  });
})();

// ── Notifications ────────────────────────────────────────────────

async function notifyNewPlan(planData) {
  if (!('Notification' in window) || Notification.permission !== 'granted') return;
  const body = `Your plan for week of ${fmtWeek(planData.week)} is ready.`;
  const opts = { body, icon: '/icon-192.png', tag: 'new-plan', data: { url: '/' } };

  // Prefer SW notification — persists and handled by sw.js notificationclick
  const swReg = await navigator.serviceWorker?.getRegistration?.().catch(() => null);
  if (swReg) {
    await swReg.showNotification('New meal plan ready', opts).catch(() => null);
  } else {
    const n = new Notification('New meal plan ready', opts);
    n.onclick = () => { window.focus(); n.close(); };
  }
}

function showNotificationBanner() {
  if (!('Notification' in window)) return;
  if (Notification.permission !== 'default') return;
  if (localStorage.getItem('notifPromptDismissed')) return;
  const banner = document.getElementById('notification-banner');
  if (banner) banner.style.display = 'flex';
}

async function requestNotificationPermission() {
  dismissNotificationBanner();
  const result = await Notification.requestPermission();
  log('NOTIFICATIONS', 'Permission', { result });
  // Persist deny so we never prompt again
  if (result === 'denied') localStorage.setItem('notifPromptDismissed', '1');
}

function dismissNotificationBanner() {
  const banner = document.getElementById('notification-banner');
  if (banner) banner.style.display = 'none';
  localStorage.setItem('notifPromptDismissed', '1');
}

async function registerServiceWorker() {
  if (!('serviceWorker' in navigator)) return;
  try {
    const reg = await navigator.serviceWorker.register('/sw.js');
    log('SW', 'Registered', { scope: reg.scope });
    if ('periodicSync' in reg) {
      const status = await navigator.permissions.query({ name: 'periodic-background-sync' });
      if (status.state === 'granted') {
        const interval = 6 * 60 * 60 * 1000;
        await reg.periodicSync.register('check-new-bundle', { minInterval: interval });
        await reg.periodicSync.register('check-new-prices', { minInterval: interval });
        log('SW', 'Periodic syncs registered');
      }
    }
  } catch (e) {
    log('SW', 'Registration failed', { error: e.message });
  }
}

// ══════════════════════════════════════════════════════════════
// MEAL ENHANCEMENTS (MEA-51)
// ══════════════════════════════════════════════════════════════

async function openEnhancements() {
  if (!_detailRecipeId) return;
  const content = document.getElementById('enhance-content');
  content.innerHTML = '<div class="sub-loading">Loading enhancements…</div>';
  document.getElementById('enhance-backdrop').classList.add('active');
  document.getElementById('enhance-sheet').classList.add('active');

  try {
    const data = await apiFetch(`/enhancements/for-recipe/${_detailRecipeId}`);
    const items = data.enhancements || [];
    if (!items.length) {
      content.innerHTML = '<div class="sub-loading">No enhancements found for this meal.</div>';
      return;
    }
    content.innerHTML = items.map(e => `
      <div class="enhance-card">
        <div class="enhance-card-header">
          <div class="enhance-name">${_esc(e.name)}</div>
          <div class="enhance-cost">${fmt$(e.estimatedCost)}</div>
        </div>
        <div class="enhance-desc">${_esc(e.description)}</div>
        <div class="enhance-ingredients">
          ${(e.ingredients || []).map(i => `<span class="enhance-tag">${_esc(i.name)} · ${_esc(i.amount)}</span>`).join('')}
        </div>
      </div>`).join('');
  } catch (err) {
    log('ENHANCEMENTS', 'Error loading', { error: err.message });
    content.innerHTML = '<div class="sub-loading">Could not load enhancements.</div>';
  }
}

function closeEnhancements() {
  document.getElementById('enhance-backdrop').classList.remove('active');
  document.getElementById('enhance-sheet').classList.remove('active');
}

// ── Capacitor deep links ─────────────────────────────────────────
// When the Android app is opened via kaiplannerapp://?tab=shopping ,
// Capacitor fires appUrlOpen before the page navigates. Token-based
// (magic link) auth has been removed — only in-app navigation is handled.
if (window.Capacitor?.isNativePlatform?.()) {
  document.addEventListener('deviceready', () => {
    window.Capacitor.Plugins.App.addListener('appUrlOpen', async (data) => {
      const url = data?.url;
      if (!url) return;
      try {
        const parsed = new URL(url);
        // kaiplannerapp://?tab=shopping
        const tab = parsed.searchParams.get('tab');
        if (tab) switchTab(tab);
      } catch (_) {}
    });
  });
}

// ── Pull-to-refresh ──────────────────────────────────────────────
(function _initPullToRefresh() {
  const THRESHOLD = 64;
  let startY = 0, pulling = false, indicator = null;

  function _getIndicator() {
    if (!indicator) {
      indicator = document.createElement('div');
      indicator.className = 'ptr-indicator';
      indicator.innerHTML = '<div class="ptr-spinner"></div>';
      document.querySelector('main').prepend(indicator);
    }
    return indicator;
  }

  document.querySelector('main').addEventListener('touchstart', e => {
    const main = document.querySelector('main');
    if (main.scrollTop === 0) {
      startY = e.touches[0].clientY;
      pulling = true;
    }
  }, { passive: true });

  document.querySelector('main').addEventListener('touchmove', e => {
    if (!pulling) return;
    const dy = e.touches[0].clientY - startY;
    if (dy > 0) {
      const el = _getIndicator();
      const progress = Math.min(dy / THRESHOLD, 1);
      el.style.transform = `translateY(${Math.min(dy * 0.4, 48)}px)`;
      el.style.opacity   = String(progress);
    }
  }, { passive: true });

  document.querySelector('main').addEventListener('touchend', async e => {
    if (!pulling) return;
    pulling = false;
    const dy = e.changedTouches[0].clientY - startY;
    const el = _getIndicator();
    el.style.transform = '';
    el.style.opacity   = '0';
    if (dy > THRESHOLD) {
      el.classList.add('ptr-indicator--loading');
      el.style.opacity = '1';
      if (_currentTab === 'week')     await loadWeek();
      else if (_currentTab === 'shopping') await loadShopping();
      else if (_currentTab === 'recipes')  await loadRecipes();
      el.classList.remove('ptr-indicator--loading');
      el.style.opacity = '0';
    }
  }, { passive: true });
})();

// ── Init ────────────────────────────────────────────────────────
window.addEventListener('popstate', () => {
  const p = window.location.pathname;
  if (['/login', '/register', '/forgot-password', '/reset-password'].includes(p)) {
    _routeAuth(p);
  }
});

(async () => {
  localStorage.removeItem('viewingBundleId'); // clear any stale viewing state from old builds
  await initAuth();
  loadPantry();
  await loadSettings();
  await loadWeek();
  loadRecipes();
  loadShopping();
  registerServiceWorker();
  _updateFab('week');

  const urlTab = new URLSearchParams(window.location.search).get('tab');
  if (urlTab) switchTab(urlTab);
})();
