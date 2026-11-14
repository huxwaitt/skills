"""Measure the palette of sample artifacts (or a rendered asset) so imagery colors in the kit
are measured, not guessed.

    python palette.py brandkits/acme/assets/samples/*.jpg [--top 8]

For each image prints: size, mean luminance, the four corner colors (backgrounds and
gradient ends) and the most common colors (quantized, near-duplicates merged).
"""
import argparse
import base64
import json
import mimetypes
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cdp import Browser  # noqa: E402

JS = """(async (src, top) => {
  const img = new Image(); img.src = src; await img.decode();
  const w = Math.min(img.naturalWidth, 400), h = Math.round(img.naturalHeight * w / img.naturalWidth);
  const c = document.createElement('canvas'); c.width = w; c.height = h;
  const g = c.getContext('2d'); g.drawImage(img, 0, 0, w, h);
  const d = g.getImageData(0, 0, w, h).data, counts = new Map(); let lum = 0;
  const hex = (r, g, b) => '#' + [r, g, b].map(v => v.toString(16).padStart(2, '0')).join('');
  for (let i = 0; i < d.length; i += 4) {
    const [r, gg, b] = [d[i], d[i + 1], d[i + 2]];
    lum += 0.2126 * r + 0.7152 * gg + 0.0722 * b;
    const k = ((r >> 3) << 10) | ((gg >> 3) << 5) | (b >> 3);
    const e = counts.get(k) || [0, 0, 0, 0]; e[0]++; e[1] += r; e[2] += gg; e[3] += b; counts.set(k, e);
  }
  const n = d.length / 4, out = [];
  for (const [, e] of [...counts].sort((a, b) => b[1][0] - a[1][0])) {
    const col = [e[1] / e[0], e[2] / e[0], e[3] / e[0]].map(Math.round);
    if (out.some(o => Math.hypot(o.rgb[0] - col[0], o.rgb[1] - col[1], o.rgb[2] - col[2]) < 28)) {
      out.find(o => Math.hypot(o.rgb[0] - col[0], o.rgb[1] - col[1], o.rgb[2] - col[2]) < 28).share += e[0] / n; continue; }
    out.push({ rgb: col, share: e[0] / n }); if (out.length >= top) break;
  }
  const px = (x, y) => { const i = (y * w + x) * 4; return hex(d[i], d[i + 1], d[i + 2]); };
  return { size: img.naturalWidth + 'x' + img.naturalHeight, meanLuminance: Math.round(lum / n),
    corners: { tl: px(2, 2), tr: px(w - 3, 2), bl: px(2, h - 3), br: px(w - 3, h - 3) },
    top: out.map(o => ({ hex: hex(...o.rgb), share: +(o.share * 100).toFixed(1) })) };
})"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("images", nargs="+")
    ap.add_argument("--top", type=int, default=8)
    a = ap.parse_args()
    with Browser(width=800, height=600) as b:
        for path in a.images:
            mime = mimetypes.guess_type(path)[0] or "image/png"
            src = f"data:{mime};base64," + base64.b64encode(open(path, "rb").read()).decode()
            res = b.eval(f"{JS}({json.dumps(src)}, {a.top})")
            print(json.dumps({"file": path, **res}))


if __name__ == "__main__":
    main()
