
function getPreferredTheme() {
  if (window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches) {
    return 'dark';
  }
  return 'light';
}

document.addEventListener('alpine:init', () => {

  let Alpine = window.Alpine;
  system_pref = getPreferredTheme();

Alpine.store('theme', {
  current: Alpine.$persist(system_pref).as('user_theme_preference'),
});

});
