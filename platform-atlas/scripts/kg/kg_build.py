"""Build the platform knowledge graph from the extraction agents' output (Graphiti-style temporal graph).

Steps (each run by `scripts/atlas.py`; the model work between them is done by agents):
  dedupe-candidates  entity names that may be the same entity -> work/dedupe/tasks/*.json
  edge-candidates    facts that may repeat or replace each other -> work/edges/tasks/*.json
  summary-tasks      entities whose summary is missing or out of date -> work/summaries/tasks/*.json
  build              kg.sqlite, with its keyword search index (no models)

Ids are content hashes, so decisions made in earlier runs stay valid and only new groups go to agents.
Facts between two entities are compared per entity pair; facts about one entity are compared per
entity and relation type (for example every HAS_STATUS fact about one service), so a note with a later
as-of date that reports a new status, limit or version marks the older fact as replaced.
"""
import hashlib
import json
import re
import sqlite3
import time
from collections import Counter, defaultdict
from difflib import SequenceMatcher

from . import paths, search_index
from .corpus import Corpus
from .vocab import canonical

TASK_SIZE = {"dedupe": 60, "edges": 25}
SAME_SPELLING = 0.88  # names this similar (letters and digits only) may be duplicates
SAME_WORD = 0.75  # two words this similar count as the same word ("prioritize", "prioritization")
MAX_BLOCK = 200  # names sharing a word are compared pairwise; a word shared by more names is too common to use
RARE_WORD = 3  # a one-word name inside a longer name is a candidate only if at most this many names use the word
NAME_STOP = frozenset("a an and at by for in of on or the to with".split())
SUMMARY_TASK_TOKENS = 30_000
SUMMARY_MIN_FACTS = 4


def norm(name):
    s = (name or "").lower().replace("&", " and ")
    s = re.sub(r"[\"'’`().,:;!?\[\]{}]", " ", s)
    s = re.sub(r"\b(the|inc|llc|ltd|corp|corporation|co)\b", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def _words(key):
    return [w for w in re.split(r"[^0-9a-z]+", key) if w and w not in NAME_STOP]


def _same_word(a, b):
    if a == b or (min(len(a), len(b)) >= 3 and (a.startswith(b) or b.startswith(a))):
        return True
    return min(len(a), len(b)) >= 4 and SequenceMatcher(None, a, b).ratio() >= SAME_WORD


def _maybe_same(a, b, wa, wb, df):
    """Cheap duplicate test for two normalized names (the dedupe agents make the call): near-identical
    spelling, or every word of the shorter name matching a word of the longer one ("Excel" and
    "Microsoft Excel", "triage skill" and "AI triage prioritize skill")."""
    sa, sb = re.sub(r"[^0-9a-z]", "", a), re.sub(r"[^0-9a-z]", "", b)
    if sa and sb and SequenceMatcher(None, sa, sb).ratio() >= SAME_SPELLING:
        return True
    short, long = (wa, wb) if len(wa) <= len(wb) else (wb, wa)
    if not short or (len(short) == 1 and (len(short[0]) < 4 or df[short[0]] > RARE_WORD)):
        return False
    return all(any(_same_word(s, w) for w in long) for s in short)


def _h(s, n=10):
    return hashlib.sha1(s.encode("utf-8")).hexdigest()[:n]


class Builder:
    def __init__(self, root=None):
        self.c = Corpus(root)
        self.dir = self.c.dir
        self.work = self.c.work

    # ---------- inputs
    def rows(self):
        man = self.c.manifest()
        valid = {c["chunk_id"]: c for c in self.c.chunks()}
        seen, rows = set(), []
        for doc_id in man:
            for r in paths.read_jsonl(self.c.output_path(doc_id)) if self.c.output_path(doc_id).is_file() else []:
                cid = r.get("chunk_id")
                if cid in valid and cid not in seen:
                    seen.add(cid)
                    r["doc_id"] = valid[cid]["doc_id"]
                    r["date"] = r.get("date") or man[r["doc_id"]]["date"]
                    rows.append(r)
        return rows

    def raw_entities(self, rows):
        ents = {}
        for r in rows:
            names = {e.get("name"): e for e in r.get("entities", []) if e.get("name")}
            for f in r.get("facts", []):
                for side in ("source", "target"):
                    n = f.get(side)
                    if n and n not in names:
                        names[n] = {"name": n, "type": "Other", "summary": ""}
            for n, e in names.items():
                k = norm(n)
                if not k:
                    continue
                x = ents.setdefault(k, {"key": k, "names": Counter(), "types": Counter(), "summaries": [], "episodes": 0,
                                       "platforms": Counter()})
                x["names"][n] += 1
                x["types"][e.get("type") or "Other"] += 1
                x["episodes"] += 1
                x["platforms"][paths.platform_of(r["doc_id"])] += 1
                if e.get("summary") and len(x["summaries"]) < 6:
                    x["summaries"].append(f"{r['date']}: {e['summary']}")
        return ents

    def _decisions(self, stage):
        d = self.work / stage / "decisions"
        files = sorted(d.glob("*.json"), key=lambda p: p.stat().st_mtime) if d.is_dir() else []
        out = []
        for p in files:
            try:
                out.append(json.loads(p.read_text(encoding="utf-8")))
            except ValueError:
                continue
        return out

    def _write_tasks(self, stage, groups, size):
        tdir = self.work / stage / "tasks"
        if tdir.exists():
            for p in tdir.glob("*.json"):
                p.unlink()
        tdir.mkdir(parents=True, exist_ok=True)
        (self.work / stage / "decisions").mkdir(parents=True, exist_ok=True)
        tasks = []
        for i in range(0, len(groups), size):
            part = groups[i:i + size]
            name = part[0]["group_id"]
            paths.write_json(tdir / f"{name}.json", {"stage": stage, "groups": part})
            tasks.append(str(tdir / f"{name}.json").replace("\\", "/"))
        return tasks

    # ---------- entity resolution
    def dedupe_candidates(self):
        rows = self.rows()
        ents = self.raw_entities(rows)
        keys = sorted(ents)
        paths.write_json(self.work / "entities_raw.json",
                         {k: {**v, "names": dict(v["names"]), "types": dict(v["types"]), "platforms": dict(v["platforms"])}
                          for k, v in ents.items()})
        if len(keys) < 2:
            return {"entities": len(keys), "groups": 0, "new_groups": 0, "tasks": []}
        parent = list(range(len(keys)))

        def find(i):
            while parent[i] != i:
                parent[i] = parent[parent[i]]
                i = parent[i]
            return i

        idx = {k: i for i, k in enumerate(keys)}
        by_first = defaultdict(list)
        for k in keys:
            by_first[k.split(" ")[0]].append(k)
        for k in keys:
            toks = k.split(" ")
            if len(toks) == 1:
                for other in by_first.get(toks[0], []):
                    if other != k:
                        parent[find(idx[k])] = find(idx[other])
            else:
                acro = "".join(t[0] for t in toks if t)
                if acro in idx:
                    parent[find(idx[k])] = find(idx[acro])
        # Spelling and word matches, compared within names that share a word or their first three letters.
        words = {k: _words(k) for k in keys}
        df = Counter(w for k in keys for w in set(words[k]))
        blocks = defaultdict(set)
        for k in keys:
            for w in words[k]:
                if len(w) >= 3:
                    blocks[w].add(k)
            blocks["#" + re.sub(r"[^0-9a-z]", "", k)[:3]].add(k)
        compared = set()
        for block in blocks.values():
            if len(block) < 2 or len(block) > MAX_BLOCK:
                continue
            bl = sorted(block)
            for i, a in enumerate(bl):
                for b in bl[i + 1:]:
                    if (a, b) in compared:
                        continue
                    compared.add((a, b))
                    if _maybe_same(a, b, words[a], words[b], df):
                        parent[find(idx[a])] = find(idx[b])
        groups = defaultdict(list)
        for k in keys:
            groups[find(idx[k])].append(k)
        reviewed = {g for d in self._decisions("dedupe") for g in d.get("groups", [])}
        out = []
        for g in groups.values():
            if len(g) < 2:
                continue
            g = sorted(g, key=lambda k: -ents[k]["episodes"])
            for j in range(0, len(g), 15):
                part = g[j:j + 15] if j == 0 else [g[0]] + g[j:j + 14]
                gid = "d" + _h("|".join(sorted(part)))
                if gid in reviewed:
                    continue
                out.append({"group_id": gid, "members": [
                    {"key": k, "names": [n for n, _ in ents[k]["names"].most_common(4)],
                     "type": ents[k]["types"].most_common(1)[0][0], "episodes": ents[k]["episodes"],
                     "platforms": sorted(ents[k]["platforms"]),
                     "summaries": ents[k]["summaries"][:3]} for k in part]})
        tasks = self._write_tasks("dedupe", out, TASK_SIZE["dedupe"])
        return {"entities": len(keys), "new_groups": len(out), "tasks": tasks}

    def canonical_map(self):
        ents = json.loads((self.work / "entities_raw.json").read_text(encoding="utf-8"))
        cmap = {k: k for k in ents}
        for d in self._decisions("dedupe"):
            for m in d.get("merges", []):
                c = m.get("canonical")
                for k in m.get("members", []):
                    if k in cmap and c in cmap:
                        cmap[k] = c
        for k in list(cmap):
            seen = set()
            while cmap[k] != k and k not in seen:
                seen.add(k)
                cmap[k] = cmap[cmap[k]]
        return ents, cmap

    # ---------- facts
    def resolved_facts(self):
        rows = self.rows()
        ents, cmap = self.canonical_map()
        facts, off_list, used = [], 0, set()
        for r in rows:
            for i, f in enumerate(r.get("facts", [])):
                s = cmap.get(norm(f.get("source")))
                t = cmap.get(norm(f.get("target"))) if f.get("target") else None
                text = (f.get("fact") or "").strip()
                if not s or not text:
                    continue
                rel, ok = canonical(f.get("relation"), bool(t))
                off_list += not ok
                fid = "f" + _h(f"{r['chunk_id']}|{text}")
                if fid in used:
                    fid = "f" + _h(f"{r['chunk_id']}|{text}|{i}")
                used.add(fid)
                ln = f.get("lines") or [None, None]
                facts.append({"fid": fid, "src": s, "dst": t, "relation": rel, "fact": text,
                              "valid_at": f.get("valid_at"), "invalid_at": f.get("invalid_at"),
                              "chunk_id": r["chunk_id"], "doc_id": r["doc_id"], "doc_date": r["date"],
                              "platform": paths.platform_of(r["doc_id"]),
                              "start_line": ln[0] if len(ln) > 0 else None, "end_line": ln[1] if len(ln) > 1 else None})
        return ents, cmap, facts, off_list

    def edge_candidates(self):
        ents, cmap, facts, off_list = self.resolved_facts()
        paths.write_json(self.work / "facts_resolved.json", facts)
        groups = defaultdict(list)
        for f in facts:
            key = tuple(sorted([f["src"], f["dst"]])) if f["dst"] else (f["src"], "@" + f["relation"])
            groups[key].append(f)
        reviewed = {g for d in self._decisions("edges") for g in d.get("groups", [])}
        out = []
        for key, fs in groups.items():
            if len(fs) < 2 or len({f["chunk_id"] for f in fs}) < 2:
                continue
            fs = sorted(fs, key=lambda f: (f["valid_at"] or f["doc_date"] or "", f["doc_date"] or ""))
            for j in range(0, len(fs), 40):
                part = fs[j:j + 40]
                gid = "e" + _h("|".join(sorted(f["fid"] for f in part)))
                if gid in reviewed:
                    continue
                out.append({"group_id": gid, "entities": list(key), "facts": [
                    {k: f[k] for k in ("fid", "src", "relation", "dst", "fact", "valid_at", "invalid_at", "doc_date", "doc_id")}
                    for f in part]})
        tasks = self._write_tasks("edges", out, TASK_SIZE["edges"])
        return {"facts": len(facts), "facts_with_relation_off_list": off_list,
                "entities_after_merge": len(set(cmap.values())), "new_groups": len(out), "tasks": tasks}

    def _edge_state(self):
        dup_of, expired = {}, {}
        for d in self._decisions("edges"):
            for x in d.get("decisions", []):
                fid = x.get("fid")
                if not fid:
                    continue
                dup_of.pop(fid, None)
                expired.pop(fid, None)
                if x.get("duplicate_of"):
                    dup_of[fid] = x["duplicate_of"]
                if x.get("invalidated_by"):
                    expired[fid] = (x["invalidated_by"], x.get("invalid_at"))
        return dup_of, expired

    # ---------- summaries
    def _entity_facts(self, facts, dup_of):
        by = defaultdict(list)
        for f in facts:
            if f["fid"] in dup_of:
                continue
            by[f["src"]].append(f)
            if f["dst"]:
                by[f["dst"]].append(f)
        return by

    def _valid_summaries(self):
        out = {}
        tdir, ddir = self.work / "summaries" / "tasks", self.work / "summaries" / "decisions"
        if not ddir.is_dir():
            return out
        for p in sorted(ddir.glob("*.json"), key=lambda p: p.stat().st_mtime):
            try:
                done = json.loads(p.read_text(encoding="utf-8"))
                hashes = json.loads((self.work / "summaries" / "hashes" / p.name).read_text(encoding="utf-8"))
            except (ValueError, OSError):
                continue
            for s in done.get("summaries", []):
                if s.get("key") in hashes and s.get("summary"):
                    out[s["key"]] = (hashes[s["key"]], s["summary"])
        return out

    def summary_tasks(self):
        facts = json.loads((self.work / "facts_resolved.json").read_text(encoding="utf-8"))
        ents, cmap = self.canonical_map()
        dup_of, _ = self._edge_state()
        by = self._entity_facts(facts, dup_of)
        names = defaultdict(Counter)
        for k, v in ents.items():
            names[cmap[k]].update(v["names"])
        have = self._valid_summaries()
        tasks = []
        for k, fs in by.items():
            if len(fs) < SUMMARY_MIN_FACTS:
                continue
            fh = _h("|".join(sorted(f["fid"] for f in fs)))
            if have.get(k, (None,))[0] == fh:
                continue
            fs = sorted(fs, key=lambda f: f["valid_at"] or f["doc_date"] or "")
            tasks.append({"key": k, "name": names[k].most_common(1)[0][0] if names[k] else k, "facts_hash": fh,
                          "facts": [f"{f['valid_at'] or f['doc_date']}: {f['fact']}" for f in fs[-60:]]})
        groups, cur, size = [], [], 0
        for t in sorted(tasks, key=lambda t: t["key"]):
            s = len(json.dumps(t)) // 4
            if cur and size + s > SUMMARY_TASK_TOKENS:
                groups.append(cur)
                cur, size = [], 0
            cur.append(t)
            size += s
        if cur:
            groups.append(cur)
        tdir = self.work / "summaries" / "tasks"
        hdir = self.work / "summaries" / "hashes"
        if tdir.exists():
            for p in tdir.glob("*.json"):
                p.unlink()
        for d in (tdir, hdir, self.work / "summaries" / "decisions"):
            d.mkdir(parents=True, exist_ok=True)
        files = []
        for g in groups:
            name = "m" + _h("|".join(t["key"] + t["facts_hash"] for t in g))
            paths.write_json(tdir / f"{name}.json", {"stage": "summaries",
                                                     "entities": [{k: t[k] for k in ("key", "name", "facts")} for t in g]})
            paths.write_json(hdir / f"{name}.json", {t["key"]: t["facts_hash"] for t in g})
            files.append(str(tdir / f"{name}.json").replace("\\", "/"))
        return {"entities_needing_summary": len(tasks), "tasks": files}

    # ---------- build
    def build(self):
        stale = self.c.ensure_sources()
        ents, cmap = self.canonical_map()
        facts = json.loads((self.work / "facts_resolved.json").read_text(encoding="utf-8"))
        dup_of, expired = self._edge_state()
        valid = self._valid_summaries()
        by = self._entity_facts(facts, dup_of)
        canon = defaultdict(lambda: {"names": Counter(), "types": Counter(), "summaries": [], "platforms": Counter()})
        for k, v in ents.items():
            c = canon[cmap[k]]
            c["names"].update(v["names"])
            c["types"].update(v["types"])
            c["summaries"] += v["summaries"]
            c["platforms"].update(v.get("platforms", {}))
        tmp = self.dir / "kg.sqlite.tmp"
        if tmp.exists():
            tmp.unlink()
        db = sqlite3.connect(tmp)
        db.executescript("""
          CREATE TABLE meta(key TEXT PRIMARY KEY, value TEXT);
          CREATE TABLE entities(key TEXT PRIMARY KEY, name TEXT, type TEXT, aliases TEXT, summary TEXT, facts INT,
            platforms TEXT);
          CREATE TABLE facts(fid TEXT PRIMARY KEY, src TEXT, dst TEXT, relation TEXT, fact TEXT, valid_at TEXT,
            invalid_at TEXT, expired_by TEXT, doc_date TEXT, platform TEXT, episodes TEXT);
          CREATE TABLE episodes(chunk_id TEXT, fid TEXT, doc_id TEXT, start_line INT, end_line INT);
          CREATE INDEX facts_src ON facts(src); CREATE INDEX facts_dst ON facts(dst);
          CREATE INDEX episodes_fid ON episodes(fid); CREATE INDEX facts_platform ON facts(platform);
        """)
        used = {f["src"] for f in facts} | {f["dst"] for f in facts if f["dst"]}
        n_ent = 0
        for k, c in canon.items():
            if k not in used:
                continue
            fs = by.get(k, [])
            fh = _h("|".join(sorted(f["fid"] for f in fs)))
            summ = valid[k][1] if k in valid and valid[k][0] == fh else (
                valid[k][1] if k in valid else " ".join(s.split(": ", 1)[-1] for s in c["summaries"][-3:]))
            name = c["names"].most_common(1)[0][0]
            aliases = [n for n in c["names"] if n != name]
            db.execute("INSERT INTO entities VALUES(?,?,?,?,?,?,?)", (k, name, c["types"].most_common(1)[0][0],
                       json.dumps(aliases), summ, len(fs), json.dumps(sorted(c["platforms"]))))
            n_ent += 1
        kept = {}
        for f in facts:
            root, seen = f["fid"], set()
            while root in dup_of and root not in seen:
                seen.add(root)
                root = dup_of[root]
            kept.setdefault(root, []).append(f) if root != f["fid"] else kept.setdefault(root, []).insert(0, f)
        byid = {f["fid"]: f for f in facts}
        n = n_exp = 0
        for fid, group in kept.items():
            f = byid.get(fid)
            if not f:
                continue
            inv, exp = f["invalid_at"], None
            if fid in expired and expired[fid][0] in byid:
                exp, inv2 = expired[fid]
                inv = inv or inv2 or byid[exp]["valid_at"] or byid[exp]["doc_date"]
                n_exp += 1
            eps = sorted({g["chunk_id"] for g in group})
            db.execute("INSERT INTO facts VALUES(?,?,?,?,?,?,?,?,?,?,?)", (fid, f["src"], f["dst"], f["relation"], f["fact"],
                       f["valid_at"], inv, exp, f["doc_date"], f.get("platform") or paths.platform_of(f["doc_id"]),
                       json.dumps(eps)))
            for g in group:
                db.execute("INSERT INTO episodes VALUES(?,?,?,?,?)", (g["chunk_id"], fid, g["doc_id"], g["start_line"], g["end_line"]))
            n += 1
        stats = {"entities": n_ent, "facts": n, "duplicates_folded": len(dup_of),
                 "replaced": n_exp, "built_at": time.strftime("%Y-%m-%dT%H:%M:%S")}
        for k, v in stats.items():
            db.execute("INSERT INTO meta VALUES(?,?)", (k, str(v)))
        search_index.index(db)
        db.commit()
        db.close()
        tmp.replace(self.dir / "kg.sqlite")
        if stale:
            stats["notes_changed_since_extraction"] = stale
        return stats
