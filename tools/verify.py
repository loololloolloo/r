#!/usr/bin/env python3
"""Verify the rebuilt archive-faithful pages against the archived CrazyGames
2026 layout. Checks structure, geometry and behaviour; prints PASS/FAIL lines
and exits non-zero if anything fails.

    python3 tools/verify.py [base_url]
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cdp  # noqa: E402  (local harness)

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:12000"

# A game that exists in the current (sportsgamesaz) catalogue and carries the
# full enrichment (rating + votes, keyword tags, description). The old checks
# pinned CrazyGames' /2048, which the source swap removed.
PLAY_SLUG = "1-archery-master"
PLAY_TITLE = "1 Archery Master"

# A gameslol.net game: self-hosted HTML5 build with its own rating/votes,
# genre tag and description. Verifies the gameslol merge stays playable and
# enriched like every other source.
GAMESLOL_SLUG = "a-grim-chase-1420"

# Archive reference values (getComputedStyle on the archived 2026 page at 1430px).
ARCHIVE = {
    "header": {"x": 0, "y": 0, "w": 1430, "h": 60},
    "rail": {"x": 0, "y": 60, "w": 60},
    "card": {"w": 218, "h": 124},
    "cardImg": {"w": 214, "h": 120},
    "sectionTitle": {"x": 68, "fs": "14px", "fw": "900"},
    "play": {"w": 1014},
    "player": {"w": 982, "h": 552},
    "side": {"w": 356},
    "headerBg": "rgb(26, 27, 40)",
    "bodyBg": "rgb(12, 13, 20)",
}

results = []


def check(name, ok, detail=""):
    results.append((name, bool(ok), detail))
    print("%-4s %-40s %s" % ("PASS" if ok else "FAIL", name, detail))


MEAS = r"""(()=>{
 const m={};
 // Skip the highlighted "recommended" carousel (bigger cards) and any hidden
 // row, so the card-geometry checks measure a standard carousel/grid card.
 const vis=s=>{for(const e of document.querySelectorAll(s)){
   if(e.closest('[data-testid="carousel-recommended"]'))continue; const b=e.getBoundingClientRect();
   if(b.width>0&&b.height>0)return e;} return document.querySelector(s);};
 const box=s=>{const e=vis(s);if(!e)return null;const b=e.getBoundingClientRect();
   return {x:Math.round(b.x),y:Math.round(b.y),w:Math.round(b.width),h:Math.round(b.height)};};
 const sty=(s,ps)=>{const e=vis(s);if(!e)return null;const c=getComputedStyle(e);
   const o={};ps.forEach(p=>o[p]=c[p]);return o;};
 const THUMB='.GameThumbDesktop_gameThumbLinkDesktop__LS_Bs';
 m.header=box('.cg-header'); m.rail=box('.cg-rail');
 m.logo=box('#logo');
 m.card=box(THUMB); m.cardImg=box('.GameThumbShared_gameThumbImage__7EHHi');
 m.sectionTitle=box('.cg-section-title');
 m.sectionTitleStyle=sty('.cg-section-title',['fontSize','fontWeight']);
 m.carouselTitleStyle=sty('[class*=CarouselSectionTitle_carouselTitle]',
   ['fontSize','fontWeight']);
 m.play=box('.GamePageDesktop_mainContainer__QMRhB'); m.player=box('.GamePageDesktop_gfAspectRatioContainer__f_hUp'); m.side=box('.GamePageDesktop_rightSidebar__QgTMJ');
 m.headerBg=getComputedStyle(document.querySelector('.cg-header')).backgroundColor;
 m.bodyBg=getComputedStyle(document.body).backgroundColor;
 m.font=getComputedStyle(document.body).fontFamily.split(',')[0];
 m.railItems=document.querySelectorAll('.cg-rail-item').length;
 m.cards=document.querySelectorAll(THUMB).length;
 m.games=(window.CG_GAMES||[]).length;
 m.imgs=[...document.querySelectorAll('img')];
 m.imgTotal=m.imgs.length;
 m.imgLoaded=m.imgs.filter(i=>i.complete&&i.naturalWidth>0).length;
 m.imgBroken=m.imgs.filter(i=>i.complete&&i.naturalWidth===0).length;
 m.imgVisible=m.imgs.filter(i=>{const b=i.getBoundingClientRect();
   return b.top<window.innerHeight&&b.bottom>0;});
 m.imgVisibleBroken=m.imgVisible.filter(i=>i.complete&&i.naturalWidth===0).length;
 m.docTitle=document.title;
 m.frame=(document.getElementById('game-iframe')||{}).src||null;
 m.h1=(document.querySelector('h1')||{}).textContent||null;
 m.ratio=(()=>{const f=document.getElementById('game-iframe');if(!f)return null;const b=f.getBoundingClientRect();
   return +(b.width/b.height).toFixed(3);})();
 m.sideCards=document.querySelectorAll('#cgSideList > a').length;
 m.ratingRows=document.querySelectorAll('.GameSummary_gameTableRow__9i4Mt').length;
 m.desc=(()=>{const e=document.querySelector('.GameInfo_styledHtmlDiv__Zg2EY');
   return e?e.textContent.trim():null;})();
 m.meta=(()=>{const e=document.querySelector('.GameSummary_gameTableRowContent__RW5fE');
   return e?e.textContent.trim():null;})();
 m.tagPills=document.querySelectorAll('.GameTags_gameTagChipContainer__F5xPO .tagPill').length;
 m.playFavBtn=!!document.getElementById('addFavoritesGame');
 m.favBtn=!!document.querySelector('.cg-fav-btn');
 m.favPanel=!!document.getElementById('cgFavPanel');
 m.deadLinks=[...document.querySelectorAll('a[href]')].filter(a=>
   /\/(favorites|admin)\/?$/.test(a.getAttribute('href'))).length;
 m.teamRail=(()=>{const a=[...document.querySelectorAll('.cg-rail-item')]
   .find(x=>/2 player/i.test(x.textContent));
   return a?a.getAttribute('href'):null;})();
 m.recentRail=(()=>{const a=document.querySelectorAll('.cg-rail-item')[1];
   return a?{label:a.textContent.trim(),href:a.getAttribute('href')}:null;})();
 m.filtered=document.querySelectorAll('#cgAllGrid '+THUMB).length;
 m.rowsHidden=[...document.querySelectorAll('.cg-section[data-row]')].every(r=>r.hidden);
 return m;})()"""

FILTER = r"""(()=>{
 const i=document.querySelector('.cg-search input');
 i.value='basket'; i.dispatchEvent(new Event('input',{bubbles:true}));
 const more=document.getElementById('cgAllMore');
 let guard=0; while(more && !more.hidden && guard++<4000){ more.click(); }
 const g=document.getElementById('cgAllGrid');
 const T='.GameThumbDesktop_gameThumbLinkDesktop__LS_Bs';
 return {n:g.querySelectorAll(T).length,
   count:document.getElementById('cgAllCount').textContent,
   title:document.getElementById('cgAllTitle').textContent,
   pages:Math.ceil((window.CG_GAMES||[]).length/60),
   rowsHidden:[...document.querySelectorAll('[data-row]')].every(r=>r.hidden)};})()"""

CATEGORY = r"""(()=>{
 const more=document.getElementById('cgAllMore');
 let guard=0; while(more && !more.hidden && guard++<4000){ more.click(); }
 const g=document.getElementById('cgAllGrid');
 const titles=[...g.querySelectorAll('.GameThumbDesktop_gameThumbLinkDesktop__LS_Bs')]
   .map(c=>c.getAttribute('aria-label'));
 return {n:titles.length, retro:titles.filter(t=>/retro bowl/i.test(t)).length,
   sports:titles.filter(t=>/football|soccer|basket|baseball|pool|rugby|hockey|golf/i.test(t)).length};})()"""

SEARCHBOX = r"""(()=>{
 const i=document.querySelector('.cg-search input');
 const box=document.getElementById('cgSearchResults');
 if(!i||!box)return {missing:true};
 i.focus(); i.value='retro'; i.dispatchEvent(new Event('input',{bubbles:true}));
 const hits=[...box.querySelectorAll('.cg-search-hit')];
 const img=hits[0]?hits[0].querySelector('img').getBoundingClientRect():null;
 return {visible:!box.hidden, rows:hits.length,
   underBar:Math.round(box.getBoundingClientRect().top) >=
            Math.round(i.getBoundingClientRect().bottom),
   smallImg:img?Math.round(img.width):0, more:!!box.querySelector('.cg-search-more')};})()"""

FAVORITES = r"""(()=>{
 localStorage.setItem('cg-favorites', JSON.stringify(['slope-rider','retro-bowl','tetris']));
 document.dispatchEvent(new CustomEvent('cg:favchange'));
 const btn=document.querySelector('.cg-fav-btn');
 const panel=document.getElementById('cgFavPanel');
 const hiddenBefore=panel.hidden;
 btn.click();
 const shown=!panel.hidden;
 const g=document.getElementById('cgFavGrid');
 const T='.GameThumbDesktop_gameThumbLinkDesktop__LS_Bs';
 const c=g?[...g.querySelectorAll(T)]:[];
 const res={openBtn:!!btn, panel:!!panel, hiddenBefore, shown,
   cards:c.length,
   titles:c.map(x=>x.getAttribute('aria-label')),
   count:(document.getElementById('cgFavCount')||{}).textContent,
   emptyHidden:(document.getElementById('cgFavEmpty')||{}).hidden,
   clearHidden:(document.getElementById('cgFavClear')||{}).hidden,
   cardBox:(()=>{const r=c[0]?c[0].getBoundingClientRect():null;
     return r?[Math.round(r.width),Math.round(r.height)]:null;})()};
 panel.querySelector('.cg-admin-close').click();
 res.closed=panel.hidden;
 return res;})()"""



LOADER = r"""(()=>{
 const f=document.getElementById('game-iframe');
 const pl=document.querySelector('.GamePageDesktop_gfAspectRatioContainer__f_hUp');
 const T='.GameThumb_gameThumbLinkDesktop__wcir5';
 return {frame:!!f, src:f&&f.src,
   playerBg:pl?getComputedStyle(pl).backgroundColor:null,
   ratio:f?+(f.getBoundingClientRect().width/f.getBoundingClientRect().height).toFixed(3):null,
   infoRows:document.querySelectorAll('.GameSummary_gameTableRow__9i4Mt').length,
   meta:(document.querySelector('.GameSummary_gameTableRowContent__RW5fE')||{}).textContent,
   tagPills:document.querySelectorAll('.GameTags_gameTagChipContainer__F5xPO .tagPill').length,
   desc:((document.querySelector('.GameInfo_styledHtmlDiv__Zg2EY')||{}).textContent||'').trim(),
   moreCards:document.querySelectorAll('#cgMoreGrid '+T).length,
   moreInInfo:!!document.querySelector('.GamePageDesktop_underGameContainerGrid__cdhNC #cgMoreGrid')};})()"""


THEME = r"""(()=>{
 const cs=getComputedStyle(document.body);
 const doc=getComputedStyle(document.documentElement);
 return {bodyBg:cs.backgroundColor, bodyFg:cs.color,
   headerBg:getComputedStyle(document.querySelector('.cg-header')).backgroundColor,
   activeBorder:getComputedStyle(document.querySelector('.cg-rail-item.cg-active')).borderLeftColor,
   dim:doc.getPropertyValue('--cg-dim').trim(),
   purple:doc.getPropertyValue('--cg-purple').trim()};})()"""


ADMIN = r"""(()=>{
 try{ localStorage.removeItem('cg-admin-ratings'); }catch(e){}
 const link=document.querySelector('.cg-admin-link');
 const linkBefore=getComputedStyle(link).display;
 const press=()=>document.dispatchEvent(new KeyboardEvent('keydown',
   {ctrlKey:true,altKey:true,key:'a',bubbles:true}));
 const p=document.getElementById('cgAdmin');
 press();
 const opened=!p.hidden, linkAfter=getComputedStyle(link).display;
 const inp=p.querySelector('.cg-admin-search');
 inp.value='Retro Bowl';
 inp.dispatchEvent(new Event('input',{bubbles:true}));
 const matched=p.querySelectorAll('.cg-admin-row').length;
 const btn=p.querySelector('.cg-admin-row .cg-admin-star[data-rate="4"]');
 if(btn) btn.click();
 const row=p.querySelector('.cg-admin-row');
 const rated=row?row.querySelectorAll('.cg-admin-star.is-on').length:0;
 const stored=JSON.parse(localStorage.getItem('cg-admin-ratings')||'{}');
 press();
 const closed=p.hidden;
 return {linkBefore, opened, linkAfter, matched, rated,
   stored:Object.keys(stored).length, closed};})()"""



TEAM = r"""(()=>{
 const more=document.getElementById('cgAllMore');
 let guard=0; while(more && !more.hidden && guard++<4000){ more.click(); }
 const titles=[...document.querySelectorAll('#cgAllGrid .GameThumbDesktop_gameThumbLinkDesktop__LS_Bs')]
   .map(e=>e.getAttribute('aria-label'));
 return {n:titles.length,
   count:document.getElementById('cgAllCount').textContent,
   title:document.getElementById('cgAllTitle').textContent,
   twoPlayer:titles.filter(t=>/2 player|multiplayer|two player/i.test(t)).length};})()"""


RECENT_VIEW = r"""(()=>{
 const t=document.getElementById('cgAllTitle');
 const c=document.getElementById('cgAllCount');
 return {title:t&&t.textContent, count:c&&c.textContent,
   hrefs:[...document.querySelectorAll('#cgAllGrid .GameThumbDesktop_gameThumbLinkDesktop__LS_Bs')]
     .map(a=>a.getAttribute('href')),
   stored:localStorage.getItem('cg-recent')};})()"""


# A star rating set in the admin panel (Ctrl+Alt+A) must override the catalogue
# rating on the play page. Retro Bowl 26 has no catalogue rating, so before the
# fix its Rating row stayed "-" no matter what was rated.
RATING_SEED = ("localStorage.setItem('cg-admin-ratings',"
               "JSON.stringify({'retro-bowl-26':4})); 'seeded'")
RATING_VIEW = r"""(()=>{
 const m=document.querySelector('.GameSummary_gameTableRowContent__RW5fE');
 const before=m?m.textContent.trim():null;
 // Simulate setting a rating in the admin panel: same store, same event.
 localStorage.setItem('cg-admin-ratings',JSON.stringify({'retro-bowl-26':5}));
 document.dispatchEvent(new CustomEvent('cg:ratingchange'));
 return {before:before, after:m?m.textContent.trim():null};})()"""


def main():
    home = cdp.run(BASE + "/", MEAS, port=9350, wait=7)
    play = cdp.run(BASE + "/" + PLAY_SLUG, MEAS, port=9351, wait=7)
    cat = cdp.run(BASE + "/?category=FPS", MEAS, port=9352, wait=7)
    srch = cdp.run(BASE + "/", FILTER, port=9353, wait=7)
    sbox = cdp.run(BASE + "/", SEARCHBOX, port=9354, wait=7)
    sport = cdp.run(BASE + "/?category=Sports", CATEGORY, port=9356, wait=7)
    load = cdp.run(BASE + "/" + PLAY_SLUG, LOADER, port=9355, wait=8)
    gameslol = cdp.run(BASE + "/" + GAMESLOL_SLUG, LOADER, port=9367, wait=8)
    fav = cdp.run(BASE + "/", FAVORITES, port=9358, wait=7)
    theme = cdp.run(BASE + "/", THEME, port=9360, wait=7)
    admin = cdp.run(BASE + "/", ADMIN, port=9361, wait=7)
    team = cdp.run(BASE + "/?category=Team", TEAM, port=9363, wait=9)
    # Play two games, then open Recently Played: it must list them, most recent
    # first, in one browser profile (run_seq keeps localStorage).
    recent = cdp.run_seq([
        (BASE + "/" + PLAY_SLUG, None),
        (BASE + "/retro-bowl", None),
        (BASE + "/?recent=1", RECENT_VIEW),
    ], port=9365, wait=8)
    # Seed a manual rating, open the game, then change the rating while the page
    # is open: the Rating row must reflect both.
    manual = cdp.run_seq([
        (BASE + "/", RATING_SEED),
        (BASE + "/retro-bowl-26", RATING_VIEW),
    ], port=9366, wait=7)
    failed = cdp.failed_requests(BASE + "/", port=9357, wait=7)
    total_cards = home["cards"]

    check("header geometry", home["header"] == ARCHIVE["header"],
          json.dumps(home["header"]))
    check("logo 58x28",
          home["logo"] is not None and home["logo"]["w"] == 58
          and home["logo"]["h"] == 28, json.dumps(home["logo"]))
    check("rail geometry", home["rail"]["x"] == 0
          and home["rail"]["w"] == 60
          and home["rail"]["y"] in (60, 61),
          json.dumps(home["rail"]))
    # 2026 thumb: a standard carousel cell is ~217x123 (16:9-ish) at 1430px,
    # with the image filling the cell.
    check("card 2026 thumb ~217x123",
          home["card"] is not None and 205 <= home["card"]["w"] <= 235
          and abs(home["card"]["w"] / home["card"]["h"] - 1.762) < 0.06,
          json.dumps(home["card"]))
    check("card image fills thumb",
          home["cardImg"] is not None
          and abs(home["cardImg"]["w"] - home["card"]["w"]) <= 6
          and abs(home["cardImg"]["h"] - home["card"]["h"]) <= 6,
          json.dumps(home["cardImg"]))
    check("section title 68px / 14px / 900",
          60 <= home["sectionTitle"]["x"] <= 76
          and home["sectionTitleStyle"]["fontSize"] == "14px"
          and home["sectionTitleStyle"]["fontWeight"] == "900",
          json.dumps(home["sectionTitleStyle"]))
    check("carousel title 20px / 700",
          home["carouselTitleStyle"]["fontSize"] == "20px"
          and home["carouselTitleStyle"]["fontWeight"] == "700",
          json.dumps(home["carouselTitleStyle"]))
    check("header background", home["headerBg"] == ARCHIVE["headerBg"],
          home["headerBg"])
    check("body background", home["bodyBg"] == ARCHIVE["bodyBg"], home["bodyBg"])
    check("Nunito font", home["font"] == "Nunito", home["font"])
    check("rail has 16 items", home["railItems"] == 16, str(home["railItems"]))
    check("home renders 2026 carousels", home["cards"] >= 100, str(home["cards"]))
    # The catalogue itself is the ~12k bundle; the home page renders carousels
    # from it rather than server-rendering every card.
    check("catalogue has 10000+ games", home["games"] >= 10000, str(home["games"]))
    check("no broken images in viewport", home["imgVisibleBroken"] == 0,
          "%d broken of %d visible" % (home["imgVisibleBroken"], len(home["imgVisible"])))

    check("play column 1014px", play["play"]["w"] == ARCHIVE["play"]["w"],
          json.dumps(play["play"]))
    # The player is the sportsgamesaz 16:9 stage (982x597 at 1430px), not the
    # CrazyGames 982x552 box the archive checks used to pin.
    check("player 16:9 stage", play["ratio"] == 1.778 and play["player"] is not None,
          json.dumps({"ratio": play["ratio"], "box": play["player"]}))
    check("play sidebar 356px", play["side"]["w"] == ARCHIVE["side"]["w"],
          json.dumps(play["side"]))
    check("play doc title", play["docTitle"] == PLAY_TITLE + " - Games",
          play["docTitle"])
    check("play h1", play["h1"] == PLAY_TITLE, str(play["h1"]))
    check("play iframe wired", (play["frame"] or "").startswith("http"),
          (play["frame"] or "")[:48])
    check("related games 20", play["sideCards"] >= 12, str(play["sideCards"]))
    # The play page carries the enrichment: a rating with a real vote count, the
    # keyword tag pills and the game's own description (not the generic blurb).
    check("play shows rating + votes",
          play["meta"] and "(" in play["meta"] and "0 votes)" not in play["meta"],
          str(play["meta"]))
    check("play shows keyword tags", play["tagPills"] >= 3, str(play["tagPills"]))
    check("play shows real description",
          play["desc"] and len(play["desc"]) > 120
          and "No download, no install" not in play["desc"],
          (play["desc"] or "")[:60])
    check("play has favorites button", play["playFavBtn"] is True,
          str(play["playFavBtn"]))

    # gameslol games load their own self-hosted player and carry the rating,
    # tag and description scraped from the source page.
    check("gameslol game loads its own player",
          gameslol["frame"] and gameslol["src"]
          and "gameslol.net" in gameslol["src"],
          (gameslol["src"] or "")[:60])
    check("gameslol game shows rating + votes",
          gameslol["meta"] and "(" in gameslol["meta"]
          and "0 votes)" not in gameslol["meta"],
          str(gameslol["meta"]))
    check("gameslol game shows real description",
          gameslol["desc"] and len(gameslol["desc"]) > 80,
          (gameslol["desc"] or "")[:60])

    # FPS games are few and grow as sources are added, so assert it narrows
    # rather than pinning a count that every catalogue change invalidates.
    # The grid is paged, so the first paint holds at most one page of cards.
    check("category filter FPS is a page", 0 < cat["filtered"] <= 60,
          str(cat["filtered"]))
    # The catalogue grows, so assert the search actually narrows rather than a
    # fixed count (a stale count failed every time games were added).
    check("search 'basket' narrows", 0 < srch["n"] < home["games"],
          f"{srch['n']} of {home['games']}")
    check("search hides carousels", srch["rowsHidden"], str(srch["rowsHidden"]))
    # "Load more" pages through every match, and the count reflects the full set.
    check("filtered view renders all matches",
          srch["n"] > 1 and srch["count"] == str(srch["n"]) + " games",
          json.dumps({k: srch.get(k) for k in ("n", "count", "pages")}))
    check("load more paginates 60 at a time", srch["pages"] >= 1,
          str(srch["pages"]))

    # Retro Bowl releases must be reachable from the Sports rail entry; they were
    # the point of adding them. The exact count shifts with the catalogue, so
    # assert presence rather than a fixed number.
    check("sports filter has retro bowl", sport.get("retro", 0) >= 5, json.dumps(sport))
    check("sports filter is sporty", sport.get("sports", 0) >= 40, json.dumps(sport))

    check("search box dropdown under bar", sbox.get("visible") and sbox.get("underBar"),
          json.dumps(sbox))
    check("search box rows small", 0 < sbox.get("rows", 0) <= 6 and sbox.get("smallImg") == 44,
          json.dumps(sbox))
    check("play stage is 16:9",
          load.get("frame") is True and load.get("ratio") == 1.778,
          json.dumps({k: load.get(k) for k in ("frame", "ratio", "playerBg")}))
    # The info column carries the Rating row and the game's own description.
    check("game info bar shows the game",
          load.get("infoRows", 0) >= 1 and load.get("meta") is not None,
          json.dumps({k: load.get(k) for k in ("infoRows", "meta")}))
    # The related grid sits under the player, using the same card component as
    # the rest of the site (the sportsgamesaz "You may also like" row).
    check("related cards under the player",
          load.get("moreInInfo") is True and load.get("moreCards") >= 8,
          json.dumps({k: load.get(k) for k in
                      ("moreInInfo", "moreCards")}))

    check("favorites popup in header",
          home.get("favBtn") is True and home.get("favPanel") is True,
          json.dumps({"btn": home.get("favBtn"), "panel": home.get("favPanel")}))
    # Favorites moved into the header popup; no page links to the old pages.
    check("no links to removed favorites/admin pages",
          home.get("deadLinks") == 0 and play.get("deadLinks") == 0,
          json.dumps({"home": home.get("deadLinks"), "play": play.get("deadLinks")}))
    # The popup renders the saved slugs as the same card component.
    check("favorites popup renders saved games",
          fav.get("openBtn") is True and fav.get("panel") is True
          and fav.get("hiddenBefore") is True and fav.get("shown") is True
          and fav.get("closed") is True
          and fav.get("cards") == 3
          and fav.get("titles") == ["Slope Rider", "Retro Bowl", "Tetris"]
          and fav.get("emptyHidden") is True
          and fav.get("clearHidden") is False,
          json.dumps(fav))
    # The 2026 thumb has no inner card box; it fills its grid cell at 16:9.
    check("favorite cards are 2026 thumbs",
          fav.get("cardBox") is not None and fav["cardBox"][0] > 100
          and abs(fav["cardBox"][0] / fav["cardBox"][1] - 16 / 9) < 0.1,
          json.dumps(fav.get("cardBox")))

    # A manual star rating overrides the catalogue rating on the play page, both
    # on load and live when it is changed while the page is open.
    check("manual rating overrides catalogue",
          manual.get("before") == "4(your rating)"
          and manual.get("after") == "5(your rating)",
          json.dumps(manual))

    # 2026 CrazyGames palette, not the stock Bootstrap dark theme.
    check("2026 crazygames palette",
          theme.get("bodyBg") == "rgb(12, 13, 20)"
          and theme.get("bodyFg") == "rgb(249, 250, 255)"
          and theme.get("headerBg") == "rgb(26, 27, 40)"
          and theme.get("activeBorder") == "rgb(164, 142, 255)"
          and theme.get("dim") == "#aaadbe"
          and theme.get("purple") == "#6842ff",
          json.dumps(theme))

    # Team is the site's 2-player/multiplayer category, reachable from the rail.
    check("Team category is 2 player / multiplayer",
          team.get("n", 0) >= 400
          and team.get("count") == str(team.get("n")) + " games"
          and team.get("twoPlayer", 0) >= 150,
          json.dumps(team))
    check("team rail entry labelled 2 Player",
          home.get("teamRail") == "./?category=Team",
          str(home.get("teamRail")))
    check("rail second entry is Recently Played",
          (home.get("recentRail") or {}).get("label") == "Recently Played"
          and (home.get("recentRail") or {}).get("href") == "./?recent=1",
          json.dumps(home.get("recentRail")))
    # Playing two games then opening Recently Played lists both, newest first.
    rh = recent.get("hrefs") or []
    check("recently played tracks and orders games",
          recent.get("title") == "Recently played"
          and "./retro-bowl" in rh and ("./" + PLAY_SLUG) in rh
          and rh.index("./retro-bowl") < rh.index("./" + PLAY_SLUG),
          json.dumps(recent))

    # Ctrl+Alt+A opens the admin panel; its search + star rating work; the
    # header admin link stays hidden until the panel is opened.
    check("Ctrl+Alt+A admin panel",
          admin.get("linkBefore") == "none" and admin.get("opened") is True
          and admin.get("linkAfter") != "none" and admin.get("matched", 0) >= 1
          and admin.get("rated") == 4 and admin.get("stored") == 1
          and admin.get("closed") is True,
          json.dumps(admin))

    # Every local asset the page asks for must resolve. Relative URLs inside
    # assets/cg2026/theme.css resolve from that directory, not the site root, so
    # a wrong prefix silently 404s the fonts, icons and rail art.
    local_failed = [(s, u) for s, u in failed if "127.0.0.1" in u or u.startswith("/")]
    check("no failed local asset requests", not local_failed,
          json.dumps(local_failed[:8]))

    bad = [r for r in results if not r[1]]
    print("\nFAILURES: %d" % len(bad))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
