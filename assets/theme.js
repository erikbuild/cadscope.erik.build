// ABOUTME: Theme selection for the CADScope UI: dark default with a light override.
// ABOUTME: Resolves and persists the choice, applies data-theme on <html>, emits themechange.

// Maps a stored preference to a theme name; anything unrecognized is dark.
export function resolveTheme(value) {
  return value === 'light' ? 'light' : 'dark';
}

export function nextTheme(theme) {
  return theme === 'dark' ? 'light' : 'dark';
}

const STORAGE_KEY = 'cadscope-theme';

function storedTheme() {
  try {
    return localStorage.getItem(STORAGE_KEY);
  } catch (e) {
    return null;
  }
}

function persistTheme(theme) {
  try {
    localStorage.setItem(STORAGE_KEY, theme);
  } catch (e) {
    // Storage unavailable; the choice lasts for this session only.
  }
}

function applyTheme(theme) {
  if (theme === 'light') {
    document.documentElement.dataset.theme = 'light';
  } else {
    delete document.documentElement.dataset.theme;
  }
  document.dispatchEvent(new CustomEvent('themechange', { detail: { theme } }));
}

// Wires the header switch: restores the saved theme, keeps the switch in
// sync, persists changes, and emits themechange on every application.
export function initTheme() {
  let theme = resolveTheme(storedTheme());
  applyTheme(theme);
  const toggle = document.getElementById('themeToggle');
  if (!toggle) return;
  toggle.checked = theme === 'light';
  toggle.addEventListener('change', () => {
    theme = nextTheme(theme);
    persistTheme(theme);
    applyTheme(theme);
  });
}
