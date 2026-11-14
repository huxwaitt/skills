"""Capture a website's frontend architecture and in-use design tokens.

    python capture.py https://example.com --out brandkits/example [--pages /about /pricing]

Writes to --out:
  capture/architecture.json   raw extraction per page (frameworks, structure, CSS, tokens, logos)
  capture/network.json        every response: type, mime, origin, size
  capture/<page>-desktop-<scheme>.png  full-page screenshot at 1440 wide, per color scheme
  capture/<page>-mobile-<scheme>.png   first screen at 390x844, primary scheme
  capture/report.md           readable map of the above, the input for BRAND.md
  assets/site/                logo SVGs, favicons, og:image, manifest icons, as served
"""
import argparse
import collections
import hashlib
import json
import os
import re
import sys
import urllib.request
from urllib.parse import urljoin, urlparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cdp import Browser  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/130.0.0.0 Safari/537.36")
MOBILE_UA = ("Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 "
             "(KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1")


def slug(path):
    s = re.sub(r"[^a-z0-9]+", "-", path.lower()).strip("-")
    return s or "home"


def rgb_to_hex(v):
    m = re.match(r"rgba?\((\d+),\s*(\d+),\s*(\d+)(?:,\s*([\d.]+))?\)", v or "")
    if not m:
        return v
    r, g, b = (int(x) for x in m.groups()[:3])
    a = m.group(4)
    hx = f"#{r:02x}{g:02x}{b:02x}"
    return hx if a is None or float(a) == 1 else f"{hx} @{float(a):.2f}"


def merge_colors(*lists):
    """Combine weighted rgb lists into hex, folding alpha variants into their base."""
    out = collections.Counter()
    for lst in lists:
        for item in lst:
            out[rgb_to_hex(item["value"])] += item["weight"]
    return [{"hex": k, "weight": v} for k, v in out.most_common(30)]


def download(url, dest_dir, name_hint=None):
    os.makedirs(dest_dir, exist_ok=True)
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=20) as r:
            data, ctype = r.read(), r.headers.get("Content-Type", "")
    except Exception as e:
        return {"url": url, "error": str(e)}
    ext = os.path.splitext(urlparse(url).path)[1][:6] or {
        "image/svg+xml": ".svg", "image/png": ".png", "image/jpeg": ".jpg", "image/webp": ".webp",
        "image/x-icon": ".ico", "image/vnd.microsoft.icon": ".ico", "application/json": ".json",
        "application/manifest+json": ".json"}.get(ctype.split(";")[0], ".bin")
    name = (name_hint or slug(os.path.basename(urlparse(url).path)) or "file") + ext
    path = os.path.join(dest_dir, name)
    with open(path, "wb") as f:
        f.write(data)
    return {"url": url, "file": path, "bytes": len(data), "type": ctype,
            "sha256": hashlib.sha256(data).hexdigest()[:16]}


def summarize_network(events, site):
    site_host = urlparse(site).hostname or ""
    rows, by_type, by_origin = [], collections.Counter(), collections.Counter()
    sizes = {e["params"]["requestId"]: e["params"].get("encodedDataLength", 0)
             for e in events if e["method"] == "Network.loadingFinished"}
    for e in events:
        if e["method"] != "Network.responseReceived":
            continue
        p = e["params"]
        url = p["response"]["url"]
        if url.startswith("data:"):
            continue
        size = sizes.get(p["requestId"], 0)
        origin = urlparse(url).netloc
        rows.append({"type": p.get("type"), "status": p["response"]["status"],
                     "mime": p["response"].get("mimeType"), "url": url[:300], "bytes": size})
        by_type[p.get("type")] += size
        by_origin[origin] += 1
    first_party = sum(c for o, c in by_origin.items() if o.split(":")[0].endswith(site_host.replace("www.", "")))
    return {"requests": len(rows), "bytesByType": dict(by_type.most_common()),
            "requestsByOrigin": dict(by_origin.most_common(25)), "firstPartyRequests": first_party,
            "responses": rows}


def capture_page(url, outdir, js, tag, schemes):
    data, net = None, None
    for scheme in schemes:
        with Browser(width=1440, height=900, user_agent=UA, scheme=scheme) as b:
            b.goto(url, settle=4)
            d = b.eval(js)
            b.screenshot(os.path.join(outdir, f"{tag}-desktop-{scheme}.png"), full_page=True)
            if data is None:
                data, net = d, summarize_network(b.events, url)
                data["scheme"] = scheme
            else:
                data.setdefault("altSchemes", {})[scheme] = {"tokens": d["tokens"], "typography": d["typography"],
                                                             "components": d["components"], "logos": d["logos"]}
    with Browser(width=390, height=844, scale=2, mobile=True, user_agent=MOBILE_UA, scheme=schemes[0]) as b:
        b.goto(url, settle=3)
        b.screenshot(os.path.join(outdir, f"{tag}-mobile-{schemes[0]}.png"))
        try:
            data["mobileTypography"] = b.eval(js)["typography"]
        except Exception as e:
            data["mobileTypography"] = {"error": str(e)}
    return data, net


def fmt_list(items, key="value", n=10):
    return ", ".join(f"`{i[key]}` ({i['weight']})" for i in items[:n]) or "none found"


def write_report(pages, nets, saved, path):
    home = pages[0]
    L = [f"# Capture report: {home['url']}", "", f"Title: {home['title']}  ", f"Lang: {home['lang'] or '?'}  ",
         f"Description: {home['meta'].get('description')}  ", f"theme-color: {home['meta'].get('themeColor')}", ""]
    L += ["## Frontend architecture", ""]
    fw = {k: v for p in pages for k, v in p["frameworks"].items()}
    L += [f"- **{k}**: {v}" for k, v in fw.items()] or ["- no framework fingerprint matched"]
    s = home["structure"]
    L += ["", f"- DOM: {s['elements']} elements, depth {s['maxDepth']}, {s['shadowRoots']} shadow roots",
          f"- Landmarks: " + ", ".join(f"{k} {v}" for k, v in s["landmarks"].items() if v),
          f"- Custom elements: " + (", ".join(f"`{c['value']}`×{c['weight']}" for c in s["customElements"][:15]) or "none"),
          f"- Scripts: {home['scripts']['external']} external, {home['scripts']['inline']} inline, "
          f"{home['scripts']['modules']} modules; origins: {', '.join(home['scripts']['origins'][:8])}",
          f"- CSS: {len(home['css']['sheets'])} sheets ({home['css']['crossOriginSheets']} cross-origin, unreadable), "
          f"{home['css']['inlineStyleBlocks']} <style> blocks, {home['css']['styleAttrs']} style= attributes, "
          f"{home['css']['variableCount']} custom properties on :root",
          f"- Breakpoints: {fmt_list(home['css']['breakpoints'])}",
          f"- Icons: {home['iconSystems']}"]
    n = nets[0]
    L += [f"- Network: {n['requests']} responses; bytes by type {n['bytesByType']}",
          f"- Origins: {n['requestsByOrigin']}", ""]
    L += ["### Page outline", ""] + [f"- {h['level']}: {h['text']}" for h in s["headings"][:20]] + [""]
    t = home["tokens"]
    L += ["## Tokens in use (computed, weighted)", "",
          "Text colors are weighted by characters, backgrounds by area (kpx²).", ""]
    L += [f"- Page background: `{rgb_to_hex(t['pageBackground'])}`",
          f"- Text colors: " + ", ".join(f"`{c['hex']}` ({c['weight']})" for c in merge_colors(t["textColor"])[:10]),
          f"- Backgrounds: " + ", ".join(f"`{c['hex']}` ({c['weight']})" for c in merge_colors(t["bgColor"])[:10]),
          f"- Borders: " + ", ".join(f"`{c['hex']}` ({c['weight']})" for c in merge_colors(t["borderColor"])[:8]),
          f"- Font families: {fmt_list(t['fontFamily'])}",
          f"- Font sizes: {fmt_list(t['fontSize'], n=12)}",
          f"- Weights: {fmt_list(t['fontWeight'])}",
          f"- Line heights: {fmt_list(t['lineHeight'])}",
          f"- Letter spacing: {fmt_list(t['letterSpacing'])}",
          f"- Radii: {fmt_list(t['radius'])}",
          f"- Spacing: {fmt_list(t['spacing'], n=14)}",
          f"- Gaps: {fmt_list(t['gap'])}",
          f"- Motion: {fmt_list(t['transition'], n=6)}",
          f"- Shadows:"] + [f"  - `{x['value']}` ({x['weight']})" for x in t["shadow"][:6]]
    L += ["", f"- Fonts loaded: {', '.join(home['loadedFonts'][:30]) or 'none reported'}"]
    faces = {(f["family"], f["src"][:160]) for p in pages for f in p["css"]["fontFaces"]}
    L += [f"- @font-face (readable sheets): {len(faces)}"] + [f"  - {fam}: `{src}`" for fam, src in list(faces)[:12]]
    if home["css"]["variables"]:
        L += ["", "### Custom properties (first 60)", ""] + [f"- `{k}: {v}`" for k, v in list(home["css"]["variables"].items())[:60]]
    for scheme, alt in home.get("altSchemes", {}).items():
        at = alt["tokens"]
        L += ["", f"### {scheme} scheme", "",
              f"- Page background: `{rgb_to_hex(at['pageBackground'])}`",
              f"- Text colors: " + ", ".join(f"`{c['hex']}` ({c['weight']})" for c in merge_colors(at["textColor"])[:8]),
              f"- Backgrounds: " + ", ".join(f"`{c['hex']}` ({c['weight']})" for c in merge_colors(at["bgColor"])[:8])]
        for name, items in alt["components"].items():
            for c in items[:3]:
                L.append(f"- {name} \"{c['text'][:24]}\": bg `{rgb_to_hex(c['bg'])}`, text `{rgb_to_hex(c['color'])}`, radius {c['radius']}")
    L += ["", f"## Typography roles (desktop, {home.get('scheme')})", ""]
    for role, r in home["typography"].items():
        L.append(f"- **{role}**: {r['weight']} {r['size']}/{r['lineHeight']} {r['family'][:60]}, "
                 f"ls {r['letterSpacing']}, {rgb_to_hex(r['color'])}, \"{r['sample'][:40]}\"")
    L += ["", "## Components sampled", ""]
    for name, items in home["components"].items():
        L.append(f"### {name}")
        for c in items[:5]:
            L.append(f"- \"{c['text'][:30]}\" {c['w']}×{c['h']}: bg `{rgb_to_hex(c['bg'])}`, text `{rgb_to_hex(c['color'])}`, "
                     f"radius {c['radius']}, padding {c['padding']}, border {c['border']}, font {c['font']}")
        L.append("")
    L += ["## Logo candidates", ""]
    for lg in home["logos"][:6]:
        L.append(f"- score {lg['score']} <{lg['tag']}> {lg['w']}×{lg['h']} at y={lg['top']}, alt={lg['alt']!r}, src={lg['src']}")
    for p in pages[1:]:
        t = p["tokens"]
        L += ["", f"## Also captured: {p['url']}", "",
              f"- Frameworks: {', '.join(p['frameworks']) or 'none matched'}; {p['structure']['elements']} elements; "
              f"{p['css']['variableCount']} custom properties",
              f"- Text colors: " + ", ".join(f"`{c['hex']}`" for c in merge_colors(t["textColor"])[:8]),
              f"- Backgrounds: " + ", ".join(f"`{c['hex']}`" for c in merge_colors(t["bgColor"])[:8]),
              f"- Families: {fmt_list(t['fontFamily'], n=6)}",
              f"- Sizes: {fmt_list(t['fontSize'], n=10)}",
              f"- Radii: {fmt_list(t['radius'], n=8)}",
              f"- Fonts loaded: {', '.join(p['loadedFonts'][:20])}"]
        for role, r in p["typography"].items():
            L.append(f"- **{role}**: {r['weight']} {r['size']}/{r['lineHeight']} {r['family'][:50]}, ls {r['letterSpacing']}, "
                     f"{rgb_to_hex(r['color'])}, \"{r['sample'][:40]}\"")
        for name, items in p["components"].items():
            for c in items[:3]:
                L.append(f"- {name} \"{c['text'][:24]}\": bg `{rgb_to_hex(c['bg'])}`, text `{rgb_to_hex(c['color'])}`, "
                         f"radius {c['radius']}, padding {c['padding']}, font {c['font']}")
    L += ["", "## Saved assets", ""] + [f"- {s.get('file', s.get('error'))} ← {s['url'][:120]}" for s in saved]
    L += ["", "## Brand-related links found on the site", ""] + [f"- {u}" for p in pages for u in p["links"][:30]]
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(L) + "\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("url")
    ap.add_argument("--out", required=True)
    ap.add_argument("--pages", nargs="*", default=[], help="extra paths or URLs on the same site")
    ap.add_argument("--schemes", nargs="+", default=["light", "dark"], choices=["light", "dark"],
                    help="color schemes to emulate; the first is primary")
    a = ap.parse_args()
    url = a.url if "://" in a.url else "https://" + a.url
    cap, site_assets = os.path.join(a.out, "capture"), os.path.join(a.out, "assets", "site")
    os.makedirs(cap, exist_ok=True)
    js = open(os.path.join(HERE, "extract.js"), encoding="utf-8").read()

    pages, nets = [], []
    for i, target in enumerate([url] + [urljoin(url, p) for p in a.pages]):
        u = urlparse(target)
        tag = "home" if i == 0 else slug(u.netloc.replace("www.", "") + u.path)
        print(f"capturing {target}", file=sys.stderr)
        data, net = capture_page(target, cap, js, tag, a.schemes)
        pages.append(data); nets.append(net)

    home, saved = pages[0], []
    for i, lg in enumerate(home["logos"][:4]):
        if lg["svg"]:
            p = os.path.join(site_assets, f"logo-inline-{i}.svg")
            os.makedirs(site_assets, exist_ok=True)
            svg = lg["svg"] if "xmlns=" in lg["svg"] else lg["svg"].replace("<svg", '<svg xmlns="http://www.w3.org/2000/svg"', 1)
            open(p, "w", encoding="utf-8").write(svg)
            saved.append({"url": f"inline svg #{i} ({lg['w']}x{lg['h']})", "file": p})
        elif lg["src"] and not lg["src"].startswith("data:"):
            saved.append(download(lg["src"], site_assets, f"logo-{i}"))
    for ic in home["icons"]:
        saved.append(download(ic["href"], site_assets, slug(ic["rel"]) + (f"-{ic['sizes']}" if ic.get("sizes") else "")))
    if home["meta"].get("ogImage"):
        saved.append(download(urljoin(url, home["meta"]["ogImage"]), site_assets, "og-image"))

    json.dump(pages, open(os.path.join(cap, "architecture.json"), "w", encoding="utf-8"), indent=1)
    json.dump(nets, open(os.path.join(cap, "network.json"), "w", encoding="utf-8"), indent=1)
    write_report(pages, nets, saved, os.path.join(cap, "report.md"))
    print(os.path.join(cap, "report.md"))


if __name__ == "__main__":
    main()
