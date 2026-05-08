// ── Logging utility ──────────────────────────────────────────────
function log(section, message, data = null) {
  const timestamp = new Date().toISOString();
  const msg = `[${timestamp}] [${section}] ${message}`;
  console.log(msg, data || '');
}

// ── Config ──────────────────────────────────────────────────────
// Override via ?api=http://host:port  e.g. ?api=http://192.168.1.10:8000
const _apiParam = new URLSearchParams(window.location.search).get('api');
const _hostname = window.location.hostname;
const _isLocal  = !_hostname || _hostname === 'localhost' || _hostname === '127.0.0.1';

const API = _apiParam
  ? _apiParam.replace(/\/$/, '') + '/api'
  : _isLocal
    ? 'http://192.168.1.85:8000/api'
    : `http://${_hostname}:8000/api`;

log('CONFIG', 'API endpoint set to:', API);

// ── State ───────────────────────────────────────────────────────
let plan          = null;   // active bundle with recipes
let checked       = {};
let currentWeek   = null;
let cookSteps     = [];
let cookIndex     = 0;
let historyData   = [];     // [{week, activeBundleId, weekSummary, bundleCount, ...}]
let allRecipes    = [];     // full library across all weeks
let recipeSearch  = '';
let activeProtein = 'all';
let activeCookTime = 'all';

// ── Fetch helpers ───────────────────────────────────────────────
async function apiFetch(path) {
  const url = `${API}${path}`;
  log('FETCH', `GET ${url}`);
  const res = await fetch(url);
  if (!res.ok) throw new Error(`HTTP ${res.status}: ${res.statusText} (${url})`);
  return res.json();
}

async function apiPost(path) {
  const url = `${API}${path}`;
  log('FETCH', `POST ${url}`);
  const res = await fetch(url, { method: 'POST' });
  if (!res.ok) throw new Error(`HTTP ${res.status}: ${res.statusText} (${url})`);
  return res.json();
}

// ── Tab switching ───────────────────────────────────────────────
document.querySelectorAll('.tab').forEach(tab => {
  tab.addEventListener('click', () => {
    document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('.view').forEach(v => v.classList.remove('active'));
    tab.classList.add('active');
    document.getElementById(`view-${tab.dataset.view}`).classList.add('active');
  });
});

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

    document.getElementById('week-badge').textContent = `Week of ${fmtWeek(plan.week)}`;
    document.getElementById('budget-pill').textContent = `${fmt$(plan.estimatedTotal)} / $60`;
    document.getElementById('bundle-switcher-btn').style.display = 'flex';

    document.getElementById('week-summary').innerHTML = `
      <div class="summary-text">${plan.weekSummary}</div>
      <div class="summary-stats">
        <div class="stat">
          <div class="stat-val">${plan.recipes?.length || 0}</div>
          <div class="stat-label">Dinners</div>
        </div>
        <div class="stat">
          <div class="stat-val">${fmt$(plan.estimatedTotal)}</div>
          <div class="stat-label">Est. spend</div>
        </div>
        <div class="stat">
          <div class="stat-val">${fmt$(60 - plan.estimatedTotal)}</div>
          <div class="stat-label">Under budget</div>
        </div>
      </div>`;

    document.getElementById('meal-cards').innerHTML = (plan.recipes || []).map((meal, i) => `
      <div class="meal-card" onclick="openRecipe('${meal.recipeId}')">
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
          <div class="meal-arrow">›</div>
        </div>
      </div>`).join('');

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
    const data  = await apiFetch('/shopping/latest');
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
    };

    document.getElementById('shopping-loading').style.display = 'none';
    document.getElementById('shopping-content').style.display = 'block';
  } catch (e) {
    log('SHOPPING', 'Error', { error: e.message });
    document.getElementById('shopping-loading').innerHTML =
      '<span class="icon">⚠️</span>Could not load shopping list.<br><small>Check console for details.</small>';
  }
}

function renderShoppingItems(items, storeKey) {
  const done  = items.filter((_, i) => checked[i]).length;
  const total = items.length;
  document.getElementById('progress-fill').style.width = `${total ? (done/total)*100 : 0}%`;

  document.getElementById('shopping-items').innerHTML = items.map((item, i) => {
    // sharedWith is computed by API — show recipe names it's used in
    const usedIn = (item.usedInNames || item.usedIn || []).join(', ');
    const shared = item.sharedWith?.length > 0
      ? `<span class="item-shared">shared</span>`
      : '';
    return `
      <div class="shop-item ${checked[i] ? 'checked' : ''}" onclick="toggleItem(${i}, '${storeKey}')">
        <div class="check-box"><span class="check-tick">✓</span></div>
        <div class="item-info">
          <div class="item-name">
            ${item.name}
            ${item.isSpecial ? '<span class="item-special">🔥 SPECIAL</span>' : ''}
            ${shared}
          </div>
          <div class="item-sub">${item.amount}${usedIn ? ' · ' + usedIn : ''}</div>
        </div>
        <div class="item-price">${item.estimatedCost != null ? fmt$(item.estimatedCost) : '—'}</div>
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
    ? filtered.map(meal => `
        <div class="recipe-list-item" onclick="openRecipe('${meal.recipeId}')">
          <div class="recipe-num">${PROTEIN_EMOJI[inferProtein(meal)] || '🍽'}</div>
          <div>
            <div class="recipe-list-name">${meal.name}</div>
            <div class="recipe-list-meta">⏱ ${meal.cookTime} · ${meal.ingredients?.length || 0} ingredients</div>
          </div>
          <div style="color:var(--text-muted)">›</div>
        </div>`).join('')
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
  const meal = allRecipes.find(m => m.recipeId === id)
            || (plan?.recipes || []).find(m => m.recipeId === id);
  if (!meal) return;

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

  document.getElementById('detail-ingredients').innerHTML =
    (meal.ingredients || []).map(ing => `
      <div class="ingr-item">
        <span class="ingr-name">${ing.name}${ing.fromSpecial ? ' 🔥' : ''}</span>
        <span class="ingr-amount">${ing.amount}</span>
      </div>`).join('');

  document.getElementById('start-cooking-btn').onclick = () => startCooking(meal);
}

document.getElementById('back-btn').onclick = () => {
  document.getElementById('recipe-list').style.display = 'block';
  document.getElementById('recipe-detail').classList.remove('active');
};

// ══════════════════════════════════════════════════════════════
// COOK MODE
// ══════════════════════════════════════════════════════════════
function startCooking(meal) {
  cookSteps = meal.method || [];
  cookIndex = 0;
  document.getElementById('cook-recipe-name').textContent = meal.name;
  renderCookStep();
  document.getElementById('cook-mode').classList.add('active');
}

function renderCookStep() {
  const total = cookSteps.length;
  document.getElementById('cook-step-num').textContent = `STEP ${cookIndex + 1} OF ${total}`;
  document.getElementById('cook-step-text').textContent = cookSteps[cookIndex];
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
  else document.getElementById('cook-mode').classList.remove('active');
};

document.getElementById('cook-close').onclick = () => {
  document.getElementById('cook-mode').classList.remove('active');
};

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
  // A bundle is "active" if it matches the week's activeBundleId
  // AND it's the currently loaded plan
  const isWeekActive = bundle.bundleId === activeBundleId;
  const isLoaded     = bundle.bundleId === plan?.bundleId;
  const time         = fmtTime(bundle.createdAt);

  return `
    <div class="bundle-item ${isWeekActive ? 'is-active' : ''}"
         onclick="selectBundle('${bundle.bundleId}', '${bundle.week}')">
      ${isWeekActive ? '<div class="bundle-active-tag">Active</div>' : ''}
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
  // If already the active loaded plan, just close
  if (bundleId === plan?.bundleId) {
    closeBundleSheet();
    return;
  }

  try {
    log('BUNDLES', 'Activating bundle', { bundleId, week });
    await apiPost(`/bundle/${bundleId}/activate`);

    // Update local history so active badge updates immediately on next open
    historyData = historyData.map(w =>
      w.week === week ? { ...w, activeBundleId: bundleId } : w
    );

    closeBundleSheet();
    resetViews();
    await loadWeek();
    loadRecipes();
    loadShopping();
    log('BUNDLES', 'Bundle switched successfully');
  } catch (e) {
    log('BUNDLES', 'Error activating bundle', { error: e.message });
    alert('Could not switch to this plan. Please try again.');
  }
}

// ── Init ────────────────────────────────────────────────────────
(async () => {
  await loadWeek();
  loadRecipes();
  loadShopping();
})();
