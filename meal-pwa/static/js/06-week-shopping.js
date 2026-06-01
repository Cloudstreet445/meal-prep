// ══════════════════════════════════════════════════════════════
// VIEW: THIS WEEK
// ══════════════════════════════════════════════════════════════
function _clearViewingBundle() {
  _viewingBundleId = null;
  document.getElementById('viewing-banner')?.remove();
}

async function _viewBundle(bundleId, weekLabel) {
  _viewingBundleId = bundleId;
  closeBundleSheet();
  await loadWeek();
}

async function loadWeek() {
  renderWeekSkeletons();
  try {
    log('WEEK', 'Loading bundle...');
    plan = _viewingBundleId
      ? await apiFetch(`/bundle/${_viewingBundleId}`)
      : await apiFetch('/bundle/latest');
    currentWeek = plan.week;
    log('WEEK', 'Bundle loaded', { week: currentWeek, recipes: plan.recipes?.length });

    if (plan.bundleId) localStorage.setItem('lastSeenBundleId', plan.bundleId);

    document.getElementById('week-badge').textContent = `Week of ${fmtWeek(plan.week)}`;
    document.getElementById('budget-pill').textContent = `${fmt$(plan.estimatedTotal)} / ${fmt$(settings.budget)}`;
    updateNavPlanDesc();

    const _total = plan.estimatedTotal || 0;
    const _budget = settings.budget || 60;
    const _over = _total > _budget;
    const _diff = Math.abs(_total - _budget);
    const _pct = Math.min((_total / _budget) * 100, 110);
    const _barColor = _pct >= 100 ? 'var(--danger)' : _pct >= 80 ? 'var(--warning)' : 'var(--success)';

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

    renderMealCards();
    renderWeekRecipesInTab();

    // Viewing banner (shown when browsing a non-active historical bundle)
    document.getElementById('viewing-banner')?.remove();
    if (_viewingBundleId && _viewingBundleId !== plan.bundleId) {
      _clearViewingBundle(); // bundleId not found/stale — fall back to active
    } else if (_viewingBundleId) {
      const banner = document.createElement('div');
      banner.id = 'viewing-banner';
      banner.className = 'viewing-banner';
      banner.innerHTML = `<span>Viewing plan from ${_esc(fmtWeek(plan.week))}</span>
        <button class="viewing-banner__set" onclick="setViewedBundleAsActive('${_esc(plan.bundleId)}','${_esc(plan.week)}')">Set as current</button>
        <button class="viewing-banner__close" onclick="_clearViewingBundle();loadWeek()">✕ Return to current</button>`;
      document.getElementById('view-week').prepend(banner);
    }

    document.getElementById('week-loading').style.display = 'none';
    document.getElementById('week-content').style.display = 'block';
  } catch (e) {
    log('WEEK', 'Error', { error: e.message });
    document.getElementById('week-loading').style.display = 'none';
    const is404 = e.message?.includes('HTTP 404') || e.message?.includes('404');
    const el = document.getElementById('meal-cards');
    if (el) el.innerHTML = _emptyState(is404 ? {
      icon: _SVG_CALENDAR,
      title: 'No plan yet',
      subtitle: "You haven't generated a plan this week.",
      ctaLabel: 'Generate Plan →',
      ctaFn: 'generatePlan()',
    } : {
      icon: _SVG_CALENDAR,
      title: 'Could not load plan',
      subtitle: 'Check your connection and try again.',
      ctaLabel: 'Retry',
      ctaFn: 'loadWeek()',
    });
    document.getElementById('week-summary').innerHTML = '';
    log('WEEK', 'Error', { error: e.message });
  }
}

// ══════════════════════════════════════════════════════════════
// VIEW: SHOPPING
// ══════════════════════════════════════════════════════════════
async function loadShopping() {
  renderShoppingSkeletons();
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
    window._shopData = items;
    window._shopBundleId = data.bundleId;
    // Load ad-hoc items from localStorage
    const adhocKey = `adhoc_${storeKey}`;
    const adhocItems = JSON.parse(localStorage.getItem(adhocKey) || '[]');
    adhocItems.forEach(i => { if (!window._shopData.find(x => x.name === i.name)) window._shopData.push(i); });
    renderShoppingItems(window._shopData, storeKey);

    document.getElementById('clear-btn').onclick = () => {
      const checkedCount = Object.values(checked).filter(Boolean).length;
      if (!confirm(`Clear all ${checkedCount} checked item${checkedCount !== 1 ? 's' : ''}?`)) return;
      checked = {};
      localStorage.setItem(storeKey, JSON.stringify(checked));
      localStorage.removeItem(`adhoc_${storeKey}`);
      window._shopData = items;
      renderShoppingItems(window._shopData, storeKey);
      document.getElementById('clear-btn').style.display = 'none';
    };

    const anyChecked = Object.values(checked).some(Boolean);
    document.getElementById('clear-btn').style.display = anyChecked ? '' : 'none';

    document.getElementById('shopping-loading').style.display = 'none';
    document.getElementById('shopping-content').style.display = 'block';
  } catch (e) {
    log('SHOPPING', 'Error', { error: e.message });
    const is404 = e.message?.includes('404');
    const el = document.getElementById('shopping-items');
    if (el) el.innerHTML = _emptyState(is404 ? {
      icon: _SVG_BAG,
      title: 'Your shopping list will appear here',
      subtitle: 'Generate a plan first to see your shopping list.',
    } : {
      icon: _SVG_BAG,
      title: 'Could not load shopping list',
      subtitle: 'Check your connection and try again.',
      ctaLabel: 'Retry',
      ctaFn: 'loadShopping()',
    });
  }
}

function dealBadge(item) {
  const pct = item.dealStrength;
  if (!pct || pct < 5) return '';
  const tier = pct >= 20 ? 'strong' : pct >= 10 ? 'good' : 'fair';
  const savings = item.priceSavings ? ` · save $${item.priceSavings.toFixed(2)}` : '';
  return `<span class="item-deal item-deal--${tier}">–${pct}%${savings}</span>`;
}

function _shopItemHtml(item, i, storeKey) {
  const usedIn   = (item.usedInNames || item.usedIn || []).join(', ');
  const shared   = item.sharedWith?.length > 0 ? `<span class="item-shared">shared</span>` : '';
  const inPantry = isPantryItem(item.name);
  // Whole-pack rounding can leave spare you've paid for — surface it so it
  // isn't silent (only when it's a meaningful amount and not a pantry staple).
  const fmtG = (g) => g >= 1000 ? `${(g / 1000).toFixed(1)}kg` : `${g}g`;
  const leftover = (!inPantry && item.leftoverG >= 50)
    ? `<span class="item-leftover" title="Whole-pack rounding — spare you've paid for. Tip: turn on pack-efficient plans to reuse it.">≈${fmtG(item.leftoverG)} spare</span>`
    : '';
  // Names/amounts/recipe titles flow DB→API (AI-generated) and from ad-hoc
  // user input — escape everything interpolated into innerHTML. For values
  // passed into inline onclick="..." JS string args, HTML-escape AND
  // backslash-escape quotes so they can't break out of the handler.
  const jsArg = (s) => _esc(String(s ?? '').replace(/\\/g, '\\\\').replace(/'/g, "\\'"));
  return `
    <div class="shop-item ${checked[i] ? 'checked' : ''} ${inPantry ? 'in-pantry' : ''}" onclick="toggleItem(${i}, '${storeKey}')">
      <div class="check-box"><span class="check-tick">✓</span></div>
      <div class="item-info">
        <div class="item-name">
          ${_esc(item.name)}
          ${item.isSpecial && !(item.dealStrength >= 5) ? '<span class="item-special">🔥 SPECIAL</span>' : ''}
          ${dealBadge(item)}
          ${inPantry ? '<span class="item-pantry">in pantry</span>' : ''}
          ${shared}
          ${leftover}
        </div>
        <div class="item-sub">${item.amount_parts?.length
          ? item.amount_parts.map(p => `${_esc(p.amount)} <span class="amount-recipe">(${_esc(p.recipe)})</span>`).join(', ')
          : _esc(item.amount || '')}${item.brand ? ' · ' + _esc(item.brand) : ''}${item.isOverride ? ' <span class="item-pinned">pinned</span>' : ''}${usedIn ? ' · ' + _esc(usedIn) : ''}</div>
      </div>
      <div class="item-price">${item.packPrice != null ? fmt$(item.packPrice) : (item.estimatedCost != null ? fmt$(item.estimatedCost) : '—')}</div>
      ${!inPantry ? `<button class="swap-btn" onclick="pickProduct('${jsArg(item.name)}', '${jsArg(item.amount || '')}', event)" title="Choose a different brand or cut">↔</button>` : ''}
    </div>`;
}

const _CATEGORY_LABELS = {
  protein: '🥩 Meat & Seafood',
  vegetable: '🥦 Produce',
  dairy: '🧀 Dairy & Eggs',
  pantry: '🫙 Pantry',
  other: '🛒 Other',
};

function _shopRunningTotal(items) {
  // Mirror the API total: exclude pantry items (already owned) so the running
  // total agrees with the "estimated total" header and the week-tab figure.
  const toBuy = items.filter((item, i) =>
    !checked[i] && !item.inPantry && !isPantryItem(item.name));
  const cost = toBuy.reduce((s, item) => s + (item.packPrice ?? item.estimatedCost ?? 0), 0);
  return { count: toBuy.length, cost };
}

function renderShoppingItems(items, storeKey) {
  const done  = items.filter((_, i) => checked[i]).length;
  const total = items.length;
  document.getElementById('progress-fill').style.width = `${total ? (done/total)*100 : 0}%`;

  // Live running total
  const rt = _shopRunningTotal(items);
  const rtEl = document.getElementById('shop-running-total');
  if (rtEl) rtEl.textContent = `${rt.count} item${rt.count !== 1 ? 's' : ''} remaining · ${fmt$(rt.cost)}`;

  // Group by category, preserving original item index for checked state
  const groups = {};
  const order = ['protein', 'vegetable', 'dairy', 'pantry', 'other'];
  items.forEach((item, i) => {
    const cat = item.category || 'other';
    if (!groups[cat]) groups[cat] = [];
    groups[cat].push({ item, i });
  });

  const hidePantry = settings.hidePantryFromShopping || false;

  // Separate pantry items from main list
  const mainGroups = {};
  const pantryItems = [];

  order.forEach(cat => {
    (groups[cat] || []).forEach(({ item, i }) => {
      const inPantry = isPantryItem(item.name);
      if (inPantry && !hidePantry) {
        pantryItems.push({ item, i });
      } else if (!inPantry || hidePantry === false) {
        if (!mainGroups[cat]) mainGroups[cat] = [];
        if (!inPantry) mainGroups[cat].push({ item, i });
      }
    });
  });

  const mainHtml = order
    .filter(cat => mainGroups[cat]?.length)
    .map(cat => {
      const label = _CATEGORY_LABELS[cat] || cat;
      const rows  = mainGroups[cat].map(({ item, i }) => _shopItemHtml(item, i, storeKey)).join('');
      return `<div class="shop-category-group">
        <div class="shop-category-header">${label}</div>
        ${rows}
      </div>`;
    }).join('');

  const pantrySection = !hidePantry && pantryItems.length ? `
    <div class="pantry-section" id="pantry-section">
      <button class="pantry-section__header" onclick="togglePantrySection()">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="14" height="14" id="pantry-chevron"><path d="M9 18l6-6-6-6"/></svg>
        Already in pantry (${pantryItems.length} item${pantryItems.length !== 1 ? 's' : ''})
      </button>
      <div class="pantry-section__body" id="pantry-section-body" style="max-height:0;overflow:hidden">
        ${pantryItems.map(({ item, i }) => _shopItemHtml(item, i, storeKey)).join('')}
      </div>
    </div>` : '';

  const html = mainHtml + pantrySection + `
    <div class="shop-adhoc-row" id="shop-adhoc-row">
      <button class="shop-adhoc-trigger" onclick="showAdHocInput()">＋ Add item</button>
      <input type="text" id="shop-adhoc-input" class="shop-adhoc-input" placeholder="Item name…" style="display:none" onkeydown="handleAdHocKey(event,'${storeKey}')" onblur="commitAdHocItem('${storeKey}')">
    </div>`;

  document.getElementById('shopping-items').innerHTML = html;
}

function toggleItem(index, storeKey) {
  checked[index] = !checked[index];
  localStorage.setItem(storeKey, JSON.stringify(checked));

  const shopItems = document.querySelectorAll('.shop-item');
  let done = 0;
  shopItems.forEach((el, i) => {
    el.classList.toggle('checked', !!checked[i]);
    if (checked[i]) done++;
  });
  document.getElementById('progress-fill').style.width =
    `${shopItems.length ? (done/shopItems.length)*100 : 0}%`;

  // Update running total — recount from current _shopData
  if (window._shopData) {
    const rt = _shopRunningTotal(window._shopData);
    const rtEl = document.getElementById('shop-running-total');
    if (rtEl) rtEl.textContent = `${rt.count} item${rt.count !== 1 ? 's' : ''} remaining · ${fmt$(rt.cost)}`;
  }

  const anyChecked = Object.values(checked).some(Boolean);
  document.getElementById('clear-btn').style.display = anyChecked ? '' : 'none';
}

function togglePantrySection() {
  const body    = document.getElementById('pantry-section-body');
  const chevron = document.getElementById('pantry-chevron');
  const isOpen  = body.style.maxHeight !== '0px' && body.style.maxHeight !== '';
  if (isOpen) {
    body.style.maxHeight = '0';
    if (chevron) chevron.style.transform = '';
  } else {
    body.style.maxHeight = body.scrollHeight + 'px';
    if (chevron) chevron.style.transform = 'rotate(90deg)';
  }
}

function showAdHocInput() {
  const btn   = document.querySelector('.shop-adhoc-trigger');
  const input = document.getElementById('shop-adhoc-input');
  if (btn)   btn.style.display = 'none';
  if (input) { input.style.display = ''; input.focus(); }
}

function handleAdHocKey(e, storeKey) {
  if (e.key === 'Enter') { e.target.blur(); }
  if (e.key === 'Escape') {
    e.target.value = '';
    e.target.blur();
  }
}

function commitAdHocItem(storeKey) {
  const input = document.getElementById('shop-adhoc-input');
  const btn   = document.querySelector('.shop-adhoc-trigger');
  const name  = input?.value?.trim();
  if (name && window._shopData) {
    const adhocKey = `adhoc_${storeKey}`;
    const adhocList = JSON.parse(localStorage.getItem(adhocKey) || '[]');
    adhocList.push({ name, category: 'other', estimatedCost: 0, amount: '' });
    localStorage.setItem(adhocKey, JSON.stringify(adhocList));
    // Append to data and re-render
    window._shopData.push(...adhocList.slice(-1));
    renderShoppingItems(window._shopData, storeKey);
  }
  if (input) { input.value = ''; input.style.display = 'none'; }
  if (btn)   btn.style.display = '';
}

