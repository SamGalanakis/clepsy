(() => {
  const STORAGE_KEY = 'themeVariant';
  const docEl = document.documentElement;

  function getStoredTheme() {
    return localStorage.getItem(STORAGE_KEY);
  }

  function setStoredTheme(theme) {
    if (theme) localStorage.setItem(STORAGE_KEY, theme);
    else localStorage.removeItem(STORAGE_KEY);
  }

  function setDocumentTheme(theme) {
    // Remove existing theme-* classes safely
    Array.from(docEl.classList)
      .filter((c) => c.startsWith('theme-'))
      .forEach((c) => docEl.classList.remove(c));
    if (theme) docEl.classList.add(`theme-${theme}`);
  }

  function syncSelect(theme) {
    const themeSelect = document.getElementById('theme-select');
    if (themeSelect) themeSelect.value = theme || '';
  }

  function onThemeChange(e) {
    const newTheme = e.target.value;
    setStoredTheme(newTheme || '');
    setDocumentTheme(newTheme || '');
  emitThemeChanged();
  }

  function wireUpListener() {
    const themeSelect = document.getElementById('theme-select');
    if (themeSelect && !themeSelect._themeListenerBound) {
      themeSelect.addEventListener('change', onThemeChange);
      themeSelect._themeListenerBound = true;
    }
    // Keep the select in sync with storage
    syncSelect(getStoredTheme());
  }

  // Apply ASAP on script load
  const initialTheme = getStoredTheme();
  setDocumentTheme(initialTheme);
  syncSelect(initialTheme);
  wireUpListener();

  // Fallback when DOM is ready (e.g., select not present yet)
  document.addEventListener('DOMContentLoaded', () => {
    setDocumentTheme(getStoredTheme());
    wireUpListener();
  });

  // Handle bfcache restores
  window.addEventListener('pageshow', () => {
    const t = getStoredTheme();
    setDocumentTheme(t);
    syncSelect(t);
  });

  function getCurrentLightMode() {
    return docEl.classList.contains('dark') ? 'dark' : 'light';
  }

  function getCurrentThemeVariant() {
    const t = getStoredTheme();
    return t && t.length > 0 ? t : 'default';
  }

  function emitThemeChanged() {
    try {
      const detail = {
        theme: getCurrentThemeVariant(),
        light_mode: getCurrentLightMode(),
      };
      document.dispatchEvent(new CustomEvent('theme_changed', { detail }));
    } catch (_) {}
  }
})();
