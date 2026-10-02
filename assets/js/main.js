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
  // Guarded: on a browser without ResizeObserver an uncaught throw here would
  // abort the rest of this script, taking the navbar toggle down with it.
  if (window.ResizeObserver) {
    try {
      new ResizeObserver(syncHeaderHeight).observe(header);
    } catch (error) {
      /* height simply stays at the CSS default */
    }
  }
}

// Below xl the top navbar is a dropdown panel, hidden off the top of the header
// and revealed with a downward slide. Managed directly rather than via
// Bootstrap's Collapse: that class animates height, which cannot combine with an
// absolutely-positioned overlay and left the panel stuck open.
const topNav = document.getElementById('rgTopNav');
const topNavToggle = document.querySelector('.navbar-toggler');
const navOverlayQuery = window.matchMedia('(max-width: 1199.98px)');

if (topNav && topNavToggle) {
  // Strip Bootstrap's collapse hooks if the markup still carries them (e.g. a
  // cached older index.html). Left in place, Bootstrap's collapse JS and this
  // script both drive the panel and fight, leaving it stuck invisible.
  topNav.classList.remove('collapse', 'show');
  topNavToggle.removeAttribute('data-bs-toggle');
  topNavToggle.removeAttribute('data-bs-target');

  const setTopNavOpen = (open) => {
    topNav.classList.toggle('rg-open', open);
    topNavToggle.setAttribute('aria-expanded', String(open));
  };

  const isTopNavOpen = () => topNav.classList.contains('rg-open');

  topNavToggle.addEventListener('click', () => {
    if (!navOverlayQuery.matches) return;
    setTopNavOpen(!isTopNavOpen());
  });

  // Choosing a link dismisses the panel.
  topNav.addEventListener('click', (event) => {
    if (navOverlayQuery.matches && event.target.closest('a.nav-link')) setTopNavOpen(false);
  });

  // Clicking anywhere outside closes it.
  document.addEventListener('click', (event) => {
    if (!navOverlayQuery.matches || !isTopNavOpen()) return;
    if (topNav.contains(event.target) || topNavToggle.contains(event.target)) return;
    setTopNavOpen(false);
  });

  // Escape closes it and returns focus to the toggle.
  document.addEventListener('keydown', (event) => {
    if (event.key !== 'Escape' || !navOverlayQuery.matches || !isTopNavOpen()) return;
    setTopNavOpen(false);
    topNavToggle.focus();
  });

  // Leaving the overlay range (e.g. resizing to desktop) must clear the state.
  navOverlayQuery.addEventListener('change', (event) => {
    if (!event.matches) setTopNavOpen(false);
  });
}
