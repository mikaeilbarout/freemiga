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
      slot.innerHTML = `
        <a class="btn btn-ghost btn-sm" href="/dashboard">${me.username}</a>
        <button class="btn btn-ghost btn-sm" onclick="navLogout()">${i18n.logout}</button>
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
