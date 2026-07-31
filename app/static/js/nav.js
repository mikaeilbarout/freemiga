// #navAuthSlot's logged-in/out markup is rendered server-side (see
// app/main.py's render() + _nav.html) from the session cookie, so it's
// correct on first paint — no client fetch needed here anymore.
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
    drawer.inert = false;
    btn.setAttribute('aria-expanded', 'true');
    document.body.style.overflow = 'hidden';
  }

  function closeDrawer() {
    drawer.classList.remove('open');
    overlay.classList.remove('open');
    drawer.setAttribute('aria-hidden', 'true');
    // `inert` (not just aria-hidden) keeps its links/close-button out of
    // the Tab order while closed — aria-hidden alone hides it from screen
    // readers but doesn't stop a sighted keyboard user from tabbing into
    // an off-screen, invisible drawer.
    drawer.inert = true;
    btn.setAttribute('aria-expanded', 'false');
    document.body.style.overflow = '';
  }

  btn.addEventListener('click', openDrawer);
  overlay.addEventListener('click', closeDrawer);
  if (closeBtn) closeBtn.addEventListener('click', closeDrawer);
  document.addEventListener('keydown', e => { if (e.key === 'Escape') closeDrawer(); });
  drawer.querySelectorAll('a').forEach(a => a.addEventListener('click', closeDrawer));
})();
