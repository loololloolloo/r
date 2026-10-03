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

  var BADGE_NEW = '<div aria-label="New" class="GameThumbLabel_label__dz3yR ' +
    'GameThumbLabel_new__8GnG6"><span role="img" aria-hidden="true" ' +
    'class="Icon_icon__OracF Icon_icon-new__vmtCf Icon_size20__yF8AY"></span></div>';
  var BADGE_HOT = '<div aria-label="Hot" class="GameThumbLabel_label__dz3yR ' +
    'GameThumbLabel_hot__CWhxn"><span role="img" aria-hidden="true" ' +
    'class="Icon_icon__OracF Icon_icon-hot__Tir31 Icon_size20__yF8AY"></span></div>';

  /* Card markup, kept in one place so the catalogue, the play sidebar and the
     favourites page all render the same thing. Matches the archived CrazyGames
     2026 thumb: an image-only link whose title lives in the aria-label.
     `withBadge` adds the 2026 new/hot corner labels (home carousels only). */
  function cardHTML(g, i, withBadge, liCls) {
    var t = esc(g.title);
    var badge = "";
    if (withBadge) badge = (i % 5 === 1) ? BADGE_NEW : (i % 5 === 3) ? BADGE_HOT : "";
    return '<li' + (liCls ? ' class="' + liCls + '"' : '') + '>' +
      '<a class="GameThumbDesktop_gameThumbLinkDesktop__LS_Bs ' +
      'GameThumbDesktop_hasHoverOverlay__qNdmo game-thumb-test-class" ' +
      'aria-label="' + t + '" href="./' + g.slug + '">' + badge +
      '<div class="GameThumbDesktop_gameThumbMedia__L7si1">' +
      '<img class="GameThumbShared_gameThumbImage__7EHHi ' +
      'GameThumbShared_gameThumbImagePositioned__LJJut" loading="lazy" width="273" ' +
      'alt="' + t + '" src="' + esc(g.thumb) + '"></div></a></li>';
  }

  function homeCardHTML(g, i) { return cardHTML(g, i, true); }

  /* "Top games today": a repeating tile of one big card followed by a column of
     two small cards. The track becomes the grid; big cells span both rows. */
  function fillHero(track, list) {
    if (!track) return;
    track.classList.add("cg-hero-grid");
    var html = "", i = 0, n = 0;
    while (i < list.length) {
      html += cardHTML(list[i++], n++, true, "cg-hero-big");
      for (var k = 0; k < 2 && i < list.length; k++) {
        html += cardHTML(list[i++], n++, true, "cg-hero-small");
      }
    }
    track.innerHTML = html;
  }

  /* New games / Trending now: one scroller per row, games split down the middle. */
  function fillTwoRow(track, list) {
    if (!track) return;
    var second = document.getElementById(track.id + "-2");
    if (!second) { track.innerHTML = list.map(homeCardHTML).join(""); return; }
    var mid = Math.ceil(list.length / 2);
    track.innerHTML = list.slice(0, mid).map(homeCardHTML).join("");
    second.innerHTML = list.slice(mid).map(homeCardHTML).join("");
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

  /* Fill the home-page hero, carousels and "best games" grid from the bundle. */
  function initHome() {
    var hero = document.getElementById("cgHeroCards");
    var newest = document.getElementById("cgNewTrack");
    var top = document.getElementById("cgTopTrack");
    var trending = document.getElementById("cgTrendTrack");
    var best = document.getElementById("cgBestGrid");
    if (!hero && !newest && !top && !best) return;

    var rated = byRating(games);
    var pool = rated.length ? rated : games;

    if (hero) fillHero(hero, pool.slice(0, 30));
    // Two-row carousels: split the games down the middle, one scroller each.
    fillTwoRow(newest, games.slice().reverse().slice(0, 48));
    fillTwoRow(trending, pool.slice(0, 48));
    if (top) {
      top.innerHTML = rated.slice(0, 24).map(homeCardHTML).join("");
    }

    var recentSection = document.getElementById("cgRecentSection");
    var recentTrack = document.getElementById("cgRecentTrack");
    if (recentSection && recentTrack) {
      var bySlug = {};
      for (var r = 0; r < games.length; r++) bySlug[games[r].slug] = games[r];
      var played = recentSlugs().map(function (s) { return bySlug[s]; })
        .filter(Boolean);
      if (played.length) {
        recentTrack.innerHTML = played.slice(0, 12).map(homeCardHTML).join("");
        recentSection.hidden = false;
      }
    }

    var tracks = document.querySelectorAll(".crazy-carousel[data-cat]");
    for (var i = 0; i < tracks.length; i++) {
      var cat = tracks[i].getAttribute("data-cat");
      var got = games.filter(function (g) {
        return (g.categories || []).indexOf(cat) !== -1;
      });
      tracks[i].innerHTML = spread(got, 24).map(homeCardHTML).join("");
    }
    if (best) {
      best.innerHTML = (rated.length ? rated : games).slice(0, 48)
        .map(cardHTML).join("");
    }
    paintFavs();
  }

  function initCatalogue() {
    var rows = document.querySelectorAll("[data-row]");
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
      rows.forEach(function (r) {
        // "Continue playing" is only shown when it actually has history.
        r.hidden = showAll ||
          (r.id === "cgRecentSection" && !r.querySelector("li"));
      });
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
          '" href="./' + g.slug + '">' +
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

    // Game pages live at the site root (/<slug>); ?g=<slug> still works for
    // any links already in the wild.
    var slug = qs("g") || decodeURIComponent(
      location.pathname.replace(/\/+$/, "").split("/").pop());
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
    var crumbGame = document.getElementById("cgCrumbGame");
    if (crumbGame) crumbGame.textContent = game.title;

    // Rating: the catalogue's 0-10 value with its vote count, else a plain note.
    var meta = document.getElementById("cgMetaRating");
    if (meta) {
      meta.innerHTML = game.rating
        ? "<b>" + Number(game.rating).toFixed(1) + '</b><span class="cg-votes">(' +
          (game.votes || 0) + " votes)</span>"
        : "Not rated yet";
    }

    var cats = game.categories || [];
    var tags = document.getElementById("cgMetaCats");
    if (tags) {
      tags.innerHTML = cats.map(function (c) {
        return '<a href="./?category=' + encodeURIComponent(c) + '">' +
          '<div class="TagGrid_tagPillContainer__rY0CY tagPill"><p>' + esc(c) +
          "</p><span>&rsaquo;</span></div></a>";
      }).join("");
    }
    var crumbCat = document.getElementById("cgCrumbCat");
    if (crumbCat) {
      var primary = cats[0] || "Casual";
      crumbCat.textContent = primary;
      crumbCat.href = "./?category=" + encodeURIComponent(primary);
    }

    var desc = document.getElementById("cgMetaDesc");
    if (desc) {
      var body = game.desc && game.desc.length > 40
        ? esc(game.desc)
        : "Play " + esc(game.title) +
          " for free in your browser. No download, no install.";
      desc.innerHTML = "<p><strong>" + esc(game.title) + "</strong></p><p>" +
        body + "</p>";
    }

    // Related first (shared category), then the rest, so both grids show
    // genre-mates instead of the catalogue's first alphabetical entries.
    var others = games.filter(function (g) { return g.slug !== game.slug; });
    var sameCat = others.filter(function (g) {
      return (g.categories || []).some(function (c) { return cats.indexOf(c) >= 0; });
    });
    var related = sameCat.concat(others.filter(function (g) {
      return sameCat.indexOf(g) < 0;
    }));

    var more = document.getElementById("cgMoreGrid");
    if (more) more.innerHTML = related.slice(0, 15).map(playCard).join("");
    var side = document.getElementById("cgSideList");
    if (side) side.innerHTML = related.slice(0, 20).map(playCard).join("");
  }

  /* Play-page thumb: the sportsgamesaz/2026 anchor shape (title overlay, vignette,
     image), not the home carousel's <li> card. */
  function playCard(g) {
    var t = esc(g.title);
    return '<a class="GameThumb_gameThumbLinkDesktop__wcir5 ' +
      "GameThumb_isResponsiveGrid__b4QQf GameThumb_isResponsive__UwFpC " +
      'game-thumb-test-class" aria-label="Play ' + t + ' game" href="./' +
      g.slug + '">' +
      '<div class="GameThumb_gameThumbTitleContainer__J1K4D gameThumbTitleContainer">' +
      t + "</div>" +
      '<div class="GameThumb_gradientVignette__Q04oZ"></div>' +
      '<img class="GameThumb_gameThumbImage__FSasr" loading="lazy" alt="' + t +
      '" src="' + esc(g.thumb) + '"></a>';
  }

  function initRandom() {
    if (qs("random") === null || !games.length) return;
    var g = games[Math.floor(Math.random() * games.length)];
    window.location.replace("./" + encodeURIComponent(g.slug));
  }

  /* The 2026 home ends with a collapsed SEO block; "Show more" expands it. */
  function initSeo() {
    var seo = document.getElementById("cgSeo");
    if (!seo) return;
    var btn = seo.querySelector(".cg-seo-toggle");
    if (!btn) return;
    btn.addEventListener("click", function () {
      var open = seo.classList.toggle("is-open");
      btn.setAttribute("aria-expanded", open ? "true" : "false");
      btn.textContent = open ? "Show less" : "Show more";
    });
  }

  document.addEventListener("DOMContentLoaded", function () {
    initImageFallback();
    initRandom();
    initFavorites();
    initFavoritesPanel();
    initCatalogue();
    initSearchBox();
    initPlay();
    initSeo();
    paintFavs();
  });
})();
