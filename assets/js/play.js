/* Game player: looks the requested slug up in data/games.json, drops the game's
   own site into a full-width 16:9 iframe, and fills the "Play next" row. */
(() => {
  const DATA_URL = 'data/games.json';
  const params = new URLSearchParams(window.location.search);
  const slug = params.get('g') || '';
  const PLAY_NEXT = 10;

  const esc = (value) => String(value == null ? '' : value)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;').replace(/'/g, '&#39;');

  const playUrl = (s) => `/play?g=${encodeURIComponent(s)}`;

  const showError = (mount, note, message) => {
    note.textContent = message;
    note.hidden = false;
    mount.classList.add('rg-player-error');
  };

  const load = async () => {
    const res = await fetch(DATA_URL, { cache: 'no-cache' });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return res.json();
  };

  const card = (game) => `
    <a class="rg-card" href="${playUrl(game.slug)}">
      <span class="rg-card-thumb">
        <img src="${esc(game.thumb)}" alt="${esc(game.title)}" loading="lazy" decoding="async">
      </span>
      <span class="rg-card-title">${esc(game.title)}</span>
    </a>`;

  const renderPlayNext = (mount, games, current) => {
    if (!mount) return;
    const pool = games.filter((game) => game.slug !== current.slug);
    const categories = new Set(current.categories || []);
    // Related first (shared categories), then the rest, so the row is never
    // short just because a game has unusual tags.
    const related = pool.filter((game) =>
      (game.categories || []).some((name) => categories.has(name)));
    const rest = pool.filter((game) => !related.includes(game));
    const picks = related.concat(rest).slice(0, PLAY_NEXT);
    mount.innerHTML = picks.map(card).join('') ||
      '<p class="rg-empty">No other games yet.</p>';
  };

  const addFullscreen = (mount) => {
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'btn btn-sm btn-outline-secondary text-nowrap';
    button.innerHTML = '<i class="bi bi-arrows-fullscreen me-1"></i>Fullscreen';
    button.addEventListener('click', () => {
      const frame = mount.querySelector('iframe');
      if (frame && frame.requestFullscreen) frame.requestFullscreen();
    });
    document.getElementById('rgPlayActions')?.append(button);
  };

  const main = async () => {
    const mount = document.getElementById('rgPlayer');
    const note = document.getElementById('rgPlayerNote');
    const title = document.getElementById('rgPlayTitle');
    const nextMount = document.getElementById('rgPlayNext');
    if (!mount || !note) return;

    if (!slug) {
      title.textContent = 'No game selected';
      showError(mount, note, 'Pick a game from the homepage to start playing.');
      if (nextMount) nextMount.innerHTML = '';
      return;
    }

    let games;
    let game;
    try {
      games = await load();
      game = games.find((entry) => entry.slug === slug);
    } catch (error) {
      title.textContent = 'Games';
      showError(mount, note, 'Could not load the game list.');
      return;
    }

    if (!game) {
      title.textContent = 'Game not found';
      showError(mount, note, 'That game is not in the catalogue.');
      if (nextMount) nextMount.innerHTML = '';
      return;
    }

    document.title = `${game.title} · Games`;
    title.textContent = game.title;
    renderPlayNext(nextMount, games, game);

    const frame = document.createElement('iframe');
    frame.className = 'rg-frame';
    frame.src = game.embed;
    frame.title = game.title;
    frame.setAttribute('allowfullscreen', '');
    frame.setAttribute('allow', 'autoplay; fullscreen; gamepad; clipboard-write');
    frame.setAttribute('referrerpolicy', 'no-referrer-when-downgrade');

    // Reveal the frame only once the game has loaded, so the player never
    // flashes an empty black box over the loading note.
    frame.addEventListener('load', () => {
      note.hidden = true;
    });

    mount.appendChild(frame);
    addFullscreen(mount);
  };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', main);
  } else {
    main();
  }
})();
