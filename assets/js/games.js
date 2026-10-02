/* Catalogue rendering: game grid, search, category filtering and the sidebar
   category list. Data comes from data/games.json, produced by
   tools/fetch-games.py. */
(() => {
  const DATA_URL = 'data/games.json';
  const params = new URLSearchParams(window.location.search);

  const esc = (value) => String(value == null ? '' : value)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;').replace(/'/g, '&#39;');

  const playUrl = (slug) => `/play?g=${encodeURIComponent(slug)}`;

  const normalize = (value) => String(value || '').toLowerCase().trim();

  /* ---------- catalogue ---------- */

  const load = async () => {
    const res = await fetch(DATA_URL, { cache: 'no-cache' });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const games = await res.json();
    return Array.isArray(games) ? games : [];
  };

  /* ---------- filtering ---------- */

  const filterGames = (games, query, category) => {
    const needle = normalize(query);
    const cat = normalize(category);
    return games.filter((game) => {
      if (cat) {
        const cats = (game.categories || []).map(normalize);
        if (!cats.includes(cat)) return false;
      }
      if (!needle) return true;
      if (normalize(game.title).includes(needle)) return true;
      return (game.categories || []).some((c) => normalize(c).includes(needle));
    });
  };

  /* ---------- grid ---------- */

  const card = (game) => `
    <a class="rg-card" href="${playUrl(game.slug)}">
      <span class="rg-card-thumb">
        <img src="${esc(game.thumb)}" alt="${esc(game.title)}" loading="lazy" decoding="async">
      </span>
      <span class="rg-card-title">${esc(game.title)}</span>
    </a>`;

  const renderGrid = (mount, games, query, category, defaultLabel) => {
    const list = filterGames(games, query, category);
    const heading = document.getElementById('rgGridHeading');
    if (heading) {
      if (category) heading.textContent = /game/i.test(category) ? category : `${category} games`;
      else if (query) heading.textContent = `Results for “${query}”`;
      else heading.textContent = defaultLabel || 'All games';
    }

    if (!list.length) {
      mount.innerHTML = '<p class="rg-empty">No games match that. Try another search.</p>';
      return;
    }
    mount.innerHTML = list.map(card).join('');
  };

  /* ---------- sidebar categories ---------- */

  const renderCategories = (mount, games, activeCategory) => {
    const counts = new Map();
    games.forEach((game) => {
      (game.categories || []).forEach((name) => {
        counts.set(name, (counts.get(name) || 0) + 1);
      });
    });

    const rows = [...counts.entries()]
      .sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]))
      .map(([name, count]) => {
        const active = normalize(name) === normalize(activeCategory);
        const href = `/?category=${encodeURIComponent(name)}`;
        return `<li class="nav-item">
            <a class="nav-link${active ? ' active' : ''}" href="${href}">
              <i class="bi bi-tag rg-nav-icon"></i>${esc(name)}
              <span class="rg-count">${count}</span>
            </a>
          </li>`;
      });

    mount.innerHTML = rows.join('') ||
      '<li class="nav-item"><span class="nav-link disabled">No categories yet</span></li>';
  };

  /* ---------- wiring ---------- */

  const wireSearch = (input, apply) => {
    if (!input) return;
    if (params.get('q')) input.value = params.get('q');
    input.addEventListener('input', () => apply(input.value));
    const form = input.closest('form');
    if (form) {
      form.addEventListener('submit', (event) => {
        event.preventDefault();
        apply(input.value);
      });
    }
  };

  const main = async () => {
    const gridMount = document.getElementById('rgGrid');
    const catMount = document.getElementById('rgCategories');
    if (!gridMount && !catMount) return;

    let games;
    try {
      games = await load();
    } catch (error) {
      const message = '<p class="rg-empty">Could not load the game list.</p>';
      if (gridMount) gridMount.innerHTML = message;
      return;
    }

    const category = params.get('category') || '';
    if (catMount) renderCategories(catMount, games, category);

    if (params.get('random')) {
      const pool = filterGames(games, params.get('q') || '', category);
      if (pool.length) {
        const pick = pool[Math.floor(Math.random() * pool.length)];
        window.location.replace(playUrl(pick.slug));
      }
      return;
    }

    if (gridMount) {
      const search = document.querySelector('.rg-search input[type="search"]');
      const sorted = params.get('sort') === 'rating';
      const defaultLabel = sorted ? 'Top games' : 'All games';
      const apply = (value) => renderGrid(gridMount, games, value, category, defaultLabel);
      wireSearch(search, apply);
      if (sorted) games = [...games].sort((a, b) => (b.rating || 0) - (a.rating || 0));
      apply(params.get('q') || '');
    }
  };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', main);
  } else {
    main();
  }
})();
