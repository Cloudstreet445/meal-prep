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
let cookRecipeId  = null;   // recipeId of the meal currently in cook mode
let settings      = { budget: 60, serves: 2, exclusions: [] };
let pantry        = []; // [{name, canonical}] — localStorage only

// ── Fetch helpers ───────────────────────────────────────────────
async function apiFetch(path) {
  const url = `${API}${path}`;
  log('FETCH', `GET ${url}`);
  const res = await fetch(url);
  if (!res.ok) throw new Error(`HTTP ${res.status}: ${res.statusText} (${url})`);
  return res.json();
}

async function apiPost(path, body = null, method = 'POST') {
  const url = `${API}${path}`;
  log('FETCH', `${method} ${url}`);
  const opts = { method };
  if (body !== null) {
    opts.headers = { 'Content-Type': 'application/json' };
    opts.body = JSON.stringify(body);
  }
  const res = await fetch(url, opts);
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
    document.getElementById('budget-pill').textContent = `${fmt$(plan.estimatedTotal)} / ${fmt$(settings.budget)}`;
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
          <div class="stat-val">${fmt$(settings.budget - plan.estimatedTotal)}</div>
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
            ${item.isSpecial ? '<span class="item-special">🔥 SPECIAL</span>' : ''}
            ${item.dealStrength > 0 ? `<span class="item-deal">↓${item.dealStrength}% vs avg</span>` : ''}
            ${inPantry ? '<span class="item-pantry">in pantry</span>' : ''}
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
  cookSteps    = meal.method || [];
  cookIndex    = 0;
  cookRecipeId = meal.recipeId;
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
  else {
    document.getElementById('cook-mode').classList.remove('active');
    if (cookRecipeId) showRatingOverlay(cookRecipeId,
      document.getElementById('cook-recipe-name').textContent);
  }
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

  // ── Build my own ──
  html += `<button class="build-own-btn" onclick="openBuilder()">✏️ Build my own plan</button>`;

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
}

function openSettings() {
  document.getElementById('settings-budget').value  = settings.budget;
  document.getElementById('settings-serves').value  = settings.serves;
  renderExclusionTags();
  renderPantryTags();
  document.getElementById('settings-backdrop').classList.add('active');
  document.getElementById('settings-sheet').classList.add('active');
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
    settings = await apiPost('/settings/', { budget, serves, exclusions: settings.exclusions || [] }, 'PUT');
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
  if (document.getElementById('picker-overlay').classList.contains('active'))  { closePicker();       return; }
  if (document.getElementById('builder-overlay').classList.contains('active')) { closeBuilder();      return; }
  if (document.getElementById('cook-mode').classList.contains('active'))       { document.getElementById('cook-mode').classList.remove('active'); return; }
  if (document.getElementById('rating-overlay').classList.contains('active'))  { closeRatingOverlay();return; }
  if (document.getElementById('settings-sheet').classList.contains('active'))  { closeSettings();     return; }
  if (document.getElementById('bundle-sheet').classList.contains('active'))    { closeBundleSheet();  return; }
});

// ── Init ────────────────────────────────────────────────────────
(async () => {
  loadPantry();
  await loadSettings();
  await loadWeek();
  loadRecipes();
  loadShopping();
})();
