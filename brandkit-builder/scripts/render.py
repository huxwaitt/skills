"""Render an HTML asset to PNG at an exact size with headless Chromium.

    python render.py asset.html asset.png --size 1200x630 [--scale 2]
    python render.py page.html page.png --size 1440xfull      (full-page web page)

Waits for web fonts, then fails loudly if any declared @font-face did not load, because a
silent fallback font is the most common reason a regenerated asset looks fake.
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cdp import Browser  # noqa: E402

FONT_CHECK = """(async () => { await document.fonts.ready;
  const faces = [...document.fonts];
  return { loaded: faces.filter(f => f.status === 'loaded').map(f => f.family + ' ' + f.weight),
           failed: faces.filter(f => f.status === 'error').map(f => f.family + ' ' + f.weight),
           unused: faces.filter(f => f.status === 'unloaded').length,
           overflow: [...document.querySelectorAll('body *')].filter(e => e.scrollWidth > e.clientWidth + 1
             && getComputedStyle(e).overflow === 'hidden').length }; })()"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("html")
    ap.add_argument("png")
    ap.add_argument("--size", default="1200x630")
    ap.add_argument("--scale", type=float, default=1)
    a = ap.parse_args()
    ws, hs = a.size.lower().split("x")
    w, full = int(ws), hs == "full"
    h = 900 if full else int(hs)
    with Browser(width=w, height=h, scale=a.scale) as b:
        b.set_content(a.html, settle=1.5)
        report = b.eval(FONT_CHECK)
        b.screenshot(a.png, full_page=full, max_height=12000)
    print(json.dumps({"png": a.png, "size": f"{w}x{hs}@{a.scale}x", **report}))
    if report["failed"]:
        sys.exit(f"font(s) failed to load: {report['failed']}")


if __name__ == "__main__":
    main()
