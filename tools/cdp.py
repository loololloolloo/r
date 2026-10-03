#!/usr/bin/env python3
"""Tiny Chrome DevTools Protocol harness for tools/verify.py.

Launches a headless Chromium, loads a URL, evaluates a snippet of JavaScript in
the page and returns its (JSON) value. Optionally writes a screenshot.

    python3 tools/cdp.py <url> "<js>" [--port N] [--wait S]

Only needs `websocket-client` (pip install websocket-client) and a chromium
binary. Keeping this in the repo means verification does not depend on a
harness that happens to live in /tmp.
"""
import json
import os
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request

import websocket

CHROME_CANDIDATES = (
    "chromium", "chromium-browser", "google-chrome", "google-chrome-stable",
)


def _chrome():
    for name in CHROME_CANDIDATES:
        path = shutil.which(name)
        if path:
            return path
    raise RuntimeError("no chromium/chrome binary found")


def _free_port(preferred):
    """Use the requested debug port, or any free one if it is taken."""
    with socket.socket() as s:
        try:
            s.bind(("127.0.0.1", preferred))
            return preferred
        except OSError:
            pass
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class _Browser:
    def __init__(self, width, height):
        self.proc = None
        self.profile = tempfile.mkdtemp(prefix="cdp-profile-")
        self.port = _free_port(9222)
        args = [
            _chrome(),
            "--headless=new",
            "--disable-gpu",
            "--no-sandbox",
            "--disable-dev-shm-usage",
            "--hide-scrollbars",
            "--mute-audio",
            "--no-first-run",
            "--no-default-browser-check",
            f"--user-data-dir={self.profile}",
            f"--remote-debugging-port={self.port}",
            "--remote-allow-origins=*",
            f"--window-size={width},{height}",
            "about:blank",
        ]
        self.proc = subprocess.Popen(
            args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            preexec_fn=os.setsid)
        self._wait_ready()

    def _wait_ready(self, timeout=30):
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                with urllib.request.urlopen(
                        f"http://127.0.0.1:{self.port}/json/version", timeout=1):
                    return
            except OSError:
                time.sleep(0.2)
        raise RuntimeError("chromium debug port never came up")

    def target(self):
        with urllib.request.urlopen(
                f"http://127.0.0.1:{self.port}/json/list", timeout=5) as resp:
            for t in json.load(resp):
                if t.get("type") == "page":
                    return t["webSocketDebuggerUrl"]
        raise RuntimeError("no page target")

    def close(self):
        if self.proc and self.proc.poll() is None:
            try:
                os.killpg(os.getpgid(self.proc.pid), signal.SIGTERM)
                self.proc.wait(timeout=5)
            except (OSError, subprocess.TimeoutExpired):
                try:
                    os.killpg(os.getpgid(self.proc.pid), signal.SIGKILL)
                except OSError:
                    pass
        shutil.rmtree(self.profile, ignore_errors=True)


class _Session:
    def __init__(self, ws_url):
        self.ws = websocket.create_connection(ws_url, timeout=60)
        self.next_id = 0

    def call(self, method, **params):
        self.next_id += 1
        mid = self.next_id
        self.ws.send(json.dumps({"id": mid, "method": method, "params": params}))
        while True:
            msg = json.loads(self.ws.recv())
            if msg.get("id") == mid:
                if "error" in msg:
                    raise RuntimeError(f"{method}: {msg['error']}")
                return msg.get("result", {})

    def close(self):
        try:
            self.ws.close()
        except Exception:
            pass


def run(url, js, port=9299, wait=8, shot=None, width=1430, height=1400):
    """Load url, evaluate js, return its value (or {} when the js returns null)."""
    browser = _Browser(width, height)
    try:
        session = _Session(browser.target())
        try:
            session.call("Page.enable")
            session.call("Runtime.enable")
            session.call("Page.navigate", url=url)
            time.sleep(wait)
            result = session.call(
                "Runtime.evaluate", expression=js, returnByValue=True,
                awaitPromise=True)
            if shot:
                png = session.call("Page.captureScreenshot")["data"]
                import base64
                with open(shot, "wb") as fh:
                    fh.write(base64.b64decode(png))
            value = result.get("result", {}).get("value")
            return value if value is not None else {}
        finally:
            session.close()
    finally:
        browser.close()


def run_seq(steps, port=9299, wait=7, width=1430, height=1400):
    """Visit several URLs in one browser (so localStorage persists), evaluating
    each step's [url, js] after its load. Returns the last step's value."""
    browser = _Browser(width, height)
    try:
        session = _Session(browser.target())
        try:
            session.call("Page.enable")
            session.call("Runtime.enable")
            value = None
            for url, js in steps:
                session.call("Page.navigate", url=url)
                time.sleep(wait)
                if js:
                    result = session.call("Runtime.evaluate", expression=js,
                                          returnByValue=True, awaitPromise=True)
                    value = result.get("result", {}).get("value")
            return value if value is not None else {}
        finally:
            session.close()
    finally:
        browser.close()


def failed_requests(url, port=9299, wait=8, width=1430, height=1400):
    """Load url and return [(status, url), ...] for every response >= 400."""
    browser = _Browser(width, height)
    try:
        session = _Session(browser.target())
        try:
            session.call("Network.enable")
            session.call("Page.enable")
            session.call("Page.navigate", url=url)
            failed = []
            deadline = time.time() + wait
            session.ws.settimeout(0.5)
            while time.time() < deadline:
                try:
                    msg = json.loads(session.ws.recv())
                except Exception:
                    continue
                if msg.get("method") == "Network.responseReceived":
                    resp = msg["params"]["response"]
                    if resp.get("status", 0) >= 400:
                        failed.append((resp["status"], resp["url"]))
            session.ws.settimeout(60)
            return failed
        finally:
            session.close()
    finally:
        browser.close()


def main():
    url = sys.argv[1]
    js = sys.argv[2]
    opts = dict(zip(sys.argv[3::2], sys.argv[4::2]))
    print(json.dumps(run(
        url, js,
        port=int(opts.get("--port", 9299)),
        wait=float(opts.get("--wait", 8)),
        shot=opts.get("--shot"),
        width=int(opts.get("--width", 1430)),
        height=int(opts.get("--height", 1400)),
    ), indent=1))


if __name__ == "__main__":
    main()
