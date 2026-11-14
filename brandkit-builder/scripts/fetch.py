"""Download brand assets into a kit and record where each came from.

    python fetch.py --kit brandkits/acme --into official --source https://acme.com/brand \
        --terms "Editorial use only; no co-branding" logo-full=https://.../logo.svg https://.../guide.pdf

Each argument is a URL or name=URL. Files land in <kit>/assets/<into>/ and are appended to
<kit>/assets/manifest.json with source page, usage terms, size, type and sha256, so the kit can
always answer "where did this come from and what may we do with it".
"""
import argparse
import datetime
import hashlib
import json
import os
import re
import urllib.request
from urllib.parse import unquote, urlparse

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/130.0.0.0 Safari/537.36")
EXT = {"image/svg+xml": ".svg", "image/png": ".png", "image/jpeg": ".jpg", "image/webp": ".webp",
       "image/gif": ".gif", "application/pdf": ".pdf", "application/zip": ".zip", "font/woff2": ".woff2",
       "font/woff": ".woff", "font/ttf": ".ttf", "image/x-icon": ".ico", "text/css": ".css"}


def name_for(url, hint, ctype, disposition):
    m = re.search(r'filename\*?=(?:UTF-8\'\')?"?([^";]+)', disposition or "") or \
        re.search(r"filename%3D([^&]+)", url)
    base = unquote(m.group(1)) if m else os.path.basename(urlparse(url).path) or "file"
    stem, ext = os.path.splitext(base)
    ext = ext or EXT.get((ctype or "").split(";")[0].strip(), ".bin")
    stem = re.sub(r"[^A-Za-z0-9._-]+", "-", hint or stem).strip("-") or "file"
    return stem + ext.lower()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--kit", required=True)
    ap.add_argument("--into", default="official", help="subfolder of assets/ (official, samples, fonts...)")
    ap.add_argument("--source", required=True, help="page the assets were found on")
    ap.add_argument("--terms", default="unknown", help="usage terms as stated by the source")
    ap.add_argument("urls", nargs="+")
    a = ap.parse_args()
    dest = os.path.join(a.kit, "assets", a.into)
    os.makedirs(dest, exist_ok=True)
    man_path = os.path.join(a.kit, "assets", "manifest.json")
    manifest = json.load(open(man_path, encoding="utf-8")) if os.path.exists(man_path) else []
    for arg in a.urls:
        hint, url = (arg.split("=", 1) if re.match(r"^[\w.-]+=https?://", arg) else (None, arg))
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=60) as r:
                data = r.read()
                ctype, disp = r.headers.get("Content-Type", ""), r.headers.get("Content-Disposition", "")
        except Exception as e:
            print(f"FAIL {url[:100]}: {e}")
            continue
        digest = hashlib.sha256(data).hexdigest()
        dupe = next((m for m in manifest if m["sha256"] == digest), None)
        if dupe:
            print(f"skip {url[:80]}: same bytes as {dupe['file']}")
            continue
        fname = name_for(url, hint, ctype, disp)
        path = os.path.join(dest, fname)
        with open(path, "wb") as f:
            f.write(data)
        entry = {"file": os.path.relpath(path, a.kit).replace("\\", "/"), "url": url.split("?X-Goog-")[0][:500],
                 "source": a.source, "terms": a.terms, "type": ctype.split(";")[0], "bytes": len(data),
                 "sha256": digest, "fetched": datetime.date.today().isoformat()}
        manifest = [m for m in manifest if m["file"] != entry["file"]] + [entry]
        print(f"ok   {entry['file']} ({len(data):,} B, {entry['type']})")
    json.dump(manifest, open(man_path, "w", encoding="utf-8"), indent=1)


if __name__ == "__main__":
    main()
