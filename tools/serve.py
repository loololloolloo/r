"""Static server that mimics GitHub Pages' extensionless URL mapping
(/ -> index.html, /play -> play.html, /about -> about.html)."""
import http.server, os, sys

ROOT = sys.argv[1] if len(sys.argv) > 1 else "."
PORT = int(sys.argv[2]) if len(sys.argv) > 2 else 12000
# Bind all interfaces so the port-forward proxy (which connects from outside the
# container) can reach it. 127.0.0.1 alone makes the forwarded URL return 502.
HOST = sys.argv[3] if len(sys.argv) > 3 else "0.0.0.0"


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **k):
        super().__init__(*a, directory=ROOT, **k)

    def translate_path(self, path):
        full = super().translate_path(path)
        if os.path.exists(full):
            return full
        if not os.path.splitext(full)[1] and os.path.exists(full + ".html"):
            return full + ".html"
        # Game pages live at the site root (/<slug>); GitHub Pages resolves an
        # unknown path to 404.html, so mimic that for the flat-slug routes.
        if not os.path.splitext(full)[1] and os.path.exists(
                os.path.join(ROOT, "404.html")):
            return os.path.join(ROOT, "404.html")
        return full

    def log_message(self, *a):
        pass


http.server.ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()
