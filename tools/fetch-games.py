#!/usr/bin/env python3
"""Collect game metadata for the Games site.

Reads the public listing pages on iogames.space, which embed a __NEXT_DATA__
JSON payload per page, and writes:

  data/games.json              catalogue (slug, title, thumb, embed, categories, rating)
  assets/img/games/<slug>.<ext> downloaded thumbnail

Usage:  python3 tools/fetch-games.py
"""
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

LISTINGS = [
    "https://iogames.space/popular",
    "https://iogames.space/new",
    "https://iogames.space/featured",
]

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120 Safari/537.36")

EXT_BY_TYPE = {"image/png": ".png", "image/jpeg": ".jpg", "image/webp": ".webp",
               "image/gif": ".gif", "image/svg+xml": ".svg"}

# Cards render around 320px wide, so this covers retina without shipping 1280px
# source art.
THUMB_WIDTH = 480


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    return urllib.request.urlopen(req, timeout=30).read()


def next_data(html):
    m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.S)
    if not m:
        return None
    return json.loads(m.group(1))


def collect_game_lists(obj, out):
    """Gather every list of game-shaped dicts anywhere in the payload."""
    if isinstance(obj, dict):
        for value in obj.values():
            collect_game_lists(value, out)
    elif isinstance(obj, list):
        if obj and isinstance(obj[0], dict) and "embedUrl" in obj[0] and "title" in obj[0]:
            out.append(obj)
        else:
            for value in obj:
                collect_game_lists(value, out)


def slugify(path, title):
    if path:
        slug = path.strip("/").split("/")[-1]
    else:
        slug = re.sub(r"[^a-z0-9]+", "-", (title or "").lower()).strip("-")
    return slug or "game"


def https_embed(url):
    """Our site is https, so http embeds would be blocked as mixed content.

    Only upgrade when the host actually answers over https.
    """
    if url.startswith("https://"):
        return url
    if not url.startswith("http://"):
        return url
    upgraded = "https://" + url[len("http://"):]
    host = urllib.parse.urlsplit(upgraded).netloc
    try:
        urllib.request.urlopen(
            urllib.request.Request(f"https://{host}/", headers={"User-Agent": UA}),
            timeout=15)
        return upgraded
    except urllib.error.HTTPError:
        return upgraded  # answers, just not 200 for "/"
    except (urllib.error.URLError, OSError):
        return url


def optimize(path):
    if Image is None:
        return
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
    """Save the thumbnail locally (optimised) and return its site-relative path."""
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
        name = slug + ext
        dest = os.path.join(IMG_DIR, name)
        with open(dest, "wb") as fh:
            fh.write(body)
        final = optimize(dest) if ext != ".gif" else dest
        return f"assets/img/games/{os.path.basename(final)}"
    except (urllib.error.URLError, OSError) as exc:
        print(f"    ! thumbnail failed for {slug}: {exc}", file=sys.stderr)
        return ""


def main():
    os.makedirs(IMG_DIR, exist_ok=True)
    os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)

    seen = {}
    for listing in LISTINGS:
        print(f"listing {listing}")
        try:
            html = fetch(listing).decode("utf-8", "ignore")
        except (urllib.error.URLError, OSError) as exc:
            print(f"  ! skipped: {exc}", file=sys.stderr)
            continue

        payload = next_data(html)
        if not payload:
            print("  ! no __NEXT_DATA__ found", file=sys.stderr)
            continue

        lists = []
        collect_game_lists(payload, lists)
        for group in lists:
            for game in group:
                title = (game.get("title") or "").strip()
                embed = (game.get("embedUrl") or "").strip()
                if not title or not embed:
                    continue
                slug = slugify(game.get("path"), title)
                if slug in seen:
                    continue
                seen[slug] = {
                    "slug": slug,
                    "title": title,
                    "thumb": "",
                    "thumbSource": game.get("thumbnailUrl") or "",
                    "embed": embed,
                    "categories": [c.get("name") for c in (game.get("categories") or [])
                                   if c.get("name")],
                    "rating": game.get("displayRating") or game.get("ratingAverage") or None,
                }
        print(f"  running total: {len(seen)}")

    games = sorted(seen.values(), key=lambda g: g["title"].lower())

    print(f"downloading {len(games)} thumbnails")
    for i, game in enumerate(games, 1):
        game["thumb"] = download_thumb(game["thumbSource"], game["slug"])
        if i % 20 == 0:
            print(f"  {i}/{len(games)}")
        time.sleep(0.05)

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

    for game in games:
        game.pop("thumbSource", None)

    with open(DATA_FILE, "w", encoding="utf-8") as fh:
        json.dump(games, fh, indent=2, ensure_ascii=False)
        fh.write("\n")

    with_thumb = sum(1 for g in games if g["thumb"])
    insecure = sum(1 for g in games if g["embed"].startswith("http://"))
    print(f"wrote {DATA_FILE} ({len(games)} games, {with_thumb} with thumbnails, "
          f"{insecure} still http)")


if __name__ == "__main__":
    main()

