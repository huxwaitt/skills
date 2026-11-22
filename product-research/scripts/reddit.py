"""Keyless Reddit search and thread reader for product research. Stdlib only.

Method follows mvanhorn/last30days-skill (MIT): Reddit's anonymous .json API
answers 403, so search reads the site-search HTML fragment, and posts and
comments come from the Arctic Shift public archive (scores there are
snapshots, slightly behind live). The archive's title search sheds load with
HTTP 422, so when it refuses, thread links come from a plain web search for
"site:reddit.com <query>" and the archive is asked for those posts by id.

  python reddit.py search "all-clad d3" --sub cookware --time year --sort top
  python reddit.py thread 1abcd2e --top 25        (id or thread URL)
  python reddit.py selftest
"""
import argparse
import html
import json
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/130.0 Safari/537.36")
REDDIT = "https://www.reddit.com"
ARCTIC = "https://arctic-shift.photon-reddit.com/api"
PAUSE = 1.5  # seconds between requests to one host

TRACKER = re.compile(r'<search-telemetry-tracker\b[^>]*?\bdata-faceplate-tracking-context="([^"]*)"')
HREF = re.compile(r'<a\b[^>]*?data-testid="post-title"[^>]*?\bhref="([^"]*)"'
                  r'|<a\b[^>]*?\bhref="([^"]*)"[^>]*?data-testid="post-title"')
TIMEAGO = re.compile(r'<faceplate-timeago\b[^>]*?\bts="([^"]+)"')
COUNTER = re.compile(r'<faceplate-number\b[^>]*?\bnumber="(\d+)"[^>]*>\s*</faceplate-number>\s*(vote|comment)')
NEXT = re.compile(r'<faceplate-partial\b[^>]*?\bsrc="([^"]*/svc/shreddit/[^"]*search/[^"]*)"')
THREAD = re.compile(r"reddit\.com/r/([A-Za-z0-9_]+)/comments/([a-z0-9]+)(?:/([A-Za-z0-9_]+))?")
# (name, results page, freshness parameter, its prefix); tried in order
ENGINES = (("Brave", "https://search.brave.com/search?source=web&", "tf", "p"),
           ("DuckDuckGo", "https://html.duckduckgo.com/html/?", "df", ""))


class RedditRefused(Exception):
    """Reddit answered 403: it blocks this network's anonymous requests."""


def get(url, accept, retries=1, soft=False):
    """Page text. A failed request exits, or returns "" when soft."""
    req = urllib.request.Request(url, headers={
        "User-Agent": UA, "Accept": accept, "Accept-Language": "en-US,en;q=0.9"})
    try:
        with urllib.request.urlopen(req, timeout=25) as r:
            return r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        if e.code in (422, 429) and retries:  # both hosts answer these to mean "slow down"
            time.sleep(20)  # the archive refuses again if asked sooner
            return get(url, accept, retries - 1, soft)
        if e.code == 403 and url.startswith(REDDIT):
            raise RedditRefused(url)
        if soft:
            return ""
        sys.exit(f"HTTP {e.code} from {urllib.parse.urlsplit(url).netloc}: {url}")
    except urllib.error.URLError as e:
        if soft:
            return ""
        sys.exit(f"could not reach {urllib.parse.urlsplit(url).netloc}: {e.reason}")


def day(ts):
    try:
        if isinstance(ts, str) and not ts.isdigit():
            return ts[:10]
        return datetime.fromtimestamp(int(ts), timezone.utc).strftime("%Y-%m-%d")
    except (TypeError, ValueError):
        return "?"


def parse_search(text):
    """One search fragment -> (posts, next-page cursor or None)."""
    units = []
    for m in TRACKER.finditer(text):
        try:
            ctx = json.loads(html.unescape(m.group(1)))
        except ValueError:
            continue
        post = ctx.get("post") if isinstance(ctx, dict) else None
        action = ctx.get("action_info") if isinstance(ctx, dict) else None
        if isinstance(post, dict) and post.get("id") and isinstance(action, dict) and action.get("type") == "post":
            units.append((m.start(), ctx))
    posts, seen = [], set()
    for i, (start, ctx) in enumerate(units):
        pid = ctx["post"]["id"]
        if pid in seen:
            continue
        seen.add(pid)
        # a post's markup runs until the first tracker that belongs to another post
        end = next((s for s, c in units[i + 1:] if c["post"]["id"] != pid), len(text))
        seg = text[start:end]
        href = HREF.search(seg)
        path = html.unescape((href.group(1) or href.group(2)) if href else "")
        counts = {}
        for n, kind in COUNTER.findall(seg):
            counts.setdefault(kind, int(n))
        ts = TIMEAGO.search(seg)
        sub = ctx.get("subreddit")
        posts.append({
            "id": pid.removeprefix("t3_"),
            "title": ctx["post"].get("title") or "",
            "sub": (sub.get("name") if isinstance(sub, dict) else "") or "",
            "score": counts.get("vote"),
            "comments": counts.get("comment"),
            "date": day(ts.group(1)) if ts else "?",
            "url": (REDDIT + path) if path.startswith("/") else path,
        })
    cursor = None
    for src in NEXT.findall(text):
        cursor = (urllib.parse.parse_qs(urllib.parse.urlsplit(html.unescape(src)).query).get("cursor") or [None])[0]
        if cursor:
            break
    return posts, cursor


def archive_search(query, sub, when, sort):
    """Fallback when Reddit refuses: the archive matches post TITLES in one subreddit, newest 100."""
    days = {"year": 365, "month": 30, "week": 7, "day": 1}.get(when)
    url = (f"{ARCTIC}/posts/search?subreddit={urllib.parse.quote(sub, safe='')}"
           f"&title={urllib.parse.quote(query)}&limit=100&sort=desc")
    if days:
        url += "&after=" + datetime.fromtimestamp(time.time() - days * 86400, timezone.utc).strftime("%Y-%m-%d")
    text = get(url, "application/json", soft=True)
    if not text:
        return None  # refused: the caller falls back to web search
    rows = json.loads(text).get("data") or []
    posts = [{"id": r.get("id"), "title": r.get("title") or "", "sub": r.get("subreddit") or sub,
              "score": r.get("score"), "comments": r.get("num_comments"), "date": day(r.get("created_utc")),
              "url": REDDIT + (r.get("permalink") or f"/comments/{r.get('id')}")} for r in rows]
    key = "comments" if sort == "comments" else "score"
    return posts if sort == "new" else sorted(posts, key=lambda p: -(p[key] or 0))


def thread_links(text, sub=None):
    """{post id: (subreddit, slug)} for the threads a results page links to, in page order."""
    text = urllib.parse.unquote(html.unescape(text))  # DuckDuckGo wraps each link in an encoded redirect
    found = {}
    for s, pid, slug in THREAD.findall(text):
        if not sub or s.lower() == sub.lower():
            found.setdefault(pid, (s, slug))
    return found


def results_page(url):
    """A search engine's results page, "" on failure.

    Brave answers Python's own client with 429 whatever the User-Agent (measured 2026-11-22) and
    serves the same request from curl, so curl fetches the page where it is installed.
    """
    if shutil.which("curl"):
        r = subprocess.run(["curl", "-sL", "-m", "25", "-A", UA, "-H", "Accept: text/html",
                            "-H", "Accept-Language: en-US,en;q=0.9", url], capture_output=True)
        if r.returncode == 0:
            return r.stdout.decode("utf-8", "replace")
    return get(url, "text/html", soft=True)


def web_search(query, sub, when, sort):
    """Last fallback: thread links from a web search, details from the archive by id."""
    q = f"site:reddit.com r/{sub} {query}" if sub else f"site:reddit.com {query}"
    for name, base, key, prefix in ENGINES:
        params = {"q": q} if when == "all" else {"q": q, key: prefix + when[0]}
        found = thread_links(results_page(base + urllib.parse.urlencode(params)), sub)
        if found:
            break
        time.sleep(PAUSE)
    else:
        return [], None
    ids = list(found)[:100]
    rows = json.loads(get(f"{ARCTIC}/posts/ids?ids={','.join(ids)}", "application/json", soft=True) or "{}").get("data") or []
    meta = {r.get("id"): r for r in rows}
    posts = []
    for pid in ids:
        s, slug = found[pid]
        r = meta.get(pid, {})  # the archive may refuse or lag: keep the thread, without its counts
        posts.append({"id": pid, "title": r.get("title") or slug.replace("_", " "), "sub": s,
                      "score": r.get("score"), "comments": r.get("num_comments"),
                      "date": day(r.get("created_utc")), "url": f"{REDDIT}/r/{s}/comments/{pid}/{slug}"})
    if sort == "new":
        posts.sort(key=lambda p: p["date"], reverse=True)
    elif sort in ("comments", "top"):  # relevance and hot keep the search engine's order
        posts.sort(key=lambda p: -(p["comments" if sort == "comments" else "score"] or 0))
    return posts, name


def search(query, sub, when, sort, limit):
    path = f"/svc/shreddit/r/{urllib.parse.quote(sub, safe='')}/search/" if sub else "/svc/shreddit/search/"
    posts, cursor, seen = [], None, set()
    try:
        while len(posts) < limit:
            params = [("q", query), ("type", "posts"), ("t", when), ("sort", sort)]
            if cursor:
                params.append(("cursor", cursor))
            page, cursor = parse_search(get(f"{REDDIT}{path}?{urllib.parse.urlencode(params)}", "text/html"))
            new = [p for p in page if p["id"] not in seen]
            seen.update(p["id"] for p in new)
            posts += new
            if not new or not cursor:
                break
            time.sleep(PAUSE)
        print("# route: Reddit site search")
    except RedditRefused:
        posts = archive_search(query, sub, when, sort) if sub else None
        if posts is not None:
            print("# route: archive title search (Reddit refused site search). Matches post titles only, newest 100, "
                  "so try several short queries.")
        else:
            posts, engine = web_search(query, sub, when, sort)
            print(f"# route: {engine or 'no'} web search for thread links (Reddit refused site search, archive "
                  "search refused or needs --sub). One page of results, so try several short queries.")
    if not posts:
        print("no results (or Reddit served a page this script does not recognise)")
    for p in posts[:limit]:
        score = "?" if p["score"] is None else p["score"]
        comments = "?" if p["comments"] is None else p["comments"]
        print(f"{score:>6} pts {comments:>5} c  {p['date']}  r/{p['sub']}  {p['id']}  {p['title']}\n        {p['url']}")


def thread(ref, top, chars):
    m = re.search(r"/comments/([a-z0-9]+)", ref)
    pid = (m.group(1) if m else ref).removeprefix("t3_")
    post = (json.loads(get(f"{ARCTIC}/posts/ids?ids={pid}", "application/json")).get("data") or [{}])[0]
    time.sleep(PAUSE)
    nodes = json.loads(get(f"{ARCTIC}/comments/tree?link_id=t3_{pid}&limit=500", "application/json")).get("data") or []
    rows, stack = [], [(n, 0) for n in reversed(nodes)]
    while stack:
        node, depth = stack.pop()
        data = node.get("data") if isinstance(node, dict) and node.get("kind") == "t1" else None
        if not isinstance(data, dict):
            continue
        if data.get("author") not in ("[deleted]", "[removed]", None) and data.get("body") not in ("[deleted]", "[removed]", None):
            rows.append((int(data.get("score") or 0), depth, data))
        replies = data.get("replies")
        children = ((replies or {}).get("data") or {}).get("children") if isinstance(replies, dict) else None
        stack.extend((c, depth + 1) for c in reversed(children or []))
    print(f"{post.get('title', '(post not in archive)')}\nr/{post.get('subreddit', '?')} | {post.get('score', '?')} pts | "
          f"{post.get('num_comments', '?')} comments | {day(post.get('created_utc'))} | u/{post.get('author', '?')}\n"
          f"{REDDIT}/comments/{pid}\n")
    if post.get("selftext"):
        print(post["selftext"][:chars * 2].strip() + "\n")
    print(f"--- top {min(top, len(rows))} of {len(rows)} archived comments, by score")
    for score, depth, d in sorted(rows, key=lambda r: -r[0])[:top]:
        body = " ".join((d.get("body") or "").split())
        print(f"[{score:>4}] u/{d.get('author')} (depth {depth}, {day(d.get('created_utc'))}): {body[:chars]}")


def selftest():
    ctx = html.escape(json.dumps({"action_info": {"type": "post"}, "post": {"id": "t3_abc12", "title": "D3 vs D5?"},
                                  "subreddit": {"name": "cookware"}}))
    unit = (f'<search-telemetry-tracker data-faceplate-tracking-context="{ctx}">'
            '<a data-testid="post-title" href="/r/cookware/comments/abc12/d3_vs_d5/">D3 vs D5?</a>'
            '<faceplate-timeago ts="2026-03-04T10:00:00.000Z"></faceplate-timeago>'
            '<faceplate-number number="41"></faceplate-number> votes'
            '<faceplate-number number="17"></faceplate-number> comments</search-telemetry-tracker>')
    more = '<faceplate-partial src="/svc/shreddit/r/cookware/search/?q=d3&amp;cursor=XYZ"></faceplate-partial>'
    posts, cursor = parse_search(unit + unit + more)  # duplicate tracker must not duplicate the post
    assert posts == [{"id": "abc12", "title": "D3 vs D5?", "sub": "cookware", "score": 41, "comments": 17,
                      "date": "2026-03-04", "url": REDDIT + "/r/cookware/comments/abc12/d3_vs_d5/"}], posts
    assert cursor == "XYZ", cursor
    assert parse_search("<html>challenge</html>") == ([], None)
    page = ('<a href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fwww.reddit.com%2Fr%2FCookware%2Fcomments%2Fabc12%2Fd3_vs_d5%2F">x</a>'
            '<a href="https://www.reddit.com/r/other/comments/zzz99/nope/">y</a>'
            '<a href="https://www.reddit.com/r/cookware/comments/abc12/d3_vs_d5/">dup</a>'
            '<a href="https://www.reddit.com/r/cookware/wiki/index">not a thread</a>')
    assert thread_links(page, "cookware") == {"abc12": ("Cookware", "d3_vs_d5")}, thread_links(page, "cookware")
    assert list(thread_links(page)) == ["abc12", "zzz99"]
    print("selftest ok")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    cmd = ap.add_subparsers(dest="cmd", required=True)
    s = cmd.add_parser("search")
    s.add_argument("query")
    s.add_argument("--sub", help="restrict to one subreddit, e.g. cookware")
    s.add_argument("--time", default="all", choices=["all", "year", "month", "week", "day"])
    s.add_argument("--sort", default="relevance", choices=["relevance", "top", "comments", "new", "hot"])
    s.add_argument("--limit", type=int, default=25)
    t = cmd.add_parser("thread")
    t.add_argument("ref", help="post id or thread URL")
    t.add_argument("--top", type=int, default=25, help="comments to print, highest score first")
    t.add_argument("--chars", type=int, default=700, help="characters kept per comment")
    cmd.add_parser("selftest")
    a = ap.parse_args()
    if a.cmd == "search":
        search(a.query, a.sub, a.time, a.sort, a.limit)
    elif a.cmd == "thread":
        thread(a.ref, a.top, a.chars)
    else:
        selftest()
