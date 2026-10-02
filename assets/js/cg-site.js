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

  /* ------------------------------------------------------------- catalogue -- */

  function initCatalogue() {
    var rows = document.querySelectorAll(".cg-section[data-row]");
    var all = document.getElementById("cgAllGames");
    var grid = document.getElementById("cgAllGrid");
    if (!grid || !all) return;

    var input = document.querySelector(".cg-search input");
    var term = qs("q") || "";
    var category = qs("category") || "";
    var sort = qs("sort") || "";

    if (input) {
      input.value = term;
      input.addEventListener("input", function () {
        render(input.value, category);
      });
      input.addEventListener("keydown", function (e) {
        if (e.key === "Enter") e.preventDefault();
      });
    }

    if (term || category || sort === "rating" || sort === "newest") {
      render(term, category, sort);
    }

    function render(t, cat, sortMode) {
      var showAll = Boolean(t || cat || sortMode);
      rows.forEach(function (r) { r.hidden = showAll; });
      all.hidden = !showAll;
      if (!showAll) return;

      var needle = (t || "").trim().toLowerCase();
      var matched = games.filter(function (g) {
        var okCat = !cat || (g.categories || []).indexOf(cat) !== -1;
        var okTerm = !needle || g.title.toLowerCase().indexOf(needle) !== -1;
        return okCat && okTerm;
      });

      if (sortMode === "rating") {
        matched = matched.slice().sort(function (a, b) {
          return (b.rating || 0) - (a.rating || 0);
        });
      } else if (sortMode === "newest") {
        matched = matched.slice().reverse();
      }

      var title = document.getElementById("cgAllTitle");
      if (title) {
        title.textContent = needle
          ? 'Results for "' + t + '"'
          : cat ? cat + " games"
          : sortMode === "rating" ? "Top games"
          : sortMode === "newest" ? "New games"
          : "All games";
      }
      var count = document.getElementById("cgAllCount");
      if (count) count.textContent = matched.length + " games";

      grid.innerHTML = matched.map(function (g) {
        return '<li><a class="cg-card" href="/play?g=' + g.slug + '">' +
          '<div class="cg-card-title">' + esc(g.title) + "</div>" +
          '<img class="cg-card-img" loading="lazy" src="' + esc(g.thumb) +
          '" alt="' + esc(g.title) + '"></a></li>';
      }).join("");
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
          '" href="/play?g=' + g.slug + '">' +
          '<img src="' + esc(g.thumb) + '" alt="" loading="lazy">' +
          '<span class="cg-search-hit-title">' + esc(g.title) + "</span></a>";
      }).join("");
      if (hits.length > shown.length) {
        html += '<a class="cg-search-more" href="/?q=' +
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
    frame.src = game.embed;

    var h1 = document.getElementById("cgStageTitle");
    if (h1) h1.textContent = game.title;

    var meta = document.getElementById("cgMetaRating");
    if (meta) {
      meta.innerHTML = game.rating
        ? '<b>' + Number(game.rating).toFixed(1) + '</b><span class="cg-votes">(out of 10)</span>'
        : "Not rated yet";
    }

    var cats = document.getElementById("cgMetaCats");
    if (cats) {
      cats.innerHTML = (game.categories || []).map(function (c) {
        return '<a class="cg-chip" href="/?category=' +
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
      }).slice(0, 20).map(function (g) {
        return '<li><a class="cg-card" href="/play?g=' + g.slug + '">' +
          '<div class="cg-card-title">' + esc(g.title) + "</div>" +
          '<img class="cg-card-img" loading="lazy" src="' + esc(g.thumb) +
          '" alt=""></a></li>';
      }).join("");
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
    window.location.replace("/play?g=" + encodeURIComponent(g.slug));
  }

  document.addEventListener("DOMContentLoaded", function () {
    initRandom();
    initCatalogue();
    initSearchBox();
    initPlay();
  });
})();
