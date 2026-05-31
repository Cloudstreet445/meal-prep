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
async function _safeJson(res) {
  try { return await res.json(); } catch (_) { return {}; }
}

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
    const data = await _safeJson(res);
    if (res.status === 429) throw new Error('Too many attempts — please wait a minute and try again');
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
    const data = await _safeJson(res);
    if (res.status === 429) throw new Error('Too many attempts — please wait a minute and try again');
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
    const res = await fetch(`${API}/auth/forgot-password`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      credentials: 'include', body: JSON.stringify({ email }),
    });
    if (res.status === 429) {
      btn.disabled = false; btn.textContent = 'Send reset link';
      return _showFormError('forgot-form-err', 'Too many attempts — please wait a minute and try again');
    }
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
    const data = await _safeJson(res);
    if (!res.ok) throw new Error(data.detail || 'Reset failed');
    document.getElementById('reset-form-wrap').style.display = 'none';
    document.getElementById('reset-success').style.display = '';
    setTimeout(() => { window.history.replaceState({}, '', '/login'); _renderLoginPage(); }, 2000);
  } catch (err) {
    btn.disabled = false; btn.textContent = 'Set new password →';
    _showFormError('reset-form-err', err.message);
  }
}

// ── Main auth init ────────────────────────────────────────────────
async function initAuth() {
  const path = window.location.pathname;
  const params = new URLSearchParams(window.location.search);

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
      const device = _esc(ua.length > 40 ? ua.slice(0, 40) + '…' : ua);
      const date = s.createdAt ? new Date(s.createdAt).toLocaleDateString() : '';
      const currentBadge = s.isCurrent ? '<span class="session-badge">Current</span>' : '';
      const revokeBtn = s.isCurrent ? '' :
        `<button class="session-revoke-btn" onclick="revokeSession('${_esc(s.sessionId)}')">Revoke</button>`;
      return `<div class="session-card">
        <div class="session-info">
          <div class="session-device">${device}${currentBadge}</div>
          <div class="session-meta">${date} · ${_esc(s.ipAddress || '')}</div>
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

