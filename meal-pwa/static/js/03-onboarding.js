// ── Onboarding ──────────────────────────────────────────────────
let _obStep = 0;
const _obStepCount = 5;
let _obExclusions = [];
let _obStore = null;
let _obThemes = [];
let _obThemeList = [];              // [{id,label}] fetched from the API
let _obPantrySuggestions = [];
let _obPantryChecked = new Set();   // canonicals the user confirmed they own

// Minimal fallback so the picker still works if the themes fetch fails.
const _OB_THEME_FALLBACK = [
  { id: 'asian', label: 'Asian' }, { id: 'italian', label: 'Italian' },
  { id: 'indian', label: 'Indian' }, { id: 'mexican', label: 'Mexican' },
  { id: 'nz-classic', label: 'Kiwi Classic' },
];

async function showOnboarding() {
  _obStep = 0;
  _obExclusions = [];
  _obThemes = [];
  _obThemeList = [];
  _obPantryChecked = new Set();
  // Themes + stores are independent — fetch together so step 0/2 are ready.
  try {
    _obThemeList = await apiFetch('/settings/themes');
  } catch (_) {}
  if (!Array.isArray(_obThemeList) || !_obThemeList.length) _obThemeList = _OB_THEME_FALLBACK;
  renderObThemeChips();
  // Load stores for step 0
  try {
    const stores = await apiFetch('/settings/stores');
    const el = document.getElementById('ob-store-options');
    if (el) {
      el.innerHTML = stores.map(s => `
        <div class="ob-store-option${s === 'paknsave-lower-hutt' ? ' selected' : ''}" data-store="${_esc(s)}" onclick="obSelectStore(this, '${_esc(s)}')">
          ${_esc(s.replace('paknsave-', 'PAK\'nSave ').replace(/-/g, ' ').replace(/\b\w/g, c => c.toUpperCase()))}
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
    `<span class="excl-tag">${_esc(t)}<span class="excl-tag-remove" onclick="obRemoveExclusion('${_esc(t)}')">✕</span></span>`
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

// ── Theme picker (step 2) ─────────────────────────────────────────
function renderObThemeChips() {
  const el = document.getElementById('ob-theme-chips');
  if (!el) return;
  el.innerHTML = _obThemeList.map(t => `
    <button type="button" class="ob-theme-chip${_obThemes.includes(t.id) ? ' selected' : ''}"
            data-theme="${_esc(t.id)}" onclick="obToggleTheme('${_esc(t.id)}')">${_esc(t.label)}</button>
  `).join('');
}

function obToggleTheme(id) {
  _obThemes = _obThemes.includes(id) ? _obThemes.filter(t => t !== id) : [..._obThemes, id];
  renderObThemeChips();
}

// Continue from the theme step: pull suggested staples for the chosen themes,
// then advance to the confirm-your-pantry step.
async function obThemesNext() {
  if (!_obThemes.length) { obNext(); return; }
  const list = document.getElementById('ob-pantry-list');
  if (list) list.innerHTML = '<div class="pantry-confirm-empty">Loading staples…</div>';
  try {
    const data = await apiFetch('/pantry/suggestions', { params: { themes: _obThemes.join(',') } });
    _obPantrySuggestions = data.suggestions || [];
    // Default everything ticked — it's faster to untick the few you lack.
    _obPantryChecked = new Set(_obPantrySuggestions.map(s => s.canonical));
  } catch (_) {
    _obPantrySuggestions = [];
  }
  renderObPantryList();
  obNext();
}

function renderObPantryList() {
  const list = document.getElementById('ob-pantry-list');
  if (!list) return;
  if (!_obPantrySuggestions.length) {
    list.innerHTML = `<div class="pantry-confirm-empty">No suggestions — you can add pantry staples any time from Settings.</div>`;
    return;
  }
  list.innerHTML = _obPantrySuggestions.map(s => {
    const checked = _obPantryChecked.has(s.canonical);
    return `
      <label class="pantry-confirm-item${checked ? '' : ' pantry-confirm-item--off'}">
        <input type="checkbox" ${checked ? 'checked' : ''} onchange="obTogglePantryItem('${_esc(s.canonical)}')">
        <span class="pantry-confirm-box" aria-hidden="true"></span>
        <span class="pantry-confirm-name">${_esc(s.name)}</span>
      </label>`;
  }).join('');
}

function obTogglePantryItem(canonical) {
  if (_obPantryChecked.has(canonical)) _obPantryChecked.delete(canonical);
  else _obPantryChecked.add(canonical);
  renderObPantryList();
}

async function finishOnboarding() {
  const budget = parseFloat(document.getElementById('ob-budget')?.value) || 60;
  const serves = parseInt(document.getElementById('ob-serves')?.value) || 2;
  const storeId = _obStore || 'paknsave-lower-hutt';

  try {
    await apiFetch('/settings/', {
      method: 'PUT',
      body: JSON.stringify({ budget, serves, storeId, exclusions: _obExclusions, mealThemes: _obThemes }),
    });
  } catch (e) { console.error('[ONBOARDING] Settings save failed:', e); }

  // Seed the pantry with the staples the user confirmed they already own.
  const confirmed = (_obPantrySuggestions || []).filter(s => _obPantryChecked.has(s.canonical));
  if (confirmed.length) {
    try {
      await apiFetch('/pantry/bulk', {
        method: 'POST',
        body: JSON.stringify({ items: confirmed.map(s => ({ name: s.name, canonical: s.canonical })) }),
      });
    } catch (e) { console.error('[ONBOARDING] Pantry seed failed:', e); }
  }

  document.getElementById('onboarding-overlay').style.display = 'none';
  if (window._obResolve) { window._obResolve(); window._obResolve = null; }

  // Show install prompt after onboarding
  showInstallBannerIfAvailable();
}

