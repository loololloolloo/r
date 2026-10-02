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

// The brand logo doubles as the sidebar toggle. Below lg the sidebar is an
// offcanvas, so Bootstrap's own toggle handles it; from lg up we collapse it to
// an icon rail instead. Done with a class rather than the `hidden` attribute so
// the CSS transition can animate it.
const RAIL_KEY = 'rg-sidebar-collapsed';
const shell = document.getElementById('rgShell');
const railToggle = document.getElementById('rgSidebarToggle');

if (shell && railToggle) {
  const desktop = window.matchMedia('(min-width: 992px)');
  const collapsed = () => shell.classList.contains('rg-shell-collapsed');

  const syncToggleState = () => {
    railToggle.setAttribute('aria-expanded', String(!collapsed()));
  };

  const applyStoredState = () => {
    let stored = null;
    try {
      stored = localStorage.getItem(RAIL_KEY);
    } catch (error) {
      /* private mode - just use the default */
    }
    shell.classList.toggle('rg-shell-collapsed', stored === '1');
    syncToggleState();
  };

  applyStoredState();

  railToggle.addEventListener('click', (event) => {
    // On mobile the same element is a normal link back to "/" and the
    // offcanvas is opened by the hamburger, so leave that behaviour alone.
    if (!desktop.matches) return;
    event.preventDefault();
    shell.classList.toggle('rg-shell-collapsed');
    syncToggleState();
    try {
      localStorage.setItem(RAIL_KEY, collapsed() ? '1' : '0');
    } catch (error) {
      /* not fatal - the choice just does not persist */
    }
  });

  // Leaving the rail collapsed is fine, but re-expand when the layout goes back
  // to mobile so the offcanvas is never stuck in a collapsed-looking state.
  const onBreakpoint = () => {
    if (!desktop.matches) shell.classList.remove('rg-shell-collapsed');
    else applyStoredState();
  };
  if (desktop.addEventListener) desktop.addEventListener('change', onBreakpoint);
  else if (desktop.addListener) desktop.addListener(onBreakpoint);
}
