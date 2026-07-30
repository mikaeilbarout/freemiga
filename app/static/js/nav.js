// Shared nav auth-state — populates the right side of the header on every
// page based on whether a customer session exists. Keeps one nav markup
// consistent everywhere instead of duplicating logged-in/out variants.
(async function () {
  const slot = document.getElementById('navAuthSlot');
  if (!slot) return;
  const i18n = window.__NAV_I18N || { login: 'Log in', signup: 'Sign up', logout: 'Log out' };

  try {
    const res = await fetch('/api/auth/me');
    if (res.ok) {
      const me = await res.json();
      const initial = me.username.charAt(0).toUpperCase();
      slot.innerHTML = `
        <a class="btn btn-ghost btn-sm nav-user-link" href="/dashboard">
          <span class="nav-user-avatar" aria-hidden="true">${initial}</span>
          <span class="nav-user-name">${me.username}</span>
        </a>
        <button class="btn btn-ghost btn-sm nav-logout-btn" onclick="navLogout()" aria-label="${i18n.logout}">
          <span class="nav-logout-text">${i18n.logout}</span>
          <svg class="nav-logout-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><polyline points="16 17 21 12 16 7"/><line x1="21" y1="12" x2="9" y2="12"/></svg>
        </button>
      `;
      return;
    }
  } catch (e) {}

  slot.innerHTML = `
    <a class="btn btn-ghost btn-sm" href="/login">${i18n.login}</a>
    <a class="btn btn-primary btn-sm" href="/signup">${i18n.signup}</a>
  `;
})();

async function navLogout() {
  await fetch('/api/auth/logout', {method: 'POST'});
  window.location.href = '/';
}
