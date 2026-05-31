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
  const isViewing    = bundle.bundleId === _viewingBundleId || bundle.bundleId === plan?.bundleId;
  const time         = fmtTime(bundle.createdAt);
  const bid          = _esc(bundle.bundleId);
  const wk           = _esc(bundle.week);

  return `
    <div class="bundle-item ${isWeekActive ? 'is-active' : ''} ${isViewing ? 'is-loaded' : ''}">
      <div class="bundle-tags">
        ${isViewing    ? '<div class="bundle-tag tag-viewing">Viewing</div>' : ''}
        ${isWeekActive ? '<div class="bundle-tag tag-active">Active</div>'   : ''}
      </div>
      <div class="bundle-dot"></div>
      <div class="bundle-info">
        <div class="bundle-summary">${_esc(bundle.weekSummary || 'Meal plan')}</div>
        <div class="bundle-meta">Generated ${time}</div>
      </div>
      <div class="bundle-price">${fmt$(bundle.estimatedTotal)}</div>
      <div class="bundle-actions">
        ${!isViewing ? `<button class="bundle-view-btn" onclick="_viewBundle('${bid}')">View</button>` : ''}
        ${!isWeekActive ? `<button class="bundle-set-btn" onclick="setViewedBundleAsActive('${bid}','${wk}')">Set current</button>` : ''}
      </div>
    </div>`;
}

async function setViewedBundleAsActive(bundleId, week) {
  try {
    await apiPost(`/bundle/${bundleId}/activate`);
    historyData = historyData.map(w =>
      w.week === week ? { ...w, activeBundleId: bundleId } : w
    );
    _clearViewingBundle();
    closeBundleSheet();
    await loadWeek();
    loadShopping();
    showToast('Plan set as current');
  } catch (_) {
    showToast('Could not set plan as current');
  }
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
  // View the bundle read-only — DB active flag is unchanged
  await _viewBundle(bundleId, week);
}

// ══════════════════════════════════════════════════════════════
// RATINGS
// ══════════════════════════════════════════════════════════════

function lastRating(recipe) {
  const mine = (recipe.ratings || []).filter(r => r.userId === 'default');
  return mine.length ? mine[mine.length - 1].score : null;
}

function openSwapPicker(recipeId, protein) {
  openRecipePicker({ swapRecipeId: recipeId, filterProtein: protein });
}

function openRecipePicker({ swapRecipeId, filterProtein }) {
  swapState = { recipeId: swapRecipeId, protein: filterProtein };
  pickerSlotIndex = -1;
  pickerSearchText = '';
  document.getElementById('picker-search-input').value = '';
  document.getElementById('picker-title').textContent = 'Swap Meal';
  renderPickerList('');
  document.getElementById('picker-overlay').classList.add('active');
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
    <div class="store-option ${id === current ? 'active' : ''}" onclick="selectStore('${_esc(id)}')">
      <span class="store-option-dot"></span>
      ${_esc(storeName(id))}
    </div>`).join('');
}

function selectStore(id) {
  settings.storeId = id;
  renderStoreSelector();
}

function openSettings() {
  switchSettingsTab('planning');
  document.getElementById('settings-budget').value  = settings.budget;
  document.getElementById('settings-serves').value  = settings.serves;
  renderExclusionTags();
  renderStoreSelector();
  renderHouseholdSection();
  renderSessionsSection();
  document.getElementById('settings-backdrop').classList.add('active');
  document.getElementById('settings-sheet').classList.add('active');
}

function switchSettingsTab(tab) {
  document.querySelectorAll('.settings-tab').forEach(btn =>
    btn.classList.toggle('active', btn.dataset.tab === tab));
  document.querySelectorAll('.settings-panel').forEach(panel =>
    panel.classList.toggle('active', panel.id === `settings-panel-${tab}`));
}

function saveHidePantrySetting(value) {
  settings.hidePantryFromShopping = value;
  apiPost('/settings', { hidePantryFromShopping: value }).catch(() => {});
  if (window._shopData && plan?.bundleId) {
    const storeKey = `checked_${plan.bundleId}`;
    renderShoppingItems(window._shopData, storeKey);
  }
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
        <div class="settings-label">${_esc(h.name)}</div>
        <div class="household-members">
          ${members.map(m => {
            const display = m.email || m.userId || '?';
            const initial = (m.email || m.userId || '?')[0].toUpperCase();
            return `
            <div class="household-member">
              <span class="member-avatar">${_esc(initial)}</span>
              <span class="member-email">${_esc(display)}</span>
              <span class="member-role-badge ${_esc(m.role)}">${_esc(m.role)}</span>
              ${isOwner && m.role !== 'owner' ? `<button class="member-remove-btn" onclick="removeMember('${_esc(m.userId)}')">Remove</button>` : ''}
            </div>`;
          }).join('')}
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
      ${_esc(ex)}
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

// Auto-save budget and serves on blur
async function _autoSaveField(field) {
  const budget = parseFloat(document.getElementById('settings-budget').value);
  const serves = parseInt(document.getElementById('settings-serves').value, 10);
  if (!budget || budget < 20 || !serves || serves < 1) return;
  try {
    settings = await apiPost('/settings/', {
      budget, serves,
      exclusions: settings.exclusions || [],
      storeId: settings.storeId || DEFAULT_STORE,
    }, 'PUT');
    const indicator = document.getElementById(`${field}-saved`);
    if (indicator) { indicator.style.opacity = '1'; setTimeout(() => { indicator.style.opacity = '0'; }, 1500); }
  } catch (_) {}
}
document.getElementById('settings-budget').addEventListener('blur', () => _autoSaveField('settings-budget'));
document.getElementById('settings-serves').addEventListener('blur', () => _autoSaveField('settings-serves'));

// ══════════════════════════════════════════════════════════════
// PANTRY
// ══════════════════════════════════════════════════════════════

async function loadPantry() {
  // Prefer the server pantry (shared across the household and used by the API
  // to exclude owned items from the shopping total); fall back to localStorage.
  pantry = JSON.parse(localStorage.getItem('pantry') || '[]');
  try {
    const server = await apiFetch('/pantry/');
    if (Array.isArray(server)) {
      pantry = server;
      savePantry();
    }
  } catch { /* offline or anonymous — keep localStorage copy */ }
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
  const tags = document.getElementById('pantry-tags');
  const empty = document.getElementById('pantry-empty');
  if (!tags) return;
  tags.innerHTML = pantry.map((item, i) => `
    <span class="excl-tag">
      ${_esc(item.name)}
      <span class="excl-tag-remove" onclick="removePantryItem(${i})">✕</span>
    </span>`).join('');
  if (empty) empty.style.display = pantry.length ? 'none' : '';
}

function renderPantryView() {
  renderPantryTags();
  const toggle = document.getElementById('pantry-hide-toggle');
  if (toggle) toggle.checked = !!settings.hidePantryFromShopping;
  const desc = document.getElementById('nav-pantry-desc');
  if (desc && pantry.length) desc.textContent = `${pantry.length} item${pantry.length !== 1 ? 's' : ''} stocked`;
}

function removePantryItem(i) {
  const removed = pantry[i];
  pantry = pantry.filter((_, idx) => idx !== i);
  savePantry();
  renderPantryTags();
  if (removed) {
    apiFetch(`/pantry/${encodeURIComponent(removed.canonical)}`, { method: 'DELETE' }).catch(() => {});
  }
}

function addPantryItem() {
  const input     = document.getElementById('pantry-input');
  const val       = input.value.trim();
  const canonical = val.toLowerCase();
  if (!val || pantry.some(p => p.canonical === canonical)) { input.value = ''; return; }
  pantry = [...pantry, { name: val, canonical }];
  savePantry();
  input.value = '';
  renderPantryTags();
  apiFetch('/pantry/', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name: val, canonical }),
  }).catch(() => {});
}

document.getElementById('pantry-add-btn').onclick = addPantryItem;
document.getElementById('pantry-input').addEventListener('keydown', e => {
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
          <div class="builder-slot-name">${_esc(r?.name || rid)}</div>
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
  swapState = null;
  document.getElementById('picker-title').textContent = 'Add a Recipe';
  document.getElementById('picker-overlay').classList.remove('active');
}

function renderPickerList(search) {
  let list = allRecipes;

  if (swapState) {
    // In swap mode: show same protein only, exclude meals already in the plan
    const planIds = new Set((plan?.recipes || []).map(r => r.recipeId));
    planIds.delete(swapState.recipeId); // allow re-selecting current meal
    list = list.filter(r => inferProtein(r) === swapState.protein && !planIds.has(r.recipeId));
  }

  if (search) {
    const q = search.toLowerCase();
    list = list.filter(r => r.name.toLowerCase().includes(q));
  }

  document.getElementById('picker-list-items').innerHTML = list.length
    ? list.map(r => {
        const cost = (r.ingredients || []).reduce((s, i) => s + (i.estimatedCost || 0), 0);
        return `
          <div class="recipe-list-item" onclick="pickRecipe('${_esc(r.recipeId)}')">
            <div class="recipe-num">${PROTEIN_EMOJI[inferProtein(r)] || '🍽'}</div>
            <div style="flex:1">
              <div class="recipe-list-name">${_esc(r.name)}</div>
              <div class="recipe-list-meta">⏱ ${_esc(r.cookTime)} · ${fmt$(cost)}</div>
            </div>
            <div style="color:var(--accent);font-size:18px">+</div>
          </div>`;
      }).join('')
    : '<div class="state-msg" style="padding-top:32px"><span class="icon">🔍</span>No recipes match</div>';
}

async function pickRecipe(recipeId) {
  if (swapState) {
    const oldId = swapState.recipeId;
    closePicker();
    await doSwap(oldId, recipeId);
    return;
  }
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

async function doSwap(oldRecipeId, newRecipeId) {
  if (!plan?.bundleId) return;

  const oldCard = document.querySelector(`.meal-card[data-recipe-id="${oldRecipeId}"]`);
  if (oldCard) oldCard.classList.add('meal-card--swapping-out');

  try {
    const result = await apiFetch(`/bundle/${plan.bundleId}/swap`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ oldRecipeId, newRecipeId }),
    });

    const newRecipe = allRecipes.find(r => r.recipeId === newRecipeId);
    if (newRecipe) {
      const idx = (plan.recipes || []).findIndex(r => r.recipeId === oldRecipeId);
      if (idx >= 0) plan.recipes[idx] = newRecipe;
    }
    plan.estimatedTotal = result.estimatedTotal;

    _refreshWeekSummary();
    renderMealCards();

    const newCard = document.querySelector(`.meal-card[data-recipe-id="${newRecipeId}"]`);
    if (newCard) {
      newCard.classList.add('meal-card--swapping-in');
      newCard.addEventListener('animationend', () => newCard.classList.remove('meal-card--swapping-in'), { once: true });
    }
  } catch (e) {
    renderMealCards();
    showToast('Swap failed — try again', 3000);
  }
}

function _refreshWeekSummary() {
  const _total  = plan.estimatedTotal || 0;
  const _budget = settings.budget || 60;
  const _over   = _total > _budget;
  const _diff   = Math.abs(_total - _budget);
  const _pct    = Math.min((_total / _budget) * 100, 110);
  const _barColor = _pct >= 100 ? 'var(--danger)' : _pct >= 80 ? 'var(--warning)' : 'var(--success)';

  const pill = document.getElementById('budget-pill');
  if (pill) pill.textContent = `${fmt$(_total)} / ${fmt$(_budget)}`;

  document.getElementById('week-summary').innerHTML = `
    <div class="week-stat-bar">
      <div class="stat-card">
        <div class="stat-value">${plan.recipes?.length || 0}</div>
        <div class="stat-label">MEALS</div>
      </div>
      <div class="stat-card">
        <div class="stat-value">${fmt$(_total)}</div>
        <div class="stat-label">ESTIMATED</div>
      </div>
      <div class="stat-card">
        <div class="stat-value" style="color:${_over ? 'var(--danger)' : 'var(--success)'}">${fmt$(_diff)}</div>
        <div class="stat-label" style="color:${_over ? 'var(--danger)' : 'inherit'}">${_over ? 'OVER BUDGET' : 'REMAINING'}</div>
      </div>
    </div>
    <div class="budget-progress-bar">
      <div class="budget-progress-fill" style="width:${_pct}%;background:${_barColor}"></div>
    </div>
    <div class="week-summary-text">${_esc(plan.weekSummary)}</div>`;
}

