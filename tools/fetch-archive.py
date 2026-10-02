#!/usr/bin/env python3
"""Fetch the static assets the archived CrazyGames 2024 shell needs.

The site reuses CrazyGames' 2024 CSS/layout (see tools/build-archive.py) but with
our own branding and catalogue. Everything that shell references must be served
locally, so this script downloads:

  assets/cg/archive.css          the 2024 stylesheet (emotion output), rewritten
  assets/cg/sprite.svg           <symbol> defs (new-label, etc.)
  assets/cg/bg.jpg               the repeating page background
  assets/cg/fonts/nunito-*.woff* Nunito weights used by the stylesheet

Usage:  python3 tools/fetch-archive.py [--force]
"""
import os
import re
import sys
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "assets", "cg")
CACHE = os.path.join(ROOT, ".cache")
ARCHIVE = "https://web.archive.org/web/20240701162028id_/https://www.crazygames.com/"
GAME = "https://web.archive.org/web/20240721165449id_/https://www.crazygames.com/game/2048"

UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/126 Safari/537.36"}


def get(url, timeout=90):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def fetch_page(url, name):
    os.makedirs(CACHE, exist_ok=True)
    path = os.path.join(CACHE, name + ".html")
    if os.path.exists(path) and "--force" not in sys.argv:
        return open(path, encoding="utf-8", errors="replace").read()
    html = get(url).decode("utf-8", "replace")
    open(path, "w", encoding="utf-8").write(html)
    return html


def strip_scripts(html):
    html = re.sub(r"<script\b[^>]*>.*?</script>", "", html, flags=re.S)
    html = re.sub(r"<script\b[^>]*/>", "", html)
    html = re.sub(r"<!-- BEGIN WAYBACK TOOLBAR INSERT -->.*?"
                  r"<!-- END WAYBACK TOOLBAR INSERT -->", "", html, flags=re.S)
    return html


def main():
    os.makedirs(OUT, exist_ok=True)
    os.makedirs(os.path.join(OUT, "fonts"), exist_ok=True)

    home = strip_scripts(fetch_page(ARCHIVE, "home"))
    play = strip_scripts(fetch_page(GAME, "play"))

    # --- stylesheet: concatenate every inline <style> the shell ships ---------
    css = "\n".join(re.findall(r"<style[^>]*>(.*?)</style>", home, re.S))
    css += "\n" + "\n".join(re.findall(r"<style[^>]*>(.*?)</style>", play, re.S))

    # --- fonts: pull every gstatic URL the stylesheet references --------------
    fonts = sorted(set(re.findall(
        r"https://fonts\.gstatic\.com/[^)\"'\s]+\.(?:woff2?|ttf)", css)))
    for url in fonts:
        fname = "nunito-" + re.sub(r"[^a-zA-Z0-9]", "", url.rsplit("/", 1)[-1])
        dest = os.path.join(OUT, "fonts", fname)
        if not os.path.exists(dest) or "--force" in sys.argv:
            try:
                open(dest, "wb").write(get(url))
            except Exception as e:
                print("  font fail", url[-40:], e)
                continue
        css = css.replace(url, "assets/cg/fonts/" + fname)
    print("fonts:", len(fonts))

    # --- background image -----------------------------------------------------
    bg = os.path.join(OUT, "bg.jpg")
    if not os.path.exists(bg) or "--force" in sys.argv:
        try:
            open(bg, "wb").write(get("https://web.archive.org/web/2024id_/"
                                     "https://www.crazygames.com/images/background2.jpg"))
        except Exception as e:
            print("  bg fail:", e)
    css = css.replace("url(/images/background2.jpg)", "url(assets/cg/bg.jpg)")

    # --- sprite: every <svg><use href="#id"> referenced by markup -------------
    sprite_ids = sorted(set(re.findall(r'<use href="#([a-zA-Z0-9_-]+)"', home + play)))
    defs = []
    for sid in sprite_ids:
        m = re.search(r'<symbol[^>]*id="%s".*?</symbol>' % re.escape(sid),
                      home + play, re.S)
        if not m:
            m = re.search(r'<svg[^>]*id="%s".*?</svg>' % re.escape(sid),
                          home + play, re.S)
        if m:
            defs.append(m.group(0))
    sprite = ('<svg xmlns="http://www.w3.org/2000/svg" '
              'xmlns:xlink="http://www.w3.org/1999/xlink" style="display:none">'
              + "".join(defs) + "</svg>")
    open(os.path.join(OUT, "sprite.svg"), "w", encoding="utf-8").write(sprite)
    print("sprite symbols:", len(defs), sprite_ids)

    open(os.path.join(OUT, "archive.css"), "w", encoding="utf-8").write(css)
    print("css bytes:", len(css))


if __name__ == "__main__":
    main()
