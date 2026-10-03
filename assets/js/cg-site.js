/* Client behaviour for the archive-derived shell.
 *
 * The catalogue is rendered server-side by tools/build-archive.py; this file
 * only filters it in place (so the HTML is complete without JS) and wires the
 * play page. Games come from window.CG_GAMES, emitted alongside the pages.
 */
(function () {
  "use strict";

  var games = window.CG_GAMES || [];

  function qs(name) {
    return new URLSearchParams(window.location.search).get(name);
  }

  function esc(s) {
    return String(s).replace(/[&<>"]/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c];
    });
  }

  /* ------------------------------------------------------------ favourites -- */

  var FAV_KEY = "cg-favorites";

  function favSlugs() {
    try {
      var raw = JSON.parse(localStorage.getItem(FAV_KEY));
      return Array.isArray(raw) ? raw : [];
    } catch (e) {
      return [];
    }
  }

  function saveFavs(list) {
    try { localStorage.setItem(FAV_KEY, JSON.stringify(list)); } catch (e) {}
  }

  /* ------------------------------------------------------ recently played -- */

  var RECENT_KEY = "cg-recent";
  var RECENT_MAX = 60;

  function recentSlugs() {
    try {
      var raw = JSON.parse(localStorage.getItem(RECENT_KEY));
      return Array.isArray(raw) ? raw : [];
    } catch (e) {
      return [];
    }
  }

  function markPlayed(slug) {
    if (!slug) return;
    var list = recentSlugs().filter(function (s) { return s !== slug; });
    list.unshift(slug);
    try {
      localStorage.setItem(RECENT_KEY, JSON.stringify(list.slice(0, RECENT_MAX)));
    } catch (e) {}
  }

  /* --------------------------------------------------------- image fallback -- */

  /* Card markup, kept in one place so the catalogue, the play sidebar and the
     favourites page all render the same thing. */
  function cardHTML(g) {
    return '<li><a class="cg-card" href="./play?g=' + g.slug + '">' +
      '<div class="cg-card-title">' + esc(g.title) + "</div>" +
      '<img class="cg-card-img" loading="lazy" src="' + esc(g.thumb) +
      '" alt="' + esc(g.title) + '">' +
      '<button class="cg-fav" type="button" data-fav="' + esc(g.slug) +
      '" aria-label="Add to favourites" aria-pressed="false">' +
      '<svg viewBox="0 0 24 24" aria-hidden="true">' +
      '<use href="#cg-heart"></use></svg></button></a></li>';
  }

  /* Reflect the stored list onto every heart currently in the DOM. */
  function paintFavs() {
    var saved = favSlugs();
    var btns = document.querySelectorAll(".cg-fav, .cg-pill-fav");
    for (var i = 0; i < btns.length; i++) {
      var on = saved.indexOf(btns[i].getAttribute("data-fav")) !== -1;
      btns[i].classList.toggle("is-fav", on);
      btns[i].setAttribute("aria-pressed", on ? "true" : "false");
      btns[i].setAttribute("aria-label",
        on ? "Remove from favourites" : "Add to favourites");
      var label = btns[i].querySelector("span");
      if (label) label.textContent = on ? "Favorited" : "Favorite";
    }
  }

  function initFavorites() {
    document.addEventListener("click", function (e) {
      var btn = e.target.closest ? e.target.closest(".cg-fav, .cg-pill-fav") : null;
      if (!btn) return;
      // The heart lives inside the card's link, so stop it opening the game.
      e.preventDefault();
      e.stopPropagation();
      var slug = btn.getAttribute("data-fav");
      var list = favSlugs();
      var at = list.indexOf(slug);
      if (at === -1) list.push(slug); else list.splice(at, 1);
      saveFavs(list);
      paintFavs();
      document.dispatchEvent(new CustomEvent("cg:favchange"));
    });
    paintFavs();
  }

  /* ------------------------------------------------------- favourites popup -- */

  function initFavoritesPanel() {
    var panel = document.getElementById("cgFavPanel");
    if (!panel) return;

    var grid = document.getElementById("cgFavGrid");
    var empty = document.getElementById("cgFavEmpty");
    var count = document.getElementById("cgFavCount");
    var clear = document.getElementById("cgFavClear");
    var openBtn = document.querySelector(".cg-fav-btn");

    function render() {
      var items = favSlugs().map(function (slug) {
        for (var i = 0; i < games.length; i++) {
          if (games[i].slug === slug) return games[i];
        }
        return null;
      }).filter(Boolean);

      grid.innerHTML = items.map(cardHTML).join("");
      paintFavs();
      if (empty) empty.hidden = items.length > 0;
      if (count) {
        count.textContent = items.length +
          (items.length === 1 ? " game" : " games");
      }
      if (clear) clear.hidden = items.length === 0;
    }

    function open() {
      render();
      panel.hidden = false;
      var close = panel.querySelector(".cg-admin-close");
      if (close) close.focus();
    }

    function close() { panel.hidden = true; }

    function toggle() { if (panel.hidden) open(); else close(); }

    if (openBtn) {
      openBtn.addEventListener("click", function (e) {
        e.preventDefault();
        toggle();
      });
    }

    panel.addEventListener("click", function (e) {
      if (e.target === panel || (e.target.closest &&
          e.target.closest(".cg-admin-close"))) close();
    });

    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape" && !panel.hidden) close();
    });

    render();
    document.addEventListener("cg:favchange", function () {
      if (!panel.hidden) render();
    });

    if (clear) {
      clear.addEventListener("click", function () {
        saveFavs([]);
        document.dispatchEvent(new CustomEvent("cg:favchange"));
      });
    }
  }

  /* A handful of source CDNs 404 the odd icon; hide the broken image so the
     card's own background shows instead of a torn-image glyph. */
  function initImageFallback() {
    document.addEventListener("error", function (e) {
      var el = e.target;
      if (el && el.tagName === "IMG" && !el.classList.contains("cg-img-fail")) {
        el.classList.add("cg-img-fail");
      }
    }, true);
  }

  /* ------------------------------------------------------------- catalogue -- */

  // Cards added per "Load more" click in the all-games grid. A big category
  // (Casual ~25k) would otherwise build every card and image in one go.
  var PAGE = 60;

  function spread(items, count) {
    // Sample evenly instead of taking the head, so a category carousel does not
    // show only the A-B titles.
    if (items.length <= count) return items.slice();
    var step = items.length / count, out = [];
    for (var i = 0; i < count; i++) {
      out.push(items[Math.min(Math.floor(i * step), items.length - 1)]);
    }
    return out;
  }

  function byRating(list) {
    return list.slice().sort(function (a, b) {
      return (b.rating || 0) - (a.rating || 0);
    });
  }

  /* Fill the home-page carousels and the "best games" grid from the bundle. */
  function initHome() {
    var newest = document.getElementById("cgNewTrack");
    var top = document.getElementById("cgTopTrack");
    var best = document.getElementById("cgBestGrid");
    if (!newest && !top && !best) return;

    var rated = byRating(games);
    if (newest) {
      newest.innerHTML = games.slice().reverse().slice(0, 24).map(cardHTML).join("");
    }
    if (top) {
      top.innerHTML = rated.slice(0, 24).map(cardHTML).join("");
    }
    var tracks = document.querySelectorAll(".cg-carousel-track[data-cat]");
    for (var i = 0; i < tracks.length; i++) {
      var cat = tracks[i].getAttribute("data-cat");
      var got = games.filter(function (g) {
        return (g.categories || []).indexOf(cat) !== -1;
      });
      tracks[i].innerHTML = spread(got, 24).map(cardHTML).join("");
    }
    if (best) {
      best.innerHTML = (rated.length ? rated : games).slice(0, 48)
        .map(cardHTML).join("");
    }
    paintFavs();
  }

  function initCatalogue() {
    var rows = document.querySelectorAll(".cg-section[data-row]");
    var all = document.getElementById("cgAllGames");
    var grid = document.getElementById("cgAllGrid");
    if (!grid || !all) return;

    var input = document.querySelector(".cg-search input");
    var term = qs("q") || "";
    var category = qs("category") || "";
    var sort = qs("sort") || "";
    if (qs("recent") !== null) sort = "recent";

    var shown = 0;          // cards currently in the grid
    var results = [];       // full match set for the current view

    var moreBtn = document.getElementById("cgAllMore");
    if (moreBtn) {
      moreBtn.addEventListener("click", function () { grow(); });
    }

    function grow() {
      var slice = results.slice(shown, shown + PAGE);
      grid.insertAdjacentHTML("beforeend", slice.map(cardHTML).join(""));
      shown += slice.length;
      paintFavs();
      if (moreBtn) {
        moreBtn.hidden = shown >= results.length;
        moreBtn.textContent = "Load more (" + (results.length - shown) + ")";
      }
    }

    if (input) {
      input.value = term;
      input.addEventListener("input", function () {
        render(input.value, category);
      });
      input.addEventListener("keydown", function (e) {
        if (e.key === "Enter") e.preventDefault();
      });
    }

    if (term || category || sort === "rating" || sort === "newest"
        || sort === "recent") {
      render(term, category, sort);
    } else {
      initHome();
    }

    function render(t, cat, sortMode) {
      var showAll = Boolean(t || cat || sortMode);
      rows.forEach(function (r) { r.hidden = showAll; });
      all.hidden = !showAll;
      if (!showAll) return;

      var needle = (t || "").trim().toLowerCase();
      results = games.filter(function (g) {
        var okCat = !cat || (g.categories || []).indexOf(cat) !== -1;
        var okTerm = !needle || g.title.toLowerCase().indexOf(needle) !== -1;
        return okCat && okTerm;
      });

      if (sortMode === "rating") {
        results = byRating(results);
      } else if (sortMode === "newest") {
        results = results.slice().reverse();
      } else if (sortMode === "recent") {
        var order = recentSlugs();
        var rank = {};
        order.forEach(function (s, i) { rank[s] = i; });
        results = results.filter(function (g) {
          return order.indexOf(g.slug) !== -1;
        }).sort(function (a, b) { return rank[a.slug] - rank[b.slug]; });
      }

      var title = document.getElementById("cgAllTitle");
      if (title) {
        title.textContent = needle
          ? 'Results for "' + t + '"'
          : cat ? cat + " games"
          : sortMode === "rating" ? "Top games"
          : sortMode === "newest" ? "New games"
          : sortMode === "recent" ? "Recently played"
          : "All games";
      }
      var count = document.getElementById("cgAllCount");
      if (count) count.textContent = results.length + " games";

      grid.innerHTML = "";
      shown = 0;
      grow();
    }
  }

  /* ------------------------------------------------------------ search box -- */

  function initSearchBox() {
    var input = document.querySelector(".cg-search input");
    var box = document.getElementById("cgSearchResults");
    if (!input || !box) return;

    var active = -1;

    function close() {
      box.hidden = true;
      box.innerHTML = "";
      active = -1;
    }

    function open(term) {
      var needle = term.trim().toLowerCase();
      if (!needle) return close();

      var hits = games.filter(function (g) {
        return g.title.toLowerCase().indexOf(needle) !== -1;
      });
      if (!hits.length) return close();

      var shown = hits.slice(0, 6);
      var html = shown.map(function (g, i) {
        return '<a class="cg-search-hit" role="option" data-i="' + i +
          '" href="./play?g=' + g.slug + '">' +
          '<img src="' + esc(g.thumb) + '" alt="" loading="lazy">' +
          '<span class="cg-search-hit-title">' + esc(g.title) + "</span></a>";
      }).join("");
      if (hits.length > shown.length) {
        html += '<a class="cg-search-more" href="./?q=' +
          encodeURIComponent(term.trim()) + '">See all ' + hits.length +
          " results</a>";
      }
      box.innerHTML = html;
      box.hidden = false;
      active = -1;
    }

    function highlight(delta) {
      var rows = box.querySelectorAll(".cg-search-hit");
      if (!rows.length) return;
      if (active >= 0) rows[active].classList.remove("cg-active");
      active = (active + delta + rows.length) % rows.length;
      rows[active].classList.add("cg-active");
      rows[active].scrollIntoView({ block: "nearest" });
    }

    input.addEventListener("input", function () { open(input.value); });
    input.addEventListener("focus", function () {
      if (input.value.trim()) open(input.value);
    });

    input.addEventListener("keydown", function (e) {
      if (e.key === "ArrowDown") { e.preventDefault(); highlight(1); }
      else if (e.key === "ArrowUp") { e.preventDefault(); highlight(-1); }
      else if (e.key === "Enter") {
        var rows = box.querySelectorAll(".cg-search-hit");
        if (!box.hidden && active >= 0 && rows[active]) {
          e.preventDefault();
          window.location.href = rows[active].getAttribute("href");
        }
      } else if (e.key === "Escape") {
        close();
      }
    });

    document.addEventListener("click", function (e) {
      if (!e.target.closest(".cg-search")) close();
    });
  }

  /* ------------------------------------------------------------------ play -- */

  function initPlay() {
    var frame = document.getElementById("cgFrame");
    if (!frame) return;

    var loader = document.getElementById("cgLoader");
    if (loader) {
      frame.addEventListener("load", function () { loader.hidden = true; });
      // A frame that never loads (or is blocked) must not spin forever.
      setTimeout(function () { loader.hidden = true; }, 12000);
    }

    var slug = qs("g");
    var game = null;
    for (var i = 0; i < games.length; i++) {
      if (games[i].slug === slug) { game = games[i]; break; }
    }
    if (!game) game = games[0];
    if (!game) return;

    document.title = game.title + " - Games";
    markPlayed(game.slug);

    if (frame.getAttribute("src") !== game.embed) frame.src = game.embed;

    var h1 = document.getElementById("cgStageTitle");
    if (h1) h1.textContent = game.title;

    // Admin ratings (1-5) are a local override; without one the catalogue's
    // own 0-10 rating is shown.
    function paintRating() {
      var meta = document.getElementById("cgMetaRating");
      if (!meta) return;
      var mine = window.CGAdmin ? window.CGAdmin.ratingFor(game.slug) : 0;
      if (mine) {
        meta.innerHTML = '<b>' + mine.toFixed(1) +
          '</b><span class="cg-votes">(out of 5)</span>';
      } else {
        meta.innerHTML = game.rating
          ? '<b>' + Number(game.rating).toFixed(1) +
            '</b><span class="cg-votes">(out of 10)</span>'
          : "Not rated yet";
      }
    }
    paintRating();
    document.addEventListener("cg:ratingchange", paintRating);

    var src = document.getElementById("cgMetaSource");
    if (src) src.textContent = game.source || "Unknown";

    var cats = document.getElementById("cgMetaCats");
    if (cats) {
      cats.innerHTML = (game.categories || []).map(function (c) {
        return '<a class="cg-chip" href="./?category=' +
          encodeURIComponent(c) + '">' + esc(c) + "</a>";
      }).join("") || "<span>Casual</span>";
    }

    var desc = document.getElementById("cgMetaDesc");
    if (desc) {
      desc.textContent = "Play " + game.title +
        " for free in your browser. No download, no install.";
    }

    var side = document.getElementById("cgSideList");
    if (side) {
      side.innerHTML = games.filter(function (g) {
        return g.slug !== game.slug;
      }).slice(0, 20).map(cardHTML).join("");
    }

    // Heart in the info bar, mirroring the card hearts.
    var fav = document.getElementById("cgFavToggle");
    if (fav) {
      fav.setAttribute("data-fav", game.slug);
      fav.hidden = false;
    }

    var fs = document.getElementById("cgFullscreen");
    if (fs) {
      fs.addEventListener("click", function () {
        var box = frame.parentElement;
        if (document.fullscreenElement) document.exitFullscreen();
        else if (box.requestFullscreen) box.requestFullscreen();
      });
    }
  }

  function initRandom() {
    if (qs("random") === null || !games.length) return;
    var g = games[Math.floor(Math.random() * games.length)];
    window.location.replace("./play?g=" + encodeURIComponent(g.slug));
  }

  document.addEventListener("DOMContentLoaded", function () {
    initImageFallback();
    initRandom();
    initFavorites();
    initFavoritesPanel();
    initCatalogue();
    initSearchBox();
    initPlay();
    paintFavs();
  });
})();
