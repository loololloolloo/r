#!/usr/bin/env python3
"""Collect game metadata for the Games site.

Pulls from several public catalogues, de-duplicates across them, downloads and
optimises each icon, and writes:

  data/games.json               catalogue (slug, title, thumb, embed, categories, rating)
  assets/img/games/<slug>.jpg   downloaded icon

Usage:  python3 tools/fetch-games.py

Sources are tried in order and the first one to claim a game wins, so the more
authoritative catalogues should come first. De-duplication is by slug, by
normalised title, and by embed host+path, so the same game listed on two sites
only appears once.
"""
import concurrent.futures
import json
import os
import re
import sys
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

# Upper bound on the catalogue. Every game costs a thumbnail download, so the
# cap keeps a full rebuild bounded; the highest-priority sources are first in
# the raw list, so trimming the tail drops the least wanted games.
MAX_GAMES = 1200

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


def source_gamemonetize():
    """GameMonetize's public feed is a JSON catalogue of html5 games.

    The feed serves at most MAX_FEED entries; asking for more simply truncates,
    so this pulls a large slice and lets the global cap do the trimming.
    """
    url = "https://gamemonetize.com/feed.php?format=0&num=5000"
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


SOURCES = [
    ("retrobowl26.com", source_retrobowl26),
    ("iogames.space", source_iogames_space),
    ("iogames.fun", source_iogames_fun),
    ("retrobowlfree.io", source_retrobowlfree),
    ("3kh0-lite", source_3kh0),
    ("gamemonetize", source_gamemonetize),
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


def main():
    os.makedirs(IMG_DIR, exist_ok=True)
    os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)

    raw = [dict(game) for game in SPECIAL_GAMES]
    for name, fn in SOURCES:
        print(f"source: {name}")
        try:
            found = fn()
        except (urllib.error.URLError, OSError, ValueError) as exc:
            print(f"  ! source failed: {exc}", file=sys.stderr)
            continue
        print(f"  {len(found)} entries")
        raw.extend(found)

    print(f"collected {len(raw)} raw entries")

    # Every Retro Bowl release is kept: the user asked for all of them, and on
    # retrobowl26.com each one is a distinct playable build rather than a
    # re-skin of the same embed, so de-duplication will not collapse them.
    games = dedupe(raw)
    print(f"{len(games)} games after de-duplication")

    if len(games) > MAX_GAMES:
        print(f"capping at {MAX_GAMES} (dropping {len(games) - MAX_GAMES} from the tail)")
        games = games[:MAX_GAMES]

    print("upgrading http embeds to https where possible")
    playable = []
    for game in games:
        game["embed"] = https_embed(game["embed"])
        if game["embed"].startswith("http://"):
            # An http embed would be blocked as mixed content on our https site.
            print(f"  - dropping {game['slug']} (no https embed)", file=sys.stderr)
            continue
        playable.append(game)
    games = playable

    games.sort(key=lambda g: g["title"].lower())

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
