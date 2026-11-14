"""platform-atlas command line. Run with `python -I <skill>/scripts/atlas.py <command> ...`.

Lookups (no models; every fact line carries its as-of date and a [doc_id:Lx-Ly] citation):
  status                                  per-platform coverage, as-of dates, staleness, CLI maps
  search   "QUERY" [--platform P] [--k N] [--at YYYY-MM-DD] [--current]
  nodes    "QUERY" [--platform P] [--k N]  entities by name, alias or summary
  entity   "NAME"  [--platform P]          one entity, its summary and every fact
  neighbors "NAME" [--hops 1|2] [--relation R] [--platform P]
  path     "A" "B" [--at DATE] [--history] how two entities connect
  facts    [--platform P] [--relation R] [--type T] [--contains TEXT] [--since D] [--until D] [--current] [--limit N]
  relations [--platform P]
  show     "DOC_ID:Lx-Ly" | CHUNK_ID       the cited passage (or --doc DOC_ID --start N --end M)
  cli-find "QUERY" [--cli NAME]            grep the CLI command maps in kb/cli/
  page-get "NAME" ["NAME2"]                saved answer page and whether it is stale
  page-save "NAME" ["NAME2"] --file PAGE.md

Build (the model work between steps is done by agents; see SKILL.md):
  prepare | check | dedupe-candidates | edge-candidates | summary-tasks | build

Lookups print text; build commands print one JSON object.
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from kg import paths  # noqa: E402

BUILD = ("prepare", "check", "dedupe-candidates", "edge-candidates", "summary-tasks", "build", "status")


def main():
    ap = argparse.ArgumentParser(description="platform-atlas knowledge graph")
    ap.add_argument("command")
    ap.add_argument("args", nargs="*")
    ap.add_argument("--platform")
    ap.add_argument("--k", type=int)
    ap.add_argument("--at")
    ap.add_argument("--current", action="store_true")
    ap.add_argument("--history", action="store_true")
    ap.add_argument("--hops", type=int, default=1)
    ap.add_argument("--relation")
    ap.add_argument("--type")
    ap.add_argument("--contains")
    ap.add_argument("--since")
    ap.add_argument("--until")
    ap.add_argument("--limit", type=int, default=100)
    ap.add_argument("--doc")
    ap.add_argument("--start", type=int, default=1)
    ap.add_argument("--end", type=int, default=60)
    ap.add_argument("--cli")
    ap.add_argument("--file")
    a = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    try:
        out = run(a)
    except paths.AtlasError as e:
        out = {"error": str(e)}
    print(out if isinstance(out, str) else json.dumps(out, indent=1, ensure_ascii=False))
    return 1 if isinstance(out, dict) and "error" in out else 0


def _need(a, n, usage):
    if len(a.args) < n:
        raise paths.AtlasError(f"usage: atlas.py {a.command} {usage}")
    return a.args


def run(a):
    cmd = a.command
    if cmd in BUILD:
        from kg.corpus import Corpus
        from kg.kg_build import Builder
        from kg.kg_store import status
        return {"prepare": lambda: Corpus().prepare(), "check": lambda: Corpus().check(),
                "dedupe-candidates": lambda: Builder().dedupe_candidates(),
                "edge-candidates": lambda: Builder().edge_candidates(),
                "summary-tasks": lambda: Builder().summary_tasks(), "build": lambda: Builder().build(),
                "status": lambda: status()}[cmd]()
    if cmd == "show" and a.doc:
        from kg.corpus import Corpus
        return Corpus().show(a.doc, a.start, a.end)
    if cmd == "cli-find":
        return cli_find(" ".join(_need(a, 1, '"QUERY" [--cli NAME]')), a.cli, a.limit)
    from kg.kg_store import Store
    s = Store()
    if cmd == "search":
        return s.search(" ".join(_need(a, 1, '"QUERY"')), k=a.k or 20, platform=a.platform, at=a.at, current_only=a.current)
    if cmd == "nodes":
        return s.nodes(" ".join(_need(a, 1, '"QUERY"')), k=a.k or 10, platform=a.platform)
    if cmd == "entity":
        return s.entity(" ".join(_need(a, 1, '"NAME"')), platform=a.platform)
    if cmd == "neighbors":
        return s.neighbors(" ".join(_need(a, 1, '"NAME"')), hops=a.hops, relation=a.relation, platform=a.platform)
    if cmd == "path":
        x, y = _need(a, 2, '"A" "B"')[:2]
        return s.path(x, y, at=a.at, include_ended=a.history)
    if cmd == "facts":
        return s.facts_query(platform=a.platform, since=a.since, until=a.until, relation=a.relation,
                             entity_type=a.type, contains=a.contains, current_only=a.current, limit=a.limit)
    if cmd == "relations":
        return s.relations(platform=a.platform)
    if cmd == "show":
        return s.episode(_need(a, 1, '"DOC_ID:Lx-Ly" | CHUNK_ID')[0])
    if cmd in ("page-get", "page-save"):
        from kg import pages
        names = _need(a, 1, '"NAME" ["NAME2"]')[:2]
        if cmd == "page-get":
            return pages.get(s, names)
        if not a.file:
            raise paths.AtlasError("page-save needs --file PAGE.md")
        return pages.save(s, names, Path(a.file).read_text(encoding="utf-8"))
    raise paths.AtlasError(f"unknown command {cmd!r}; run with -h for the list")


def cli_find(query, cli=None, limit=100):
    """Lines in the CLI command maps that contain every word of the query (case-insensitive)."""
    d = paths.cli_dir()
    words = [w.lower() for w in query.split() if w]
    files = sorted(d.glob(f"{cli}.md" if cli else "*.md")) if d.is_dir() else []
    if not files:
        return f"no CLI maps{' for ' + cli if cli else ''} in {d}; build them with scripts/cli_map.py"
    hits = []
    for f in files:
        meta = {}
        for i, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
            if i < 10 and line.startswith(("as_of:", "version:")):
                key, val = line.split(":", 1)
                meta[key] = val.strip()
                continue
            low = line.lower()
            if all(w in low for w in words):
                hits.append(f"[cli/{f.stem}:L{i}] (as of {meta.get('as_of', '?')}, v{meta.get('version', '?')}) "
                            f"{line.strip()}")
    more = f"\n... {len(hits) - limit} more; add words" if len(hits) > limit else ""
    return "\n".join(hits[:limit]) + more if hits else f"no CLI map line contains all of: {query}"


if __name__ == "__main__":
    sys.exit(main())
