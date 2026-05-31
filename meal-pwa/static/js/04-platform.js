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
const _PROTEIN_CHIP = {
  chicken:    { label: 'Chicken', color: '#f59e0b', bg: 'rgba(245,158,11,0.15)' },
  beef:       { label: 'Beef',    color: '#ef4444', bg: 'rgba(239,68,68,0.15)' },
  pork:       { label: 'Pork',    color: '#f97316', bg: 'rgba(249,115,22,0.15)' },
  lamb:       { label: 'Lamb',    color: '#a78bfa', bg: 'rgba(167,139,250,0.15)' },
  vegetarian: { label: 'Vege',    color: '#22c55e', bg: 'rgba(34,197,94,0.15)' },
  other:      { label: 'Other',   color: '#94a3b8', bg: 'rgba(148,163,184,0.15)' },
};
const _DAY_LABELS = ['MON', 'TUE', 'WED', 'THU', 'FRI', 'SAT', 'SUN'];

function renderMealCards() {
  const cooked = plan?.bundleId ? getCookedSet(plan.bundleId) : new Set();
  const recipes = plan?.recipes || [];

  document.getElementById('meal-cards').innerHTML = recipes.map((meal, i) => {
    const isCooked   = cooked.has(meal.recipeId);
    const protein    = inferProtein(meal);
    const chip       = _PROTEIN_CHIP[protein] || _PROTEIN_CHIP.other;
    const day        = _DAY_LABELS[i] || `Day ${i + 1}`;
    const rating     = lastRating(meal);
    const cost       = meal.estimatedCost != null ? fmt$(meal.estimatedCost) : null;

    const ratingBadge = rating === 1
      ? `<span class="meal-card__rating-badge meal-card__rating-badge--up" title="You liked this">👍</span>`
      : rating === -1
      ? `<span class="meal-card__rating-badge meal-card__rating-badge--down" title="You disliked this">👎</span>`
      : '';

    const cookedBadge = isCooked
      ? `<span class="meal-card__cooked-badge" title="Cooked">
           <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" width="14" height="14"><path d="M20 6L9 17l-5-5"/></svg>
         </span>`
      : '';

    const swapBtn = !isCooked
      ? `<button class="meal-card__swap-pill" onclick="event.stopPropagation();openSwapPicker('${_esc(meal.recipeId)}','${protein}')" title="Swap this meal">⇄ Swap</button>`
      : '';

    return `
      <div class="meal-card${isCooked ? ' meal-card--cooked' : ''}" data-recipe-id="${_esc(meal.recipeId)}" onclick="openRecipe('${_esc(meal.recipeId)}')">
        <div class="meal-card-swipe-hint">✓ Cooked</div>
        <div class="meal-card__top-row">
          <span class="meal-card__day-pill">${day}</span>
          ${cookedBadge}
        </div>
        <div class="meal-card__name">${_esc(meal.name)}</div>
        <div class="meal-card__protein-chip" style="color:${chip.color};background:${chip.bg}">${chip.label}</div>
        <div class="meal-card__footer">
          <span class="meal-card__meta">⏱ ${_esc(meal.cookTime)}</span>
          ${cost ? `<span class="meal-card__cost">${cost}</span>` : ''}
          <div class="meal-card__footer-right">${ratingBadge}${swapBtn}</div>
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
let activeCost    = 'all';
let filterOpen    = false;
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

