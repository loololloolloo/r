document.addEventListener('click', (event) => {
  const trigger = event.target.closest('[data-rg-top]');
  if (!trigger) return;
  event.preventDefault();
  window.scrollTo({ top: 0, behavior: 'smooth' });
});

// The sticky sidebar's top offset must match the header, which grows when the
// collapsed navbar is expanded. Track the real rendered height instead of the
// fixed CSS value.
const header = document.querySelector('.rg-header');

if (header) {
  const syncHeaderHeight = () => {
    document.documentElement.style.setProperty('--rg-header-h', `${header.offsetHeight}px`);
  };

  syncHeaderHeight();
  // Guarded: an uncaught throw here would abort the rest of this script.
  if (window.ResizeObserver) {
    try {
      new ResizeObserver(syncHeaderHeight).observe(header);
    } catch (error) {
      /* height simply stays at the CSS default */
    }
  }
}
