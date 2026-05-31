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
function _setLogoutVisible(visible) {
  const btn = document.getElementById('nav-logout-btn');
  if (btn) btn.style.display = visible ? '' : 'none';
  // Update header avatar
  const icon = document.getElementById('header-avatar-icon');
  const letter = document.getElementById('header-avatar-letter');
  const avatarBtn = document.getElementById('nav-menu-btn');
  const initial = currentUser?.email?.[0]?.toUpperCase() || '';
  if (icon && letter) {
    icon.style.display = visible ? 'none' : '';
    letter.style.display = visible ? '' : 'none';
    letter.textContent = initial;
  }
  if (avatarBtn) avatarBtn.classList.toggle('signed-in', visible && !!initial);
}

function openNavMenu() {
  document.getElementById('nav-menu-backdrop').classList.add('active');
  document.getElementById('nav-menu-sheet').classList.add('active');
  updateNavThemeItem();
  updateNavPlanDesc();
  _setLogoutVisible(!!currentUser);
  // Update drawer profile
  const drawerAvatar = document.getElementById('drawer-avatar');
  const drawerName = document.getElementById('drawer-user-name');
  const drawerEmail = document.getElementById('drawer-user-email');
  const emailEl = document.getElementById('nav-user-email');
  if (currentUser?.email) {
    const initial = currentUser.email[0].toUpperCase();
    if (drawerAvatar) { drawerAvatar.textContent = initial; drawerAvatar.classList.add('signed-in'); }
    if (drawerName) drawerName.textContent = initial + currentUser.email.slice(1, currentUser.email.indexOf('@')) || 'You';
    if (drawerEmail) { drawerEmail.textContent = currentUser.email; drawerEmail.style.display = ''; }
    if (emailEl) emailEl.textContent = currentUser.email;
  } else {
    if (drawerAvatar) {
      drawerAvatar.innerHTML = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="8" r="4"/><path d="M4 20c0-4 3.6-7 8-7s8 3 8 7"/></svg>`;
      drawerAvatar.classList.remove('signed-in');
    }
    if (drawerName) drawerName.textContent = 'Kai Planner';
    if (drawerEmail) drawerEmail.style.display = 'none';
  }
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
  const toggle = document.getElementById('drawer-theme-toggle');
  const moonSVG = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12.79A9 9 0 1111.21 3 7 7 0 0021 12.79z"/></svg>`;
  const sunSVG = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="5"/><path d="M12 1v2M12 21v2M4.22 4.22l1.42 1.42M18.36 18.36l1.42 1.42M1 12h2M21 12h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42"/></svg>`;
  if (icon) icon.innerHTML = isDark ? moonSVG : sunSVG;
  if (name) name.textContent = isDark ? 'Dark Mode' : 'Light Mode';
  if (toggle) toggle.classList.toggle('on', isDark);
}

function updateNavPlanDesc() {
  const desc = document.getElementById('nav-plan-desc');
  if (desc && plan?.week) desc.textContent = `Week of ${fmtWeek(plan.week)}`;
}

// ── HTML escape utility (XSS prevention) ─────────────────────────
function _esc(str) {
  return String(str ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

// ── Logging utility ──────────────────────────────────────────────
function log(section, message, data = null) {
  const timestamp = new Date().toISOString();
  const msg = `[${timestamp}] [${section}] ${message}`;
  console.log(msg, data || '');
}

// ── Config ──────────────────────────────────────────────────────
// API calls go to /api/ — proxied internally by nginx to the API service.
const API = '/api';

// ── State ───────────────────────────────────────────────────────
let _detailRecipeId = null;
let plan          = null;
let checked       = {};
let currentWeek   = null;
let currentUser   = null;   // { userId, email, householdId } or null
let _viewingBundleId = null; // session-only — never persisted across page loads
let swapState = null;        // { recipeId, protein } when a meal-swap is in progress

