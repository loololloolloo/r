#!/usr/bin/env python3
"""Localise the archived CrazyGames 2026 home-page styling.

The 2026 portal is a Next.js app. Its home page is a stack of carousels and
grids whose look lives in a 1MB emotion bundle. We only want the *home content*
— the nav/sidebar stay ours — so this script keeps just the rules for the home
components and rewrites every asset URL to a relative local path.

Output:
  assets/cg2026/home.css          filtered, URL-rewritten stylesheet
  assets/cg2026/fonts/*.woff2     Nunito weights the stylesheet needs
  assets/cg2026/icons/*.svg       icon masks (hot/new/originals/…)

Usage:  python3 tools/fetch-2026.py [--force]
"""
import concurrent.futures as futures
import os
import re
import sys
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "assets", "cg2026")
CACHE = os.path.join(ROOT, ".cache", "cg2026")
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/148 Safari/537.36"}

CSS_BASE = "https://builds.crazygames.com/portal-web/_next/static/css/"
# The portal ships its emotion CSS in many content-hashed chunks; the home and
# game pages pull different sets. We fetch both so one theme covers the site.
CSS_FILES = [
    # home page set
    "789024bb7f0612ce", "afe72c6734863da3", "cbb7209652c8dd7e", "b8ee59741b3042d3",
    "007c4fc47700a588", "e59d3f24e1615bfc", "5353b622f8ad5f13", "031e1778ec9c348e",
    "32da7329c8d9f54f", "547ea8437d44347f", "abc7c0e61ac42678", "614e687fbe00b148",
    "986c924fc2920fed",
    # game page set
    "e9348d93f5388955", "5b78b1a863e9910a", "8c1ab040a3b4e1d1", "6e72f0ae5fbb924b",
    "26370454787e2208", "2db747fd5582ef01", "a635e38897426270", "680d805aecf46e35",
    "9b6da900b6e9c0fa", "15852e0673a20e15",
]

# Class-name prefixes of the shell, home content and game page. Rules whose
# selector mentions any of these (or the generic tokens below) are kept;
# everything else is ad/onboarding chrome we render ourselves.
KEEP_PREFIXES = (
    # shell chrome
    "Layout_", "Header_", "HeaderSidebarButton_", "Sidebar_", "TopSearch_",
    "QuickSearchIcon_", "LogoImage_", "UserPortalIcons_", "Button_", "IconButton_",
    "CrazyModal_", "SocialButton_", "Spinner_", "Icon_",
    # home content
    "HomePage_", "CrazyCarousel_", "CarouselSectionTitle_", "CarouselRichHeader_",
    "RecommendedCarouselTitle_", "GameThumbDesktop_", "GameThumbShared_",
    "GameThumbLabel_", "GameGrid_", "LazyCarouselsSection_", "LeaderboardsCarousel_",
    "LeaderboardCountdown_", "IntentCarousel_", "SEOCategoriesBlock_",
    "TopPromotionalRecentBanner_", "LoaderBullets_",
    # game page
    "GamePageDesktop_", "GameContainerDesktop_", "GameInfo_", "GameSummary_",
    "GameTags_", "TagGrid_", "Breadcrumbs_",
)
KEEP_TOKENS = (".crazy-carousel", ".skeleton", "GameThumb", "Carousel")

# The left rail uses its own mono icon set, served from imgs.crazygames.com
# rather than the mask icons above. Capitalised names, so they do not clash
# with the lowercase theme icons.
SIDEBAR_ICON_BASE = "https://imgs.crazygames.com/icon/mono-sidebar-icons-2/"
SIDEBAR_ICONS = [
    "Home", "Recent", "New", "Trending", "Updated", "Originals", "Multiplayer",
    "Leaderboards", "Action", "Adventure", "Casual", "Board", "Card", "Clicker",
    "Driving", "io", "Puzzle", "Shooting", "Sports", "Strategy", "Trivia",
    "Word", "Tags",
]


def get(url, timeout=90):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def load_bundle(force):
    os.makedirs(CACHE, exist_ok=True)
    path = os.path.join(CACHE, "bundle.css")
    if os.path.exists(path) and not force:
        return open(path, encoding="utf-8").read()
    chunks = []
    for name in CSS_FILES:
        chunks.append(f"/* === {name} === */\n"
                      + get(CSS_BASE + name + ".css").decode("utf-8", "replace"))
    css = "\n".join(chunks)
    open(path, "w", encoding="utf-8").write(css)
    return css


def split_rules(css):
    """Split a stylesheet into top-level rules (depth-aware, so @media blocks
    stay whole)."""
    rules, depth, buf = [], 0, []
    for ch in css:
        buf.append(ch)
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                rules.append("".join(buf).strip())
                buf = []
    if buf:
        rules.append("".join(buf).strip())
    return rules


def wanted(rule):
    sel = rule.split("{", 1)[0]
    if rule.startswith("@font-face") or rule.startswith("@keyframes"):
        return True
    if sel.startswith(":root") or sel.startswith("html") or sel.startswith("*") \
            or sel.startswith("body"):
        return True
    return any(p in sel for p in KEEP_PREFIXES) or any(t in sel for t in KEEP_TOKENS)


def filter_css(css):
    """Keep home-content rules, recursing into @media so hover/responsive
    variants survive while the nav/modal/ad rules around them do not."""
    out = []
    for rule in split_rules(css):
        if rule.startswith("@media"):
            inner = rule.split("{", 1)[1]
            inner = inner[:inner.rfind("}")]
            kept = filter_css(inner)
            if kept:
                out.append(rule.split("{", 1)[0] + "{" + kept + "}")
        elif wanted(rule):
            out.append(rule)
    return "\n".join(out)


def local_name(url):
    path = url.split("?", 1)[0]
    base = os.path.basename(path)
    if path.endswith(".woff2"):
        return "fonts/" + base
    if "/SVG/icons/" in path:
        return "icons/" + base
    if "/mono-sidebar-icons-2/" in path:
        return "icons/" + base
    return "media/" + base


def download(url, dest, force):
    full = os.path.join(OUT, dest)
    if os.path.exists(full) and not force:
        return
    os.makedirs(os.path.dirname(full), exist_ok=True)
    try:
        open(full, "wb").write(get(url))
    except Exception as e:
        print("  fail", url[-60:], e)


def main():
    force = "--force" in sys.argv
    os.makedirs(OUT, exist_ok=True)
    bundle = load_bundle(force)

    all_rules = split_rules(bundle)
    css = filter_css(bundle)
    print("rules kept: %d / %d" % (len(split_rules(css)), len(all_rules)))

    urls = set(re.findall(r"url\(\s*['\"]?(https?://[^)'\"]+)['\"]?\s*\)", css))
    print("assets referenced:", len(urls))

    mapping = {u: local_name(u) for u in urls}
    for name in SIDEBAR_ICONS:
        u = SIDEBAR_ICON_BASE + name + ".svg"
        mapping[u] = "icons/" + name + ".svg"
    with futures.ThreadPoolExecutor(max_workers=16) as ex:
        for j in [ex.submit(download, u, d, force) for u, d in mapping.items()]:
            j.result()
    for url, dest in mapping.items():
        css = css.replace("url(" + url + ")", "url(" + dest + ")")
        css = css.replace('url("' + url + '")', 'url("' + dest + '")')
        css = css.replace("url('" + url + "')", "url('" + dest + "')")
    css = re.sub(r"url\(\s*['\"]?https://[^)'\"]+['\"]?\s*\)", "none", css)

    open(os.path.join(OUT, "theme.css"), "w", encoding="utf-8").write(css)
    print("theme.css bytes:", len(css))
    counts = {}
    for dest in mapping.values():
        counts[dest.split("/", 1)[0]] = counts.get(dest.split("/", 1)[0], 0) + 1
    print("downloaded:", counts)


if __name__ == "__main__":
    main()
