"""Minimal headless-Chromium driver over the DevTools Protocol. Standard library only.

Finds Chrome, Edge or Chromium, launches it headless with a throwaway profile, and talks
CDP over a hand-rolled WebSocket. Used by capture.py and render.py.
"""
import base64
import json
import os
import shutil
import socket
import struct
import subprocess
import sys
import tempfile
import time
import urllib.request
from urllib.parse import urlparse

CANDIDATES = {
    "win32": [
        r"%ProgramFiles%\Google\Chrome\Application\chrome.exe",
        r"%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe",
        r"%LocalAppData%\Google\Chrome\Application\chrome.exe",
        r"%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe",
        r"%ProgramFiles%\Microsoft\Edge\Application\msedge.exe",
    ],
    "darwin": [
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
        "/Applications/Chromium.app/Contents/MacOS/Chromium",
    ],
    "linux": ["google-chrome", "google-chrome-stable", "chromium", "chromium-browser",
              "microsoft-edge", "microsoft-edge-stable"],
}


def find_browser():
    env = os.environ.get("BRANDKIT_BROWSER")
    if env:
        return env
    plat = "win32" if sys.platform.startswith("win") else ("darwin" if sys.platform == "darwin" else "linux")
    for c in CANDIDATES[plat]:
        p = os.path.expandvars(c)
        if os.path.isfile(p):
            return p
        found = shutil.which(p)
        if found:
            return found
    raise SystemExit("No Chromium browser found. Install Chrome/Edge/Chromium or set BRANDKIT_BROWSER.")


class WebSocket:
    def __init__(self, url):
        u = urlparse(url)
        self.sock = socket.create_connection((u.hostname, u.port), timeout=60)
        key = base64.b64encode(os.urandom(16)).decode()
        req = (f"GET {u.path} HTTP/1.1\r\nHost: {u.hostname}:{u.port}\r\nUpgrade: websocket\r\n"
               f"Connection: Upgrade\r\nSec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n")
        self.sock.sendall(req.encode())
        resp = b""
        while b"\r\n\r\n" not in resp:
            chunk = self.sock.recv(4096)
            if not chunk:
                raise ConnectionError("WebSocket handshake failed")
            resp += chunk
        head, self.buf = resp.split(b"\r\n\r\n", 1)
        if b" 101 " not in head.split(b"\r\n")[0]:
            raise ConnectionError(head.decode(errors="replace"))

    def _read(self, n):
        while len(self.buf) < n:
            chunk = self.sock.recv(1 << 20)
            if not chunk:
                raise ConnectionError("socket closed")
            self.buf += chunk
        out, self.buf = self.buf[:n], self.buf[n:]
        return out

    def send(self, text):
        data = text.encode()
        head = bytearray([0x81])
        n = len(data)
        if n < 126:
            head.append(0x80 | n)
        elif n < 65536:
            head.append(0x80 | 126); head += struct.pack(">H", n)
        else:
            head.append(0x80 | 127); head += struct.pack(">Q", n)
        mask = os.urandom(4)
        head += mask
        self.sock.sendall(bytes(head) + bytes(b ^ mask[i % 4] for i, b in enumerate(data)))

    def recv(self):
        parts = []
        while True:
            b1, b2 = self._read(2)
            op, n = b1 & 0x0F, b2 & 0x7F
            if n == 126:
                n = struct.unpack(">H", self._read(2))[0]
            elif n == 127:
                n = struct.unpack(">Q", self._read(8))[0]
            if b2 & 0x80:
                mask = self._read(4)
                payload = bytes(b ^ mask[i % 4] for i, b in enumerate(self._read(n)))
            else:
                payload = self._read(n)
            if op == 0x8:
                raise ConnectionError("WebSocket closed by browser")
            if op in (0x9, 0xA):
                continue
            parts.append(payload)
            if b1 & 0x80:
                return b"".join(parts).decode()


class Browser:
    """Context manager: `with Browser() as b: b.goto(url); b.eval(js)`."""

    def __init__(self, width=1440, height=900, scale=1, mobile=False, user_agent=None, scheme="light"):
        self.metrics = dict(width=width, height=height, deviceScaleFactor=scale, mobile=mobile)
        self.scheme = scheme
        self.user_agent = user_agent
        self.events = []
        self._id = 0

    def __enter__(self):
        self.profile = tempfile.mkdtemp(prefix="brandkit-")
        args = [find_browser(), "--headless=new", "--remote-debugging-port=0",
                f"--user-data-dir={self.profile}", "--no-first-run", "--no-default-browser-check",
                "--hide-scrollbars", "--disable-extensions", "--mute-audio",
                "--lang=en-US", "--window-size=1440,900", "about:blank"]
        self.proc = subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        port_file = os.path.join(self.profile, "DevToolsActivePort")
        for _ in range(150):
            if os.path.exists(port_file) and open(port_file).read().strip():
                break
            time.sleep(0.1)
        port = int(open(port_file).read().split()[0])
        for _ in range(50):
            try:
                targets = json.load(urllib.request.urlopen(f"http://127.0.0.1:{port}/json/list"))
                page = next(t for t in targets if t["type"] == "page")
                break
            except Exception:
                time.sleep(0.1)
        self.ws = WebSocket(page["webSocketDebuggerUrl"])
        for domain in ("Page", "Runtime", "Network"):
            self.call(f"{domain}.enable")
        self.call("Emulation.setDeviceMetricsOverride", **self.metrics)
        if self.scheme:
            self.call("Emulation.setEmulatedMedia",
                      features=[{"name": "prefers-color-scheme", "value": self.scheme}])
            # Some sites (Google among them) pick the theme server-side from this client hint.
            self.call("Network.setExtraHTTPHeaders", headers={"Sec-CH-Prefers-Color-Scheme": self.scheme})
        if self.user_agent:
            self.call("Network.setUserAgentOverride", userAgent=self.user_agent)
        return self

    def __exit__(self, *exc):
        try:
            self.call("Browser.close")
        except Exception:
            pass
        try:
            self.proc.wait(timeout=10)
        except Exception:
            self.proc.kill()
        shutil.rmtree(self.profile, ignore_errors=True)

    def call(self, method, **params):
        self._id += 1
        my_id = self._id
        self.ws.send(json.dumps({"id": my_id, "method": method, "params": params}))
        while True:
            msg = json.loads(self.ws.recv())
            if msg.get("id") == my_id:
                if "error" in msg:
                    raise RuntimeError(f"{method}: {msg['error']}")
                return msg.get("result", {})
            if "method" in msg:
                self.events.append(msg)

    def wait_event(self, name, timeout=30):
        deadline = time.time() + timeout
        self.ws.sock.settimeout(1)
        try:
            while time.time() < deadline:
                if any(e["method"] == name for e in self.events):
                    return True
                try:
                    msg = json.loads(self.ws.recv())
                except socket.timeout:
                    continue
                if "method" in msg:
                    self.events.append(msg)
        finally:
            self.ws.sock.settimeout(60)
        return False

    def idle(self, seconds):
        """Keep draining events (network activity) for a fixed settle time."""
        self.ws.sock.settimeout(0.5)
        end = time.time() + seconds
        try:
            while time.time() < end:
                try:
                    msg = json.loads(self.ws.recv())
                    if "method" in msg:
                        self.events.append(msg)
                except socket.timeout:
                    pass
        finally:
            self.ws.sock.settimeout(60)

    def goto(self, url, settle=3.0, timeout=45):
        self.events = [e for e in self.events if e["method"] != "Page.loadEventFired"]
        self.call("Page.navigate", url=url)
        self.wait_event("Page.loadEventFired", timeout)
        self.idle(settle)

    def eval(self, expression):
        r = self.call("Runtime.evaluate", expression=expression, returnByValue=True,
                      awaitPromise=True, timeout=60000)
        if "exceptionDetails" in r:
            raise RuntimeError(json.dumps(r["exceptionDetails"])[:2000])
        return r["result"].get("value")

    def set_content(self, html_path, settle=1.5):
        self.goto("file:///" + os.path.abspath(html_path).replace("\\", "/").lstrip("/"), settle=settle)

    def screenshot(self, path, full_page=False, max_height=8000):
        if full_page:
            h = self.call("Page.getLayoutMetrics")["cssContentSize"]["height"]
            self.call("Emulation.setDeviceMetricsOverride",
                      **{**self.metrics, "height": int(min(h, max_height))})
            self.idle(0.8)
        data = self.call("Page.captureScreenshot", format="png")["data"]
        if full_page:
            self.call("Emulation.setDeviceMetricsOverride", **self.metrics)
        with open(path, "wb") as f:
            f.write(base64.b64decode(data))
        return path
