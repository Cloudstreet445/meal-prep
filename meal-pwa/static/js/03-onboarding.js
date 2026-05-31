// ── Onboarding ──────────────────────────────────────────────────
let _obStep = 0;
const _obStepCount = 3;
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

async function finishOnboarding() {
  const budget = parseFloat(document.getElementById('ob-budget')?.value) || 60;
  const serves = parseInt(document.getElementById('ob-serves')?.value) || 2;
  const storeId = _obStore || 'paknsave-lower-hutt';

  try {
    await apiFetch('/settings/', {
      method: 'PUT',
      body: JSON.stringify({ budget, serves, storeId, exclusions: _obExclusions }),
    });
  } catch (e) { console.error('[ONBOARDING] Settings save failed:', e); }

  document.getElementById('onboarding-overlay').style.display = 'none';
  if (window._obResolve) { window._obResolve(); window._obResolve = null; }

  // Show install prompt after onboarding
  showInstallBannerIfAvailable();
}

