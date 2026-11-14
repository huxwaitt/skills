"""Query side of the platform graph: one in-memory store, loaded from `<kb>/graph/kg.sqlite`.

Every fact line shows when it became true, whether it ENDED (and which fact replaced it), its **as-of
date** (the date of the note it came from, i.e. when it was last checked against vendor sources), the
platform, and its citations (`doc_id:Lstart-Lend`), so the source passage is one call away. Search is
keyword search (see search_index.py): no models.
"""
import datetime
import difflib
import json
import sqlite3
from collections import Counter, defaultdict, deque

from . import paths, search_index
from .corpus import Corpus
from .kg_build import norm

STALE_DAYS = 90  # notes older than this get a freshness warning


def today():
    return datetime.date.today().isoformat()


def _current(f, at=None):
    """True when the fact holds at date `at` (default today). A fact with a future end date, such as a
    scheduled retirement or price change, is still current until that date."""
    end = f["invalid_at"]
    if at:
        start = f["valid_at"] or f["doc_date"] or ""
        return start <= at and (not end or end > at)
    if end:
        return end > today()
    return not f["expired_by"]


def age_days(day):
    try:
        return (datetime.date.today() - datetime.date.fromisoformat(day)).days
    except (TypeError, ValueError):
        return None


class Store:
    def __init__(self, root=None):
        self.corpus = Corpus(root)
        self.dir = self.corpus.dir
        self.db_path = self.dir / "kg.sqlite"
        if not self.db_path.is_file():
            raise paths.AtlasError("No graph yet. Run `atlas.py build` (seconds, no models); if that reports no "
                                   "extraction output, run the build steps in SKILL.md.")
        db = sqlite3.connect(self.db_path)
        db.row_factory = sqlite3.Row
        self.meta = {r["key"]: r["value"] for r in db.execute("SELECT * FROM meta")}
        self.ents = {r["key"]: dict(r) for r in db.execute("SELECT * FROM entities")}
        self.facts = {r["fid"]: dict(r) for r in db.execute("SELECT * FROM facts")}
        self.eps = defaultdict(list)
        for r in db.execute("SELECT * FROM episodes"):
            self.eps[r["fid"]].append(dict(r))
        db.close()
        self.adj = defaultdict(list)
        for f in self.facts.values():
            self.adj[f["src"]].append(f["fid"])
            if f["dst"]:
                self.adj[f["dst"]].append(f["fid"])
        self.alias = {}
        for k, e in self.ents.items():
            for n in [e["name"]] + json.loads(e["aliases"]):
                self.alias.setdefault(norm(n), k)
        self.chunks = None

    # ---------- helpers
    def name(self, key):
        return self.ents[key]["name"] if key in self.ents else (key or "")

    def fact_line(self, f, refs=True):
        dst = f" -> {self.name(f['dst'])}" if f["dst"] else ""
        end = f["invalid_at"]
        when = f"valid {f['valid_at'] or '?'}" + (f", {'ENDS' if end > today() else 'ENDED'} {end}" if end else "")
        if f.get("expired_by"):
            when += f" (replaced by {f['expired_by']})"
        s = f"{self.name(f['src'])} -[{f['relation']}]{dst}: {f['fact']} ({when}; as of {f['doc_date']}; {f['platform']})"
        if refs:
            eps = self.eps.get(f["fid"], [])[:3]
            s = f"{f['fid']} | " + s + " | cite: " + ", ".join(
                f"[{e['doc_id']}:L{e['start_line']}-L{e['end_line']}]" for e in eps)
        return s

    def _platform_ok(self, f, platform):
        return not platform or f["platform"] == platform

    def resolve(self, name):
        """(key, exact): exact or alias match first, then the closest spelling, then the best keyword match."""
        k = norm(name)
        if k in self.alias:
            return self.alias[k], True
        close = difflib.get_close_matches(k, list(self.alias), n=1, cutoff=0.8)
        if close:
            return self.alias[close[0]], False
        hits = search_index.find(self.db_path, "entity_search", name, 1)
        return (hits[0][0], False) if hits and hits[0][0] in self.ents else (None, False)

    # ---------- tools
    def search(self, query, k=20, platform=None, at=None, current_only=False):
        """Facts matching the query's words, best first."""
        k = max(1, min(int(k or 20), 60))
        filtered = bool(at or current_only or platform)
        out = []
        for fid, _ in search_index.find(self.db_path, "fact_search", query, 800 if filtered else k):
            f = self.facts.get(fid)
            if f and self._platform_ok(f, platform) and (not (at or current_only) or _current(f, at)):
                out.append(f)
            if len(out) >= k:
                break
        return "\n".join(self.fact_line(f) for f in out) or (
            "no facts matched these words; search again with other words (product names, synonyms, the vendor's "
            "own terms), or use nodes, entity or facts")

    def nodes(self, query, k=10, platform=None):
        """Entities whose names, aliases or summary match the query's words; an exact name comes first."""
        k = max(1, min(int(k or 10), 40))
        keys = []
        exact = self.alias.get(norm(query))
        if exact:
            keys.append(exact)
        for key, _ in search_index.find(self.db_path, "entity_search", query, 200):
            if key in self.ents and key not in keys:
                keys.append(key)
        lines = []
        for key in keys:
            e = self.ents[key]
            plats = json.loads(e.get("platforms") or "[]")
            if platform and platform not in plats:
                continue
            lines.append(f"{e['name']} ({e['type']}; {e['facts']} facts; {', '.join(plats)}): {e['summary']}")
            if len(lines) >= k:
                break
        return "\n".join(lines) or "no entities matched these words; try other words or part of the name"

    def entity(self, name, platform=None):
        key, exact = self.resolve(name)
        if key is None:
            return f"no entity matching {name!r}"
        e = self.ents[key]
        fs = sorted((self.facts[i] for i in self.adj[key] if self._platform_ok(self.facts[i], platform)),
                    key=lambda f: (not _current(f), f["relation"], f["valid_at"] or f["doc_date"] or ""))
        note = "" if exact else f"(no exact match for {name!r}; closest entity shown)\n"
        head = (f"{e['name']} ({e['type']}; platforms {', '.join(json.loads(e.get('platforms') or '[]')) or '-'}); "
                f"aliases {', '.join(json.loads(e['aliases'])) or '-'}\nSummary: {e['summary']}\n"
                f"{len(fs)} facts (current first):")
        body = [self.fact_line(f) for f in fs[:150]]
        if len(fs) > 150:
            body.append(f"... {len(fs) - 150} more; narrow with `facts` or `search`")
        return note + head + "\n" + "\n".join(body)

    def neighbors(self, name, hops=1, relation=None, platform=None):
        hops = max(1, min(int(hops or 1), 2))
        key, _ = self.resolve(name)
        if key is None:
            return f"no entity matching {name!r}"
        frontier, seen, lines = {key}, {key}, []
        for h in range(hops):
            nxt = set()
            for k in frontier:
                for fid in self.adj[k]:
                    f = self.facts[fid]
                    if relation and f["relation"] != relation.upper() or not self._platform_ok(f, platform):
                        continue
                    lines.append(f"hop {h + 1}: " + self.fact_line(f))
                    for o in (f["src"], f["dst"]):
                        if o and o not in seen:
                            seen.add(o)
                            nxt.add(o)
            frontier = nxt
        lines = list(dict.fromkeys(lines))
        more = f"\n... {len(lines) - 200} more" if len(lines) > 200 else ""
        return f"{self.name(key)}: {len(lines)} facts within {hops} hop(s)\n" + "\n".join(lines[:200]) + more

    def path(self, a, b, at=None, include_ended=False):
        """Shortest chain of facts between two entities, using every qualifying fact between each pair."""
        ka, _ = self.resolve(a)
        kb, _ = self.resolve(b)
        if not (ka and kb):
            return f"no matching entities for {a!r} and {b!r}"
        pairs = defaultdict(list)
        for f in self.facts.values():
            if f["dst"] and (include_ended or _current(f, at)):
                pairs[tuple(sorted((f["src"], f["dst"])))].append(f)
        nodes = _shortest_path(pairs, ka, kb)
        if not nodes:
            return f"no {'current ' if not include_ended else ''}connection between {self.name(ka)} and {self.name(kb)}"
        lines = [" -> ".join(self.name(n) for n in nodes)]
        for u, v in zip(nodes, nodes[1:]):
            fs = sorted(pairs[tuple(sorted((u, v)))], key=lambda f: f["valid_at"] or f["doc_date"] or "", reverse=True)
            lines.append(f"  {self.name(u)} <-> {self.name(v)} ({len(fs)} fact{'s' if len(fs) != 1 else ''}):")
            lines += ["    " + self.fact_line(f) for f in fs[:5]]
            if len(fs) > 5:
                lines.append(f"    ... {len(fs) - 5} more")
        return "\n".join(lines)

    def facts_query(self, platform=None, since=None, until=None, relation=None, entity_type=None, contains=None,
                    current_only=False, limit=100):
        limit = max(1, min(int(limit or 100), 400))
        rows = []
        for f in self.facts.values():
            d = f["valid_at"] or f["doc_date"] or ""
            if since and d < since or until and d > until or not self._platform_ok(f, platform):
                continue
            if relation and f["relation"] != relation.upper():
                continue
            if current_only and not _current(f):
                continue
            if entity_type and entity_type.lower() not in {(self.ents.get(x) or {}).get("type", "").lower()
                                                           for x in (f["src"], f["dst"])}:
                continue
            if contains and contains.lower() not in f["fact"].lower():
                continue
            rows.append((d, f))
        rows.sort(key=lambda r: r[0])
        lines = [self.fact_line(f) for _, f in rows[:limit]]
        if len(rows) > limit:
            lines.append(f"... {len(rows) - limit} more; narrow the filters")
        return f"{len(rows)} facts\n" + "\n".join(lines)

    def relations(self, platform=None):
        c = Counter(f["relation"] for f in self.facts.values() if self._platform_ok(f, platform))
        return "\n".join(f"{r}: {n}" for r, n in c.most_common())

    def episode(self, ref):
        """The passage behind a chunk id, or a `doc_id:Lx-Ly` citation."""
        if ":L" in ref:
            doc_id, rng = ref.strip("[]").rsplit(":L", 1)
            a, _, b = rng.partition("-L")
            return self.corpus.show(doc_id, int(a), int(b or a))
        if self.chunks is None:
            self.chunks = {c["chunk_id"]: c for c in self.corpus.chunks()}
        c = self.chunks.get(ref)
        if not c:
            return f"no passage {ref!r}"
        return f"{c['doc_id']} lines {c['start_line']}-{c['end_line']}\n{self.corpus.passage(c)}"

    def subject_facts(self, names):
        """Fact ids touching one entity, or linking two entities (for page freshness)."""
        keys = [self.resolve(n)[0] for n in names]
        if None in keys:
            raise paths.AtlasError(f"no entity matching {names[keys.index(None)]!r}")
        if len(keys) == 1:
            return keys, sorted(self.adj[keys[0]])
        a, b = keys
        return keys, sorted(fid for fid in self.adj[a] if {self.facts[fid]["src"], self.facts[fid]["dst"]} == {a, b})


def _shortest_path(pairs, a, b):
    """Breadth-first shortest chain of entity keys from a to b over the given entity pairs, or None."""
    adj = defaultdict(set)
    for u, v in pairs:
        adj[u].add(v)
        adj[v].add(u)
    if a not in adj or b not in adj:
        return [a] if a == b else None
    prev, queue = {a: None}, deque([a])
    while queue:
        u = queue.popleft()
        if u == b:
            chain = []
            while u is not None:
                chain.append(u)
                u = prev[u]
            return chain[::-1]
        for v in sorted(adj[u]):
            if v not in prev:
                prev[v] = u
                queue.append(v)
    return None


def status(root=None):
    """Per-platform coverage and freshness, read from the manifest and the graph file (no store load)."""
    c = Corpus(root)
    reg = paths.registry()["platforms"]
    man = list(c.manifest().values())
    files = dict(c.scan())
    per = {}
    for slug, p in reg.items():
        per[slug] = {"platform": slug, "name": p["name"], "notes": 0, "parts": {}, "as_of": None, "age_days": None}
    for d in man:
        row = per.setdefault(d["platform"], {"platform": d["platform"], "name": d["platform"], "notes": 0,
                                             "parts": {}, "as_of": None, "age_days": None})
        row["notes"] += 1
        part = d.get("part") or "other"
        row["parts"][part] = max(row["parts"].get(part, ""), d["date"])
    for row in per.values():
        if row["parts"]:
            row["as_of"] = min(row["parts"].values())
            row["age_days"] = age_days(row["as_of"])
        row["stale"] = row["age_days"] is None or row["age_days"] > STALE_DAYS
    graph = None
    db_path = c.dir / "kg.sqlite"
    if db_path.is_file():
        db = sqlite3.connect(db_path)
        graph = dict(db.execute("SELECT key, value FROM meta").fetchall())
        for plat, n, cur in db.execute("SELECT platform, COUNT(*), SUM(CASE WHEN invalid_at IS NOT NULL THEN invalid_at > ? "
                                       "ELSE expired_by IS NULL END) FROM facts GROUP BY platform", (today(),)):
            if plat in per:
                per[plat]["facts"], per[plat]["current_facts"] = n, cur
        db.close()
    unprepared = sorted(set(files) - {d["doc_id"] for d in man})
    return {"kb": str(c.root), "graph": graph, "stale_after_days": STALE_DAYS,
            "notes_not_yet_prepared": unprepared, "platforms": list(per.values()),
            "cli_maps": sorted(p.stem for p in paths.cli_dir(root).glob("*.md")) if paths.cli_dir(root).is_dir() else []}
