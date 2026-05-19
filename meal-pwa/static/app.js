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
let _viewingBundleId = localStorage.getItem('viewingBundleId') || null;

// ── Auth Router ───────────────────────────────────────────────────
const EMAIL_RE = /^[^@\s]+@[^@\s]+\.[^@\s]+$/;
const _authRoot = () => document.getElementById('auth-root');

function _showAuthRoot() {
  _authRoot().classList.add('visible');
  const app = document.getElementById('app');
  if (app) app.style.visibility = 'hidden';
}
function _hideAuthRoot() {
  _authRoot().classList.remove('visible');
  const app = document.getElementById('app');
  if (app) app.style.visibility = '';
  if (window._authResolve) { window._authResolve(); window._authResolve = null; }
}
function _renderAuth(html) { _authRoot().innerHTML = html; _showAuthRoot(); }

function _pwStrength(pw) {
  let s = 0;
  if (pw.length >= 8) s++;
  if (pw.length >= 12) s++;
  if (/[A-Z]/.test(pw)) s++;
  if (/[0-9]/.test(pw)) s++;
  if (/[^A-Za-z0-9]/.test(pw)) s++;
  return s; // 0–5
}

function _strengthLabel(s) {
  if (s <= 1) return ['Weak', 'var(--red)', `${s * 20 + 10}%`];
  if (s <= 3) return ['Fair', '#f59e0b', `${s * 20}%`];
  return ['Strong', 'var(--accent)', `${Math.min(s * 20, 100)}%`];
}

function _bindStrengthBar(inputId, wrapId, fillId, labelId) {
  const inp = document.getElementById(inputId);
  const wrap = document.getElementById(wrapId);
  const fill = document.getElementById(fillId);
  const lbl = document.getElementById(labelId);
  if (!inp) return;
  inp.addEventListener('input', () => {
    const pw = inp.value;
    if (!pw) { wrap.classList.remove('visible'); return; }
    wrap.classList.add('visible');
    const [text, color, width] = _strengthLabel(_pwStrength(pw));
    fill.style.width = width;
    fill.style.background = color;
    lbl.textContent = text;
    lbl.style.color = color;
  });
}

function _bindEmailValidation(inputId, errorId) {
  const inp = document.getElementById(inputId);
  const err = document.getElementById(errorId);
  if (!inp) return;
  inp.addEventListener('blur', () => {
    const v = inp.value.trim();
    if (!v) return;
    if (!EMAIL_RE.test(v)) {
      inp.classList.add('invalid'); inp.classList.remove('valid');
      _showFieldError(errorId, 'Please enter a valid email address');
    } else {
      inp.classList.remove('invalid'); inp.classList.add('valid');
      _hideFieldError(errorId);
    }
  });
}

function _showFieldError(id, msg) {
  const el = document.getElementById(id);
  if (el) { el.textContent = msg; el.classList.add('visible'); }
}
function _hideFieldError(id) {
  const el = document.getElementById(id);
  if (el) { el.classList.remove('visible'); }
}
function _showFormError(id, msg) {
  const el = document.getElementById(id);
  if (el) { el.textContent = msg; el.classList.add('visible'); }
}
function _hideFormError(id) {
  const el = document.getElementById(id);
  if (el) el.classList.remove('visible');
}

function _authNav(path) {
  window.history.pushState({}, '', path);
  _routeAuth(path);
}

function _routeAuth(path) {
  if (path === '/login') return _renderLoginPage();
  if (path === '/register') return _renderRegisterPage();
  if (path === '/forgot-password') return _renderForgotPage();
  if (path === '/reset-password') return _renderResetPage();
}

// ── Login page ────────────────────────────────────────────────────
const _AUTH_LOGO_SVG = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><path d="M8 12c0-2.2 1.8-4 4-4s4 1.8 4 4"/><path d="M12 12v4"/><circle cx="12" cy="17" r="0.5" fill="currentColor"/></svg>`;
const _ICON_EMAIL    = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="4" width="20" height="16" rx="2"/><path d="m2 7 10 7 10-7"/></svg>`;
const _ICON_LOCK     = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="11" width="18" height="11" rx="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg>`;

function _authLogoHtml() {
  return `
    <div class="auth-logo-mark">${_AUTH_LOGO_SVG}</div>
    <div class="auth-page-logo">Kai <span>Planner</span></div>
    <div class="auth-page-tagline">Plan 5 dinners a week from PAK'nSave prices</div>`;
}

function _renderLoginPage() {
  _renderAuth(`
    <div class="auth-page">
      ${_authLogoHtml()}
      <div class="auth-form">
        <div class="auth-card-title">Sign in</div>
        <div class="auth-form-error" id="login-form-err"></div>
        <div class="auth-field">
          <div class="auth-input-wrap">
            <span class="auth-input-icon">${_ICON_EMAIL}</span>
            <input class="auth-input" id="login-email" type="email" placeholder="Email address"
              autocomplete="email" inputmode="email">
          </div>
          <div class="auth-field-error" id="login-email-err"></div>
        </div>
        <div class="auth-field">
          <div class="auth-input-wrap">
            <span class="auth-input-icon">${_ICON_LOCK}</span>
            <input class="auth-input" id="login-pw" type="password" placeholder="Password"
              autocomplete="current-password">
          </div>
          <div class="auth-field-error" id="login-pw-err"></div>
        </div>
        <button class="auth-submit-btn" id="login-btn" onclick="_doLogin()">Sign in →</button>
        <div class="auth-switch">
          <a onclick="_authNav('/forgot-password')">Forgot password?</a>
        </div>
        <div class="auth-switch">
          Don't have an account? <a onclick="_authNav('/register')">Create one</a>
        </div>
      </div>
    </div>`);
  _bindEmailValidation('login-email', 'login-email-err');
  document.getElementById('login-email').addEventListener('keydown', e => { if (e.key === 'Enter') document.getElementById('login-pw').focus(); });
  document.getElementById('login-pw').addEventListener('keydown', e => { if (e.key === 'Enter') _doLogin(); });
}

async function _doLogin() {
  const email = document.getElementById('login-email')?.value?.trim();
  const pw = document.getElementById('login-pw')?.value;
  _hideFormError('login-form-err');
  if (!email || !EMAIL_RE.test(email)) return _showFieldError('login-email-err', 'Please enter a valid email address');
  if (!pw) return _showFieldError('login-pw-err', 'Please enter your password');

  const btn = document.getElementById('login-btn');
  btn.disabled = true; btn.textContent = 'Signing in…';
  try {
    const res = await fetch(`${API}/auth/login`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      credentials: 'include', body: JSON.stringify({ email, password: pw }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Invalid email or password');
    currentUser = { userId: data.userId, email: data.email, householdId: data.householdId };
    _setLogoutVisible(true);
    _hideAuthRoot();
    window.history.replaceState({}, '', '/');
  } catch (err) {
    btn.disabled = false; btn.textContent = 'Sign in →';
    _showFormError('login-form-err', err.message);
  }
}

// ── Register page ─────────────────────────────────────────────────
function _renderRegisterPage() {
  _renderAuth(`
    <div class="auth-page">
      ${_authLogoHtml()}
      <div class="auth-form">
        <div class="auth-card-title">Create account</div>
        <div class="auth-form-error" id="reg-form-err"></div>
        <div class="auth-field">
          <div class="auth-input-wrap">
            <span class="auth-input-icon">${_ICON_EMAIL}</span>
            <input class="auth-input" id="reg-email" type="email" placeholder="Email address"
              autocomplete="email" inputmode="email">
          </div>
          <div class="auth-field-error" id="reg-email-err"></div>
        </div>
        <div class="auth-field">
          <div class="auth-input-wrap">
            <span class="auth-input-icon">${_ICON_LOCK}</span>
            <input class="auth-input" id="reg-pw" type="password" placeholder="Password (8+ characters)"
              autocomplete="new-password">
          </div>
          <div class="auth-field-error" id="reg-pw-err"></div>
          <div class="pw-strength-wrap" id="reg-pw-wrap">
            <div class="pw-strength-bar"><div class="pw-strength-fill" id="reg-pw-fill"></div></div>
            <div class="pw-strength-label" id="reg-pw-lbl"></div>
          </div>
        </div>
        <div class="auth-field">
          <div class="auth-input-wrap">
            <span class="auth-input-icon">${_ICON_LOCK}</span>
            <input class="auth-input" id="reg-confirm" type="password" placeholder="Confirm password"
              autocomplete="new-password">
          </div>
          <div class="auth-field-error" id="reg-confirm-err"></div>
        </div>
        <button class="auth-submit-btn" id="reg-btn" onclick="_doRegister()">Create account →</button>
        <div class="auth-switch">
          Already have an account? <a onclick="_authNav('/login')">Sign in</a>
        </div>
      </div>
    </div>`);
  _bindEmailValidation('reg-email', 'reg-email-err');
  _bindStrengthBar('reg-pw', 'reg-pw-wrap', 'reg-pw-fill', 'reg-pw-lbl');
  document.getElementById('reg-pw').addEventListener('keydown', e => { if (e.key === 'Enter') document.getElementById('reg-confirm').focus(); });
  document.getElementById('reg-confirm').addEventListener('keydown', e => { if (e.key === 'Enter') _doRegister(); });
  document.getElementById('reg-confirm').addEventListener('input', () => {
    const pw = document.getElementById('reg-pw')?.value;
    const c = document.getElementById('reg-confirm')?.value;
    if (c && pw !== c) _showFieldError('reg-confirm-err', 'Passwords do not match');
    else _hideFieldError('reg-confirm-err');
  });
}

async function _doRegister() {
  const email = document.getElementById('reg-email')?.value?.trim();
  const pw = document.getElementById('reg-pw')?.value;
  const confirm = document.getElementById('reg-confirm')?.value;
  _hideFormError('reg-form-err');
  if (!email || !EMAIL_RE.test(email)) return _showFieldError('reg-email-err', 'Please enter a valid email address');
  if (!pw || pw.length < 8) return _showFieldError('reg-pw-err', 'Password must be at least 8 characters');
  if (pw !== confirm) return _showFieldError('reg-confirm-err', 'Passwords do not match');

  const btn = document.getElementById('reg-btn');
  btn.disabled = true; btn.textContent = 'Creating account…';
  try {
    const res = await fetch(`${API}/auth/register`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      credentials: 'include', body: JSON.stringify({ email, password: pw }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Registration failed');
    currentUser = { userId: data.userId, email: data.email, householdId: data.householdId };
    _setLogoutVisible(true);
    _hideAuthRoot();
    window.history.replaceState({}, '', '/');
    if (data.isNewUser) await showOnboarding();
  } catch (err) {
    btn.disabled = false; btn.textContent = 'Create account →';
    _showFormError('reg-form-err', err.message);
  }
}

// ── Forgot password page ──────────────────────────────────────────
function _renderForgotPage() {
  _renderAuth(`
    <div class="auth-page">
      ${_authLogoHtml()}
      <div class="auth-form">
        <div class="auth-card-title">Reset password</div>
        <div id="forgot-confirm" style="display:none">
          <div class="auth-confirm-msg">
            If that email is registered, we've sent a reset link. Check your inbox.
          </div>
          <div class="auth-switch"><a onclick="_authNav('/login')">Back to sign in</a></div>
        </div>
        <div id="forgot-form-wrap">
          <div class="auth-form-error" id="forgot-form-err"></div>
          <div class="auth-field">
            <div class="auth-input-wrap">
              <span class="auth-input-icon">${_ICON_EMAIL}</span>
              <input class="auth-input" id="forgot-email" type="email" placeholder="Email address"
                autocomplete="email" inputmode="email">
            </div>
            <div class="auth-field-error" id="forgot-email-err"></div>
          </div>
          <button class="auth-submit-btn" id="forgot-btn" onclick="_doForgot()">Send reset link →</button>
          <div class="auth-switch"><a onclick="_authNav('/login')">Back to sign in</a></div>
        </div>
      </div>
    </div>`);
  _bindEmailValidation('forgot-email', 'forgot-email-err');
  document.getElementById('forgot-email').addEventListener('keydown', e => { if (e.key === 'Enter') _doForgot(); });
}

async function _doForgot() {
  const email = document.getElementById('forgot-email')?.value?.trim();
  _hideFormError('forgot-form-err');
  if (!email || !EMAIL_RE.test(email)) return _showFieldError('forgot-email-err', 'Please enter a valid email address');

  const btn = document.getElementById('forgot-btn');
  btn.disabled = true; btn.textContent = 'Sending…';
  try {
    await fetch(`${API}/auth/forgot-password`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      credentials: 'include', body: JSON.stringify({ email }),
    });
  } catch (_) {}
  document.getElementById('forgot-form-wrap').style.display = 'none';
  document.getElementById('forgot-confirm').style.display = '';
}

// ── Reset password page ───────────────────────────────────────────
function _renderResetPage() {
  const token = new URLSearchParams(window.location.search).get('token');
  if (!token) { _authNav('/forgot-password'); return; }
  _renderAuth(`
    <div class="auth-page">
      ${_authLogoHtml()}
      <div class="auth-form">
        <div class="auth-card-title">Set new password</div>
        <div id="reset-success" style="display:none">
          <div class="auth-confirm-msg">Password updated! Redirecting to sign in…</div>
        </div>
        <div id="reset-form-wrap">
          <div class="auth-form-error" id="reset-form-err"></div>
          <div class="auth-field">
            <div class="auth-input-wrap">
              <span class="auth-input-icon">${_ICON_LOCK}</span>
              <input class="auth-input" id="reset-pw" type="password" placeholder="New password (8+ characters)"
                autocomplete="new-password">
            </div>
            <div class="auth-field-error" id="reset-pw-err"></div>
            <div class="pw-strength-wrap" id="reset-pw-wrap">
              <div class="pw-strength-bar"><div class="pw-strength-fill" id="reset-pw-fill"></div></div>
              <div class="pw-strength-label" id="reset-pw-lbl"></div>
            </div>
          </div>
          <div class="auth-field">
            <div class="auth-input-wrap">
              <span class="auth-input-icon">${_ICON_LOCK}</span>
              <input class="auth-input" id="reset-confirm" type="password" placeholder="Confirm new password"
                autocomplete="new-password">
            </div>
            <div class="auth-field-error" id="reset-confirm-err"></div>
          </div>
          <button class="auth-submit-btn" id="reset-btn" onclick="_doReset('${token}')">Set new password →</button>
        </div>
      </div>
    </div>`);
  _bindStrengthBar('reset-pw', 'reset-pw-wrap', 'reset-pw-fill', 'reset-pw-lbl');
  document.getElementById('reset-pw').addEventListener('keydown', e => { if (e.key === 'Enter') document.getElementById('reset-confirm').focus(); });
  document.getElementById('reset-confirm').addEventListener('keydown', e => { if (e.key === 'Enter') _doReset(token); });
}

async function _doReset(token) {
  const pw = document.getElementById('reset-pw')?.value;
  const confirm = document.getElementById('reset-confirm')?.value;
  _hideFormError('reset-form-err');
  if (!pw || pw.length < 8) return _showFieldError('reset-pw-err', 'Password must be at least 8 characters');
  if (pw !== confirm) return _showFieldError('reset-confirm-err', 'Passwords do not match');

  const btn = document.getElementById('reset-btn');
  btn.disabled = true; btn.textContent = 'Saving…';
  try {
    const res = await fetch(`${API}/auth/reset-password`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      credentials: 'include', body: JSON.stringify({ token, password: pw }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Reset failed');
    document.getElementById('reset-form-wrap').style.display = 'none';
    document.getElementById('reset-success').style.display = '';
    setTimeout(() => { window.history.replaceState({}, '', '/login'); _renderLoginPage(); }, 2000);
  } catch (err) {
    btn.disabled = false; btn.textContent = 'Set new password →';
    _showFormError('reset-form-err', err.message);
  }
}

// ── Magic link callback (legacy Android deep link) ────────────────
async function handleAuthCallback(token) {
  _renderAuth('<div class="auth-page"><div class="auth-page-logo">Kai <span>Planner</span></div><div class="auth-page-tagline">Signing you in…</div></div>');
  try {
    const res = await fetch(`${API}/auth/verify?token=${encodeURIComponent(token)}`, { credentials: 'include' });
    if (!res.ok) throw new Error('Invalid link');
    const data = await res.json();
    currentUser = { userId: data.userId, email: data.email, householdId: data.householdId };
    _setLogoutVisible(true);
    _hideAuthRoot();
    window.history.replaceState({}, '', '/');
    if (data.isNewUser) await showOnboarding();
  } catch (_) {
    _authNav('/login');
  }
}

// ── Main auth init ────────────────────────────────────────────────
async function initAuth() {
  const path = window.location.pathname;
  const params = new URLSearchParams(window.location.search);

  // Magic link callback
  const authToken = params.get('auth_token');
  if (authToken) {
    window.history.replaceState({}, '', '/');
    await handleAuthCallback(authToken);
    return;
  }

  // Invite token
  const inviteToken = params.get('invite_token');
  if (inviteToken) window.history.replaceState({}, '', '/');

  // Auth routes — render immediately without checking session
  if (['/login', '/register', '/forgot-password', '/reset-password'].includes(path)) {
    _routeAuth(path);
    await waitForLogin();
    return;
  }

  // Check existing session
  try {
    const res = await fetch(`${API}/auth/me`, { credentials: 'include' });
    if (res.ok) {
      currentUser = await res.json();
      log('AUTH', 'Signed in', { email: currentUser.email });
      _setLogoutVisible(true);
      if (inviteToken) await handleInviteToken(inviteToken);
      return;
    }
  } catch (_) { /* network error — fall through to login */ }

  // No session — redirect to login
  window.history.replaceState({}, '', '/login');
  _renderLoginPage();
  await waitForLogin();
}

function waitForLogin() {
  return new Promise(resolve => { window._authResolve = resolve; });
}

async function logout() {
  await fetch(`${API}/auth/logout`, { method: 'POST', credentials: 'include' });
  currentUser = null;
  _setLogoutVisible(false);
  window.history.pushState({}, '', '/login');
  _renderLoginPage();
  await waitForLogin();
  await loadSettings();
  await loadWeek();
  loadShopping();
}

// ── Sessions in settings ─────────────────────────────────────────
async function renderSessionsSection() {
  const section = document.getElementById('sessions-section');
  if (!currentUser || !section) return;
  section.style.display = '';
  const list = document.getElementById('sessions-list');
  list.innerHTML = '<div class="settings-hint">Loading…</div>';
  try {
    const res = await fetch(`${API}/auth/sessions`, { credentials: 'include' });
    const sessions = await res.json();
    if (!sessions.length) { list.innerHTML = '<div class="settings-hint">No active sessions</div>'; return; }
    list.innerHTML = sessions.map(s => {
      const ua = s.userAgent || 'Unknown device';
      const device = ua.length > 40 ? ua.slice(0, 40) + '…' : ua;
      const date = s.createdAt ? new Date(s.createdAt).toLocaleDateString() : '';
      const currentBadge = s.isCurrent ? '<span class="session-badge">Current</span>' : '';
      const revokeBtn = s.isCurrent ? '' :
        `<button class="session-revoke-btn" onclick="revokeSession('${s.sessionId}')">Revoke</button>`;
      return `<div class="session-card">
        <div class="session-info">
          <div class="session-device">${device}${currentBadge}</div>
          <div class="session-meta">${date} · ${s.ipAddress || ''}</div>
        </div>
        ${revokeBtn}
      </div>`;
    }).join('');
  } catch (_) {
    list.innerHTML = '<div class="settings-hint">Could not load sessions</div>';
  }
}

async function revokeSession(sessionId) {
  try {
    await fetch(`${API}/auth/sessions/${sessionId}`, { method: 'DELETE', credentials: 'include' });
    await renderSessionsSection();
  } catch (_) { showToast('Could not revoke session'); }
}

async function revokeAllSessions() {
  if (!confirm('Log out of all devices? You will need to sign in again.')) return;
  try {
    await fetch(`${API}/auth/sessions`, { method: 'DELETE', credentials: 'include' });
    await logout();
  } catch (_) { showToast('Could not log out of all devices'); }
}

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
      : `<button class="meal-card__swap-btn" onclick="event.stopPropagation();openSwapPicker('${_esc(meal.recipeId)}','${protein}')" title="Swap this meal">
           <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" width="14" height="14"><path d="M7 16V4m0 0L3 8m4-4l4 4M17 8v12m0 0l4-4m-4 4l-4-4"/></svg>
         </button>`;

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
          ${ratingBadge}
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
  if (res.status === 401) {
    // Session expired or revoked — redirect to login
    currentUser = null;
    _setLogoutVisible(false);
    window.history.pushState({}, '', '/login');
    _routeAuth('/login');
    throw new Error('Not authenticated');
  }
  if (!res.ok) throw new Error(`HTTP ${res.status}: ${res.statusText} (${url})`);
  return res.json();
}

async function apiPost(path, body = null, method = 'POST') {
  return apiFetch(path, { method, body });
}

// ── Tab switching ───────────────────────────────────────────────
let _currentTab = 'week';

function _updateFab(view) {
  const fab = document.getElementById('tab-fab');
  if (!fab) return;
  const icon = document.getElementById('fab-icon');
  if (view === 'week') {
    fab.style.display = '';
    fab.setAttribute('aria-label', 'Generate plan');
    if (icon) icon.innerHTML = `<path d="M12 5v14M5 12h14"/>`;
  } else if (view === 'shopping') {
    fab.style.display = '';
    fab.setAttribute('aria-label', 'Add item');
    if (icon) icon.innerHTML = `<path d="M12 5v14M5 12h14"/>`;
  } else {
    fab.style.display = 'none';
  }
}

function fabAction() {
  if (_currentTab === 'week') generatePlan();
  else if (_currentTab === 'shopping') focusAdHocInput();
}

function focusAdHocInput() {
  const input = document.getElementById('shop-adhoc-input');
  if (input) input.focus();
}

document.querySelectorAll('.tab').forEach(tab => {
  tab.addEventListener('click', () => {
    document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('.view').forEach(v => v.classList.remove('active'));
    tab.classList.add('active');
    _currentTab = tab.dataset.view;
    document.getElementById(`view-${tab.dataset.view}`).classList.add('active');
    if (tab.dataset.view === 'recipes') renderWeekRecipesInTab();
    _updateFab(tab.dataset.view);
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

// ── Empty & error states ─────────────────────────────────────────
const _SVG_CALENDAR = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="4" width="18" height="18" rx="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/><rect x="7" y="14" width="3" height="3" rx="0.5"/><rect x="14" y="14" width="3" height="3" rx="0.5"/></svg>`;
const _SVG_BAG      = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M6 2L3 6v14a2 2 0 002 2h14a2 2 0 002-2V6l-3-4z"/><line x1="3" y1="6" x2="21" y2="6"/><path d="M16 10a4 4 0 01-8 0"/></svg>`;
const _SVG_SEARCH   = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>`;

function _emptyState({ icon, title, subtitle, ctaLabel, ctaFn }) {
  return `<div class="empty-state">
    <div class="empty-state__icon">${icon}</div>
    <div class="empty-state__title">${_esc(title)}</div>
    ${subtitle ? `<div class="empty-state__subtitle">${_esc(subtitle)}</div>` : ''}
    ${ctaLabel ? `<button class="empty-state__cta" onclick="${ctaFn}">${_esc(ctaLabel)}</button>` : ''}
  </div>`;
}

// ── Skeleton screens ─────────────────────────────────────────────
function renderWeekSkeletons() {
  const skels = Array.from({ length: 5 }, () => `
    <div class="skeleton-card">
      <div class="skeleton-row">
        <div class="skeleton skeleton-pill"></div>
        <div class="skeleton" style="width:28px;height:28px;border-radius:6px"></div>
      </div>
      <div class="skeleton skeleton-title"></div>
      <div class="skeleton skeleton-pill" style="width:60px;margin-bottom:10px"></div>
      <div class="skeleton skeleton-row">
        <div class="skeleton skeleton-line" style="width:30%"></div>
        <div class="skeleton skeleton-line" style="width:20%"></div>
      </div>
    </div>`).join('');

  const statSkel = `
    <div class="week-stat-bar" style="margin-bottom:10px">
      ${Array.from({ length: 3 }, () => `
        <div class="stat-card">
          <div class="skeleton" style="width:50px;height:22px;margin-bottom:6px;border-radius:6px"></div>
          <div class="skeleton" style="width:60px;height:9px;border-radius:4px"></div>
        </div>`).join('')}
    </div>`;

  const summaryEl = document.getElementById('week-summary');
  if (summaryEl) summaryEl.innerHTML = statSkel;
  const cardsEl = document.getElementById('meal-cards');
  if (cardsEl) cardsEl.innerHTML = skels;

  document.getElementById('week-loading').style.display = 'none';
  document.getElementById('week-content').style.display = 'block';
}

function renderShoppingSkeletons() {
  const catSkel = Array.from({ length: 3 }, (_, ci) => `
    <div class="shop-category-group">
      <div class="skeleton" style="width:80px;height:11px;border-radius:4px;margin:10px 16px 4px"></div>
      ${Array.from({ length: 4 }, () => `
        <div class="skeleton-row" style="padding:10px 16px">
          <div class="skeleton skeleton-check"></div>
          <div style="flex:1;display:flex;flex-direction:column;gap:4px">
            <div class="skeleton skeleton-line" style="width:60%"></div>
            <div class="skeleton skeleton-line" style="width:35%"></div>
          </div>
          <div class="skeleton skeleton-line" style="width:36px"></div>
        </div>`).join('')}
    </div>`).join('');

  document.getElementById('shopping-loading').style.display = 'none';
  document.getElementById('shopping-content').style.display = 'block';
  const itemsEl = document.getElementById('shopping-items');
  if (itemsEl) itemsEl.innerHTML = catSkel;
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
function _clearViewingBundle() {
  _viewingBundleId = null;
  localStorage.removeItem('viewingBundleId');
  document.getElementById('viewing-banner')?.remove();
}

async function _viewBundle(bundleId, weekLabel) {
  _viewingBundleId = bundleId;
  localStorage.setItem('viewingBundleId', bundleId);
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
    document.getElementById('week-loading').innerHTML =
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
}

const _CATEGORY_LABELS = {
  protein: '🥩 Meat & Seafood',
  vegetable: '🥦 Produce',
  dairy: '🧀 Dairy & Eggs',
  pantry: '🫙 Pantry',
  other: '🛒 Other',
};

function _shopRunningTotal(items) {
  const unchecked = items.filter((_, i) => !checked[i]);
  const cost = unchecked.reduce((s, item) => s + (item.estimatedCost || 0), 0);
  return { count: unchecked.length, cost };
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

  const noResultsHtml = recipeSearch
    ? _emptyState({ icon: _SVG_SEARCH, title: `No recipes match "${recipeSearch}"`, subtitle: null, ctaLabel: 'Clear search', ctaFn: 'clearSearch()' })
    : _emptyState({ icon: _SVG_SEARCH, title: 'No recipes yet', subtitle: 'Recipes will appear here once added.' });

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
              <div class="recipe-list-name">${_esc(meal.name)}${badge}</div>
              <div class="recipe-list-meta">⏱ ${_esc(meal.cookTime)} · ${meal.ingredients?.length || 0} ingredients</div>
            </div>
            <div style="color:var(--text-muted)">›</div>
          </div>`;
      }).join('')
    : noResultsHtml;
}

function clearSearch() {
  recipeSearch = '';
  const el = document.getElementById('recipe-search');
  if (el) el.value = '';
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
  // Stub — full implementation in MEA-158 (single meal swap)
  // For now open the recipe picker filtered to same protein
  openRecipePicker && openRecipePicker({ swapRecipeId: recipeId, filterProtein: protein });
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
  const hidePantryEl = document.getElementById('setting-hide-pantry');
  if (hidePantryEl) hidePantryEl.checked = !!settings.hidePantryFromShopping;
  renderExclusionTags();
  renderPantryTags();
  renderStoreSelector();
  renderHouseholdSection();
  renderSessionsSection();
  document.getElementById('settings-backdrop').classList.add('active');
  document.getElementById('settings-sheet').classList.add('active');
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
            <div style="color:var(--accent);font-size:18px">+</div>
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

let _generating = false;

async function generatePlan() {
  if (_generating) return;
  _generating = true;

  const fab = document.getElementById('tab-fab');
  if (fab) { fab.classList.add('fab--spinning'); fab.disabled = true; }

  const _steps = ['Checking prices', 'Selecting meals', 'Building plan'];
  const statusEl = document.getElementById('generate-status');
  let _stepIdx = 0;

  function _showStep(i) {
    if (!statusEl) return;
    statusEl.style.display = 'block';
    statusEl.innerHTML = _steps.map((s, j) =>
      `<span class="gen-step ${j < i ? 'gen-step--done' : j === i ? 'gen-step--active' : ''}">${s}</span>`
    ).join('<span class="gen-sep">›</span>');
  }

  _showStep(0);
  const t1 = setTimeout(() => _showStep(1), 1500);
  const t2 = setTimeout(() => _showStep(2), 3200);

  try {
    const result = await apiPost('/plan/generate');
    clearTimeout(t1); clearTimeout(t2);
    if (statusEl) statusEl.style.display = 'none';
    await notifyNewPlan({ week: result.week });
    await loadWeek();
    loadRecipes();
    await loadShopping();
    showToast(`Plan ready · ${result.recipeCount || plan?.recipes?.length || 5} meals · ${fmt$(result.estimatedTotal || plan?.estimatedTotal || 0)} est.`, 3000);
  } catch (e) {
    clearTimeout(t1); clearTimeout(t2);
    if (statusEl) {
      statusEl.style.display = 'block';
      statusEl.innerHTML = `<span class="gen-error">Generation failed — <button class="gen-retry-btn" onclick="generatePlan()">Try again</button></span>`;
    }
    log('GENERATE', 'Error', { error: e.message });
  } finally {
    _generating = false;
    if (fab) { fab.classList.remove('fab--spinning'); fab.disabled = false; }
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

// ── Pull-to-refresh ──────────────────────────────────────────────
(function _initPullToRefresh() {
  const THRESHOLD = 64;
  let startY = 0, pulling = false, indicator = null;

  function _getIndicator() {
    if (!indicator) {
      indicator = document.createElement('div');
      indicator.className = 'ptr-indicator';
      indicator.innerHTML = '<div class="ptr-spinner"></div>';
      document.querySelector('main').prepend(indicator);
    }
    return indicator;
  }

  document.querySelector('main').addEventListener('touchstart', e => {
    const main = document.querySelector('main');
    if (main.scrollTop === 0) {
      startY = e.touches[0].clientY;
      pulling = true;
    }
  }, { passive: true });

  document.querySelector('main').addEventListener('touchmove', e => {
    if (!pulling) return;
    const dy = e.touches[0].clientY - startY;
    if (dy > 0) {
      const el = _getIndicator();
      const progress = Math.min(dy / THRESHOLD, 1);
      el.style.transform = `translateY(${Math.min(dy * 0.4, 48)}px)`;
      el.style.opacity   = String(progress);
    }
  }, { passive: true });

  document.querySelector('main').addEventListener('touchend', async e => {
    if (!pulling) return;
    pulling = false;
    const dy = e.changedTouches[0].clientY - startY;
    const el = _getIndicator();
    el.style.transform = '';
    el.style.opacity   = '0';
    if (dy > THRESHOLD) {
      el.classList.add('ptr-indicator--loading');
      el.style.opacity = '1';
      if (_currentTab === 'week')     await loadWeek();
      else if (_currentTab === 'shopping') await loadShopping();
      else if (_currentTab === 'recipes')  await loadRecipes();
      el.classList.remove('ptr-indicator--loading');
      el.style.opacity = '0';
    }
  }, { passive: true });
})();

// ── Init ────────────────────────────────────────────────────────
window.addEventListener('popstate', () => {
  const p = window.location.pathname;
  if (['/login', '/register', '/forgot-password', '/reset-password'].includes(p)) {
    _routeAuth(p);
  }
});

(async () => {
  await initAuth();
  loadPantry();
  await loadSettings();
  await loadWeek();
  loadRecipes();
  loadShopping();
  registerServiceWorker();
  _updateFab('week');

  const urlTab = new URLSearchParams(window.location.search).get('tab');
  if (urlTab) switchTab(urlTab);
})();
