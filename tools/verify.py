#!/usr/bin/env python3
"""Verify the rebuilt archive-faithful pages against the archived CrazyGames
2024 layout. Checks structure, geometry and behaviour; prints PASS/FAIL lines
and exits non-zero if anything fails.

    python3 tools/verify.py [base_url]
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cdp  # noqa: E402  (local harness)

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:12000"

# Archive reference values (getComputedStyle on the archived page at 1430px).
ARCHIVE = {
    "header": {"x": 0, "y": 0, "w": 1430, "h": 60},
    "rail": {"x": 0, "y": 60, "w": 60},
    "card": {"w": 218, "h": 124},
    "cardImg": {"w": 214, "h": 120},
    "sectionTitle": {"x": 68, "fs": "14px", "fw": "900"},
    "play": {"w": 1294},
    "player": {"w": 922, "h": 519},
    "side": {"w": 364},
    "headerBg": "rgba(33, 34, 51, 0.9)",
    "bodyBg": "rgb(12, 13, 20)",
}

results = []


def check(name, ok, detail=""):
    results.append((name, bool(ok), detail))
    print("%-4s %-40s %s" % ("PASS" if ok else "FAIL", name, detail))


MEAS = r"""(()=>{
 const m={};
 const box=s=>{const e=document.querySelector(s);if(!e)return null;const b=e.getBoundingClientRect();
   return {x:Math.round(b.x),y:Math.round(b.y),w:Math.round(b.width),h:Math.round(b.height)};};
 const sty=(s,ps)=>{const e=document.querySelector(s);if(!e)return null;const c=getComputedStyle(e);
   const o={};ps.forEach(p=>o[p]=c[p]);return o;};
 m.header=box('.cg-header'); m.rail=box('.cg-rail');
 m.card=box('.cg-card'); m.cardImg=box('.cg-card-img');
 m.sectionTitle=box('.cg-section-title');
 m.sectionTitleStyle=sty('.cg-section-title',['fontSize','fontWeight']);
 m.cardTitle=box('.cg-card-title');
 m.play=box('.cg-play'); m.player=box('.cg-player'); m.side=box('.cg-play-side');
 m.headerBg=getComputedStyle(document.querySelector('.cg-header')).backgroundColor;
 m.bodyBg=getComputedStyle(document.body).backgroundColor;
 m.font=getComputedStyle(document.body).fontFamily.split(',')[0];
 m.railItems=document.querySelectorAll('.cg-rail-item').length;
 m.cards=document.querySelectorAll('.cg-card').length;
 m.games=(window.CG_GAMES||[]).length;
 m.imgs=[...document.querySelectorAll('img')];
 m.imgTotal=m.imgs.length;
 m.imgLoaded=m.imgs.filter(i=>i.complete&&i.naturalWidth>0).length;
 m.imgBroken=m.imgs.filter(i=>i.complete&&i.naturalWidth===0).length;
 m.imgVisible=m.imgs.filter(i=>{const b=i.getBoundingClientRect();
   return b.top<window.innerHeight&&b.bottom>0;});
 m.imgVisibleBroken=m.imgVisible.filter(i=>i.complete&&i.naturalWidth===0).length;
 m.docTitle=document.title;
 m.frame=(document.getElementById('cgFrame')||{}).src||null;
 m.h1=(document.getElementById('cgStageTitle')||{}).textContent||null;
 m.ratio=(()=>{const f=document.getElementById('cgFrame');if(!f)return null;const b=f.getBoundingClientRect();
   return +(b.width/b.height).toFixed(3);})();
 m.sideCards=document.querySelectorAll('#cgSideList .cg-card').length;
 m.favHearts=document.querySelectorAll('.cg-fav').length;
 m.favRail=(()=>{const a=[...document.querySelectorAll('.cg-rail-item')]
   .find(x=>/favorites/i.test(x.textContent));
   return a?{href:a.getAttribute('href'),
     icon:(a.querySelector('img')||{}).getAttribute('src')}:null;})();
 m.filtered=document.querySelectorAll('#cgAllGrid .cg-card').length;
 m.rowsHidden=[...document.querySelectorAll('.cg-section[data-row]')].every(r=>r.hidden);
 return m;})()"""

FILTER = r"""(()=>{
 const i=document.querySelector('.cg-search input');
 i.value='basket'; i.dispatchEvent(new Event('input',{bubbles:true}));
 const g=document.getElementById('cgAllGrid');
 return {n:g.querySelectorAll('.cg-card').length,
   count:document.getElementById('cgAllCount').textContent,
   title:document.getElementById('cgAllTitle').textContent,
   rowsHidden:[...document.querySelectorAll('.cg-section[data-row]')].every(r=>r.hidden)};})()"""

CATEGORY = r"""(()=>{
 const g=document.getElementById('cgAllGrid');
 const titles=[...g.querySelectorAll('.cg-card')].map(c=>c.querySelector('.cg-card-title').textContent);
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
 localStorage.setItem('cg-favorites', JSON.stringify(['2048','retro-bowl','tetris']));
 document.dispatchEvent(new CustomEvent('cg:favchange'));
 const g=document.getElementById('cgFavGrid');
 const c=g?[...g.querySelectorAll('.cg-card')]:[];
 const hearts=g?[...g.querySelectorAll('.cg-fav')]:[];
 const rect=hearts[0]?hearts[0].getBoundingClientRect():null;
 return {cards:c.length,
   titles:c.map(x=>x.querySelector('.cg-card-title').textContent),
   count:(document.getElementById('cgFavCount')||{}).textContent,
   emptyHidden:(document.getElementById('cgFavEmpty')||{}).hidden,
   clearHidden:(document.getElementById('cgFavClear')||{}).hidden,
   lit:hearts.filter(h=>h.classList.contains('is-fav')).length,
   heartBox:rect?[Math.round(rect.width),Math.round(rect.height)]:null,
   heartOpacity:hearts[0]?getComputedStyle(hearts[0]).opacity:null,
   cardBox:(()=>{const r=c[0]?c[0].getBoundingClientRect():null;
     return r?[Math.round(r.width),Math.round(r.height)]:null;})()};})()"""



LOADER = r"""(()=>{
 const l=document.getElementById('cgLoader'), f=document.getElementById('cgFrame');
 if(!l||!f)return {missing:true};
 const sp=l.querySelector('.cg-spinner');
 const c=sp.querySelector('circle');
 const sc=getComputedStyle(sp);
 const lb=l.getBoundingClientRect();
 const sb=sp.getBoundingClientRect();
 return {hiddenAfterLoad:l.hidden, box:parseInt(sc.width,10),
   strokeWidth:getComputedStyle(c).strokeWidth,
   dash:getComputedStyle(c).strokeDasharray,
   anim:getComputedStyle(sp).animationName,
   dashAnim:getComputedStyle(c).animationName,
   bg:getComputedStyle(l).backgroundColor,
   playerBg:getComputedStyle(document.querySelector('.cg-player')).backgroundColor,
   centered:Math.abs((lb.left+lb.width/2)-(sb.left+sb.width/2))<2 &&
            Math.abs((lb.top+lb.height/2)-(sb.top+sb.height/2))<2,
   infoBg:getComputedStyle(document.getElementById('gameInfoContainer')).backgroundColor,
   infoRows:document.querySelectorAll('.cg-info-row').length,
   infoTitle:(document.getElementById('cgStageTitle')||{}).textContent,
   moreCards:document.querySelectorAll('#cgMoreGrid .cg-card').length,
   moreInInfo:!!document.querySelector('#gameInfoContainer .cg-info-grid'),
   moreCols:(()=>{const g=document.getElementById('cgMoreGrid');
     return g?getComputedStyle(g).gridTemplateColumns.split(' ').length:0;})(),
   moreTitles:[...document.querySelectorAll('#cgMoreGrid .cg-card-title')]
     .slice(0,3).map(t=>t.textContent)};})()"""


def main():
    home = cdp.run(BASE + "/", MEAS, port=9350, wait=7)
    play = cdp.run(BASE + "/play?g=2048", MEAS, port=9351, wait=7)
    cat = cdp.run(BASE + "/?category=FPS", MEAS, port=9352, wait=7)
    srch = cdp.run(BASE + "/", FILTER, port=9353, wait=7)
    sbox = cdp.run(BASE + "/", SEARCHBOX, port=9354, wait=7)
    sport = cdp.run(BASE + "/?category=Sports", CATEGORY, port=9356, wait=7)
    load = cdp.run(BASE + "/play?g=2048", LOADER, port=9355, wait=8)
    fav = cdp.run(BASE + "/favorites", FAVORITES, port=9358, wait=7)
    failed = cdp.failed_requests(BASE + "/", port=9357, wait=7)
    total_cards = home["cards"]

    check("header geometry", home["header"] == ARCHIVE["header"],
          json.dumps(home["header"]))
    check("rail geometry", home["rail"]["x"] == 0
          and home["rail"]["w"] == 60
          and home["rail"]["y"] in (60, 61),
          json.dumps(home["rail"]))
    check("card 218x124", home["card"]["w"] == 218 and home["card"]["h"] == 124,
          json.dumps(home["card"]))
    check("card image 214x120",
          home["cardImg"]["w"] == 214 and home["cardImg"]["h"] == 120,
          json.dumps(home["cardImg"]))
    check("section title 68px / 14px / 900",
          home["sectionTitle"]["x"] == 68
          and home["sectionTitleStyle"]["fontSize"] == "14px"
          and home["sectionTitleStyle"]["fontWeight"] == "900",
          json.dumps(home["sectionTitleStyle"]))
    check("card title collapsed to 0x0",
          home["cardTitle"]["w"] == 0 and home["cardTitle"]["h"] == 0,
          json.dumps(home["cardTitle"]))
    check("header background", home["headerBg"] == ARCHIVE["headerBg"],
          home["headerBg"])
    check("body background", home["bodyBg"] == ARCHIVE["bodyBg"], home["bodyBg"])
    check("Nunito font", home["font"] == "Nunito", home["font"])
    check("rail has 19 items", home["railItems"] == 19, str(home["railItems"]))
    check("catalogue cards rendered", home["cards"] >= 200, str(home["cards"]))
    # The catalogue itself is the ~12k bundle; the home page renders carousels
    # from it rather than server-rendering every card.
    check("catalogue has 10000+ games", home["games"] >= 10000, str(home["games"]))
    check("no broken images in viewport", home["imgVisibleBroken"] == 0,
          "%d broken of %d visible" % (home["imgVisibleBroken"], len(home["imgVisible"])))

    check("play column 1294px", play["play"]["w"] == ARCHIVE["play"]["w"],
          json.dumps(play["play"]))
    check("player 922x519", play["player"]["w"] == 922 and play["player"]["h"] == 519,
          json.dumps(play["player"]))
    check("play sidebar 364px", play["side"]["w"] == ARCHIVE["side"]["w"],
          json.dumps(play["side"]))
    check("player 16:9", play["ratio"] == 1.778, str(play["ratio"]))
    check("play doc title", play["docTitle"] == "2048 - Games", play["docTitle"])
    check("play h1", play["h1"] == "2048", str(play["h1"]))
    check("play iframe wired", (play["frame"] or "").startswith("http"),
          (play["frame"] or "")[:40])
    check("related games 20", play["sideCards"] == 20, str(play["sideCards"]))

    # FPS games are few and grow as sources are added, so assert it narrows
    # rather than pinning a count that every catalogue change invalidates.
    check("category filter FPS narrows", 0 < cat["filtered"] < total_cards,
          str(cat["filtered"]))
    # The catalogue grows, so assert the search actually narrows rather than a
    # fixed count (a stale count failed every time games were added).
    check("search 'basket' narrows", 0 < srch["n"] < total_cards,
          f"{srch['n']} of {total_cards}")
    check("search hides carousels", srch["rowsHidden"], str(srch["rowsHidden"]))
    # Filtered views render every match at once, with no "Load more" button.
    check("filtered view renders all matches",
          srch["n"] > 1 and srch["count"] == str(srch["n"]) + " games",
          json.dumps({k: srch.get(k) for k in ("n", "count")}))

    # Every Retro Bowl release must be reachable from the Sports rail entry; it
    # was the whole point of adding them, and they used to be invisible here.
    check("sports filter has retro bowl", sport.get("retro", 0) >= 10, json.dumps(sport))
    check("sports filter is sporty", sport.get("sports", 0) >= 40, json.dumps(sport))

    check("search box dropdown under bar", sbox.get("visible") and sbox.get("underBar"),
          json.dumps(sbox))
    check("search box rows small", 0 < sbox.get("rows", 0) <= 6 and sbox.get("smallImg") == 44,
          json.dumps(sbox))
    check("player loader hides after load", load.get("hiddenAfterLoad") is True,
          json.dumps(load))
    # Archive GameContainer: MUI CircularProgress with disableShrink on #13141E.
    # The ring only rotates; the dash must stay at the disableShrink 80px/200px.
    check("player loader matches archive spinner",
          load.get("box") == 40 and load.get("strokeWidth") == "3.6px"
          and load.get("dash") == "80px, 200px" and load.get("anim") == "cg-spin"
          and load.get("dashAnim") == "none"
          and load.get("bg") == "rgb(19, 20, 30)"
          and load.get("playerBg") == "rgb(19, 20, 30)"
          and load.get("centered") is True,
          json.dumps(load))
    # The CrazyGames game-page GUI around the player: details rows on #1A1B28.
    check("game info bar matches archive",
          load.get("infoBg") == "rgb(26, 27, 40)" and load.get("infoRows") >= 4
          and load.get("infoTitle") == "2048",
          json.dumps({k: load.get(k) for k in ("infoBg", "infoRows", "infoTitle")}))
    # The archive puts a related-games grid inside the info area, under the
    # description, using the same card component as the rest of the site.
    check("related cards in the info area",
          load.get("moreInInfo") is True and load.get("moreCards") >= 12
          and load.get("moreCols") >= 2 and len(load.get("moreTitles") or []) == 3,
          json.dumps({k: load.get(k) for k in
                      ("moreInInfo", "moreCards", "moreCols", "moreTitles")}))

    # Every card carries a heart; the Favorites rail entry points at the page.
    check("cards have favourite hearts",
          home.get("favHearts") == home.get("cards"),
          json.dumps({"hearts": home.get("favHearts"), "cards": home.get("cards")}))
    check("favorites rail entry",
          (home.get("favRail") or {}).get("href") == "/favorites"
          and "Favorites.svg" in ((home.get("favRail") or {}).get("icon") or ""),
          json.dumps(home.get("favRail")))
    # /favorites renders the saved slugs as the same card component, lit hearts.
    check("favorites page renders saved games",
          fav.get("cards") == 3
          and fav.get("titles") == ["2048", "Retro Bowl", "Tetris"]
          and fav.get("lit") == 3 and fav.get("emptyHidden") is True
          and fav.get("clearHidden") is False,
          json.dumps(fav))
    # Heart sits over the card's top-right; the card itself keeps its ratio.
    check("favorite heart 26x26 on cards",
          fav.get("heartBox") == [26, 26] and fav.get("heartOpacity") == "1",
          json.dumps({"heart": fav.get("heartBox"), "opacity": fav.get("heartOpacity")}))

    # Every local asset the page asks for must resolve. Relative URLs inside
    # assets/cg/archive.css resolve from that directory, not the site root, so a
    # wrong prefix silently 404s the fonts and background.
    local_failed = [(s, u) for s, u in failed if "127.0.0.1" in u or u.startswith("/")]
    check("no failed local asset requests", not local_failed,
          json.dumps(local_failed[:8]))

    bad = [r for r in results if not r[1]]
    print("\nFAILURES: %d" % len(bad))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
