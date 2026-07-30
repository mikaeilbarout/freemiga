// Shared toast notifications — replaces native alert() everywhere on the
// site with a styled, dismissible, non-blocking notification. Loaded via
// _fonts.html so it's available on every page without per-template wiring.
(function () {
  function ensureContainer() {
    let c = document.getElementById('toastContainer');
    if (!c) {
      c = document.createElement('div');
      c.id = 'toastContainer';
      c.className = 'toast-container';
      document.body.appendChild(c);
    }
    return c;
  }

  const ICONS = { error: '✕', success: '✓', info: 'i' };

  window.showToast = function (message, type) {
    type = ICONS[type] ? type : 'error';
    const container = ensureContainer();
    const el = document.createElement('div');
    el.className = `toast toast-${type}`;
    el.innerHTML = `
      <span class="toast-icon">${ICONS[type]}</span>
      <span class="toast-msg"></span>
      <button class="toast-close" type="button" aria-label="Close">×</button>
    `;
    el.querySelector('.toast-msg').textContent = message;
    let timer;
    const remove = () => {
      clearTimeout(timer);
      el.classList.add('toast-out');
      setTimeout(() => el.remove(), 200);
    };
    el.querySelector('.toast-close').addEventListener('click', remove);
    container.appendChild(el);
    timer = setTimeout(remove, 5000);
  };
})();
