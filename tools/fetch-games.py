#!/usr/bin/env python3
"""Collect game metadata for the Games site.

Pulls from several public catalogues, de-duplicates across them, and writes:

  data/games.json   catalogue (slug, title, thumb, embed, categories, rating)

Usage:  python3 tools/fetch-games.py

Icons are hotlinked from each source's CDN by default (see HOTLINK_THUMBS);
`CG_MIRROR_THUMBS=1` downloads and optimises them into
`assets/img/games/<slug>.jpg` instead.

Sources are tried in order and the first one to claim a game wins, so the more
authoritative catalogues should come first. De-duplication is by slug, by
normalised title, and by embed host+path, so the same game listed on two sites
only appears once.
"""
import collections
import concurrent.futures
import gzip
import html
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

try:
    from PIL import Image
except ImportError:  # thumbnails are simply left unoptimised
    Image = None

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_FILE = os.path.join(ROOT, "data", "games.json")
IMG_DIR = os.path.join(ROOT, "assets", "img", "games")

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120 Safari/537.36")

EXT_BY_TYPE = {"image/png": ".png", "image/jpeg": ".jpg", "image/webp": ".webp",
               "image/gif": ".gif", "image/svg+xml": ".svg"}

# Cards render around 320px wide, so this covers retina without shipping 1280px
# source art.
THUMB_WIDTH = 480

# Thumbnails are network-bound; a handful of workers keeps a large run down to
# a few minutes without hammering anyone.
WORKERS = 16

# Upper bound on the catalogue. Sources are ordered by quality and trimmed from
# the tail, so the cap drops the least wanted games first. The bulk sources
# (playgama ~90k, gamepix ~18k, gamemonetize ~38k) sit at the tail, so the cap
# mainly bounds how many of those secondary games are kept.
MAX_GAMES = 120000

# Thumbnails are hotlinked from the source CDN rather than mirrored. A full
# catalogue is ~12k games; downloading and re-encoding each icon would make a
# rebuild take hours and put hundreds of MB in the repo. The source feeds serve
# their icons with permissive CORS and no referer check, so the cards load them
# directly. Set CG_MIRROR_THUMBS=1 to download them locally instead.
HOTLINK_THUMBS = os.environ.get("CG_MIRROR_THUMBS") != "1"

# iogames.fun's genre slugs and the display names we use for them. Games get
# these as categories so the sidebar describes the whole catalogue, not just
# the iogames.space subset.
IOGAMES_FUN_GENRES = {
    "2d-shooter", "3d", "agario", "chat", "cooperative", "fantasy", "fighting",
    "football", "fps", "logic", "pixels", "platform", "racing", "rpg", "ships",
    "slitherio", "space", "spectate", "splix", "strategy", "tanks", "weird",
    "zombies",
}
IOGAMES_FUN_GENRE_NAMES = {
    "2d-shooter": "2D Shooter",
    "agario": "Agario Style",
    "slitherio": "Snake Games",
    "splix": "Splix Style",
    "fps": "FPS",
    "rpg": "RPG",
    "tanks": "Tank",
    "weird": "Weird",
}

# retrobowlfree.io groups its games under /games/<name>-games pages.
RETROBOWLFREE_SKIP = {
    "about-us", "contact-us", "privacy-policy", "term-of-use", "terms-of-use",
    "blog", "new-games", "hot-games", "random",
    "copyright-infringement-notice-procedure",
}


# retrobowl26.com: /<game> pages, embed is /<game>.embed. Pages that are not
# games (listings, tags, blog, legal) must be skipped.
RETROBOWL26_SKIP_PREFIX = ("games/", "tag/", "blog")
RETROBOWL26_SKIP = {
    "new-games", "hot-games", "about-us", "contact-us", "privacy-policy",
    "term-of-use", "copyright-infringement-notice-procedure",
}

# gameslol.net: game pages are /<slug>-<id>.html; the player iframe is injected
# by script with escaped quotes, so the raw markup has to be unescaped first.
# Its breadcrumb JSON-LD names the genre page, which maps to our rail names.
GAMESLOL_NON_GAME = re.compile(r"/(page-\d+|contact|privacy|tags)\.(html|php)$")
GAMESLOL_GENRES = {
    "1-action-games.html": "Action",
    "2-adventure-games.html": "Adventure",
    "3-kids-games.html": "Casual",
    "4-girl-games.html": "Casual",
    "5-bike-games.html": "Racing",
    "6-puzzle-games.html": "Puzzle",
    "7-sports-games.html": "Sports",
    "8-car-games.html": "Racing",
    "arcade-games.php": "Arcade",
    "board-games.php": "Board",
    "bubble-games.php": "Puzzle",
    "card-games.php": "Card",
    "cooking-games.php": "Cooking",
    "dress-up-games.php": "Casual",
    "fantasy-games.php": "Fantasy",
    "fighting-games.php": "Fighting",
    "hidden-objects-games.php": "Puzzle",
    "idle-games.php": "Clicker",
    "mahjong-games.php": "Board",
    "match-3-games.php": "Puzzle",
    "music-games.php": "Music",
    "parking-games.php": "Racing",
    "platform-games.php": "Platform",
    "quiz-games.php": "Quiz",
    "retro-games.php": "Retro",
    "rpg-games.php": "RPG",
    "shooting-games.php": "Shooter",
    "simulation-games.php": "Simulation",
    "strategy-games.php": "Strategy",
}

# gameslol entries whose player is not actually a playable, frameable game.
# Each was checked by hand: a login endpoint, hosts that answer 403/404/dead,
# and two that send X-Frame-Options: SAMEORIGIN. Hosts are stored without a
# leading "www." because the page parser strips it before matching.
GAMESLOL_SKIP_HOSTS = {
    "auth-live.gop3.nl",           # Governor of Poker 3: auth endpoint
    "bonk.io",                     # X-Frame-Options: SAMEORIGIN
    "cdn.gameplayer.io",           # dead host
    "emea.iframed.cn.dmti.cloud",  # dead host
    "freefalltournament.com",      # redirects to a non-game page
    "gameflare.com",               # 403 + X-Frame-Options: SAMEORIGIN
    "hidden4fun.com",              # unreachable
    "warmerise.com",               # 404
}


def fetch(url, timeout=30):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    return urllib.request.urlopen(req, timeout=timeout).read()


def fetch_text(url, timeout=30):
    return fetch(url, timeout=timeout).decode("utf-8", "ignore")


def head_ok(url, timeout=15):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA}, method="HEAD")
        urllib.request.urlopen(req, timeout=timeout)
        return True
    except urllib.error.HTTPError:
        return True  # answers, just not 200
    except (urllib.error.URLError, OSError):
        return False


def slugify(value):
    return re.sub(r"[^a-z0-9]+", "-", (value or "").lower()).strip("-") or "game"


def norm_title(value):
    """Loose key so "Smash Karts" and "smash-karts" collide."""
    return re.sub(r"[^a-z0-9]+", "", (value or "").lower())


def embed_key(url):
    """Identity of an embed: host + path, ignoring scheme/query/www."""
    parts = urllib.parse.urlsplit(url)
    host = parts.netloc.lower().removeprefix("www.")
    path = parts.path.rstrip("/").lower()
    return f"{host}{path}"


# -------------------------------------------------------------- categories
# The rail filters on exact category names ("Sports", "Action", ...). Sources
# that publish no genre metadata (retrobowl26.com, 3kh0) therefore produced
# games with no categories, and those games could not be found from the rail at
# all - which is how the whole Retro Bowl family ended up invisible under
# Sports. There is no genre field to read, so classify by title.
#
# Matched as substrings of the alnum-lowered title ("8 Ball Pool" -> "8ballpool").
# First match wins, so more specific needles come first: "cannonbasketball"
# before "cannon", "moto" before "pool".
CATEGORY_RULES = [
    # Retro Bowl and friends. Each release is a distinct build, and the family
    # is what the user came for, so it gets a stable, explicit mapping.
    ("nflretrobowl", ["Sports", "Football", "Retro", "Casual"]),
    ("retrobowl", ["Sports", "Football", "Retro", "Casual"]),
    # These three must sit above the broad "ball" / "pool" / "retro" needles,
    # which would otherwise swallow them (Factory Balls is a puzzle, not a
    # sport; MotoX3M Pool is a bike game; Web Retro Local is the emulator).
    ("webretrolocal", ["Retro", "Emulator"]),
    ("factoryballs", ["Puzzle"]),
    ("motox3m", ["Racing"]),
    ("retrosportschampion", ["Sports", "Football", "Retro", "Arcade"]),
    ("retrogoal", ["Sports", "Football", "Arcade"]),
    ("retro", ["Retro", "Arcade"]),
    ("backyardfootball", ["Sports", "Football"]),
    ("footballbros", ["Sports", "Football", "Team"]),
    ("footballlegends", ["Sports", "Football"]),
    ("ragdollfootball", ["Sports", "Football", "Arcade"]),
    ("realfootball", ["Sports", "Football"]),
    ("googlefootball", ["Sports", "Football"]),
    ("soccerbros", ["Sports", "Football", "Team"]),
    ("soccerphysics", ["Sports", "Football"]),
    ("soccerskills", ["Sports", "Football"]),
    ("soccerstrike", ["Sports", "Football"]),
    ("soccerrandom", ["Sports", "Football", "Casual"]),
    ("soccerreal", ["Sports", "Football"]),
    ("soccergrid", ["Sports", "Football", "Puzzle"]),
    ("superliquidsoccer", ["Sports", "Football", "Arcade"]),
    ("buttonsoccer", ["Sports", "Football"]),
    ("indoorsoccer", ["Sports", "Football"]),
    ("newstarsoccer", ["Sports", "Football", "Simulation"]),
    ("orbitkick", ["Sports", "Football", "Arcade"]),
    ("penaltykick", ["Sports", "Football"]),
    ("flickshotsoccer", ["Sports", "Football"]),
    ("fifa", ["Sports", "Football", "Retro"]),
    ("rocketgoal", ["Sports", "Football"]),
    ("rocketsoccer", ["Sports", "Football", "Arcade"]),
    ("goalgang", ["Sports", "Football"]),
    ("goalheads", ["Sports", "Football"]),
    ("4thandgoal", ["Sports", "Football", "Strategy"]),
    ("nflgrid", ["Sports", "Football", "Puzzle"]),
    ("3dfreekick", ["Sports", "Football"]),
    ("tecmo", ["Sports", "Football", "Retro"]),
    ("ballpark", ["Sports", "Baseball"]),
    ("hotfoot", ["Sports", "Baseball"]),
    ("baseball", ["Sports", "Baseball"]),
    ("cannonbasketball", ["Sports", "Basketball"]),
    ("basketball", ["Sports", "Basketball"]),
    ("hoopgrids", ["Sports", "Basketball", "Puzzle"]),
    ("dunk", ["Sports", "Basketball"]),
    ("basket", ["Sports", "Basketball"]),
    ("rugby", ["Sports"]),
    ("bowling", ["Sports"]),
    ("hockey", ["Sports"]),
    ("cricket", ["Sports"]),
    ("golf", ["Sports"]),
    ("miniputt", ["Sports"]),
    ("minigolf", ["Sports"]),
    ("ball", ["Sports"]),
    ("speedstars", ["Sports"]),
    ("nba", ["Sports", "Basketball", "Retro"]),
    ("premierleague", ["Sports", "Football"]),
    ("superbowl", ["Sports", "Football"]),
    ("8ballpool", ["Sports"]),
    ("8poolmaster", ["Sports"]),
    ("9ballpool", ["Sports"]),
    ("poolclub", ["Sports"]),
    ("pool", ["Sports"]),
    ("mma", ["Sports", "Fighting"]),
    ("freekick", ["Sports", "Football"]),
    # Shooters and action.
    ("onetapfps", ["Shooter", "Action", "FPS"]),
    ("fps", ["Shooter", "Action", "FPS"]),
    ("wolfenstein", ["Shooter", "Action"]),
    ("smokingbarrels", ["Shooter", "Action"]),
    ("defendthetank", ["Tank", "Strategy"]),
    ("tank", ["Tank", "Action"]),
    ("missiles", ["Shooter", "Action"]),
    ("cannon", ["Shooter", "Casual"]),
    ("sniper", ["Shooter", "Action"]),
    ("boxhead", ["Shooter", "Zombies"]),
    ("stormthehouse", ["Shooter", "Strategy"]),
    ("endlesswar", ["Shooter", "Strategy"]),
    ("zombie", ["Zombies", "Action"]),
    ("backrooms", ["Horror", "Adventure"]),
    ("superhot", ["Shooter", "Action", "Puzzle"]),
    ("amongus", ["Strategy", "Casual"]),
    ("soldierlegend", ["Shooter", "Action"]),
    ("soilderlegend", ["Shooter", "Action"]),
    ("tacticalassassin", ["Action", "Shooter"]),
    ("matrixrampage", ["Action", "Shooter"]),
    ("rooftopsnipers", ["Shooter", "Action"]),
    ("battlearena", ["Action"]),
    ("beastclash", ["Action"]),
    ("robotleague", ["Action"]),
    ("hoverbot", ["Action"]),
    ("hexbound", ["Action", "Adventure"]),
    ("blockader", ["Action"]),
    ("schoolfury", ["Action"]),
    ("shipsmasher", ["Action"]),
    ("snowbattle", ["Action"]),
    ("championarcher", ["Action"]),
    ("blackknight", ["Action", "Platform"]),
    ("ironsnout", ["Action", "Casual"]),
    ("goatrampage", ["Casual", "Action"]),
    ("getyoked", ["Casual", "Action"]),
    # Racing, running and arcade reflexes.
    ("motocross", ["Racing"]),
    ("moto", ["Racing"]),
    ("hexgl", ["Racing", "Sci-Fi"]),
    ("forzahorizon", ["Racing"]),
    ("tanukisunset", ["Racing"]),
    ("tunnelrush", ["Racing", "Arcade"]),
    ("templerun", ["Running", "Arcade"]),
    ("twerkrace", ["Racing", "Casual"]),
    ("escaperoad", ["Racing", "Arcade"]),
    ("taproad", ["Racing", "Arcade"]),
    ("smashcarts", ["Racing", "Arcade"]),
    ("swerve", ["Racing", "Arcade"]),
    ("ngon", ["Arcade", "Racing"]),
    ("cubefield", ["Arcade", "Running"]),
    ("slope", ["Arcade", "Running"]),
    ("colorsurfer", ["Arcade", "Running"]),
    ("gimmetheairpod", ["Arcade", "Running"]),
    ("chromedino", ["Arcade", "Running"]),
    ("flappy", ["Arcade", "Casual"]),
    ("helicopter", ["Arcade", "Casual"]),
    ("avalanche", ["Arcade"]),
    ("kittencannon", ["Arcade"]),
    ("tosstheturtle", ["Arcade"]),
    ("rollyvortex", ["Arcade"]),
    ("fliprush", ["Arcade"]),
    ("rotaterush", ["Arcade", "Puzzle"]),
    ("waverider", ["Arcade"]),
    ("paperyplanes", ["Arcade"]),
    ("polybranch", ["Arcade"]),
    ("circlo", ["Arcade"]),
    ("stack", ["Arcade"]),
    # Platforms.
    ("vex", ["Platform", "Puzzle"]),
    ("doodlejump", ["Platform", "Casual"]),
    ("doublewires", ["Platform", "Casual"]),
    ("nsshaft", ["Platform", "Casual"]),
    ("geometrydash", ["Arcade", "Platform"]),
    ("supermario", ["Platform", "Retro"]),
    ("mario", ["Platform", "Retro"]),
    ("bigtower", ["Platform", "Puzzle"]),
    ("thisistheonlylevel", ["Platform", "Puzzle"]),
    ("worldshardestgame", ["Puzzle", "Platform"]),
    ("deathrun", ["Platform", "Action"]),
    ("achievementunlocked", ["Platform", "Puzzle"]),
    ("creativekillchamber", ["Platform", "Action"]),
    ("gettingoverit", ["Platform", "Casual"]),
    # Puzzle and strategy.
    ("2048", ["Puzzle"]),
    ("solitaire", ["Puzzle", "Card"]),
    ("solitare", ["Puzzle", "Card"]),
    ("tetris", ["Puzzle"]),
    ("minesweeper", ["Puzzle"]),
    ("connect3", ["Puzzle"]),
    ("bloxors", ["Puzzle"]),
    ("cuttherope", ["Puzzle", "Casual"]),
    ("wordle", ["Puzzle"]),
    ("cellmachine", ["Puzzle", "Simulation"]),
    ("hextris", ["Puzzle", "Arcade"]),
    ("pushthesquare", ["Puzzle", "Arcade"]),
    ("unboxtheroom", ["Puzzle", "Casual"]),
    ("stealingthediamond", ["Puzzle", "Action"]),
    ("breakingthebank", ["Puzzle", "Action"]),
    ("theheist", ["Puzzle", "Action"]),
    ("impossiblequiz", ["Puzzle"]),
    ("thereisnogame", ["Puzzle", "Weird"]),
    ("bigredbutton", ["Puzzle", "Weird"]),
    ("portal", ["Puzzle", "Action"]),
    ("bloonstd", ["Strategy", "Tower Defense"]),
    ("canyonedefense", ["Strategy", "Tower Defense"]),
    ("thefinalearth", ["Strategy", "Simulation"]),
    ("hexempire", ["Strategy"]),
    ("stickwar", ["Strategy", "Action"]),
    ("battleforgondor", ["Strategy", "Action"]),
    ("thebattle", ["Strategy"]),
    ("sortthecourt", ["Puzzle", "Simulation"]),
    # Idle, sandbox and odds and ends.
    ("cookieclicker", ["Clicker"]),
    ("particleclicker", ["Clicker"]),
    ("clicker", ["Clicker"]),
    ("idle", ["Clicker"]),
    ("dogeminer", ["Clicker"]),
    ("grindcraft", ["Clicker", "Simulation"]),
    ("craftmine", ["Adventure", "Simulation"]),
    ("minecraft", ["Adventure", "Simulation"]),
    ("eaglercraft", ["Adventure", "Simulation"]),
    ("precisionclient", ["Adventure", "Simulation"]),
    ("melonsandbox", ["Simulation", "Sandbox"]),
    ("ragdollsandbox", ["Simulation", "Sandbox"]),
    ("sandgame", ["Simulation"]),
    ("interactivebuddy", ["Simulation", "Casual"]),
    ("papaspizzaria", ["Casual", "Simulation"]),
    ("ducklife", ["Casual", "Simulation"]),
    ("learntofly", ["Casual", "Simulation"]),
    ("idolsofash", ["RPG", "Adventure"]),
    ("garticphone", ["Casual", "Multiplayer"]),
    ("soundboard", ["Casual"]),
    ("meccha", ["Casual"]),
    ("paperio", ["Agario Style"]),
    ("qwop", ["Casual", "Weird"]),
    ("tvstatic", ["Weird"]),
    ("fakevirus", ["Weird"]),
    ("hackertyper", ["Weird"]),
    ("evilglitch", ["Weird"]),
    ("youraislopboresme", ["Weird"]),
    ("gameinsideagame", ["Weird", "Puzzle"]),
    ("dealornodeal", ["Casual"]),
    ("glasscity", ["Casual", "Action"]),
    ("exo", ["Action"]),
    ("roper", ["Arcade"]),
]


def classify(title, existing):
    """Categories for a game whose source published none.

    Existing source categories always win; this only fills the gaps so every
    game is reachable from at least one rail entry.
    """
    if existing:
        return existing
    key = norm_title(title)
    for needle, cats in CATEGORY_RULES:
        if needle in key:
            return list(cats)
    return ["Casual"]


# "Team" is the site's 2-player/multiplayer entry point. The feeds only tag a
# few hundred games as multiplayer, so anything already tagged with a
# multiplayer-ish category - or whose title says so - joins Team as well.
TEAM_CATS = {
    "Multiplayer", "2 Player", "Cooperative", "Team", "Free For All",
    "Battle Royale", "Agario Style", ".io", ".IO", "Moomoo.io Style",
    "Splix Style", "Diep Style", "Spectate",
}
TEAM_TITLE = re.compile(
    r"\b(2 player|two player|2-player|multiplayer|multi-player|co-?op|"
    r"local multiplayer|party game|versus|pvp)\b", re.I)


def ensure_team(games):
    """Make every multiplayer game reachable from the 2 Player rail entry."""
    added = 0
    for game in games:
        cats = game.get("categories") or []
        if "Team" in cats:
            continue
        if set(cats) & TEAM_CATS or TEAM_TITLE.search(game.get("title", "")):
            game["categories"] = cats + ["Team"]
            added += 1
    print(f"tagged {added} games as Team (2 player / multiplayer)")


# The source a game came from, for the play page's "Source:" row. The big
# distributors get a friendly name; everything else (the ~300 .io sites) shows
# its bare domain, since inventing a brand name for a one-game host is worse
# than the domain the player is actually loading.
SOURCE_NAMES = [
    ("gamemonetize.co", "GameMonetize"),
    ("gamepix.com", "GamePix"),
    ("playgama.com", "Playgama"),
    ("crazygames.com", "CrazyGames"),
    ("3kh0.net", "3kh0"),
    ("retrobowl26.com", "Retro Bowl"),
    ("retrobowlfree.io", "Retro Bowl"),
    ("retrogames.cc", "RetroGames"),
    ("gameslol.net", "GamesLOL"),
]


def source_label(embed):
    """Provider/distributor a game's embed belongs to, derived from its host."""
    host = (urllib.parse.urlparse(embed).hostname or "").lower()
    if host.startswith("www."):
        host = host[4:]
    for domain, name in SOURCE_NAMES:
        if host == domain or host.endswith("." + domain):
            return name
    return host or "Unknown"


# ---------------------------------------------------------------- sources


def source_iogames_space():
    """iogames.space embeds a __NEXT_DATA__ JSON payload per listing page."""
    listings = ["https://iogames.space/popular",
                "https://iogames.space/new",
                "https://iogames.space/featured"]
    games = []
    for listing in listings:
        try:
            payload = re.search(
                r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>',
                fetch_text(listing), re.S)
            if not payload:
                print(f"  ! no __NEXT_DATA__ on {listing}", file=sys.stderr)
                continue
            payload = json.loads(payload.group(1))
        except (urllib.error.URLError, OSError, ValueError) as exc:
            print(f"  ! skipped {listing}: {exc}", file=sys.stderr)
            continue

        found = []
        _walk_for_games(payload, found)
        for game in found:
            title = (game.get("title") or "").strip()
            embed = (game.get("embedUrl") or "").strip()
            if not title or not embed:
                continue
            games.append({
                "slug": slugify(game.get("path") or title),
                "title": title,
                "embed": embed,
                "thumbSource": game.get("thumbnailUrl") or "",
                "categories": [c.get("name") for c in (game.get("categories") or [])
                               if c.get("name")],
                "rating": game.get("displayRating") or game.get("ratingAverage") or None,
            })
    return games


def _walk_for_games(obj, out):
    """Gather every list of game-shaped dicts anywhere in the payload."""
    if isinstance(obj, dict):
        for value in obj.values():
            _walk_for_games(value, out)
    elif isinstance(obj, list):
        if obj and isinstance(obj[0], dict) and "embedUrl" in obj[0] and "title" in obj[0]:
            out.extend(obj)
        else:
            for value in obj:
                _walk_for_games(value, out)


def source_iogames_fun():
    """iogames.fun has a sitemap of /<game> pages; the page embeds the game's
    own site and carries its icon in og:image.

    The icon path is not predictable - it is sometimes /images/games/og/x.jpg
    and sometimes /images/games/x.jpg - so the game page is read for the real
    URL (and a properly formatted title) rather than guessing. Genres come from
    the /genres/<genre> pages, which list the games in each one.
    """
    index = fetch_text("https://iogames.fun/sitemap.xml")
    paths = []
    for sitemap in re.findall(r"<loc>([^<]+sitemap-games\.xml)</loc>", index):
        xml = fetch_text(sitemap)
        # Strip ?lang= duplicates: one entry per game.
        paths.extend(sorted({urllib.parse.urlsplit(u).path.strip("/")
                             for u in re.findall(r"<loc>([^<]+)</loc>", xml)}))
    paths = [p for p in paths if p and "/" not in p]

    with concurrent.futures.ThreadPoolExecutor(max_workers=WORKERS) as pool:
        pages = list(pool.map(_iogames_fun_page, paths))
    games = [game for game in pages if game]

    known = {game["slug"] for game in games}
    by_slug = {game["slug"]: game for game in games}
    with concurrent.futures.ThreadPoolExecutor(max_workers=WORKERS) as pool:
        genre_maps = pool.map(_iogames_fun_genre, sorted(IOGAMES_FUN_GENRES))
    for genre, slugs in genre_maps:
        name = IOGAMES_FUN_GENRE_NAMES.get(genre, genre.replace("-", " ").title())
        for slug in slugs & known:
            by_slug[slug]["categories"].append(name)
    return games


def _iogames_fun_genre(genre):
    try:
        html = fetch_text(f"https://iogames.fun/genres/{genre}")
    except (urllib.error.URLError, OSError) as exc:
        print(f"  ! iogames.fun genre {genre}: {exc}", file=sys.stderr)
        return genre, set()
    return genre, {slugify(m) for m in re.findall(r'href="/([a-z0-9][a-z0-9.-]*)"', html)}


def _iogames_fun_page(path):
    try:
        html = fetch_text(f"https://iogames.fun/{path}")
    except (urllib.error.URLError, OSError) as exc:
        print(f"  ! iogames.fun {path}: {exc}", file=sys.stderr)
        return None

    icon = re.search(r'property="og:image"\s+content="([^"]+)"', html) \
        or re.search(r'content="([^"]+)"\s+property="og:image"', html)
    match = re.search(r"<title>(.*?)</title>", html, re.S)
    title = match.group(1).strip() if match else ""
    # "Krunker — Play Krunker at iogames.fun" -> "Krunker"
    title = re.split(r"\s+[—–|-]\s+", title)[0].strip()

    return {
        "slug": slugify(path),
        "title": title or path,
        "embed": f"https://{path}",
        "thumbSource": icon.group(1) if icon else "",
        "categories": [],
        "rating": None,
    }


def source_retrobowlfree():
    """retrobowlfree.io lists /<game> pages; embed is /<game>.embed.

    Titles are read from each page (the sitemap only has URLs), which also
    confirms the game actually exists before we keep it.
    """
    xml = fetch_text("https://retrobowlfree.io/sitemap.xml")
    paths = []
    category_paths = []
    for url in re.findall(r"<loc>([^<]+)</loc>", xml):
        path = urllib.parse.urlsplit(url).path.strip("/")
        if not path:
            continue
        if path.startswith("games/"):
            category_paths.append(path.split("/", 1)[1])
        elif "/" not in path and path not in RETROBOWLFREE_SKIP:
            paths.append(path)

    with concurrent.futures.ThreadPoolExecutor(max_workers=WORKERS) as pool:
        pages = list(pool.map(_retrobowl_page, paths))
        category_maps = list(pool.map(_retrobowl_category, category_paths))

    games = [game for game in pages if game]
    by_slug = {game["slug"]: game for game in games}
    for category, slugs in category_maps:
        name = _category_name(category)
        for slug in slugs & by_slug.keys():
            by_slug[slug]["categories"].append(name)
    return games


def _category_name(path):
    """"racing-games" -> "Racing", "retro-games" -> "Retro"."""
    name = path[:-len("-games")] if path.endswith("-games") else path
    return name.replace("-", " ").title()


def _retrobowl_category(path):
    try:
        html = fetch_text(f"https://retrobowlfree.io/games/{path}")
    except (urllib.error.URLError, OSError) as exc:
        print(f"  ! retrobowlfree category {path}: {exc}", file=sys.stderr)
        return path, set()
    # Only the game tiles count. The page also links featured games, other
    # categories and site pages, which would tag everything with everything.
    slugs = {slugify(m) for m in re.findall(
        r'<a[^>]*href="/([a-z0-9][a-z0-9-]*)"[^>]*class="grid-gamelist-1-item', html)}
    return path, slugs


def _retrobowl_page(path):
    try:
        html = fetch_text(f"https://retrobowlfree.io/{path}")
    except (urllib.error.URLError, OSError) as exc:
        print(f"  ! retrobowlfree {path}: {exc}", file=sys.stderr)
        return None
    match = re.search(r"<title>(.*?)</title>", html, re.S)
    title = match.group(1).strip() if match else ""
    # "Play Retro Bowl - Retro Bowl Free" -> "Retro Bowl"
    title = re.split(r"\s+[-|]\s+", title)[0].strip()
    title = re.sub(r"^play\s+", "", title, flags=re.I).strip()
    # The icon filename does not always match the slug (retro-bowl uses
    # retro-bowl-game.jpg), so read the real URL rather than guessing.
    icon = re.search(r'property="og:image"[^>]*content="([^"]+)"', html)
    return {
        "slug": slugify(path),
        "title": title or path,
        "embed": f"https://retrobowlfree.io/{path}.embed",
        "thumbSource": icon.group(1) if icon else "",
        "categories": [],
        "rating": None,
    }


def source_3kh0():
    """3kh0-lite self-hosts ~145 games and publishes a config/games.json index.

    Games are served from lite.3kh0.net, which does not block framing. jsDelivr
    would serve the same files but as text/plain, which browsers refuse to
    render in an iframe, so the site URL is used instead.
    """
    base = "https://lite.3kh0.net"
    try:
        index = json.loads(fetch_text(f"{base}/config/games.json"))
    except (urllib.error.URLError, OSError, ValueError) as exc:
        print(f"  ! 3kh0 index: {exc}", file=sys.stderr)
        return []

    games = []
    for entry in index:
        title = (entry.get("title") or "").strip()
        parts = [p for p in (entry.get("link") or "").split("/") if p]
        if not title or len(parts) < 2 or parts[0] != "projects":
            continue
        folder = parts[1]
        icon = entry.get("imgSrc") or ""
        games.append({
            "slug": slugify(folder),
            "title": title,
            "embed": f"{base}/projects/{folder}/",
            "thumbSource": f"{base}/{icon}" if icon else "",
            "categories": [],
            "rating": None,
        })
    return games


def source_retrobowl26():
    """retrobowl26.com lists /<game> pages; the embed is /<game>.embed.

    Its whole Retro Bowl family is kept - 25/26/27/college/NFL/unblocked are
    each a distinct playable build here, and the user asked for all of them -
    so nothing is filtered out the way retrobowlfree.io's re-skins are.
    """
    xml = fetch_text("https://retrobowl26.com/sitemap.xml")
    paths = []
    for url in re.findall(r"<loc>([^<]+)</loc>", xml):
        path = urllib.parse.urlsplit(url).path.strip("/")
        if not path or path in RETROBOWL26_SKIP:
            continue
        if path.startswith(RETROBOWL26_SKIP_PREFIX) or "/" in path:
            continue
        paths.append(path)

    with concurrent.futures.ThreadPoolExecutor(max_workers=WORKERS) as pool:
        pages = list(pool.map(_retrobowl26_page, paths))
    return [game for game in pages if game]


def _retrobowl26_page(path):
    try:
        html = fetch_text(f"https://retrobowl26.com/{path}")
    except (urllib.error.URLError, OSError) as exc:
        print(f"  ! retrobowl26 {path}: {exc}", file=sys.stderr)
        return None
    if "iframehtml5" not in html:
        return None  # a page without the player is not a game
    match = re.search(r"<title>(.*?)</title>", html, re.S)
    title = match.group(1).strip() if match else ""
    # "Retro Bowl 26 - Play Retro Bowl 26 On Retro Bowl 26" -> "Retro Bowl 26"
    title = re.split(r"\s+[-|]\s+", title)[0].strip()
    title = re.sub(r"^play\s+", "", title, flags=re.I).strip()
    icon = re.search(r'property="og:image"[^>]*content="([^"]+)"', html)
    if not icon:
        icon = re.search(r'content="([^"]+)"[^>]*property="og:image"', html)
    src = icon.group(1) if icon else ""
    if src.startswith("/"):
        src = "https://retrobowl26.com" + src
    return {
        "slug": slugify(path),
        "title": title or path,
        "embed": f"https://retrobowl26.com/{path}.embed",
        "thumbSource": src,
        "categories": [],
        "rating": None,
    }


def _crazygames_cover(slug, sitemap_covers):
    """Cover URL for a slug.

    The listing JSON carries a cover path for most games; a few only appear in
    the sitemap, which is the authoritative source for the canonical cover. The
    bare cover path 404s without the format query, so one is always appended.
    """
    cover = sitemap_covers.get(slug)
    if cover:
        return cover + "?format=webp&quality=80&width=480"
    return ""


def source_crazygames():
    """CrazyGames' whole catalogue, via its paginated listing pages.

    The JSON API (v3/en_US/games) ignores paging and always returns the same
    100 items, so it cannot enumerate the catalogue. The category listing pages
    (`/c/<slug>`, 60 items each) and the all-games listing (`/sitemap/games`,
    100 each) do paginate, and their __NEXT_DATA__ carries name, slug, cover and
    categoryName. The category pages give every game a genre; the all-games
    listing catches anything not filed under a category. The `en` sitemap is
    parsed once for the canonical cover of each slug, which fills in the
    listings that omit it.
    """
    covers = {}
    try:
        sitemap = fetch_text("https://www.crazygames.com/en/sitemap", timeout=120)
        for block in re.findall(r"<url>(.*?)</url>", sitemap, re.S):
            loc = re.search(r"<loc>https://www\.crazygames\.com/game/([^<]+)</loc>",
                            block)
            img = re.search(r"<image:loc>([^<]+)</image:loc>", block)
            if loc and img:
                covers[loc.group(1)] = html.unescape(img.group(1)).split("?")[0]
        print(f"  crazygames sitemap covers: {len(covers)}")
    except (urllib.error.URLError, OSError, ValueError) as exc:
        print(f"  ! crazygames sitemap: {exc}", file=sys.stderr)

    def next_items(url):
        # CrazyGames answers 429 when the listing pages are walked quickly, so
        # back off and retry rather than dropping the rest of the catalogue.
        for attempt in range(5):
            try:
                payload = json.loads(re.search(
                    r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>',
                    fetch_text(url, timeout=60), re.S).group(1))
                time.sleep(0.7)
                return payload["props"]["pageProps"]["games"]["items"]
            except urllib.error.HTTPError as exc:
                if exc.code != 429 or attempt == 4:
                    print(f"  ! crazygames {url}: {exc}", file=sys.stderr)
                    return []
                time.sleep(2 ** attempt)
            except (urllib.error.URLError, OSError, ValueError, KeyError,
                    AttributeError) as exc:
                print(f"  ! crazygames {url}: {exc}", file=sys.stderr)
                return []
        return []

    # Category listings, walked until a page comes back short. The sitemap only
    # lists a handful of pages per category, but the paging is contiguous.
    out, seen = [], set()

    def add(item, fallback_cat=""):
        slug = (item.get("slug") or "").strip()
        title = (item.get("name") or "").strip()
        if not slug or not title or slug in seen:
            return
        thumb = _crazygames_cover(slug, covers)
        if not thumb and item.get("cover"):
            thumb = ("https://imgs.crazygames.com/" + item["cover"] +
                     "?format=webp&quality=80&width=480")
        if not thumb:
            return
        seen.add(slug)
        cat = (item.get("categoryName") or fallback_cat).strip()
        out.append({
            "slug": slug,
            "title": title,
            "embed": f"https://www.crazygames.com/embed/{slug}",
            "thumbSource": thumb,
            "categories": [cat] if cat else [],
            "rating": None,
        })

    categories = ["action", "adventure", "arcade", "beauty", "clicker",
                  "driving", "io", "puzzle", "shooting", "sim", "sports",
                  "strategy"]
    for cat in categories:
        page = 1
        while True:
            items = next_items(f"https://www.crazygames.com/c/{cat}/{page}")
            if not items:
                break
            for item in items:
                add(item, cat.title())
            if len(items) < 60:
                break
            page += 1

    page = 1
    while True:
        items = next_items(f"https://www.crazygames.com/sitemap/games/{page}"
                           if page > 1 else "https://www.crazygames.com/sitemap/games")
        if not items:
            break
        for item in items:
            add(item)
        if len(items) < 100:
            break
        page += 1

    return out


def source_gamemonetize():
    """GameMonetize's public feed is a JSON catalogue of html5 games.

    The feed serves at most MAX_FEED entries; asking for more simply truncates,
    so this pulls a large slice and lets the global cap do the trimming.
    """
    url = "https://gamemonetize.com/feed.php?format=0&num=100000"
    try:
        entries = json.loads(fetch_text(url, timeout=120))
    except (urllib.error.URLError, OSError, ValueError) as exc:
        print(f"  ! gamemonetize feed: {exc}", file=sys.stderr)
        return []

    games = []
    for entry in entries:
        title = (entry.get("title") or "").strip()
        embed = (entry.get("url") or "").strip()
        if not title or not embed:
            continue
        categories = []
        if entry.get("category"):
            categories.append(str(entry["category"]).strip())
        games.append({
            "slug": slugify(title),
            "title": title,
            "embed": embed,
            "thumbSource": entry.get("thumb") or "",
            "categories": categories,
            "rating": None,
        })
    return games


def source_gamepix():
    """GamePix publishes its catalogue as eight plain sitemaps.

    The public site sits behind Cloudflare (the listing and API 403), but the
    sitemaps are served from the same host with an image extension that carries
    the cover, so a single fetch per sitemap yields slug, title and icon. The
    play page is /play/<slug>; the embeddable frame is /play/<slug>/embed, which
    answers without X-Frame-Options or a frame-ancestors policy.
    """
    out = []
    for page in range(1, 9):
        url = f"https://www.gamepix.com/sitemaps/games-{page}.xml"
        try:
            xml = fetch_text(url, timeout=60)
        except (urllib.error.URLError, OSError, ValueError) as exc:
            print(f"  ! gamepix sitemap {page}: {exc}", file=sys.stderr)
            continue
        for loc, slug, img in re.findall(
                r"<loc>(https://www\.gamepix\.com/play/([^<]+))</loc>"
                r"(?:<image:image><image:loc>([^<]+)</image:loc></image:image>)?",
                xml):
            slug = slug.strip()
            if not slug:
                continue
            title = re.sub(r"[-_]+", " ", slug).strip().title()
            out.append({
                "slug": slug,
                "title": title,
                "embed": f"https://play.gamepix.com/{slug}/embed",
                "thumbSource": img,
                "categories": [],
                "rating": None,
            })
    return out


def source_playgama():
    """Playgama (playhop catalogue) publishes ~90k games as four sitemaps.

    Each entry carries the slug, the English title via the og image path and an
    <image:loc> cover. The portal allows framing (frame-ancestors *), and its
    /game/<slug> page renders the game directly, so that URL is the embed.
    """
    index = fetch_text("https://playgama.com/sitemap.xml", timeout=30)
    sitemaps = re.findall(
        r"<loc>(https://playgama\.com/sitemaps/[^<]*sitemap-games-\d+\.xml)</loc>",
        index)
    out = []
    for url in sitemaps:
        try:
            xml = fetch_text(url, timeout=120)
        except (urllib.error.URLError, OSError, ValueError) as exc:
            print(f"  ! playgama sitemap {url.rsplit('/', 1)[-1]}: {exc}",
                  file=sys.stderr)
            continue
        for block in re.findall(r"<url>(.*?)</url>", xml, re.S):
            slug = re.search(r"<loc>https://playgama\.com/game/([^<]+)</loc>",
                             block)
            img = re.search(r"<image:loc>([^<]+)</image:loc>", block)
            if not slug:
                continue
            name = slug.group(1).strip()
            out.append({
                "slug": name,
                "title": re.sub(r"[-_]+", " ", name).strip().title(),
                "embed": f"https://playgama.com/game/{name}",
                "thumbSource": img.group(1) if img else "",
                "categories": [],
                "rating": None,
            })
    return out


def source_retrogames():
    """RetroGames.cc: ~33k console/arcade ROMs.

    The sitemap index points at 33 sitemaps holding one /<system>-games/<slug>.html
    URL each. A game's page embeds `/<system>-games/...` -> an
    `embed/<id>-<slug>.html` frame, but the page is 80KB+, so the id is taken
    from the thumbnail instead (`<...>/<id>_<sha>.png`) and combined with the
    slug from the sitemap URL: `embed/<id>-<slug>.html` renders the game (the
    id alone 404s). The thumbnail is hotlinked; the site serves it with
    `access-control-allow-origin: *` and no referer check.
    """
    index = fetch_text("https://www.retrogames.cc/sitemap.xml", timeout=30)
    sitemaps = re.findall(r"<loc>(https://www\.retrogames\.cc/sitemap/\d+\.xml)</loc>",
                          index)
    by_slug = {}
    for url in sitemaps:
        try:
            xml = fetch_text(url, timeout=120)
        except (urllib.error.URLError, OSError, ValueError) as exc:
            print(f"  ! retrogames sitemap {url.rsplit('/', 1)[-1]}: {exc}",
                  file=sys.stderr)
            continue
        for loc in re.findall(r"<loc>(https://www\.retrogames\.cc/[^<]+\.html)</loc>",
                              xml):
            by_slug[loc] = None

    # The listing pages carry the per-game id in the thumbnail filename, 50 at a
    # time. Walk each system until a page yields nothing new (page 2 of a 60-game
    # system is short, page 3 is the empty index, so stop on the first empty one).
    systems = sorted({urllib.parse.urlsplit(u).path.strip("/").split("/")[0]
                      for u in by_slug})
    id_by_slug, thumb_by_slug = {}, {}
    for system in systems:
        page, seen = 1, set()
        while page <= 200:
            url = (f"https://www.retrogames.cc/{system}/" if page == 1
                   else f"https://www.retrogames.cc/{system}/page/{page}.html")
            try:
                doc = fetch_text(url, timeout=60)
            except (urllib.error.URLError, OSError, ValueError):
                break
            rows = re.findall(
                r'<div[^>]*class="post-thumb[^"]*"[^>]*data-poster="([^"]+)"'
                r'[^>]*>\s*<a href="([^"]+)"[^>]*>.*?alt="([^"]*)"', doc, re.S)
            fresh = 0
            for thumb, href, _alt in rows:
                gid = re.search(r"/(\d+)_", thumb)
                if href in by_slug and gid and href not in seen:
                    id_by_slug[href] = gid.group(1)
                    thumb_by_slug[href] = thumb
                    seen.add(href)
                    fresh += 1
            if fresh == 0:
                break
            page += 1
        if not any(h.startswith(f"https://www.retrogames.cc/{system}/")
                   for h in id_by_slug):
            print(f"  ! retrogames system {system} yielded no ids", file=sys.stderr)

    out = []
    for loc in by_slug:
        gid = id_by_slug.get(loc)
        if not gid:
            continue
        slug = loc.rsplit("/", 1)[-1][:-5]
        out.append({
            "slug": slug,
            "title": re.sub(r"[-_]+", " ", slug).strip().title(),
            "embed": f"https://www.retrogames.cc/embed/{gid}-{slug}.html",
            "thumbSource": thumb_by_slug.get(loc, ""),
            "categories": ["Retro", "Emulator"],
            "rating": None,
        })
    return out


def source_sportsgamesaz():
    """SportsGamesAZ: ~420 sports games, each wrapping a provider embed.

    The sitemap lists every game as a top-level /<slug> URL. Each game's
    `/<slug>.embed` page is a thin wrapper holding the real provider iframe
    (GameDistribution, azgames, footballbros, ...), which is what we embed, and
    `/data/image/game/<slug>.png` is the card art. The wrapper page is
    frameable but the inner provider is the game, so the inner src is used.

    GameDistribution-backed entries are skipped: the site has no GD integration
    and those frames are the ones that rendered blank.
    """
    sitemap = fetch_text("https://sportsgamesaz.io/sitemap.xml", timeout=30)
    non_game = re.compile(r"/(games|tag)/|/(popular-games|hot|new|recent|trending|random)$")
    slugs = []
    for loc in re.findall(r"<loc>([^<]+)</loc>", sitemap):
        if non_game.search(loc):
            continue
        slug = loc.rstrip("/").rsplit("/", 1)[-1]
        if slug and slug not in slugs:
            slugs.append(slug)

    out = []
    for slug in slugs:
        try:
            page = fetch_text(f"https://sportsgamesaz.io/{slug}.embed", timeout=20)
        except (urllib.error.URLError, OSError, ValueError):
            continue
        inner = re.search(r'<iframe[^>]*\ssrc="(https?://[^"]+)"', page)
        if not inner:
            continue
        embed = html.unescape(inner.group(1))
        if "gamedistribution.com" in urllib.parse.urlsplit(embed).netloc:
            continue
        # The wrapper page's <title> is "Play <game> Game Online !" - the real
        # display name, which beats title-casing the slug.
        title = ""
        tm = re.search(r"<title>([^<]+)</title>", page)
        if tm:
            title = re.sub(r"^\s*Play\s+|\s+Game Online\s*!?\s*$", "",
                           html.unescape(tm.group(1))).strip()
        if not title:
            title = re.sub(r"[-_]+", " ", slug).strip().title()
        thumb = ""
        for ext in (".png", ".webp"):
            url = f"https://sportsgamesaz.io/data/image/game/{slug}{ext}"
            if head_ok(url):
                thumb = url
                break
        out.append({
            "slug": slug,
            "title": title,
            "embed": embed,
            "thumbSource": thumb,
            "categories": ["Sports"],
            "rating": None,
            # Attributed to the aggregator the catalogue came from, not the
            # provider host, so the play page's Source row reads "SportsGamesAZ".
            "source": "SportsGamesAZ",
        })
    return out


def source_gameslol():
    """gameslol.net: ~1,800 game pages, each a self-hosted HTML5/Flash/emulator build.

    The sitemap lists /<slug>-<id>.html for every game (plus page-N.html
    listings and the legal/tag pages, which are filtered out). The player is an
    iframe injected by inline script with escaped quotes, so the markup is
    unescaped before the src is read. Gameslol self-hosts most builds under
    /data/, which frames fine; the genre page named by the breadcrumb JSON-LD
    becomes the category.

    Two families are skipped: GameDistribution frames (the site has no GD
    integration and they render blank) and playhop.com (X-Frame-Options
    SAMEORIGIN plus a frame-ancestors policy).
    """
    xml = fetch_text("https://en.gameslol.net/sitemap.xml", timeout=30)
    urls = []
    for loc in re.findall(r"<loc>([^<]+)</loc>", xml):
        if not loc.endswith(".html") or GAMESLOL_NON_GAME.search(loc):
            continue
        urls.append(loc)

    with concurrent.futures.ThreadPoolExecutor(max_workers=WORKERS) as pool:
        pages = list(pool.map(_gameslol_page, urls))
    return [game for game in pages if game]


def _gameslol_page(url):
    try:
        page = fetch_text(url, timeout=25)
    except (urllib.error.URLError, OSError, ValueError) as exc:
        print(f"  ! gameslol {url.rsplit('/', 1)[-1]}: {exc}", file=sys.stderr)
        return None
    # The iframe is written into innerHTML by inline JS, so its quotes and
    # slashes arrive escaped ("<iframe id=\"embed\" src=\"data\/...\">").
    markup = page.replace('\\"', '"').replace('\\/', '/')
    inner = re.search(r'id="embed"\s+src="([^"]+)"', markup)
    if not inner:
        inner = re.search(r'<iframe[^>]*\ssrc="([^"]+)"', markup)
    if not inner:
        return None  # a page without a player is not a game
    src = html.unescape(inner.group(1))
    host = urllib.parse.urlsplit(src).netloc
    if "gamedistribution.com" in host or "playhop.com" in host:
        return None
    if host.startswith("www."):
        host = host[4:]
    if host in GAMESLOL_SKIP_HOSTS:
        return None
    # Relative srcs point at gameslol's own /data/ builds; the page is served
    # over https, so an absolute src keeps the embed on the same host.
    embed = src if src.startswith("http") else "https://en.gameslol.net/" + src.lstrip("/")

    title = ""
    match = re.search(r"<title>([^<]+)</title>", page)
    if match:
        title = re.sub(r"\s*-\s*Play Online.*$", "",
                       html.unescape(match.group(1))).strip()
    slug = re.sub(r"\.html$", "", url.rstrip("/").rsplit("/", 1)[-1])

    genre = re.search(r'"@id":"([^"]+games\.(?:html|php))"', page)
    categories = []
    if genre and genre.group(1) in GAMESLOL_GENRES:
        categories = [GAMESLOL_GENRES[genre.group(1)]]

    thumb = ""
    om = re.search(r'property="og:image"\s+content="([^"]+)"', page)
    if not om:
        om = re.search(r'content="([^"]+)"\s+property="og:image"', page)
    if om:
        thumb = html.unescape(om.group(1))

    # The page publishes a 10-point rating (8/10, 35 ratings) and a short
    # description. The catalogue is on a 5-point scale, so the rating is halved.
    rating = None
    votes = None
    rm = re.search(r'"ratingValue":\s*([\d.]+)', page)
    if rm:
        try:
            rating = round(float(rm.group(1)) / 2, 1)
        except ValueError:
            rating = None
    vm = re.search(r'"ratingCount":\s*(\d+)', page)
    if vm:
        votes = int(vm.group(1))

    desc = ""
    dm = re.search(r'<meta name="description" content="([^"]*)"', page)
    if dm:
        desc = html.unescape(dm.group(1)).strip()

    game = {
        "slug": slug,
        "title": title or re.sub(r"[-_]+", " ", slug).strip().title(),
        "embed": embed,
        "thumbSource": thumb,
        "categories": categories,
        "rating": rating,
    }
    if votes:
        game["votes"] = votes
    if desc:
        game["desc"] = desc
    return game


def source_ucwgp():
    """Ultimate Catalog of Web Game Ports: hand-curated browser ports.

    Carter54git/Ultimate-Catalog-Of-Web-Game-Ports is a README-only list of
    ports (WASM/Unity/Godot/Flash) with demo and repository links. It publishes
    no machine-readable feed and most ports are not on any portal we already
    index, so the resolved list is committed as `data/ucwgp-source.json`
    (`{name, slug, embed, thumb, repo, kind}`) and read here.

    The `embed` is the port's own play page (gn-math.dev for the games that
    portal carries, otherwise the porter's host). `thumb` is a local
    `assets/img/games/<slug>.jpg` produced by tools/fetch-ucwgp-thumbs.py, so
    these entries carry real cover art instead of a hotlinked CDN icon.
    """
    path = os.path.join(ROOT, "data", "ucwgp-source.json")
    try:
        with open(path, encoding="utf-8") as fh:
            entries = json.load(fh)
    except (OSError, ValueError) as exc:
        print(f"  ! ucwgp source: {exc}", file=sys.stderr)
        return []

    games = []
    for entry in entries:
        name = (entry.get("name") or "").strip()
        embed = (entry.get("embed") or "").strip()
        thumb = (entry.get("thumb") or "").strip()
        if not name or not embed or not thumb:
            continue
        games.append({
            "slug": entry.get("slug") or slugify(name),
            "title": name,
            "embed": embed,
            "thumbSource": thumb,
            "categories": [],
            "rating": None,
            "source": "Ultimate Catalog of Web Game Ports",
        })
    return games


SOURCES = [
    # SportsGamesAZ first: its entries are the most curated (real titles, direct
    # provider embeds) and they must win de-duplication over the bulk feeds so
    # games like soccer-bros load their provider directly instead of a
    # CrazyGames frame. gameslol comes next: its self-hosted builds are also
    # better than a bulk feed's generic frame.
    ("sportsgamesaz.io", source_sportsgamesaz),
    ("gameslol.net", source_gameslol),
    # Curated hand-built ports; listed early so their real titles/embeds win
    # de-duplication over the bulk feeds' generic frames.
    ("ucwgp", source_ucwgp),
    ("retrobowl26.com", source_retrobowl26),
    ("iogames.space", source_iogames_space),
    ("iogames.fun", source_iogames_fun),
    ("retrobowlfree.io", source_retrobowlfree),
    ("3kh0-lite", source_3kh0),
    ("gamemonetize", source_gamemonetize),
    ("gamepix", source_gamepix),
    ("playgama", source_playgama),
    ("retrogames.cc", source_retrogames),
]

# Hand-picked games that are not part of any catalogue above. They are added
# first so they always win de-duplication, and their icon is fetched like any
# other.
SPECIAL_GAMES = [
    {
        "slug": "one-tap-fps",
        "title": "One Tap FPS",
        "embed": "https://bloxity.io/g/one-tap",
        "thumbSource": ("https://tr.rbxcdn.com/180DAY-a18207a09f9bb198a153eb40402d169a"
                        "/256/256/Image/Webp/noFilter"),
        "categories": [],
        "rating": None,
    },
    {
        "slug": "sonic-robo-blast-2",
        "title": "Sonic Robo Blast 2",
        "embed": "https://vinmannie.github.io/srb2web/",
        "thumbSource": ("https://srb2wp-data.nyc3.cdn.digitaloceanspaces.com"
                        "/wp-content/uploads/srb2-title.png"),
        "categories": ["Action", "Adventure"],
        "rating": None,
        "source": "SRB2 Web",
    },
]


# ---------------------------------------------------------------- pipeline

def https_embed(url):
    """Our site is https, so http embeds would be blocked as mixed content.

    Only upgrade when the host actually answers over https.
    """
    if url.startswith("https://"):
        return url
    if not url.startswith("http://"):
        return url
    upgraded = "https://" + url[len("http://"):]
    return upgraded if head_ok(upgraded) else url


def optimize(path):
    if Image is None:
        return path
    try:
        with Image.open(path) as img:
            img = img.convert("RGB")
            if img.width > THUMB_WIDTH:
                height = round(img.height * THUMB_WIDTH / img.width)
                img = img.resize((THUMB_WIDTH, height), Image.LANCZOS)
            out = os.path.splitext(path)[0] + ".jpg"
            img.save(out, "JPEG", quality=82, optimize=True, progressive=True)
        if out != path:
            os.remove(path)
        return out
    except (OSError, ValueError):
        return path


def download_thumb(url, slug):
    """Save the icon locally (optimised) and return its site-relative path."""
    if not url:
        return ""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = resp.read()
            content_type = resp.headers.get_content_type()
        if not body:
            return ""
        # Animated gifs would be flattened by the optimiser, so keep them as-is.
        if content_type == "image/gif":
            ext = ".gif"
        else:
            ext = ".jpg" if Image else EXT_BY_TYPE.get(content_type, ".png")
        dest = os.path.join(IMG_DIR, slug + ext)
        with open(dest, "wb") as fh:
            fh.write(body)
        final = optimize(dest) if ext != ".gif" else dest
        return f"assets/img/games/{os.path.basename(final)}"
    except (urllib.error.URLError, OSError) as exc:
        print(f"    ! thumbnail failed for {slug}: {exc}", file=sys.stderr)
        return ""


def dedupe(raw_games):
    """Keep the first entry for each game, by slug, title and embed identity."""
    seen_slugs, seen_titles, seen_embeds = set(), set(), set()
    kept = []
    for game in raw_games:
        if not game["slug"] or not game["embed"]:
            continue
        slug, title_key = game["slug"], norm_title(game["title"])
        ekey = embed_key(game["embed"])
        if slug in seen_slugs or (title_key and title_key in seen_titles) \
                or (ekey and ekey in seen_embeds):
            continue
        seen_slugs.add(slug)
        if title_key:
            seen_titles.add(title_key)
        if ekey:
            seen_embeds.add(ekey)
        kept.append(game)
    return kept


def merge_into_existing(games, path):
    """Fold the freshly built catalogue back over the committed one.

    The feeds carry more than fetch-games.py records: descriptions, keyword tags
    and vote counts are read straight from the source feeds, and the play page
    depends on them. Rebuilding would otherwise drop those fields, so for a game
    that is already in the catalogue the new record wins but any enrichment it
    lacks is carried over. Games are keyed by slug *and* by embed identity, so a
    game that changed slug between runs is matched by its player URL instead of
    being duplicated.
    """
    try:
        with open(path, encoding="utf-8") as fh:
            old = json.load(fh)
    except (OSError, ValueError):
        return games
    by_slug = {g["slug"]: g for g in old}
    by_embed = {embed_key(g["embed"]): g for g in old if g.get("embed")}
    carried = 0
    for game in games:
        prev = by_slug.get(game["slug"]) or by_embed.get(embed_key(game["embed"]))
        if not prev:
            continue
        for field in ("desc", "tags", "votes"):
            if not game.get(field) and prev.get(field):
                game[field] = prev[field]
                carried += 1
    print(f"carried {carried} enrichment fields from the existing catalogue")
    return games


def main():
    if not HOTLINK_THUMBS:
        os.makedirs(IMG_DIR, exist_ok=True)
    os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)

    # `--only <source>` merges a single source into the committed catalogue
    # instead of rebuilding every feed. A full run re-fetches all ~130k entries
    # and can take half an hour, which is overkill for adding one catalogue; the
    # other sources are left exactly as they are.
    only = None
    if "--only" in sys.argv:
        only = sys.argv[sys.argv.index("--only") + 1]
        with open(DATA_FILE, encoding="utf-8") as fh:
            raw = json.load(fh)
        print(f"merging into {len(raw)} existing games")
    else:
        raw = [dict(game) for game in SPECIAL_GAMES]

    for name, fn in SOURCES:
        if only and name != only:
            continue
        print(f"source: {name}")
        try:
            found = fn()
        except (urllib.error.URLError, OSError, ValueError) as exc:
            print(f"  ! source failed: {exc}", file=sys.stderr)
            continue
        print(f"  {len(found)} entries")
        raw.extend(found)

    print(f"collected {len(raw)} raw entries")

    # Feeds publish titles with HTML entities (&amp;, &zwnj;). Unescape once here
    # so the cards, search and de-duplication all see the real title.
    for game in raw:
        game["title"] = html.unescape(game["title"])
        # Strip zero-width marks the feeds sprinkle in; they render as nothing
        # but break search and sorting.
        game["title"] = re.sub(r"[\u200b-\u200f\u2028-\u202f\ufeff]", "", game["title"]).strip()
        # Titles that carried an entity left residue in the slug ("ampzwnj-...").
        # Re-derive those from the clean title; source slugs stay untouched.
        if re.search(r"(?:^|-)(?:amp|zwnj|nbsp|ndash|mdash|quot|lt|gt|apos|hellip|rsquo|lsquo|ldquo|rdquo)(?:-|$)",
                     game["slug"]):
            game["slug"] = slugify(game["title"])

    # Every Retro Bowl release is kept: the user asked for all of them, and on
    # retrobowl26.com each one is a distinct playable build rather than a
    # re-skin of the same embed, so de-duplication will not collapse them.
    games = dedupe(raw)
    print(f"{len(games)} games after de-duplication")

    # Keep the description/tags/votes the committed catalogue already has; the
    # committed builder does not read those from the feeds.
    games = merge_into_existing(games, DATA_FILE)

    if len(games) > MAX_GAMES:
        print(f"capping at {MAX_GAMES} (dropping {len(games) - MAX_GAMES} from the tail)")
        games = games[:MAX_GAMES]

    print("upgrading http embeds to https where possible")
    playable = []
    for game in games:
        # CrazyGames frames are region-blocked for this site's audience, so no
        # game may embed one even if a feed still lists it.
        if "crazygames.com" in urllib.parse.urlsplit(game["embed"]).netloc:
            print(f"  - dropping {game['slug']} (crazygames embed)", file=sys.stderr)
            continue
        game["embed"] = https_embed(game["embed"])
        if game["embed"].startswith("http://"):
            # An http embed would be blocked as mixed content on our https site.
            print(f"  - dropping {game['slug']} (no https embed)", file=sys.stderr)
            continue
        playable.append(game)
    games = playable

    # Games whose source published no genre would otherwise be unreachable from
    # the rail, so fill those in from the title.
    filled = [g for g in games if not g["categories"]]
    for game in filled:
        game["categories"] = classify(game["title"], game["categories"])
    print(f"classified {len(filled)} games that had no categories")
    print("categories:", ", ".join(
        f"{c}={n}" for c, n in collections.Counter(
            c for g in games for c in g["categories"]).most_common()))

    games.sort(key=lambda g: g["title"].lower())

    # Stamp the provider each game came from so the play page can show a
    # "Source:" row. Derived from the final embed host, so it stays correct
    # however the sources are reordered.
    for game in games:
        # A source may name itself (the aggregator it came from); otherwise
        # derive it from the final embed host.
        game["source"] = game.get("source") or source_label(game.get("embed") or "")

    ensure_team(games)

    if HOTLINK_THUMBS:
        # Keep the source CDN URL as the card image. Only http:// icons are
        # upgraded, since an http image would be blocked as mixed content.
        for game in games:
            game["thumb"] = https_embed(game.get("thumbSource") or "")
        print(f"hotlinked {len(games)} thumbnails from source CDNs")
    else:
        print(f"downloading {len(games)} thumbnails")
        done = [0]
        with concurrent.futures.ThreadPoolExecutor(max_workers=WORKERS) as pool:
            futures = {pool.submit(download_thumb, g.pop("thumbSource"), g["slug"]): g
                       for g in games}
            for future in concurrent.futures.as_completed(futures):
                futures[future]["thumb"] = future.result() or ""
                done[0] += 1
                if done[0] % 50 == 0:
                    print(f"  {done[0]}/{len(games)}")

    # A card with no icon looks broken, so games without one are left out.
    without = [g for g in games if not g["thumb"]]
    games = [g for g in games if g["thumb"]]
    if without:
        print(f"dropped {len(without)} games with no icon")

    games.sort(key=lambda g: g["title"].lower())

    with open(DATA_FILE, "w", encoding="utf-8") as fh:
        json.dump(games, fh, indent=2, ensure_ascii=False)
        fh.write("\n")

    print(f"wrote {DATA_FILE} ({len(games)} games, all with thumbnails)")


if __name__ == "__main__":
    main()
