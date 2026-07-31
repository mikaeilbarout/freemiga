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

// Styled clickable <div>s (accordion headers, ticket rows, admin tabs,
// carousel dots) use role="button"/role="tab" for screen readers, but that
// alone doesn't give them the Enter/Space activation a native <button>
// gets for free — wired up once, site-wide, instead of per-template.
document.addEventListener('keydown', e => {
  if ((e.key === 'Enter' || e.key === ' ') && e.target.matches('[role="button"], [role="tab"]')) {
    e.preventDefault();
    e.target.click();
  }
});

// Mobile nav drawer — the top-bar links (Plans, How it works, Features,
// Setup guide) are hidden below 720px for space; the hamburger opens this
// off-canvas panel to reach them instead.
(function () {
  const btn = document.getElementById('navHamburgerBtn');
  const drawer = document.getElementById('navDrawer');
  const overlay = document.getElementById('navDrawerOverlay');
  const closeBtn = document.getElementById('navDrawerCloseBtn');
  if (!btn || !drawer || !overlay) return;

  function openDrawer() {
    drawer.classList.add('open');
    overlay.classList.add('open');
    drawer.setAttribute('aria-hidden', 'false');
    btn.setAttribute('aria-expanded', 'true');
    document.body.style.overflow = 'hidden';
  }

  function closeDrawer() {
    drawer.classList.remove('open');
    overlay.classList.remove('open');
    drawer.setAttribute('aria-hidden', 'true');
    btn.setAttribute('aria-expanded', 'false');
    document.body.style.overflow = '';
  }

  btn.addEventListener('click', openDrawer);
  overlay.addEventListener('click', closeDrawer);
  if (closeBtn) closeBtn.addEventListener('click', closeDrawer);
  document.addEventListener('keydown', e => { if (e.key === 'Escape') closeDrawer(); });
  drawer.querySelectorAll('a').forEach(a => a.addEventListener('click', closeDrawer));
})();
