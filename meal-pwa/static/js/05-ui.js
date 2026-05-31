// ── Fetch helpers ───────────────────────────────────────────────
async function apiFetch(path, opts = {}) {
  const { method = 'GET', body, params } = opts;
  let url = `${API}${path}`;
  if (params) url += '?' + new URLSearchParams(params).toString();
  log('FETCH', `${method} ${url}`);
  const fetchOpts = { method, credentials: 'include' };
  if (body !== undefined) {
    fetchOpts.headers = { 'Content-Type': 'application/json' };
    fetchOpts.body = typeof body === 'string' ? body : JSON.stringify(body);
  }
  const res = await fetch(url, fetchOpts);
  if (res.status === 401) {
    // Session expired or revoked — redirect to login
    currentUser = null;
    _setLogoutVisible(false);
    window.history.pushState({}, '', '/login');
    _routeAuth('/login');
    throw new Error('Not authenticated');
  }
  if (!res.ok) throw new Error(`HTTP ${res.status}: ${res.statusText} (${url})`);
  return res.json();
}

async function apiPost(path, body = null, method = 'POST') {
  return apiFetch(path, { method, body });
}

// ── Tab switching ───────────────────────────────────────────────
let _currentTab = 'week';

function _updateFab(view) {
  const fab = document.getElementById('tab-fab');
  if (!fab) return;
  const icon = document.getElementById('fab-icon');
  if (view === 'week') {
    fab.style.display = '';
    fab.setAttribute('aria-label', 'Generate plan');
    if (icon) icon.innerHTML = `<path d="M12 5v14M5 12h14"/>`;
  } else if (view === 'shopping') {
    fab.style.display = '';
    fab.setAttribute('aria-label', 'Add item');
    if (icon) icon.innerHTML = `<path d="M12 5v14M5 12h14"/>`;
  } else {
    fab.style.display = 'none'; // recipes, pantry, others
  }
}

function fabAction() {
  if (_currentTab === 'week') generatePlan();
  else if (_currentTab === 'shopping') focusAdHocInput();
}

function focusAdHocInput() {
  const input = document.getElementById('shop-adhoc-input');
  if (input) input.focus();
}

document.querySelectorAll('.tab').forEach(tab => {
  tab.addEventListener('click', () => {
    document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('.view').forEach(v => v.classList.remove('active'));
    tab.classList.add('active');
    _currentTab = tab.dataset.view;
    document.getElementById(`view-${tab.dataset.view}`).classList.add('active');
    if (tab.dataset.view === 'recipes') renderWeekRecipesInTab();
    if (tab.dataset.view === 'pantry') renderPantryView();
    _updateFab(tab.dataset.view);
  });
});

function switchTab(name) {
  const tab = document.querySelector(`.tab[data-view="${name}"]`);
  if (tab) tab.click();
}

// ── Toast ────────────────────────────────────────────────────────
let _toastTimer = null;
function showToast(msg, durationMs = 2800) {
  const el = document.getElementById('toast');
  if (!el) return;
  el.textContent = msg;
  el.classList.add('toast-visible');
  clearTimeout(_toastTimer);
  _toastTimer = setTimeout(() => el.classList.remove('toast-visible'), durationMs);
}

// ── Empty & error states ─────────────────────────────────────────
const _SVG_CALENDAR = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="4" width="18" height="18" rx="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/><rect x="7" y="14" width="3" height="3" rx="0.5"/><rect x="14" y="14" width="3" height="3" rx="0.5"/></svg>`;
const _SVG_BAG      = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M6 2L3 6v14a2 2 0 002 2h14a2 2 0 002-2V6l-3-4z"/><line x1="3" y1="6" x2="21" y2="6"/><path d="M16 10a4 4 0 01-8 0"/></svg>`;
const _SVG_SEARCH   = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>`;

function _emptyState({ icon, title, subtitle, ctaLabel, ctaFn }) {
  return `<div class="empty-state">
    <div class="empty-state__icon">${icon}</div>
    <div class="empty-state__title">${_esc(title)}</div>
    ${subtitle ? `<div class="empty-state__subtitle">${_esc(subtitle)}</div>` : ''}
    ${ctaLabel ? `<button class="empty-state__cta" onclick="${ctaFn}">${_esc(ctaLabel)}</button>` : ''}
  </div>`;
}

// ── Skeleton screens ─────────────────────────────────────────────
function renderWeekSkeletons() {
  const skels = Array.from({ length: 5 }, () => `
    <div class="skeleton-card">
      <div class="skeleton-row">
        <div class="skeleton skeleton-pill"></div>
        <div class="skeleton" style="width:28px;height:28px;border-radius:6px"></div>
      </div>
      <div class="skeleton skeleton-title"></div>
      <div class="skeleton skeleton-pill" style="width:60px;margin-bottom:10px"></div>
      <div class="skeleton skeleton-row">
        <div class="skeleton skeleton-line" style="width:30%"></div>
        <div class="skeleton skeleton-line" style="width:20%"></div>
      </div>
    </div>`).join('');

  const statSkel = `
    <div class="week-stat-bar" style="margin-bottom:10px">
      ${Array.from({ length: 3 }, () => `
        <div class="stat-card">
          <div class="skeleton" style="width:50px;height:22px;margin-bottom:6px;border-radius:6px"></div>
          <div class="skeleton" style="width:60px;height:9px;border-radius:4px"></div>
        </div>`).join('')}
    </div>`;

  const summaryEl = document.getElementById('week-summary');
  if (summaryEl) summaryEl.innerHTML = statSkel;
  const cardsEl = document.getElementById('meal-cards');
  if (cardsEl) cardsEl.innerHTML = skels;

  document.getElementById('week-loading').style.display = 'none';
  document.getElementById('week-content').style.display = 'block';
}

function renderShoppingSkeletons() {
  const catSkel = Array.from({ length: 3 }, (_, ci) => `
    <div class="shop-category-group">
      <div class="skeleton" style="width:80px;height:11px;border-radius:4px;margin:10px 16px 4px"></div>
      ${Array.from({ length: 4 }, () => `
        <div class="skeleton-row" style="padding:10px 16px">
          <div class="skeleton skeleton-check"></div>
          <div style="flex:1;display:flex;flex-direction:column;gap:4px">
            <div class="skeleton skeleton-line" style="width:60%"></div>
            <div class="skeleton skeleton-line" style="width:35%"></div>
          </div>
          <div class="skeleton skeleton-line" style="width:36px"></div>
        </div>`).join('')}
    </div>`).join('');

  document.getElementById('shopping-loading').style.display = 'none';
  document.getElementById('shopping-content').style.display = 'block';
  const itemsEl = document.getElementById('shopping-items');
  if (itemsEl) itemsEl.innerHTML = catSkel;
}

// ── Format helpers ───────────────────────────────────────────────
const fmt$ = n => `$${Number(n).toFixed(2)}`;

function fmtWeek(str) {
  if (!str) return '';
  return new Date(str).toLocaleDateString('en-NZ', {
    day: 'numeric', month: 'long', year: 'numeric'
  });
}

function fmtTime(str) {
  if (!str) return '';
  return new Date(str).toLocaleTimeString('en-NZ', {
    hour: '2-digit', minute: '2-digit', hour12: true
  });
}

// ── Reset views to loading state ────────────────────────────────
function resetViews() {
  plan = null;
  document.getElementById('week-loading').style.display = 'block';
  document.getElementById('week-content').style.display = 'none';
  document.getElementById('shopping-loading').style.display = 'block';
  document.getElementById('shopping-content').style.display = 'none';
  document.getElementById('recipe-list').style.display = 'block';
  document.getElementById('recipe-detail').classList.remove('active');
}

