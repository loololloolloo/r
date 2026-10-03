/* Admin panel for the archive-derived shell.
 *
 * Opened with Ctrl+Alt+A on any page (a modal over the current view) or via
 * the header button, which links to the standalone ./admin page. It searches
 * the catalogue and lets a rating of 1-5 stars be set per game; ratings are
 * kept in localStorage and override the catalogue default wherever the play
 * page shows "Rating:".
 *
 * The dialog markup is built server-side by tools/build-archive.py and only
 * filled in here, so the panel has structure without JS.
 */
(function () {
  "use strict";

  var RATING_KEY = "cg-admin-ratings";
  var MAX_RESULTS = 60;

  var games = window.CG_GAMES || [];

  function esc(s) {
    return String(s).replace(/[&<>"]/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c];
    });
  }

  function loadRatings() {
    try {
      var raw = JSON.parse(localStorage.getItem(RATING_KEY));
      return raw && typeof raw === "object" ? raw : {};
    } catch (e) {
      return {};
    }
  }

  function saveRating(slug, stars) {
    var all = loadRatings();
    if (stars) all[slug] = stars; else delete all[slug];
    try { localStorage.setItem(RATING_KEY, JSON.stringify(all)); } catch (e) {}
    document.dispatchEvent(new CustomEvent("cg:ratingchange"));
  }

  /* --------------------------------------------------------------- panel -- */

  function rowHTML(g) {
    var stars = loadRatings()[g.slug] || 0;
    var buttons = "";
    for (var i = 1; i <= 5; i++) {
      buttons += '<button class="cg-admin-star' + (i <= stars ? " is-on" : "") +
        '" type="button" data-rate="' + i + '" data-slug="' + esc(g.slug) +
        '" aria-label="Rate ' + i + ' of 5" aria-pressed="' +
        (i === stars ? "true" : "false") + '">\u2605</button>';
    }
    var sub = (g.source || "") +
      (stars ? " \u00b7 rated " + stars + "/5" : " \u00b7 not rated");
    return '<li class="cg-admin-row">' +
      '<img src="' + esc(g.thumb) + '" alt="" loading="lazy">' +
      '<span class="cg-admin-row-text">' +
        '<span class="cg-admin-row-title">' + esc(g.title) + "</span>" +
        '<span class="cg-admin-row-sub">' + esc(sub) + "</span>" +
      "</span>" +
      '<span class="cg-admin-stars">' + buttons + "</span></li>";
  }

  function render(panel, term) {
    var list = panel.querySelector(".cg-admin-results");
    if (!list) return;
    var needle = (term || "").trim().toLowerCase();
    var hits = needle
      ? games.filter(function (g) {
          return g.title.toLowerCase().indexOf(needle) !== -1;
        })
      : games.slice(0, MAX_RESULTS);
    if (!hits.length) {
      list.innerHTML = '<li class="cg-admin-empty">No games match "' +
        esc(term) + '".</li>';
      return;
    }
    list.innerHTML = hits.slice(0, MAX_RESULTS).map(rowHTML).join("");
    if (hits.length > MAX_RESULTS) {
      list.innerHTML += '<li class="cg-admin-empty">' +
        (hits.length - MAX_RESULTS) + " more matches; keep typing to narrow.</li>";
    }
  }

  function openPanel() {
    var panel = document.getElementById("cgAdmin");
    if (!panel) return;
    panel.hidden = false;
    var input = panel.querySelector(".cg-admin-search");
    if (input) {
      input.value = "";
      render(panel, "");
      input.focus();
    }
    document.documentElement.classList.add("cg-admin-on");
  }

  // Only the overlay can close; on the standalone ./admin page the panel is the
  // page content, so there is nothing to hide.
  function isOverlay(panel) {
    return !!(panel && panel.closest(".cg-admin"));
  }

  function closePanel() {
    var panel = document.getElementById("cgAdmin");
    if (isOverlay(panel)) panel.hidden = true;
  }

  function togglePanel() {
    var panel = document.getElementById("cgAdmin");
    if (isOverlay(panel) && !panel.hidden) closePanel();
    else openPanel();
  }

  function wirePanel(panel) {
    panel.addEventListener("click", function (e) {
      var star = e.target.closest ? e.target.closest(".cg-admin-star") : null;
      if (star) {
        var slug = star.getAttribute("data-slug");
        var wanted = parseInt(star.getAttribute("data-rate"), 10);
        var current = loadRatings()[slug] || 0;
        // Clicking the current rating clears it, so a mistake is reversible.
        // saveRating fires cg:ratingchange, which repaints the row.
        saveRating(slug, current === wanted ? 0 : wanted);
        return;
      }
      if (e.target === panel) closePanel();
      if (e.target.closest && e.target.closest(".cg-admin-close")) closePanel();
    });

    var input = panel.querySelector(".cg-admin-search");
    if (input) {
      input.addEventListener("input", function () { render(panel, input.value); });
      input.addEventListener("keydown", function (e) {
        if (e.key === "Enter") e.preventDefault();
        if (e.key === "Escape") closePanel();
      });
    }

    // Only rerender on rating changes raised elsewhere; our own edits already
    // refreshed the row, and this would fight the input's focus otherwise.
    document.addEventListener("cg:ratingchange", function () {
      if (!panel.hidden) render(panel, panel.querySelector(".cg-admin-search").value);
    });
  }

  document.addEventListener("keydown", function (e) {
    if (e.ctrlKey && e.altKey && (e.key === "a" || e.key === "A")) {
      e.preventDefault();
      togglePanel();
    }
  });

  // The standalone page opens with its panel already visible, so paint the
  // first page of games and focus the search box on load.
  function init() {
    var panel = document.getElementById("cgAdmin");
    if (!panel) return;
    wirePanel(panel);
    if (!isOverlay(panel)) {
      render(panel, "");
      var input = panel.querySelector(".cg-admin-search");
      if (input) input.focus();
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }

  window.CGAdmin = {
    open: openPanel,
    close: closePanel,
    ratings: loadRatings,
    ratingFor: function (slug) { return loadRatings()[slug] || 0; }
  };
})();
