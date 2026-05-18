// ── Theme ───────────────────────────────────────────────────────
(function initTheme() {
  const saved = localStorage.getItem('theme');
  if (saved) document.documentElement.dataset.theme = saved;
  const isDark = saved ? saved === 'dark'
    : window.matchMedia('(prefers-color-scheme: dark)').matches;
  const meta = document.getElementById('theme-color-meta');
  if (meta) meta.content = isDark ? '#0d1117' : '#f8fafc';
})();

function toggleTheme() {
  const current = document.documentElement.dataset.theme
    || (window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light');
  const next = current === 'dark' ? 'light' : 'dark';
  document.documentElement.dataset.theme = next;
  localStorage.setItem('theme', next);
  const meta = document.getElementById('theme-color-meta');
  if (meta) meta.content = next === 'dark' ? '#0d1117' : '#f8fafc';
  updateNavThemeItem();
}

// ── Nav menu ─────────────────────────────────────────────────────
function openNavMenu() {
  document.getElementById('nav-menu-backdrop').classList.add('active');
  document.getElementById('nav-menu-sheet').classList.add('active');
  updateNavThemeItem();
  updateNavPlanDesc();
}

function closeNavMenu() {
  document.getElementById('nav-menu-backdrop').classList.remove('active');
  document.getElementById('nav-menu-sheet').classList.remove('active');
}

function updateNavThemeItem() {
  const isDark = (document.documentElement.dataset.theme ||
    (window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light')) === 'dark';
  const icon = document.getElementById('nav-theme-icon');
  const name = document.getElementById('nav-theme-name');
  if (icon) icon.textContent = isDark ? '☾' : '☀';
  if (name) name.textContent = isDark ? 'Dark Mode' : 'Light Mode';
}

function updateNavPlanDesc() {
  const desc = document.getElementById('nav-plan-desc');
  if (desc && plan?.week) desc.textContent = `Week of ${fmtWeek(plan.week)}`;
}

// ── Logging utility ──────────────────────────────────────────────
function log(section, message, data = null) {
  const timestamp = new Date().toISOString();
  const msg = `[${timestamp}] [${section}] ${message}`;
  console.log(msg, data || '');
}

// ── Config ──────────────────────────────────────────────────────
// API calls go to /api/ — proxied internally by nginx to the API service.
// Override via ?api=http://host:port for local dev against a different host.
const _apiParam = new URLSearchParams(window.location.search).get('api');

const API = _apiParam
  ? _apiParam.replace(/\/$/, '') + '/api'
  : '/api';

log('CONFIG', 'API endpoint set to:', API);

// ── State ───────────────────────────────────────────────────────
let _detailRecipeId = null;
let plan          = null;
let checked       = {};
let currentWeek   = null;
let currentUser   = null;   // { userId, email, householdId } or null

// ── Auth ─────────────────────────────────────────────────────────
async function initAuth() {
  // Process magic link token if present in URL
  const params = new URLSearchParams(window.location.search);
  const authToken = params.get('auth_token');
  if (authToken) {
    window.history.replaceState({}, '', window.location.pathname);
    await handleAuthCallback(authToken);
    return;
  }

  // Handle invite token (from household invite link)
  const inviteToken = params.get('invite_token');
  if (inviteToken) {
    window.history.replaceState({}, '', window.location.pathname);
  }

  // Check existing session
  try {
    const res = await fetch(`${API}/auth/me`, { credentials: 'include' });
    if (res.ok) {
      currentUser = await res.json();
      log('AUTH', 'Signed in', { email: currentUser.email });
      const logoutBtn = document.getElementById('logout-btn');
      if (logoutBtn) logoutBtn.style.display = '';
      if (inviteToken) await handleInviteToken(inviteToken);
      return;
    }
  } catch (_) { /* network error — allow app to load without auth */ return; }

  // No session — show login screen
  showLoginOverlay();
  await waitForLogin();
}

function waitForLogin() {
  return new Promise(resolve => {
    window._authResolve = resolve;
  });
}

function showLoginOverlay() {
  const overlay = document.getElementById('auth-overlay');
  if (overlay) overlay.style.display = 'flex';
}

function hideLoginOverlay() {
  const overlay = document.getElementById('auth-overlay');
  if (overlay) overlay.style.display = 'none';
  if (window._authResolve) { window._authResolve(); window._authResolve = null; }
}

function showEmailStep() {
  document.getElementById('auth-email-step').style.display = '';
  document.getElementById('auth-sent-step').style.display = 'none';
  document.getElementById('auth-processing-step').style.display = 'none';
  document.getElementById('auth-error').style.display = 'none';
}

async function submitLogin() {
  const input = document.getElementById('auth-email-input');
  const email = input?.value?.trim();
  if (!email || !email.includes('@')) {
    showAuthError('Please enter a valid email address');
    return;
  }
  const errEl = document.getElementById('auth-error');
  if (errEl) errEl.style.display = 'none';
  try {
    const res = await fetch(`${API}/auth/send-magic-link`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email }),
    });
    if (!res.ok) throw new Error('Request failed');
    document.getElementById('auth-email-step').style.display = 'none';
    document.getElementById('auth-sent-step').style.display = '';
    const sentEmail = document.getElementById('auth-sent-email');
    if (sentEmail) sentEmail.textContent = `We sent a link to ${email}`;
  } catch (_) {
    showAuthError('Could not send email. Please try again.');
  }
}

function showAuthError(msg) {
  const el = document.getElementById('auth-error');
  if (el) { el.textContent = msg; el.style.display = ''; }
}

async function handleAuthCallback(token) {
  document.getElementById('auth-email-step').style.display = 'none';
  document.getElementById('auth-sent-step').style.display = 'none';
  document.getElementById('auth-processing-step').style.display = '';
  showLoginOverlay();

  try {
    const res = await fetch(`${API}/auth/verify?token=${encodeURIComponent(token)}`, {
      credentials: 'include',
    });
    if (!res.ok) throw new Error('Invalid link');
    const data = await res.json();
    currentUser = { userId: data.userId, email: data.email, householdId: data.householdId };
    const logoutBtn = document.getElementById('logout-btn');
    if (logoutBtn) logoutBtn.style.display = '';
    hideLoginOverlay();
    if (data.isNewUser) {
      await showOnboarding();
    }
  } catch (_) {
    showEmailStep();
    showAuthError('Login link invalid or expired. Please request a new one.');
  }
}

async function logout() {
  await fetch(`${API}/auth/logout`, { method: 'POST', credentials: 'include' });
  currentUser = null;
  const logoutBtn = document.getElementById('logout-btn');
  if (logoutBtn) logoutBtn.style.display = 'none';
  showLoginOverlay();
  showEmailStep();
  await waitForLogin();
  await loadSettings();
  await loadWeek();
  loadShopping();
}

// ── Onboarding ──────────────────────────────────────────────────
let _obStep = 0;
const _obStepCount = 5;
let _obExclusions = [];
let _obStore = null;

async function showOnboarding() {
  _obStep = 0;
  _obExclusions = [];
  // Load stores for step 1
  try {
    const stores = await apiFetch('/settings/stores');
    const el = document.getElementById('ob-store-options');
    if (el) {
      el.innerHTML = stores.map(s => `
        <div class="ob-store-option${s === 'paknsave-lower-hutt' ? ' selected' : ''}" data-store="${s}" onclick="obSelectStore(this, '${s}')">
          ${s.replace('paknsave-', 'PAK\'nSave ').replace(/-/g, ' ').replace(/\b\w/g, c => c.toUpperCase())}
        </div>`).join('');
      _obStore = 'paknsave-lower-hutt';
    }
  } catch (_) {}

  renderObDots();
  document.getElementById('onboarding-overlay').style.display = 'flex';
  return new Promise(resolve => { window._obResolve = resolve; });
}

function renderObDots() {
  const el = document.getElementById('onboarding-dots');
  if (!el) return;
  el.innerHTML = Array.from({ length: _obStepCount }, (_, i) =>
    `<div class="ob-dot${i === _obStep ? ' active' : ''}"></div>`
  ).join('');
}

function obSelectStore(el, storeId) {
  document.querySelectorAll('.ob-store-option').forEach(e => e.classList.remove('selected'));
  el.classList.add('selected');
  _obStore = storeId;
}

function obAddExclusion() {
  const input = document.getElementById('ob-exclusion-input');
  const val = input?.value?.trim().toLowerCase();
  if (!val || _obExclusions.includes(val)) return;
  _obExclusions.push(val);
  input.value = '';
  renderObExclusions();
}

function renderObExclusions() {
  const el = document.getElementById('ob-exclusion-tags');
  if (!el) return;
  el.innerHTML = _obExclusions.map(t =>
    `<div class="exclusion-tag">${t}<button class="exclusion-remove" onclick="obRemoveExclusion('${t}')">×</button></div>`
  ).join('');
}

function obRemoveExclusion(term) {
  _obExclusions = _obExclusions.filter(t => t !== term);
  renderObExclusions();
}

function obNext() {
  document.getElementById(`ob-step-${_obStep}`).style.display = 'none';
  _obStep++;
  if (_obStep >= _obStepCount) { finishOnboarding(); return; }
  document.getElementById(`ob-step-${_obStep}`).style.display = '';
  renderObDots();
}

async function finishOnboarding() {
  const budget = parseFloat(document.getElementById('ob-budget')?.value) || 60;
  const serves = parseInt(document.getElementById('ob-serves')?.value) || 2;
  const storeId = _obStore || 'paknsave-lower-hutt';

  try {
    await apiFetch('/settings', {
      method: 'PUT',
      body: JSON.stringify({ budget, serves, storeId, exclusions: _obExclusions }),
    });
  } catch (_) {}

  document.getElementById('onboarding-overlay').style.display = 'none';
  if (window._obResolve) { window._obResolve(); window._obResolve = null; }

  // Show install prompt after onboarding
  showInstallBannerIfAvailable();
}

// ── PWA Install Prompt ───────────────────────────────────────────
let _deferredInstallPrompt = null;

window.addEventListener('beforeinstallprompt', e => {
  e.preventDefault();
  _deferredInstallPrompt = e;
});

function showInstallBannerIfAvailable() {
  if (!_deferredInstallPrompt) return;
  if (localStorage.getItem('installBannerDismissed')) return;
  const banner = document.getElementById('install-banner');
  if (banner) banner.style.display = 'flex';
}

async function triggerInstallPrompt() {
  if (!_deferredInstallPrompt) return;
  _deferredInstallPrompt.prompt();
  const { outcome } = await _deferredInstallPrompt.userChoice;
  _deferredInstallPrompt = null;
  dismissInstallBanner();
  log('INSTALL', 'Outcome:', outcome);
}

function dismissInstallBanner() {
  localStorage.setItem('installBannerDismissed', '1');
  const banner = document.getElementById('install-banner');
  if (banner) banner.style.display = 'none';
}

// ── Cooked-meal tracking (MEA-49) ───────────────────────────────
function getCookedSet(bundleId) {
  return new Set(JSON.parse(localStorage.getItem(`cooked-${bundleId}`) || '[]'));
}
function saveCookedSet(bundleId, set) {
  localStorage.setItem(`cooked-${bundleId}`, JSON.stringify([...set]));
}
function toggleCookedMeal(recipeId) {
  if (!plan?.bundleId) return;
  const s = getCookedSet(plan.bundleId);
  s.has(recipeId) ? s.delete(recipeId) : s.add(recipeId);
  saveCookedSet(plan.bundleId, s);
  renderMealCards();
}
function renderMealCards() {
  const cooked = plan?.bundleId ? getCookedSet(plan.bundleId) : new Set();
  const recipes = plan?.recipes || [];

  document.getElementById('meal-cards').innerHTML = recipes.map((meal, i) => {
    const isCooked = cooked.has(meal.recipeId);
    return `
      <div class="meal-card${isCooked ? ' cooked' : ''}" data-recipe-id="${meal.recipeId}" onclick="openRecipe('${meal.recipeId}')">
        <div class="meal-card-swipe-hint">✓ Cooked</div>
        <div class="meal-card-header">
          <div>
            <div class="meal-id">Meal ${i + 1}</div>
            <div class="meal-name">${meal.name}</div>
            <div class="meal-meta">
              <div class="pill">⏱ ${meal.cookTime}</div>
              <div class="pill">👥 Serves ${meal.serves}</div>
              ${meal.leftovers ? '<div class="pill green">♻️ Leftovers</div>' : ''}
            </div>
          </div>
          <div class="meal-arrow">${isCooked ? '✓' : '›'}</div>
        </div>
      </div>`;
  }).join('');

  const cookedCount = recipes.filter(m => cooked.has(m.recipeId)).length;
  const progressEl = document.getElementById('cooked-progress');
  if (progressEl) {
    progressEl.textContent = cookedCount > 0 ? `${cookedCount} of ${recipes.length} cooked` : '';
  }

  attachMealCardSwipe();
}
function attachMealCardSwipe() {
  document.querySelectorAll('.meal-card').forEach(card => {
    let startX = 0, startY = 0;
    card.addEventListener('touchstart', e => {
      startX = e.touches[0].clientX;
      startY = e.touches[0].clientY;
    }, { passive: true });
    card.addEventListener('touchmove', e => {
      const dx = e.touches[0].clientX - startX;
      const dy = Math.abs(e.touches[0].clientY - startY);
      if (dx > 20 && dy < 30) card.classList.add('swiping');
      else card.classList.remove('swiping');
    }, { passive: true });
    card.addEventListener('touchend', e => {
      card.classList.remove('swiping');
      const dx = e.changedTouches[0].clientX - startX;
      const dy = Math.abs(e.changedTouches[0].clientY - startY);
      if (dx > 60 && dy < 30) {
        e.preventDefault();
        toggleCookedMeal(card.dataset.recipeId);
      }
    });
  });
}
let cookSteps     = [];
let cookIndex     = 0;
let historyData   = [];     // [{week, activeBundleId, weekSummary, bundleCount, ...}]
let allRecipes    = [];     // full library across all weeks
let recipeSearch  = '';
let activeProtein = 'all';
let activeCookTime = 'all';
let cookRecipeId  = null;   // recipeId of the meal currently in cook mode
const DEFAULT_STORE = 'paknsave-lower-hutt';

let settings      = { budget: 60, serves: 2, exclusions: [], storeId: DEFAULT_STORE };
let availableStores = [];

const STORE_NAMES = {
  'paknsave-lower-hutt': 'Lower Hutt',
  'paknsave-kilbirnie':  'Kilbirnie',
  'paknsave-porirua':    'Porirua',
  'paknsave-upper-hutt': 'Upper Hutt',
  'paknsave-kapiti':     'Kapiti',
};
let pantry        = []; // [{name, canonical}] — localStorage only

// ── Cooking terms glossary ───────────────────────────────────
// Note: 'mince' is intentionally excluded — in NZ/AU it means ground meat (an ingredient),
// not the cutting technique, so highlighting it would confuse recipe readers.
const COOKING_TERMS = {
  'sauté':       'Cook quickly in a small amount of hot fat over medium-high heat, stirring frequently.',
  'saute':       'Cook quickly in a small amount of hot fat over medium-high heat, stirring frequently.',
  'deglaze':     'Add liquid (wine, stock, water) to a hot pan to loosen the browned bits stuck to the bottom — these add deep flavour.',
  'fold':        'Gently combine a lighter mixture into a heavier one using a wide, sweeping under-and-over motion. Preserves air and texture.',
  'blanch':      'Briefly boil an ingredient then plunge it into ice water. Locks in colour and parcooks vegetables.',
  'simmer':      'Cook in liquid kept just below boiling (small, gentle bubbles). Lower and slower than boiling — builds flavour without toughening proteins.',
  'braise':      'Brown the ingredient first, then cook it low and slow in a small amount of liquid with the lid on. Makes tough cuts tender.',
  'sear':        'Cook over very high heat for a short time to create a browned crust. Adds flavour and colour; does not "seal in" juices.',
  'julienne':    'Cut into thin, uniform matchstick strips — typically 3mm wide and 5–6cm long.',
  'dice':        'Cut into uniform cubes. Fine dice ≈6mm, medium ≈12mm, large ≈20mm.',
  'sweat':       'Cook slowly in fat over low heat without browning. Softens vegetables and releases moisture and sweetness.',
  'reduce':      'Boil a liquid until some evaporates, concentrating the flavour and thickening the sauce.',
  'emulsify':    'Combine two liquids that don\'t normally mix (like oil and water) into a stable, creamy mixture — e.g. making a vinaigrette or hollandaise.',
  'baste':       'Spoon or brush the cooking juices or fat over the surface of meat or fish during cooking to keep it moist and add colour.',
  'marinate':    'Soak an ingredient in a flavoured liquid (acid + oil + aromatics) before cooking to add flavour and tenderise.',
  'poach':       'Cook gently in barely simmering liquid (no bubbles). Keeps delicate proteins — eggs, fish, chicken — moist and tender.',
  'roast':       'Cook uncovered in a dry oven. High heat browns the outside; lower heat cooks the inside through.',
  'caramelise':  'Heat sugar (or natural sugars in onions/vegetables) until it melts and turns golden-brown, developing a rich, complex sweetness.',
  'caramelize':  'Heat sugar (or natural sugars in onions/vegetables) until it melts and turns golden-brown, developing a rich, complex sweetness.',
  'char':        'Deliberately blacken the surface slightly over direct high heat. Adds a smoky, bitter edge that balances rich or fatty dishes.',
  'knead':       'Work dough with your hands (press, fold, push) to develop gluten, making the dough smooth, elastic, and able to trap gas.',
  'rest':        'Leave cooked meat off the heat before slicing. Lets the internal juices redistribute so they don\'t all run out when cut.',
  'zest':        'Grate or peel the outermost coloured layer of citrus skin. Contains the aromatic oils — avoid the bitter white pith beneath.',
  'season':      'Add salt and pepper (or other spices) to balance and heighten all the flavours in a dish. Taste as you go.',
  'parboil':     'Partially cook in boiling water, then finish by another method (roasting, frying). Common for potatoes and dense vegetables.',
  'stir-fry':    'Cook small pieces of food in a very hot wok or pan with a little oil, tossing constantly. Fast — usually under 5 minutes.',
  'render':      'Cook fatty meat (bacon, duck) slowly over low heat so the fat melts out, leaving crispy meat and usable cooking fat.',
  'whisk':       'Beat rapidly with a whisk to combine ingredients smoothly, or to incorporate air (e.g. whipped cream, eggs).',
  'toss':        'Combine ingredients by lifting and turning them repeatedly — distributes dressing, seasoning, or sauce evenly.',
  'score':       'Make shallow cuts across the surface of meat, fish, or bread. Helps heat penetrate, prevents skin from curling, and lets marinades soak in.',
  'pat dry':     'Press paper towels against the surface of meat or fish to remove moisture. Dry surfaces brown far better than wet ones.',
  'al dente':    'Italian for "to the tooth". Pasta or rice cooked until just barely tender with a slight firmness in the centre.',
  'flambé':      'Add alcohol and briefly ignite it to burn off the raw spirit flavour while keeping the aromatics.',
};

// Sort terms longest-first so multi-word terms match before their component words
const _termsSorted = Object.keys(COOKING_TERMS).sort((a, b) => b.length - a.length);

function _escapeHtml(str) {
  return str
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function highlightCookingTerms(plainText) {
  let html = _escapeHtml(plainText);
  const used = new Set();
  for (const term of _termsSorted) {
    if (used.has(term)) continue;
    // Word-boundary aware; handle special chars in term (e.g. hyphen, accent)
    const escaped = term.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    const re = new RegExp(`(?<![\\w-])(${escaped})(?![\\w-])`, 'gi');
    if (re.test(html)) {
      html = html.replace(re, (match) => {
        used.add(term);
        return `<span class="cooking-term" data-term="${term.toLowerCase()}">${match}</span>`;
      });
    }
  }
  return html;
}

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
  if (!res.ok) throw new Error(`HTTP ${res.status}: ${res.statusText} (${url})`);
  return res.json();
}

async function apiPost(path, body = null, method = 'POST') {
  return apiFetch(path, { method, body });
}

// ── Tab switching ───────────────────────────────────────────────
document.querySelectorAll('.tab').forEach(tab => {
  tab.addEventListener('click', () => {
    document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('.view').forEach(v => v.classList.remove('active'));
    tab.classList.add('active');
    document.getElementById(`view-${tab.dataset.view}`).classList.add('active');
    if (tab.dataset.view === 'recipes') renderWeekRecipesInTab();
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

// ══════════════════════════════════════════════════════════════
// VIEW: THIS WEEK
// ══════════════════════════════════════════════════════════════
async function loadWeek() {
  try {
    log('WEEK', 'Loading bundle...');
    plan = await apiFetch('/bundle/latest');
    currentWeek = plan.week;
    log('WEEK', 'Bundle loaded', { week: currentWeek, recipes: plan.recipes?.length });

    if (plan.bundleId) localStorage.setItem('lastSeenBundleId', plan.bundleId);

    document.getElementById('week-badge').textContent = `Week of ${fmtWeek(plan.week)}`;
    document.getElementById('budget-pill').textContent = `${fmt$(plan.estimatedTotal)} / ${fmt$(settings.budget)}`;
    updateNavPlanDesc();

    document.getElementById('week-summary').innerHTML = `
      <div class="week-stat-bar">
        <span>${plan.recipes?.length || 0} dinners</span>
        <span class="stat-sep">·</span>
        <span>${fmt$(plan.estimatedTotal)} / ${fmt$(settings.budget)}</span>
        <span class="stat-sep">·</span>
        <span class="week-summary-text">${plan.weekSummary}</span>
      </div>`;

    renderMealCards();
    renderWeekRecipesInTab();

    document.getElementById('week-loading').style.display = 'none';
    document.getElementById('week-content').style.display = 'block';
  } catch (e) {
    log('WEEK', 'Error', { error: e.message });
    document.getElementById('week-loading').innerHTML =
      '<span class="icon">⚠️</span>Could not load meal plan.<br>Is the API running?<br><small>Check console for details.</small>';
  }
}

// ══════════════════════════════════════════════════════════════
// VIEW: SHOPPING
// ══════════════════════════════════════════════════════════════
async function loadShopping() {
  try {
    log('SHOPPING', 'Loading...');
    const storeParam = settings.storeId || DEFAULT_STORE;
    const data  = await apiFetch(`/shopping/latest?store_id=${storeParam}`);
    const items = data.shoppingList || [];

    // Key checked state to bundleId so switching bundles resets ticks
    const storeKey = `checked_${data.bundleId || data.week}`;
    checked = JSON.parse(localStorage.getItem(storeKey) || '{}');
    log('SHOPPING', 'Loaded', { items: items.length });

    document.getElementById('shop-total').textContent = fmt$(data.estimatedTotal);
    renderShoppingItems(items, storeKey);

    document.getElementById('clear-btn').onclick = () => {
      checked = {};
      localStorage.setItem(storeKey, JSON.stringify(checked));
      renderShoppingItems(items, storeKey);
      document.getElementById('clear-btn').style.display = 'none';
    };

    const anyChecked = Object.values(checked).some(Boolean);
    document.getElementById('clear-btn').style.display = anyChecked ? '' : 'none';

    document.getElementById('shopping-loading').style.display = 'none';
    document.getElementById('shopping-content').style.display = 'block';
  } catch (e) {
    log('SHOPPING', 'Error', { error: e.message });
    document.getElementById('shopping-loading').innerHTML =
      '<span class="icon">⚠️</span>Could not load shopping list.<br><small>Check console for details.</small>';
  }
}

function dealBadge(item) {
  const pct = item.dealStrength;
  if (!pct || pct < 5) return '';
  const tier = pct >= 20 ? 'strong' : pct >= 10 ? 'good' : 'fair';
  const savings = item.priceSavings ? ` · save $${item.priceSavings.toFixed(2)}` : '';
  return `<span class="item-deal item-deal--${tier}">–${pct}%${savings}</span>`;
}

function renderShoppingItems(items, storeKey) {
  const done  = items.filter((_, i) => checked[i]).length;
  const total = items.length;
  document.getElementById('progress-fill').style.width = `${total ? (done/total)*100 : 0}%`;

  document.getElementById('shopping-items').innerHTML = items.map((item, i) => {
    // sharedWith is computed by API — show recipe names it's used in
    const usedIn    = (item.usedInNames || item.usedIn || []).join(', ');
    const shared    = item.sharedWith?.length > 0
      ? `<span class="item-shared">shared</span>`
      : '';
    const inPantry  = isPantryItem(item.name);
    return `
      <div class="shop-item ${checked[i] ? 'checked' : ''} ${inPantry ? 'in-pantry' : ''}" onclick="toggleItem(${i}, '${storeKey}')">
        <div class="check-box"><span class="check-tick">✓</span></div>
        <div class="item-info">
          <div class="item-name">
            ${item.name}
            ${item.isSpecial && !(item.dealStrength >= 5) ? '<span class="item-special">🔥 SPECIAL</span>' : ''}
            ${dealBadge(item)}
            ${inPantry ? '<span class="item-pantry">in pantry</span>' : ''}
            ${shared}
          </div>
          <div class="item-sub">${item.amount_parts?.length
            ? item.amount_parts.map(p => `${p.amount} <span class="amount-recipe">(${p.recipe})</span>`).join(', ')
            : (item.amount || '')}${usedIn ? ' · ' + usedIn : ''}</div>
        </div>
        <div class="item-price">${item.estimatedCost != null ? fmt$(item.estimatedCost) : '—'}</div>
        ${!inPantry ? `<button class="swap-btn" onclick="suggestSubstitute('${item.name.replace(/'/g, "\\'")}', event)" title="Suggest substitute">↔</button>` : ''}
      </div>`;
  }).join('');
}

function toggleItem(index, storeKey) {
  checked[index] = !checked[index];
  localStorage.setItem(storeKey, JSON.stringify(checked));
  const items = document.querySelectorAll('.shop-item');
  let done = 0;
  items.forEach((el, i) => {
    el.classList.toggle('checked', !!checked[i]);
    if (checked[i]) done++;
  });
  document.getElementById('progress-fill').style.width =
    `${items.length ? (done/items.length)*100 : 0}%`;
  const anyChecked = Object.values(checked).some(Boolean);
  document.getElementById('clear-btn').style.display = anyChecked ? '' : 'none';
}

// ══════════════════════════════════════════════════════════════
// VIEW: RECIPES
// ══════════════════════════════════════════════════════════════

const PROTEIN_EMOJI = { chicken: '🍗', beef: '🥩', pork: '🐷', lamb: '🐑', vegetarian: '🥦' };

function inferProtein(recipe) {
  const text = (recipe.name + ' ' + (recipe.ingredients || []).map(i => i.name).join(' ')).toLowerCase();
  if (/chicken|turkey/.test(text))    return 'chicken';
  if (/beef|mince|steak/.test(text))  return 'beef';
  if (/pork|bacon|ham/.test(text))    return 'pork';
  if (/lamb/.test(text))              return 'lamb';
  return 'vegetarian';
}

function parseCookMinutes(str) {
  if (!str) return 30;
  let mins = 0;
  const h = str.match(/(\d+)\s*h/i);
  const m = str.match(/(\d+)\s*m/i);
  if (h) mins += parseInt(h[1]) * 60;
  if (m) mins += parseInt(m[1]);
  return mins || 30;
}

async function loadRecipes() {
  try {
    allRecipes = await apiFetch('/recipes/');
    log('RECIPES', 'Library loaded', { count: allRecipes.length });
    document.getElementById('recipes-loading').style.display = 'none';
    renderRecipeList();
  } catch (e) {
    log('RECIPES', 'Error', { error: e.message });
    document.getElementById('recipes-loading').innerHTML =
      '<span class="icon">⚠️</span>Could not load recipes.<br><small>Check console for details.</small>';
  }
}

function renderWeekRecipesInTab() {
  const section = document.getElementById('week-recipes-section');
  const container = document.getElementById('week-recipe-items');
  if (!section || !container) return;
  const recipes = plan?.recipes || [];
  if (!recipes.length) { section.style.display = 'none'; return; }

  section.style.display = 'block';
  container.innerHTML = recipes.map(meal => {
    const rating = lastRating(meal);
    const badge  = rating === 1  ? '<span class="recipe-rating-badge up">👍</span>'
                 : rating === -1 ? '<span class="recipe-rating-badge down">👎</span>'
                 : '';
    return `
    <div class="recipe-list-item week-recipe-item" onclick="openRecipe('${meal.recipeId}')">
      <div class="recipe-num">${PROTEIN_EMOJI[inferProtein(meal)] || '🍽'}</div>
      <div style="flex:1">
        <div class="recipe-list-name">${meal.name}${badge}</div>
        <div class="recipe-list-meta">⏱ ${meal.cookTime} · ${meal.ingredients?.length || 0} ingredients</div>
      </div>
      <div style="color:var(--text-muted)">›</div>
    </div>`;
  }).join('');
}

function renderRecipeList() {
  let filtered = allRecipes;

  if (recipeSearch) {
    const q = recipeSearch.toLowerCase();
    filtered = filtered.filter(r => r.name.toLowerCase().includes(q));
  }

  if (activeProtein !== 'all') {
    filtered = filtered.filter(r => inferProtein(r) === activeProtein);
  }

  if (activeCookTime !== 'all') {
    filtered = filtered.filter(r => {
      const mins = parseCookMinutes(r.cookTime);
      if (activeCookTime === 'quick')  return mins < 30;
      if (activeCookTime === 'medium') return mins >= 30 && mins <= 60;
      if (activeCookTime === 'slow')   return mins > 60;
    });
  }

  const countEl = document.getElementById('library-count');
  if (countEl) countEl.textContent = `${filtered.length} recipe${filtered.length !== 1 ? 's' : ''}`;

  document.getElementById('recipe-list-items').innerHTML = filtered.length
    ? filtered.map(meal => {
        const rating = lastRating(meal);
        const badge  = rating === 1  ? '<span class="recipe-rating-badge up">👍</span>'
                     : rating === -1 ? '<span class="recipe-rating-badge down">👎</span>'
                     : '';
        return `
          <div class="recipe-list-item" onclick="openRecipe('${meal.recipeId}')">
            <div class="recipe-num">${PROTEIN_EMOJI[inferProtein(meal)] || '🍽'}</div>
            <div style="flex:1">
              <div class="recipe-list-name">${meal.name}${badge}</div>
              <div class="recipe-list-meta">⏱ ${meal.cookTime} · ${meal.ingredients?.length || 0} ingredients</div>
            </div>
            <div style="color:var(--text-muted)">›</div>
          </div>`;
      }).join('')
    : '<div class="state-msg" style="padding-top:32px"><span class="icon">🔍</span>No recipes match</div>';
}

// ── Search + filter chip wiring ──────────────────────────────
document.getElementById('recipe-search').addEventListener('input', e => {
  recipeSearch = e.target.value.trim();
  renderRecipeList();
});

document.getElementById('protein-chips').addEventListener('click', e => {
  const chip = e.target.closest('[data-protein]');
  if (!chip) return;
  activeProtein = chip.dataset.protein;
  document.querySelectorAll('#protein-chips .filter-chip').forEach(c =>
    c.classList.toggle('active', c === chip));
  renderRecipeList();
});

document.getElementById('time-chips').addEventListener('click', e => {
  const chip = e.target.closest('[data-time]');
  if (!chip) return;
  activeCookTime = chip.dataset.time;
  document.querySelectorAll('#time-chips .filter-chip').forEach(c =>
    c.classList.toggle('active', c === chip));
  renderRecipeList();
});

function openRecipe(id) {
  _detailRecipeId = id;
  const meal = allRecipes.find(m => m.recipeId === id)
            || (plan?.recipes || []).find(m => m.recipeId === id);
  if (!meal) return;

  // Show notification banner after first meaningful interaction
  showNotificationBanner();

  // Switch to recipes tab
  document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
  document.querySelectorAll('.view').forEach(v => v.classList.remove('active'));
  document.querySelector('[data-view="recipes"]').classList.add('active');
  document.getElementById('view-recipes').classList.add('active');

  document.getElementById('recipe-list').style.display = 'none';
  document.getElementById('recipe-detail').classList.add('active');

  document.getElementById('detail-title').textContent = meal.name;
  document.getElementById('detail-pills').innerHTML = `
    <div class="pill">⏱ ${meal.cookTime}</div>
    <div class="pill">👥 Serves ${meal.serves}</div>
    ${meal.leftovers ? '<div class="pill green">♻️ Leftovers</div>' : ''}`;

  const link = document.getElementById('detail-link');
  link.href = meal.recipeUrl || '#';
  document.getElementById('detail-link-text').textContent = meal.recipeUrl
    ? (() => { try { return new URL(meal.recipeUrl).hostname; } catch { return 'Recipe inspiration'; } })()
    : 'Recipe inspiration';

  const descEl = document.getElementById('detail-description');
  descEl.textContent = meal.description || '';
  descEl.style.display = meal.description ? '' : 'none';

  document.getElementById('detail-ingredients').innerHTML =
    (meal.ingredients || []).map(ing => `
      <div class="ingr-item">
        <span class="ingr-name">${ing.name}${ing.fromSpecial ? ' 🔥' : ''}</span>
        <span class="ingr-amount">${ing.amount}</span>
      </div>`).join('');

  const steps = meal.method || [];
  document.getElementById('method-label').style.display = steps.length ? '' : 'none';
  document.getElementById('detail-method').innerHTML =
    steps.map(s => `<li class="method-step">${highlightCookingTerms(s)}</li>`).join('');

  const rating = lastRating(meal);
  const ratingEl = document.getElementById('detail-rating');
  if (rating === 1)       ratingEl.innerHTML = '<span class="detail-rating-badge up">👍 You liked this</span>';
  else if (rating === -1) ratingEl.innerHTML = '<span class="detail-rating-badge down">👎 You disliked this</span>';
  else                    ratingEl.innerHTML = '';

  document.getElementById('start-cooking-btn').onclick = () => startCooking(meal);
}

document.getElementById('back-btn').onclick = () => {
  document.getElementById('recipe-list').style.display = 'block';
  document.getElementById('recipe-detail').classList.remove('active');
};

// ══════════════════════════════════════════════════════════════
// COOK MODE
// ══════════════════════════════════════════════════════════════
let _wakeLock = null;

async function _acquireWakeLock() {
  if (!('wakeLock' in navigator)) return;
  try { _wakeLock = await navigator.wakeLock.request('screen'); } catch (_) {}
}

function _releaseWakeLock() {
  if (_wakeLock) { _wakeLock.release(); _wakeLock = null; }
}

// Re-acquire wake lock when tab becomes visible again (browser drops it on hide)
document.addEventListener('visibilitychange', () => {
  if (document.visibilityState === 'visible' &&
      document.getElementById('cook-mode').classList.contains('active')) {
    _acquireWakeLock();
  }
});

function _exitCookMode() {
  document.getElementById('cook-mode').classList.remove('active');
  _releaseWakeLock();
}

function startCooking(meal) {
  cookSteps    = meal.method || [];
  cookIndex    = 0;
  cookRecipeId = meal.recipeId;
  document.getElementById('cook-recipe-name').textContent = meal.name;
  renderCookStep();
  document.getElementById('cook-mode').classList.add('active');
  _acquireWakeLock();
}

function renderCookStep() {
  const total = cookSteps.length;
  document.getElementById('cook-step-num').textContent = `STEP ${cookIndex + 1} OF ${total}`;
  document.getElementById('cook-step-text').innerHTML = highlightCookingTerms(cookSteps[cookIndex]);
  document.getElementById('cook-dots').innerHTML = cookSteps.map((_, i) => `
    <div class="cook-dot ${i < cookIndex ? 'done' : i === cookIndex ? 'current' : ''}"></div>
  `).join('');
  document.getElementById('cook-prev').disabled = cookIndex === 0;
  const nextBtn = document.getElementById('cook-next');
  nextBtn.textContent = cookIndex === total - 1 ? 'Done ✓' : 'Next →';
  nextBtn.classList.toggle('done', cookIndex === total - 1);
}

document.getElementById('cook-prev').onclick = () => {
  if (cookIndex > 0) { cookIndex--; renderCookStep(); }
};

document.getElementById('cook-next').onclick = () => {
  if (cookIndex < cookSteps.length - 1) { cookIndex++; renderCookStep(); }
  else {
    _exitCookMode();
    if (cookRecipeId) showRatingOverlay(cookRecipeId,
      document.getElementById('cook-recipe-name').textContent);
  }
};

document.getElementById('cook-close').onclick = _exitCookMode;

// Swipe left = next step, swipe right = prev step
(function() {
  const el   = document.getElementById('cook-mode');
  let startX = 0, startY = 0;

  el.addEventListener('touchstart', e => {
    startX = e.touches[0].clientX;
    startY = e.touches[0].clientY;
  }, { passive: true });

  el.addEventListener('touchend', e => {
    const dx = e.changedTouches[0].clientX - startX;
    const dy = e.changedTouches[0].clientY - startY;
    if (Math.abs(dx) < 40 || Math.abs(dx) < Math.abs(dy) * 1.5) return;
    if (dx < 0) document.getElementById('cook-next').click();
    else        document.getElementById('cook-prev').click();
  }, { passive: true });
})();

// ── Cooking term tooltip ──────────────────────────────────────
function showTermTooltip(term) {
  const def = COOKING_TERMS[term];
  if (!def) return;
  document.getElementById('term-tooltip-name').textContent =
    term.charAt(0).toUpperCase() + term.slice(1);
  document.getElementById('term-tooltip-def').textContent = def;
  document.getElementById('term-tooltip').classList.add('active');
}

function closeTermTooltip() {
  document.getElementById('term-tooltip').classList.remove('active');
}

document.getElementById('term-tooltip-close').onclick = closeTermTooltip;

document.addEventListener('click', e => {
  const term = e.target.closest('.cooking-term');
  if (term) { showTermTooltip(term.dataset.term); return; }
  if (!e.target.closest('#term-tooltip')) closeTermTooltip();
});

// ══════════════════════════════════════════════════════════════
// INGREDIENT SUBSTITUTIONS
// ══════════════════════════════════════════════════════════════

let _subIngredient = null;

async function suggestSubstitute(ingredientName, e) {
  e.stopPropagation();
  _subIngredient = ingredientName;
  document.getElementById('sub-ingredient-name').textContent = ingredientName;
  document.getElementById('sub-results').innerHTML = '<div class="sub-loading">Loading prices…</div>';
  document.getElementById('sub-overlay').classList.add('active');

  try {
    const data = await fetch(`${API}/substitutions/suggest`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ingredient: ingredientName, store_id: settings.storeId || DEFAULT_STORE }),
    }).then(r => r.json());

    const suggestions = data.suggestions || [];
    if (!suggestions.length) {
      document.getElementById('sub-results').innerHTML = '<div class="sub-loading">No substitutes found.</div>';
      return;
    }
    document.getElementById('sub-results').innerHTML = suggestions.map(s => `
      <div class="sub-card">
        <div class="sub-name">${s.name}</div>
        <div class="sub-meta">
          ${s.currentPrice != null ? `<span class="sub-price">${fmt$(s.currentPrice)}</span>` : '<span class="sub-no-price">price unavailable</span>'}
          ${s.isSpecial ? '<span class="item-special">🔥 SPECIAL</span>' : ''}
        </div>
      </div>`).join('');
  } catch {
    document.getElementById('sub-results').innerHTML = '<div class="sub-loading">Could not load suggestions. Try again.</div>';
  }
}

function closeSubOverlay() {
  document.getElementById('sub-overlay').classList.remove('active');
}

document.getElementById('sub-close').onclick = closeSubOverlay;
document.getElementById('sub-backdrop').onclick = closeSubOverlay;

// ══════════════════════════════════════════════════════════════
// BUNDLE SWITCHER
//
// Design:
// - /bundle/history returns [{week, activeBundleId, weekSummary, bundleCount}]
//   one entry per week — the active bundle summary for that week
// - /bundle/week/{week_id} returns all bundles for a specific week
// - Browsing previous weeks expands to show all bundles for that week
// - Only "select" actually calls /activate
// - active flag is per-week (not global) — activating one bundle
//   only deactivates others in the SAME week
// ══════════════════════════════════════════════════════════════

function openBundleSheet() {
  document.getElementById('sheet-backdrop').classList.add('active');
  document.getElementById('bundle-sheet').classList.add('active');
  loadBundleSheet();
}

function closeBundleSheet() {
  document.getElementById('sheet-backdrop').classList.remove('active');
  document.getElementById('bundle-sheet').classList.remove('active');
}

async function loadBundleSheet() {
  const content = document.getElementById('bundle-sheet-content');
  content.innerHTML = '<div class="sheet-empty">Loading...</div>';
  try {
    // history = [{week, activeBundleId, weekSummary, estimatedTotal, bundleCount}]
    historyData = await apiFetch('/bundle/history');
    log('BUNDLES', 'History loaded', { weeks: historyData.length });
    await renderBundleSheet();
  } catch (e) {
    log('BUNDLES', 'Error loading history', { error: e.message });
    content.innerHTML = '<div class="sheet-empty">Could not load plans.</div>';
  }
}

async function renderBundleSheet() {
  const content = document.getElementById('bundle-sheet-content');
  if (!historyData.length) {
    content.innerHTML = '<div class="sheet-empty">No plans found.</div>';
    return;
  }

  const [thisWeek, ...pastWeeks] = historyData;
  let html = '';

  // ── This week — fetch all bundles to show each one ──
  html += `<div class="history-week-label">This week · ${fmtWeek(thisWeek.week)}</div>`;
  try {
    const thisWeekBundles = await apiFetch(`/bundle/week/${thisWeek.week}`);
    html += thisWeekBundles.map(b => renderBundleCard(b, thisWeek.activeBundleId)).join('');
  } catch (e) {
    html += `<div class="sheet-empty">Could not load this week's plans.</div>`;
  }

  // ── Previous weeks — collapsed, expand on tap ──
  if (pastWeeks.length) {
    html += `<div class="history-week-label history-past-label">Previous weeks</div>`;
    pastWeeks.forEach(week => {
      html += `
        <div class="history-week-row" onclick="toggleWeek('${week.week}')" id="week-row-${week.week}">
          <div class="history-week-date">${fmtWeek(week.week)}</div>
          <div class="history-week-right">
            <div class="history-week-summary">${week.weekSummary || ''}</div>
            ${week.bundleCount > 1
              ? `<div class="history-week-count">${week.bundleCount} plans</div>`
              : ''}
            <div class="history-week-chevron" id="chevron-${week.week}">›</div>
          </div>
        </div>
        <div class="history-week-bundles" id="week-bundles-${week.week}" style="display:none">
          <div class="sheet-empty" style="padding:12px 0">Tap to expand</div>
        </div>`;
    });
  }

  content.innerHTML = html;
}

function renderBundleCard(bundle, activeBundleId) {
  const isWeekActive = bundle.bundleId === activeBundleId;
  const isLoaded     = bundle.bundleId === plan?.bundleId;
  const time         = fmtTime(bundle.createdAt);

  return `
    <div class="bundle-item ${isWeekActive ? 'is-active' : ''} ${isLoaded ? 'is-loaded' : ''}"
         onclick="selectBundle('${bundle.bundleId}', '${bundle.week}')">
      <div class="bundle-tags">
        ${isLoaded     ? '<div class="bundle-tag tag-viewing">Viewing</div>' : ''}
        ${isWeekActive ? '<div class="bundle-tag tag-active">Active</div>'   : ''}
      </div>
      <div class="bundle-dot"></div>
      <div class="bundle-info">
        <div class="bundle-summary">${bundle.weekSummary || 'Meal plan'}</div>
        <div class="bundle-meta">Generated ${time}</div>
      </div>
      <div class="bundle-price">${fmt$(bundle.estimatedTotal)}</div>
    </div>`;
}

async function toggleWeek(weekId) {
  const container = document.getElementById(`week-bundles-${weekId}`);
  const chevron   = document.getElementById(`chevron-${weekId}`);
  const isOpen    = container.style.display !== 'none';

  if (isOpen) {
    container.style.display = 'none';
    chevron.style.transform = '';
    return;
  }

  // Expand — fetch bundles for this week if not already loaded
  container.style.display = 'block';
  chevron.style.transform = 'rotate(90deg)';

  if (container.dataset.loaded) return; // already fetched

  container.innerHTML = '<div class="sheet-empty" style="padding:12px 0">Loading...</div>';
  try {
    const weekEntry = historyData.find(w => w.week === weekId);
    const bundles   = await apiFetch(`/bundle/week/${weekId}`);
    container.innerHTML = bundles.map(b =>
      renderBundleCard(b, weekEntry?.activeBundleId)
    ).join('');
    container.dataset.loaded = 'true';
  } catch (e) {
    container.innerHTML = '<div class="sheet-empty" style="padding:12px 0">Could not load.</div>';
  }
}

async function selectBundle(bundleId, week) {
  if (bundleId === plan?.bundleId) {
    closeBundleSheet();
    return;
  }

  // Show loading state on the tapped card
  const card = document.querySelector(`[onclick="selectBundle('${bundleId}', '${week}')"]`);
  if (card) card.classList.add('is-switching');

  try {
    log('BUNDLES', 'Activating bundle', { bundleId, week });
    await apiPost(`/bundle/${bundleId}/activate`);

    historyData = historyData.map(w =>
      w.week === week ? { ...w, activeBundleId: bundleId } : w
    );

    closeBundleSheet();
    resetViews();
    await loadWeek();
    loadRecipes();
    loadShopping();
    showToast('Plan switched');
    log('BUNDLES', 'Bundle switched successfully');
  } catch (e) {
    log('BUNDLES', 'Error activating bundle', { error: e.message });
    if (card) card.classList.remove('is-switching');
    const content = document.getElementById('bundle-sheet-content');
    const err = document.createElement('div');
    err.className = 'sheet-error';
    err.textContent = 'Could not switch plan — please try again.';
    content.prepend(err);
    setTimeout(() => err.remove(), 4000);
  }
}

// ══════════════════════════════════════════════════════════════
// RATINGS
// ══════════════════════════════════════════════════════════════

function lastRating(recipe) {
  const mine = (recipe.ratings || []).filter(r => r.userId === 'default');
  return mine.length ? mine[mine.length - 1].score : null;
}

function showRatingOverlay(recipeId, recipeName) {
  document.getElementById('rating-recipe-name').textContent = recipeName;
  document.getElementById('rating-overlay').dataset.recipeId = recipeId;
  document.getElementById('rating-overlay').classList.add('active');
}

function closeRatingOverlay() {
  document.getElementById('rating-overlay').classList.remove('active');
}

async function submitRating(score) {
  const recipeId = document.getElementById('rating-overlay').dataset.recipeId;
  closeRatingOverlay();
  try {
    await apiPost(`/recipes/${recipeId}/rate`, { score });
    const recipe = allRecipes.find(r => r.recipeId === recipeId);
    if (recipe) {
      recipe.ratings = recipe.ratings || [];
      recipe.ratings.push({ userId: 'default', score, date: new Date().toISOString().slice(0, 10) });
      renderRecipeList();
    }
    log('RATING', 'Rated recipe', { recipeId, score });
  } catch (e) {
    log('RATING', 'Error submitting rating', { error: e.message });
  }
}

document.getElementById('rating-up').onclick   = () => submitRating(1);
document.getElementById('rating-down').onclick  = () => submitRating(-1);
document.getElementById('rating-skip').onclick  = () => closeRatingOverlay();

// ══════════════════════════════════════════════════════════════
// SETTINGS
// ══════════════════════════════════════════════════════════════

async function loadSettings() {
  try {
    settings = await apiFetch('/settings/');
    log('SETTINGS', 'Loaded', settings);
  } catch (e) {
    log('SETTINGS', 'Could not load settings, using defaults', { error: e.message });
  }
  try {
    availableStores = await apiFetch('/settings/stores');
    log('SETTINGS', 'Stores loaded', { count: availableStores.length });
  } catch (e) {
    availableStores = [settings.storeId || DEFAULT_STORE];
  }
}

function storeName(id) {
  return STORE_NAMES[id] || id.replace(/^paknsave-/, '').replace(/-/g, ' ')
    .replace(/\b\w/g, c => c.toUpperCase());
}

function renderStoreSelector() {
  const container = document.getElementById('settings-store-options');
  if (!container) return;
  const current = settings.storeId || DEFAULT_STORE;
  const stores = availableStores.length ? availableStores : [current];
  container.innerHTML = stores.map(id => `
    <div class="store-option ${id === current ? 'active' : ''}" onclick="selectStore('${id}')">
      <span class="store-option-dot"></span>
      ${storeName(id)}
    </div>`).join('');
}

function selectStore(id) {
  settings.storeId = id;
  renderStoreSelector();
}

function openSettings() {
  document.getElementById('settings-budget').value  = settings.budget;
  document.getElementById('settings-serves').value  = settings.serves;
  renderExclusionTags();
  renderPantryTags();
  renderStoreSelector();
  renderHouseholdSection();
  document.getElementById('settings-backdrop').classList.add('active');
  document.getElementById('settings-sheet').classList.add('active');
}

async function renderHouseholdSection() {
  if (!currentUser) {
    document.getElementById('household-section').innerHTML =
      '<div class="settings-hint">Sign in to manage your household</div>';
    return;
  }

  // Show account info
  const accountSection = document.getElementById('account-section');
  const accountEmail = document.getElementById('account-email');
  if (accountSection) accountSection.style.display = '';
  if (accountEmail) accountEmail.textContent = currentUser.email;

  const el = document.getElementById('household-section');
  el.innerHTML = '<div class="settings-hint">Loading…</div>';
  try {
    const h = await apiFetch('/household/');
    const members = h.members || [];
    const isOwner = h.createdBy === currentUser.userId;
    el.innerHTML = `
      <div class="settings-section">
        <div class="settings-label">${h.name}</div>
        <div class="household-members">
          ${members.map(m => `
            <div class="household-member">
              <span class="member-avatar">${(m.userId || '?')[0].toUpperCase()}</span>
              <span class="member-role-badge ${m.role}">${m.role}</span>
              ${isOwner && m.role !== 'owner' ? `<button class="member-remove-btn" onclick="removeMember('${m.userId}')">Remove</button>` : ''}
            </div>`).join('')}
        </div>
        <button class="settings-link-btn" onclick="copyInviteLink()" style="margin-top:8px">📋 Copy invite link</button>
      </div>`;
  } catch (_) {
    el.innerHTML = '<div class="settings-hint">Could not load household info</div>';
  }
}

async function copyInviteLink() {
  try {
    const data = await apiFetch('/household/invite');
    const link = `${window.location.origin}/?invite_token=${data.token}`;
    await navigator.clipboard.writeText(link);
    showToast('Invite link copied to clipboard!');
  } catch (_) {
    showToast('Could not generate invite link');
  }
}

async function removeMember(userId) {
  if (!confirm('Remove this member from your household?')) return;
  try {
    await apiFetch(`/household/members/${userId}`, { method: 'DELETE' });
    renderHouseholdSection();
  } catch (_) {
    showToast('Could not remove member');
  }
}

async function handleInviteToken(token) {
  try {
    await apiFetch('/household/join', { method: 'POST', params: { token } });
    showToast("You've joined the household!");
    if (currentUser) {
      const me = await apiFetch('/auth/me');
      currentUser.householdId = me.householdId;
    }
  } catch (_) {
    showToast('Invite link invalid or expired');
  }
}

function closeSettings() {
  document.getElementById('settings-backdrop').classList.remove('active');
  document.getElementById('settings-sheet').classList.remove('active');
}

function renderExclusionTags() {
  const tags = document.getElementById('settings-exclusion-tags');
  tags.innerHTML = (settings.exclusions || []).map((ex, i) => `
    <span class="excl-tag">
      ${ex}
      <span class="excl-tag-remove" onclick="removeExclusion(${i})">✕</span>
    </span>`).join('');
}

function removeExclusion(i) {
  settings.exclusions = settings.exclusions.filter((_, idx) => idx !== i);
  renderExclusionTags();
}

function addExclusion() {
  const input = document.getElementById('settings-exclusion-input');
  const val   = input.value.trim().toLowerCase();
  if (!val || (settings.exclusions || []).includes(val)) { input.value = ''; return; }
  settings.exclusions = [...(settings.exclusions || []), val];
  input.value = '';
  renderExclusionTags();
}

async function saveSettings() {
  const btn = document.getElementById('settings-save-btn');
  const budget = parseFloat(document.getElementById('settings-budget').value);
  const serves = parseInt(document.getElementById('settings-serves').value, 10);

  if (!budget || budget < 20) { alert('Please enter a valid budget (minimum $20).'); return; }
  if (!serves || serves < 1)  { alert('Please enter a valid household size.'); return; }

  btn.textContent = 'Saving...';
  btn.disabled    = true;

  try {
    settings = await apiPost('/settings/', { budget, serves, exclusions: settings.exclusions || [], storeId: settings.storeId || DEFAULT_STORE }, 'PUT');
    closeSettings();
    // Refresh budget pill if a plan is loaded
    if (plan) {
      document.getElementById('budget-pill').textContent =
        `${fmt$(plan.estimatedTotal)} / ${fmt$(settings.budget)}`;
    }
    log('SETTINGS', 'Saved', settings);
  } catch (e) {
    log('SETTINGS', 'Error saving', { error: e.message });
    alert('Could not save settings. Please try again.');
  } finally {
    btn.textContent = 'Save Settings';
    btn.disabled    = false;
  }
}

document.getElementById('settings-save-btn').onclick = saveSettings;

document.getElementById('settings-exclusion-btn').onclick = addExclusion;

document.getElementById('settings-exclusion-input').addEventListener('keydown', e => {
  if (e.key === 'Enter') addExclusion();
});

// ══════════════════════════════════════════════════════════════
// PANTRY
// ══════════════════════════════════════════════════════════════

function loadPantry() {
  pantry = JSON.parse(localStorage.getItem('pantry') || '[]');
  log('PANTRY', 'Loaded', { count: pantry.length });
}

function savePantry() {
  localStorage.setItem('pantry', JSON.stringify(pantry));
}

function isPantryItem(itemName) {
  if (!pantry.length) return false;
  const n = itemName.toLowerCase().trim();
  return pantry.some(p => n.includes(p.canonical) || p.canonical.includes(n));
}

function renderPantryTags() {
  const tags = document.getElementById('settings-pantry-tags');
  tags.innerHTML = pantry.map((item, i) => `
    <span class="excl-tag">
      ${item.name}
      <span class="excl-tag-remove" onclick="removePantryItem(${i})">✕</span>
    </span>`).join('');
}

function removePantryItem(i) {
  pantry = pantry.filter((_, idx) => idx !== i);
  savePantry();
  renderPantryTags();
}

function addPantryItem() {
  const input    = document.getElementById('settings-pantry-input');
  const val      = input.value.trim();
  const canonical = val.toLowerCase();
  if (!val || pantry.some(p => p.canonical === canonical)) { input.value = ''; return; }
  pantry = [...pantry, { name: val, canonical }];
  savePantry();
  input.value = '';
  renderPantryTags();
}

document.getElementById('settings-pantry-btn').onclick = addPantryItem;
document.getElementById('settings-pantry-input').addEventListener('keydown', e => {
  if (e.key === 'Enter') addPantryItem();
});

// ══════════════════════════════════════════════════════════════
// CUSTOM BUNDLE BUILDER
// ══════════════════════════════════════════════════════════════

let builderSlots    = [null, null, null, null, null];
let builderWeek     = null;
let pickerSlotIndex = -1;
let pickerSearchText = '';

function getThisMonday() {
  const d = new Date();
  const day = d.getDay();
  const diff = d.getDate() - day + (day === 0 ? -6 : 1);
  d.setDate(diff);
  return d.toISOString().slice(0, 10);
}

function openBuilder() {
  closeBundleSheet();
  builderWeek   = currentWeek || getThisMonday();
  builderSlots  = [null, null, null, null, null];
  document.getElementById('builder-week-label').textContent = `Week of ${fmtWeek(builderWeek)}`;
  renderBuilderSlots();
  document.getElementById('builder-overlay').classList.add('active');
}

function closeBuilder() {
  document.getElementById('builder-overlay').classList.remove('active');
}

function builderCost() {
  return builderSlots.reduce((total, rid) => {
    if (!rid) return total;
    const r = allRecipes.find(x => x.recipeId === rid);
    return total + (r?.ingredients || []).reduce((s, i) => s + (i.estimatedCost || 0), 0);
  }, 0);
}

function renderBuilderSlots() {
  const cost      = builderCost();
  const filled    = builderSlots.filter(Boolean).length;
  document.getElementById('builder-cost').textContent = fmt$(cost);
  document.getElementById('builder-save-btn').disabled = filled === 0;

  document.getElementById('builder-slots').innerHTML = builderSlots.map((rid, i) => {
    if (rid) {
      const r = allRecipes.find(x => x.recipeId === rid);
      return `
        <div class="builder-slot filled" onclick="openPicker(${i})">
          <div class="builder-slot-num">Meal ${i + 1}</div>
          <div class="builder-slot-name">${r?.name || rid}</div>
          <div class="builder-slot-remove" onclick="event.stopPropagation(); removeBuilderSlot(${i})">✕</div>
        </div>`;
    }
    return `
      <div class="builder-slot empty" onclick="openPicker(${i})">
        <div class="builder-slot-num">Meal ${i + 1}</div>
        <div class="builder-slot-add">+ Add recipe</div>
      </div>`;
  }).join('');
}

function removeBuilderSlot(i) {
  builderSlots[i] = null;
  renderBuilderSlots();
}

async function saveCustomBundle() {
  const filledIds = builderSlots.filter(Boolean);
  if (!filledIds.length) return;

  const btn = document.getElementById('builder-save-btn');
  btn.textContent = 'Saving...';
  btn.disabled = true;

  try {
    await apiPost('/bundle/custom', { recipeIds: filledIds, week: builderWeek });
    closeBuilder();
    resetViews();
    await loadWeek();
    loadRecipes();
    loadShopping();
  } catch (e) {
    log('BUILDER', 'Error saving custom bundle', { error: e.message });
    btn.textContent = 'Save Plan';
    btn.disabled = false;
    alert('Could not save plan. Please try again.');
  }
}

document.getElementById('builder-close').onclick  = closeBuilder;
document.getElementById('builder-save-btn').onclick = saveCustomBundle;

// ── Recipe Picker ─────────────────────────────────────────────

function openPicker(slotIndex) {
  pickerSlotIndex  = slotIndex;
  pickerSearchText = '';
  document.getElementById('picker-search-input').value = '';
  renderPickerList('');
  document.getElementById('picker-overlay').classList.add('active');
}

function closePicker() {
  document.getElementById('picker-overlay').classList.remove('active');
}

function renderPickerList(search) {
  let list = allRecipes;
  if (search) {
    const q = search.toLowerCase();
    list = list.filter(r => r.name.toLowerCase().includes(q));
  }
  document.getElementById('picker-list-items').innerHTML = list.length
    ? list.map(r => {
        const cost = (r.ingredients || []).reduce((s, i) => s + (i.estimatedCost || 0), 0);
        return `
          <div class="recipe-list-item" onclick="pickRecipe('${r.recipeId}')">
            <div class="recipe-num">${PROTEIN_EMOJI[inferProtein(r)] || '🍽'}</div>
            <div style="flex:1">
              <div class="recipe-list-name">${r.name}</div>
              <div class="recipe-list-meta">⏱ ${r.cookTime} · ${fmt$(cost)}</div>
            </div>
            <div style="color:var(--green);font-size:18px">+</div>
          </div>`;
      }).join('')
    : '<div class="state-msg" style="padding-top:32px"><span class="icon">🔍</span>No recipes match</div>';
}

function pickRecipe(recipeId) {
  if (pickerSlotIndex >= 0) {
    builderSlots[pickerSlotIndex] = recipeId;
    pickerSlotIndex = -1;
  }
  closePicker();
  renderBuilderSlots();
}

document.getElementById('picker-back').onclick = closePicker;
document.getElementById('picker-search-input').addEventListener('input', e => {
  pickerSearchText = e.target.value.trim();
  renderPickerList(pickerSearchText);
});

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
});

// ── Plan generation ──────────────────────────────────────────────

async function generatePlan() {
  const btn    = document.getElementById('generate-btn');
  const status = document.getElementById('generate-status');

  btn.disabled    = true;
  btn.textContent = 'Generating...';
  status.style.display = 'block';
  status.textContent   = 'Finding meals from your library...';

  try {
    const result = await apiPost('/plan/generate');
    status.textContent = `Plan ready — ${result.recipeCount} meals, est. $${result.estimatedTotal?.toFixed(2)}`;
    await notifyNewPlan({ week: result.week });
    await loadWeek();
    loadRecipes();
    await loadShopping();
  } catch (e) {
    status.textContent = 'Generation failed — tap "Generate" to retry.';
    log('GENERATE', 'Error', { error: e.message });
  } finally {
    btn.disabled    = false;
    btn.textContent = 'Generate new plan';
    setTimeout(() => { status.style.display = 'none'; }, 6000);
  }
}

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
          <div class="enhance-name">${e.name}</div>
          <div class="enhance-cost">${fmt$(e.estimatedCost)}</div>
        </div>
        <div class="enhance-desc">${e.description}</div>
        <div class="enhance-ingredients">
          ${(e.ingredients || []).map(i => `<span class="enhance-tag">${i.name} · ${i.amount}</span>`).join('')}
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
// When the Android app is opened via kaiplannerapp://auth?token=... ,
// Capacitor fires appUrlOpen before the page navigates. We extract the
// token and run the same auth callback used by the PWA magic link flow.
if (window.Capacitor?.isNativePlatform?.()) {
  document.addEventListener('deviceready', () => {
    window.Capacitor.Plugins.App.addListener('appUrlOpen', async (data) => {
      const url = data?.url;
      if (!url) return;
      try {
        const parsed = new URL(url);
        // kaiplannerapp://auth?token=XXX
        const token = parsed.searchParams.get('token') || parsed.searchParams.get('auth_token');
        if (token) {
          await handleAuthCallback(token);
        }
        // kaiplannerapp://?tab=shopping
        const tab = parsed.searchParams.get('tab');
        if (tab) switchTab(tab);
      } catch (_) {}
    });
  });
}

// ── Init ────────────────────────────────────────────────────────
(async () => {
  await initAuth();
  loadPantry();
  await loadSettings();
  await loadWeek();
  loadRecipes();
  loadShopping();
  registerServiceWorker();

  const urlTab = new URLSearchParams(window.location.search).get('tab');
  if (urlTab) switchTab(urlTab);
})();
