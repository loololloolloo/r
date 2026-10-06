#!/usr/bin/env python3
"""Mirror thumbnails for the Ultimate Catalog of Web Game Ports source.

`data/ucwgp-source.json` is the committed game list harvested from
Carter54git/Ultimate-Catalog-Of-Web-Game-Ports. Thumbnails are produced locally
because the catalogue has no single cover CDN:

  * games carried by gn-math.dev use that portal's own cover art;
  * everything else is screenshotted from the game's play page with headless
    Chromium, so the card shows the game itself rather than a stock photo.

Both are written to `assets/img/games/<slug>.jpg` and the source file's `thumb`
field is rewritten to the local path, which `source_ucwgp()` hands to the
builder as `thumbSource`.

Usage:  python3 tools/fetch-ucwgp-thumbs.py [--force]
"""
import concurrent.futures
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

try:
    from PIL import Image
except ImportError:
    sys.exit("Pillow is required: pip install Pillow")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SOURCE_FILE = os.path.join(ROOT, "data", "ucwgp-source.json")
IMG_DIR = os.path.join(ROOT, "assets", "img", "games")
THUMB_WIDTH = 480
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120 Safari/537.36")

CHROME_CANDIDATES = ("chromium", "chromium-browser", "google-chrome",
                     "google-chrome-stable")


def chrome():
    for name in CHROME_CANDIDATES:
        path = shutil.which(name)
        if path:
            return path
    return None


def save_jpeg(path, image):
    image = image.convert("RGB")
    if image.width > THUMB_WIDTH:
        image = image.resize((THUMB_WIDTH, round(image.height * THUMB_WIDTH / image.width)),
                             Image.LANCZOS)
    image.save(path, "JPEG", quality=82, optimize=True, progressive=True)


def is_blank(path):
    """A screenshot of a failed load is a single flat colour; reject those."""
    try:
        with Image.open(path) as img:
            grey = img.convert("L").resize((32, 32))
            lo, hi = grey.getextrema()
            return hi - lo < 12
    except OSError:
        return True


def fetch_cover(url, slug):
    dest = os.path.join(IMG_DIR, slug + ".jpg")
    tmp = dest + ".png"
    try:
        r = subprocess.run(["curl", "-s", "-m", "30", "-L", "-A", UA, "-o", tmp, url],
                           timeout=35)
        if r.returncode != 0 or not os.path.exists(tmp) or os.path.getsize(tmp) < 2000:
            return None
        with Image.open(tmp) as img:
            save_jpeg(dest, img)
        return dest
    except (OSError, ValueError):
        return None
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)


def screenshot(embed, slug):
    binary = chrome()
    if not binary:
        return None
    dest = os.path.join(IMG_DIR, slug + ".jpg")
    tmp = dest + ".png"
    profile = tempfile.mkdtemp(prefix="cg-shot-")
    try:
        subprocess.run(
            [binary, "--headless", "--no-sandbox", "--disable-gpu",
             "--enable-unsafe-swiftshader", "--use-gl=angle",
             "--use-angle=swiftshader", "--hide-scrollbars", "--mute-audio",
             "--no-first-run", "--window-size=480,300",
             "--virtual-time-budget=20000",
             f"--user-data-dir={profile}", f"--screenshot={tmp}", embed],
            capture_output=True, timeout=75)
        if not os.path.exists(tmp) or os.path.getsize(tmp) < 2000 or is_blank(tmp):
            return None
        with Image.open(tmp) as img:
            save_jpeg(dest, img)
        return dest
    except (subprocess.TimeoutExpired, OSError, ValueError):
        return None
    finally:
        shutil.rmtree(profile, ignore_errors=True)
        if os.path.exists(tmp):
            os.remove(tmp)


def main():
    force = "--force" in sys.argv
    os.makedirs(IMG_DIR, exist_ok=True)
    games = json.load(open(SOURCE_FILE, encoding="utf-8"))

    todo = []
    for game in games:
        local = game.get("thumb") or ""
        if local.startswith("assets/img/games/") and os.path.exists(os.path.join(ROOT, local)):
            if not force:
                continue
        todo.append(game)
    print(f"{len(todo)} of {len(games)} games need a thumbnail")

    def build(game):
        slug = game["slug"]
        remote = game.get("thumb") or ""
        if remote.startswith("http") and "gn-math.dev" in remote:
            got = fetch_cover(remote, slug)
            how = "cover"
        else:
            got = None
            how = "shot"
        if not got:
            got = screenshot(game["embed"], slug)
            how = "shot" if got else "miss"
        return game, got, how

    done = {"cover": 0, "shot": 0, "miss": 0}
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        for game, got, how in pool.map(build, todo):
            done[how] += 1
            if got:
                game["thumb"] = os.path.relpath(got, ROOT).replace(os.sep, "/")
            else:
                game["thumb"] = ""
                print(f"  ! no thumbnail: {game['name']}", file=sys.stderr)
            if sum(done.values()) % 25 == 0:
                print(f"  {sum(done.values())}/{len(todo)}")

    json.dump(games, open(SOURCE_FILE, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    missing = [g["name"] for g in games if not g.get("thumb")]
    print(f"covers={done['cover']} shots={done['shot']} missing={done['miss']}")
    print(f"wrote {SOURCE_FILE}")
    if missing:
        print("missing:", ", ".join(missing))


if __name__ == "__main__":
    main()
