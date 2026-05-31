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
    const cost = meal.estimatedCost ?? null;
    const costTier = cost != null ? (cost < 12 ? 'budget' : cost < 20 ? 'mid' : 'premium') : null;
    const costBadge = cost != null
      ? `<span class="recipe-cost-badge recipe-cost-badge--${costTier}">${fmt$(cost)}</span>`
      : '';
    return `
    <div class="recipe-list-item week-recipe-item" onclick="openRecipe('${meal.recipeId}')">
      <div class="recipe-num">${PROTEIN_EMOJI[inferProtein(meal)] || '🍽'}</div>
      <div style="flex:1">
        <div class="recipe-list-name">${_esc(meal.name)}${badge}</div>
        <div class="recipe-list-meta">⏱ ${_esc(meal.cookTime)} · ${meal.ingredients?.length || 0} ingredients${costBadge}</div>
      </div>
      <div style="color:var(--text-muted)">›</div>
    </div>`;
  }).join('');
}

function _recipeCard(meal) {
  const rating = lastRating(meal);
  const badge  = rating === 1  ? '<span class="recipe-rating-badge up">👍</span>'
               : rating === -1 ? '<span class="recipe-rating-badge down">👎</span>'
               : '';
  const cost = (meal.ingredients || []).reduce((s, i) => s + (i.estimatedCost || 0), 0);
  const costStr = cost > 0 ? ` · ${fmt$(cost)}` : '';
  return `
    <div class="recipe-list-item" onclick="openRecipe('${_esc(meal.recipeId)}')">
      <div class="recipe-num">${PROTEIN_EMOJI[inferProtein(meal)] || '🍽'}</div>
      <div style="flex:1">
        <div class="recipe-list-name">${_esc(meal.name)}${badge}</div>
        <div class="recipe-list-meta">⏱ ${_esc(meal.cookTime)} · ${meal.ingredients?.length || 0} ing${costStr}</div>
      </div>
      <div style="color:var(--text-muted)">›</div>
    </div>`;
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

  if (activeCost !== 'all') {
    filtered = filtered.filter(r => {
      const cost = (r.ingredients || []).reduce((s, i) => s + (i.estimatedCost || 0), 0);
      if (activeCost === 'low')  return cost < 10;
      if (activeCost === 'mid')  return cost >= 10 && cost < 20;
      if (activeCost === 'high') return cost >= 20;
    });
  }

  const countEl = document.getElementById('library-count');
  if (countEl) countEl.textContent = `${filtered.length} recipe${filtered.length !== 1 ? 's' : ''}`;

  const noResultsHtml = recipeSearch
    ? _emptyState({ icon: _SVG_SEARCH, title: `No recipes match "${recipeSearch}"`, subtitle: null, ctaLabel: 'Clear search', ctaFn: 'clearSearch()' })
    : _emptyState({ icon: _SVG_SEARCH, title: 'No recipes yet', subtitle: 'Recipes will appear here once added.' });

  if (!filtered.length) {
    document.getElementById('recipe-list-items').innerHTML = noResultsHtml;
    return;
  }

  const shouldGroup = !recipeSearch && activeProtein === 'all';
  if (!shouldGroup) {
    document.getElementById('recipe-list-items').innerHTML = filtered.map(_recipeCard).join('');
    return;
  }

  const planIds = new Set((plan?.recipes || []).map(r => r.recipeId));
  const PROTEIN_ORDER = ['chicken', 'beef', 'pork', 'lamb', 'vegetarian', 'fish'];
  const groups = [];

  if (plan) {
    const inPlan = filtered.filter(r => planIds.has(r.recipeId));
    if (inPlan.length) groups.push({ label: `This week's plan (${inPlan.length})`, recipes: inPlan });
  }

  for (const p of PROTEIN_ORDER) {
    const rs = filtered.filter(r => !planIds.has(r.recipeId) && inferProtein(r) === p);
    if (rs.length) groups.push({ label: p.charAt(0).toUpperCase() + p.slice(1) + ` (${rs.length})`, recipes: rs });
  }
  const otherProteins = new Set(PROTEIN_ORDER);
  const other = filtered.filter(r => !planIds.has(r.recipeId) && !otherProteins.has(inferProtein(r)));
  if (other.length) groups.push({ label: `Other (${other.length})`, recipes: other });

  document.getElementById('recipe-list-items').innerHTML = groups.map(g => `
    <div class="recipe-group-header">${g.label}</div>
    ${g.recipes.map(_recipeCard).join('')}
  `).join('');
}

function clearSearch() {
  recipeSearch = '';
  const el = document.getElementById('recipe-search');
  if (el) el.value = '';
  renderRecipeList();
}

function toggleFilterSheet() {
  filterOpen = !filterOpen;
  document.getElementById('filter-sheet').classList.toggle('open', filterOpen);
  document.getElementById('filter-toggle-btn').classList.toggle('active', filterOpen);
}

function _activeFilterCount() {
  return (activeProtein !== 'all' ? 1 : 0) + (activeCookTime !== 'all' ? 1 : 0) + (activeCost !== 'all' ? 1 : 0);
}

function _updateFilterBadge() {
  const n = _activeFilterCount();
  const badge = document.getElementById('filter-badge');
  const clearBtn = document.getElementById('filter-clear-btn');
  if (badge) {
    badge.textContent = n > 0 ? String(n) : '';
    badge.style.display = n > 0 ? 'inline-flex' : 'none';
  }
  if (clearBtn) clearBtn.style.display = n > 0 ? 'inline' : 'none';
}

function clearAllFilters() {
  activeProtein = 'all';
  activeCookTime = 'all';
  activeCost = 'all';
  document.querySelectorAll('#protein-chips .filter-chip').forEach(c => c.classList.toggle('active', c.dataset.protein === 'all'));
  document.querySelectorAll('#time-chips .filter-chip').forEach(c => c.classList.toggle('active', c.dataset.time === 'all'));
  document.querySelectorAll('#cost-chips .filter-chip').forEach(c => c.classList.toggle('active', c.dataset.cost === 'all'));
  _updateFilterBadge();
  renderRecipeList();
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
  _updateFilterBadge();
  renderRecipeList();
});

document.getElementById('time-chips').addEventListener('click', e => {
  const chip = e.target.closest('[data-time]');
  if (!chip) return;
  activeCookTime = chip.dataset.time;
  document.querySelectorAll('#time-chips .filter-chip').forEach(c =>
    c.classList.toggle('active', c === chip));
  _updateFilterBadge();
  renderRecipeList();
});

document.getElementById('cost-chips').addEventListener('click', e => {
  const chip = e.target.closest('[data-cost]');
  if (!chip) return;
  activeCost = chip.dataset.cost;
  document.querySelectorAll('#cost-chips .filter-chip').forEach(c =>
    c.classList.toggle('active', c === chip));
  _updateFilterBadge();
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

  // Compact header row: protein chip + cook time + serves + leftovers
  const proteinInfo = _PROTEIN_CHIP[inferProtein(meal)] || { label: 'Other', color: '#6b7280', bg: '#f3f4f6' };
  document.getElementById('detail-title').textContent = meal.name;
  document.getElementById('detail-pills').innerHTML = `
    <div class="pill detail-protein-chip" style="background:${proteinInfo.bg};color:${proteinInfo.color}">
      ${proteinInfo.emoji} ${proteinInfo.label}
    </div>
    <div class="pill">⏱ ${_esc(meal.cookTime)}</div>
    <div class="pill">👥 ${_esc(String(meal.serves || '–'))}</div>
    ${meal.leftovers ? '<div class="pill green">♻️ Leftovers</div>' : ''}
    ${meal.estimatedCost ? `<div class="pill">${fmt$(meal.estimatedCost)}</div>` : ''}`;

  const link = document.getElementById('detail-link');
  link.href = meal.recipeUrl || '#';
  document.getElementById('detail-link-text').textContent = meal.recipeUrl
    ? (() => { try { return new URL(meal.recipeUrl).hostname; } catch { return 'Recipe inspiration'; } })()
    : 'Recipe inspiration';

  const descEl = document.getElementById('detail-description');
  descEl.textContent = meal.description || '';
  descEl.style.display = meal.description ? '' : 'none';

  // Ingredients: name left, amount center, cost right
  document.getElementById('detail-ingredients').innerHTML =
    (meal.ingredients || []).map(ing => {
      const amtDisplay = typeof ing.amount === 'object'
        ? (ing.amount?.display || '')
        : (ing.amount || '');
      const costStr = ing.estimatedCost ? `<span class="ingr-cost">${fmt$(ing.estimatedCost)}</span>` : '';
      const shared  = ing.sharedWith?.length ? '<span class="ingr-shared-tag">shared</span>' : '';
      const special = ing.fromSpecial ? ' 🔥' : '';
      return `
        <div class="ingr-item${ing.inPantry ? ' ingr-pantry' : ''}">
          <span class="ingr-name">${_esc(ing.name)}${special}${shared}</span>
          <span class="ingr-amount">${_esc(amtDisplay)}</span>
          ${costStr}
        </div>`;
    }).join('');

  // Method: step cards with large step number
  const steps = meal.method || [];
  document.getElementById('method-label').style.display = steps.length ? '' : 'none';
  document.getElementById('detail-method').innerHTML =
    steps.map((s, i) => `
      <li class="method-step method-step--card">
        <span class="method-step__num">${i + 1}</span>
        <span class="method-step__text">${highlightCookingTerms(_esc(s))}</span>
      </li>`).join('');

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
        <div class="sub-name">${_esc(s.name)}</div>
        <div class="sub-meta">
          ${s.currentPrice != null ? `<span class="sub-price">${fmt$(s.currentPrice)}</span>` : '<span class="sub-no-price">price unavailable</span>'}
          ${s.isSpecial ? '<span class="item-special">🔥 SPECIAL</span>' : ''}
        </div>
      </div>`).join('');
  } catch {
    document.getElementById('sub-results').innerHTML = '<div class="sub-loading">Could not load suggestions. Try again.</div>';
  }
}

// Product/brand picker — the shopping list defaults to the cheapest matching
// product; this lets the shopper switch to another brand or cut and have the
// total follow their choice (persisted as a per-bundle override).
async function pickProduct(ingredientName, amount, e) {
  e.stopPropagation();
  _subIngredient = ingredientName;
  document.getElementById('sub-ingredient-name').textContent = ingredientName;
  document.getElementById('sub-results').innerHTML = '<div class="sub-loading">Loading options…</div>';
  document.getElementById('sub-overlay').classList.add('active');

  try {
    const store = settings.storeId || DEFAULT_STORE;
    const q = new URLSearchParams({ ingredient: ingredientName, amount: amount || '', store_id: store });
    const data = await apiFetch(`/shopping/alternatives?${q.toString()}`);
    const alts = data.alternatives || [];
    if (!alts.length) {
      document.getElementById('sub-results').innerHTML = '<div class="sub-loading">No products found for this ingredient.</div>';
      return;
    }
    const argName = ingredientName.replace(/'/g, "\\'");
    document.getElementById('sub-results').innerHTML = alts.map((a, idx) => `
      <div class="sub-card" onclick="chooseProduct('${argName}', '${_esc(a.productId)}')">
        <div class="sub-name">${_esc(a.name)}${idx === 0 ? ' <span class="item-pantry">cheapest</span>' : ''}</div>
        <div class="sub-meta">
          ${a.packPrice != null ? `<span class="sub-price">${fmt$(a.packPrice)}</span>` : '<span class="sub-no-price">price unavailable</span>'}
          ${a.unitPrice ? `<span class="sub-unit">${_esc(a.unitPrice)}</span>` : ''}
          ${a.isSpecial ? '<span class="item-special">🔥 SPECIAL</span>' : ''}
        </div>
      </div>`).join('');
  } catch {
    document.getElementById('sub-results').innerHTML = '<div class="sub-loading">Could not load options. Try again.</div>';
  }
}

async function chooseProduct(ingredientName, productId) {
  const bundleId = window._shopBundleId;
  if (!bundleId) { closeSubOverlay(); return; }
  try {
    const store = settings.storeId || DEFAULT_STORE;
    await apiFetch(`/bundle/${bundleId}/override?store_id=${encodeURIComponent(store)}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ingredient: ingredientName, productId }),
    });
    closeSubOverlay();
    loadShopping();
  } catch {
    document.getElementById('sub-results').innerHTML = '<div class="sub-loading">Could not switch product. Try again.</div>';
  }
}

function closeSubOverlay() {
  document.getElementById('sub-overlay').classList.remove('active');
}

document.getElementById('sub-close').onclick = closeSubOverlay;
document.getElementById('sub-backdrop').onclick = closeSubOverlay;

