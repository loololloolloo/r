// Prefer clean URLs: "/index.html" -> "/", "/about.html" -> "/about". GitHub
// Pages serves the extensionless form directly, so this only tidies the address
// bar (replaceState, not a redirect, so there is no reload or history entry).
const cleanUrl = () => {
  const { pathname, search, hash } = window.location;
  let next = pathname;
  if (next.endsWith('/index.html')) next = next.slice(0, -'index.html'.length);
  else if (next.endsWith('.html')) next = next.slice(0, -'.html'.length);
  if (next !== pathname) window.history.replaceState(null, '', next + search + hash);
};
cleanUrl();

// The sticky sidebar's top offset must match the header. Track the real
// rendered height instead of the fixed CSS value.
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
