# Games

Static games website ("Games"). No build step, no framework, no npm.
Hosted on GitHub Pages, so every asset must be relative-path and static.

- Repo: `loololloolloo/r` (default branch `main`). Also has an empty `games` branch.
- Work happens in `/workspace/r` (the clone). `/workspace/project` is a scratch dir.
- Brand: name is "Games"; navbar uses `assets/img/logo.png` (Amazon Games logo,
  transparent PNG, pre-cropped) instead of text. Note it is a third-party trademark.
  Always keep explicit `width`/`height` on the `<img>`: the source is 384x184, so
  without them a stale or missing stylesheet makes it render at natural size and
  blows the navbar up. Favicon is `assets/img/favicon.png`, generated from the logo.

## Conventions
- Styling: Bootstrap 5.3.3 via CDN, dark theme (`<html data-bs-theme="dark">`).
- No accent color — stick to Bootstrap dark palette + its default blue `#0d6efd`.
- Layout: two vertical sidebars flanking the content — left = primary nav, right = secondary panel.
- Icons: local SVG sprite at `assets/svg/svg-map.svg`, sourced from onlinegames.io
  (`assets/svg/svg-map.svg` + inline page SVGs: menu, menu-mobile, close, youtube-round).
  Category nav icons use Bootstrap Icons (onlinegames.io itself has no per-category icons;
  its own arrow icons are Bootstrap Icons too).
- All paths relative (GitHub Pages serves from a subpath).

## Dev
- Local serve: `python3 -m http.server 12000 --bind 0.0.0.0` from repo root.
- Forwarded preview: https://work-1-rddqiwdridmxqtos.prod-runtime.all-hands.dev/ (port 12000)
- Layout: one left sidebar for primary nav (`<aside id="sidebarLeft">`), flanked by a
  top navbar holding brand, quick links, search and back-to-top. The right sidebar and
  the social row were removed by request. On <lg the sidebar becomes a Bootstrap
  offcanvas panel toggled from the navbar.
- Below xl the top navbar is a dropdown panel, NOT Bootstrap's Collapse. The panel
  is `position: absolute; top: 100%` and animates open/closed via the `.rg-open`
  class (opacity + translateY, 0.22s). Bootstrap's Collapse animates height, which
  cannot combine with an absolutely-positioned overlay and left the panel stuck
  open; an inline collapse also grows the header to ~316px and shoves the page
  down. `main.js` toggles `.rg-open` and closes on link choice, outside click, or
  Escape, all guarded to `max-width: 1199.98px`. Motion respects
  `prefers-reduced-motion`.
- `--rg-header-h` is written by `main.js` (ResizeObserver on the header) and read by the
  sidebar's sticky offset. Never size the header itself from that variable — it creates a
  feedback loop (border adds 1px per frame and the navbar grows forever). Header
  `min-height` must stay a literal.

## Deploy
- GitHub Pages serves from the **`games`** branch, path `/` — NOT `main`.
  Pushing to `main` alone will not update the live site.
- Custom domain: `games.gazeee.xyz` (CNAME file at repo root, content `games.gazeee.xyz`).
  Needs a DNS record: `CNAME games -> loololloolloo.github.io`.
- Both `main` and `games` are kept in sync at the same commit.

## Roadmap
- Phase 1 (done): dark shell, left sidebar + top navbar, icons, port-forward preview.
- Phase 2: hub page with game cards (replace placeholder card in `index.html`).
- Phase 3: games (one self-registering JS module each) + shared game shell.
