"""On-demand answer pages, written from graph facts only when a question needs more than two sentences.

A page is plain Markdown under `<kb>/graph/pages/`. Its frontmatter records the fact ids it was written
from and the oldest as-of date among them, so it is reused until a fact about its subject is added,
changed or replaced, and anyone reading it sees how old its information is.
"""
import json
import re
import time

from . import paths
from .kg_build import norm
from .kg_store import _current


def _slug(keys):
    return "--".join(re.sub(r"[^a-z0-9]+", "-", norm(k)).strip("-") or "x" for k in keys)[:120]


def _read(p):
    text = p.read_text(encoding="utf-8")
    meta = {}
    if text.startswith("---\n"):
        end = text.find("\n---\n", 4)
        if end > 0:
            for line in text[4:end].splitlines():
                if ":" in line:
                    k, v = line.split(":", 1)
                    meta[k.strip()] = v.strip()
            text = text[end + 5:]
    return meta, text


def _names(subject):
    names = subject if isinstance(subject, list) else [subject]
    if not 1 <= len(names) <= 2:
        raise paths.AtlasError("A page is about one entity or the relationship between two.")
    return names


def get(store, subject):
    keys, fids = store.subject_facts(_names(subject))
    p = store.dir / "pages" / f"{_slug(keys)}.md"
    out = {"subject": [store.name(k) for k in keys], "path": str(p), "facts_now": len(fids)}
    if not p.is_file():
        return {**out, "exists": False, "stale": True}
    meta, body = _read(p)
    try:
        had = set(json.loads(meta.get("fact_ids", "[]")))
        ended_before = set(json.loads(meta.get("ended_ids", "[]") or "[]"))
    except ValueError:
        had, ended_before = set(), set()
    new = sorted(set(fids) - had)
    gone = sorted(had - set(fids))
    changed = [fid for fid in fids if fid in had and fid not in ended_before
               and not _current(store.facts[fid])]
    stale = bool(new or gone or changed)
    res = {**out, "exists": True, "stale": stale, "written": meta.get("written"), "as_of": meta.get("as_of"),
           "content": body}
    if stale:
        res["new_or_changed_facts"] = [store.fact_line(store.facts[f]) for f in (new + changed)[:60]]
        res["dropped_fact_ids"] = gone
    return res


def save(store, subject, markdown):
    keys, fids = store.subject_facts(_names(subject))
    p = store.dir / "pages" / f"{_slug(keys)}.md"
    p.parent.mkdir(parents=True, exist_ok=True)
    ended = [f for f in fids if not _current(store.facts[f])]
    current = [store.facts[f]["doc_date"] for f in fids if f not in ended and store.facts[f]["doc_date"]]
    head = ["---", f"subject: {' and '.join(store.name(k) for k in keys)}", f"entities: {json.dumps(keys)}",
            f"as_of: {min(current) if current else ''}", f"written: {time.strftime('%Y-%m-%dT%H:%M:%S')}",
            f"fact_ids: {json.dumps(fids)}", f"ended_ids: {json.dumps(ended)}", "---", ""]
    p.write_text("\n".join(head) + markdown.strip() + "\n", encoding="utf-8", newline="\n")
    return {"path": str(p), "facts": len(fids), "as_of": min(current) if current else None}
