/* Game comments. There is no backend, so comments live in localStorage, keyed
   per game slug. That makes them per-browser, not shared - the UI says so
   rather than pretending otherwise. */
(() => {
  const STORE_PREFIX = 'rg-comments:';
  const params = new URLSearchParams(window.location.search);
  const slug = params.get('g') || '';
  const MAX_NAME = 40;
  const MAX_TEXT = 1000;

  const esc = (value) => String(value == null ? '' : value)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;').replace(/'/g, '&#39;');

  const key = () => `${STORE_PREFIX}${slug}`;

  const read = () => {
    try {
      const raw = localStorage.getItem(key());
      const list = raw ? JSON.parse(raw) : [];
      return Array.isArray(list) ? list : [];
    } catch (error) {
      return [];
    }
  };

  const write = (list) => {
    try {
      localStorage.setItem(key(), JSON.stringify(list.slice(0, 200)));
    } catch (error) {
      /* private mode or quota - the comment simply does not persist */
    }
  };

  const timeAgo = (ts) => {
    const seconds = Math.round((Date.now() - ts) / 1000);
    if (seconds < 60) return 'just now';
    const units = [['minute', 60], ['hour', 60], ['day', 24], ['month', 30], ['year', 12]];
    let value = seconds / 60;
    let label = 'minute';
    for (let i = 0; i < units.length; i += 1) {
      label = units[i][0];
      if (i + 1 < units.length && value >= units[i + 1][1]) {
        value /= units[i + 1][1];
      } else {
        break;
      }
    }
    const rounded = Math.floor(value);
    return `${rounded} ${label}${rounded === 1 ? '' : 's'} ago`;
  };

  const item = (comment) => `
    <li class="rg-comment">
      <div class="rg-comment-head">
        <span class="rg-comment-name">${esc(comment.name)}</span>
        <time class="rg-comment-time" datetime="${new Date(comment.at).toISOString()}">${esc(timeAgo(comment.at))}</time>
      </div>
      <p class="rg-comment-body">${esc(comment.text)}</p>
    </li>`;

  const render = (listEl, countEl, comments) => {
    if (countEl) countEl.textContent = comments.length ? `(${comments.length})` : '';
    if (!comments.length) {
      listEl.innerHTML = '<li class="rg-comment-empty">No comments yet. Be the first.</li>';
      return;
    }
    listEl.innerHTML = comments.map(item).join('');
  };

  const main = () => {
    const form = document.getElementById('rgCommentForm');
    const listEl = document.getElementById('rgComments');
    if (!form || !listEl || !slug) return;

    const nameEl = document.getElementById('rgCommentName');
    const textEl = document.getElementById('rgCommentText');
    const countEl = document.getElementById('rgCommentCount');

    let comments = read();
    render(listEl, countEl, comments);

    form.addEventListener('submit', (event) => {
      event.preventDefault();
      const text = textEl.value.trim().slice(0, MAX_TEXT);
      if (!text) return;
      const name = (nameEl.value.trim() || 'Guest').slice(0, MAX_NAME);
      comments.unshift({ name, text, at: Date.now() });
      write(comments);
      render(listEl, countEl, comments);
      textEl.value = '';
      // Name is remembered for the next comment via the input itself.
    });
  };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', main);
  } else {
    main();
  }
})();
