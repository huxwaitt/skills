"""Notes in, extraction batches out.

`prepare` scans `<kb>/notes/<platform>/`, converts each file to numbered text under `<kb>/graph/sources/`
(line numbers in citations refer to these files), splits it into chunks of about 1,200 tokens, and
groups notes that still need extraction into batches of about 24,000 tokens, one batch per extraction
agent. Unchanged notes are skipped; changed or deleted notes lose their old extraction output so the
next build drops their facts.

A note's date is its **as-of date**: the day its facts were checked against the vendor's sources. It
comes from the `as_of` frontmatter field, else a date in the file name, else the file's modified time.
"""
import hashlib
import re
import time
from pathlib import Path

from . import paths
from .convert import SUPPORTED, ConversionError, convert, document_date

GRAPH_TARGET = 4800     # characters per chunk, about 1,200 tokens
LONG_LINE = 1800        # lines longer than this are read in segments
BATCH_TARGET = 24_000   # tokens of note text per extraction agent (notes are dense: output, not reading, is the cost)
# Rough rate for the whole build (extraction, entity merges, replaced-fact checks, summaries), pricing the
# agents' tokens at Claude Opus API list prices. An estimate to show before spending, not a quote.
USD_PER_MILLION_TOKENS = 69.0


def est_tokens(s):
    return max(1, len(s) // 4)


def frontmatter(lines):
    """Return (fields, body_start_line_1based)."""
    if not lines or lines[0].strip() != "---":
        return {}, 1
    fields = {}
    for i in range(1, min(len(lines), 200)):
        if lines[i].strip() == "---":
            return fields, i + 2
        m = re.match(r"^([A-Za-z_]+):\s*(.*)$", lines[i])
        if m:
            fields[m.group(1)] = m.group(2).strip().strip('"')
    return fields, 1


def chunks_for(doc_id, lines, body_start):
    """Split body lines into chunks of about GRAPH_TARGET characters. Overlong lines are split by characters."""
    stem = hashlib.sha1(doc_id.encode("utf-8")).hexdigest()[:8]
    out, buf, buf_len, start = [], [], 0, None

    def cid():
        return f"G-{stem}-{len(out) + 1:03d}"

    def flush(end_line):
        nonlocal buf, buf_len, start
        if buf and any(s.strip() for s in buf):
            out.append({"chunk_id": cid(), "doc_id": doc_id, "start_line": start, "end_line": end_line,
                        "tokens": est_tokens("\n".join(buf))})
        buf, buf_len, start = [], 0, None

    for ln in range(body_start, len(lines) + 1):
        s = lines[ln - 1]
        if len(s) > GRAPH_TARGET * 1.3:
            flush(ln - 1)
            for k in range(0, len(s), GRAPH_TARGET):
                out.append({"chunk_id": cid(), "doc_id": doc_id, "start_line": ln, "end_line": ln,
                            "char_start": k, "char_end": min(len(s), k + GRAPH_TARGET),
                            "tokens": est_tokens(s[k:k + GRAPH_TARGET])})
            continue
        if start is None:
            start = ln
        buf.append(s)
        buf_len += len(s) + 1
        if buf_len >= GRAPH_TARGET:
            flush(ln)
    flush(len(lines))
    return out


def _doc_date(fm, path):
    for key in ("as_of", "date", "retrieved"):
        m = re.match(r"(\d{4}-\d{2}-\d{2})", fm.get(key, ""))
        if m:
            return m.group(1), "frontmatter"
    m = re.search(r"(\d{4}-\d{2}-\d{2})", path.name)
    if m:
        return m.group(1), "filename"
    d = document_date(path)
    if d:
        return d, "document properties"
    return time.strftime("%Y-%m-%d", time.localtime(path.stat().st_mtime)), "file modified time"


def _sha(path):
    """Content hash that ignores line endings, so a CRLF checkout of a note doesn't look like an edit."""
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def _lines(text):
    lines = text.split("\n")
    return lines[:-1] if lines and lines[-1] == "" else lines


class Corpus:
    def __init__(self, root=None):
        self.root = Path(root or paths.kb_root())
        self.notes = paths.notes_dir(self.root)
        self.dir = paths.graph_dir(self.root)
        self.sources = self.dir / "sources"
        self.work = self.dir / "work"
        self.extract = self.work / "extract"
        self.batches = self.work / "batches"

    # ---------- manifest and chunks
    def manifest(self):
        return {d["doc_id"]: d for d in paths.read_jsonl(self.dir / "manifest.jsonl")}

    def chunks(self):
        return paths.read_jsonl(self.dir / "chunks.jsonl")

    def source_path(self, doc_id):
        return self.sources / (paths.file_key(doc_id) + ".md")

    def output_path(self, doc_id):
        return self.extract / (paths.file_key(doc_id) + ".jsonl")

    def scan(self):
        """[(doc_id, file)] for every supported note under notes/<platform>/."""
        if not self.notes.is_dir():
            return []
        order = {".md": 0, ".markdown": 0, ".txt": 1}
        out, seen = [], set()
        files = sorted(self.notes.rglob("*"), key=lambda f: (str(f.with_suffix("")).lower(), order.get(f.suffix.lower(), 2)))
        for f in files:
            rel = f.relative_to(self.notes)
            if not f.is_file() or len(rel.parts) < 2 or f.name.startswith(("~$", ".")) \
                    or any(p.startswith(".") for p in rel.parts[:-1]) or f.suffix.lower() not in SUPPORTED:
                continue
            doc_id = rel.with_suffix("").as_posix()
            if doc_id in seen:
                doc_id = f"{doc_id}-{f.suffix.lower().lstrip('.')}"
            seen.add(doc_id)
            out.append((doc_id, f))
        return out

    def ensure_sources(self):
        """Recreate numbered source copies missing from a fresh clone, for notes that have not changed.
        Returns doc ids whose note changed or vanished since extraction (run `prepare` for those)."""
        files = dict(self.scan())
        stale = []
        for doc_id, d in self.manifest().items():
            f = files.get(doc_id)
            if f is None or _sha(f) != d.get("sha256"):
                stale.append(doc_id)
                continue
            if not self.source_path(doc_id).is_file():
                self.sources.mkdir(parents=True, exist_ok=True)
                self.source_path(doc_id).write_text(convert(f), encoding="utf-8", newline="\n")
        return stale

    # ---------- prepare
    def prepare(self):
        self.sources.mkdir(parents=True, exist_ok=True)
        self.extract.mkdir(parents=True, exist_ok=True)
        old = self.manifest()
        old_chunks = {}
        for c in self.chunks():
            old_chunks.setdefault(c["doc_id"], []).append(c)
        docs, chunks = [], []
        stats = {"new": [], "changed": [], "unchanged": 0, "removed": [], "failed": []}
        for doc_id, f in self.scan():
            sha = _sha(f)
            prev = old.get(doc_id)
            if prev and prev.get("sha256") == sha:
                if not self.source_path(doc_id).is_file():
                    self.source_path(doc_id).write_text(convert(f), encoding="utf-8", newline="\n")
                docs.append(prev)
                chunks += old_chunks.get(doc_id, [])
                stats["unchanged"] += 1
                continue
            try:
                text = convert(f)
            except (ConversionError, OSError, UnicodeError) as e:
                stats["failed"].append({"file": str(f), "error": str(e)})
                continue
            self.source_path(doc_id).write_text(text, encoding="utf-8", newline="\n")
            lines = _lines(text)
            fm, body_start = frontmatter(lines)
            date, date_source = _doc_date(fm, f)
            doc = {"doc_id": doc_id, "platform": fm.get("platform") or paths.platform_of(doc_id),
                   "part": fm.get("part", ""), "title": fm.get("title") or f.stem,
                   "date": date, "date_source": date_source, "file": f.relative_to(self.root).as_posix(), "sha256": sha,
                   "lines": len(lines), "body_start": body_start,
                   "tokens": est_tokens("\n".join(lines[body_start - 1:])),
                   "long_lines": [i + 1 for i, s in enumerate(lines) if len(s) > LONG_LINE]}
            docs.append(doc)
            chunks += chunks_for(doc_id, lines, body_start)
            (stats["changed"] if prev else stats["new"]).append(doc_id)
            out = self.output_path(doc_id)
            if out.exists():
                out.unlink()
        current = {d["doc_id"] for d in docs}
        for doc_id in old:
            if doc_id not in current:
                stats["removed"].append(doc_id)
                for p in (self.output_path(doc_id), self.source_path(doc_id)):
                    if p.exists():
                        p.unlink()
        docs.sort(key=lambda d: (d["date"] or "", d["doc_id"]))
        paths.write_jsonl(self.dir / "manifest.jsonl", docs)
        paths.write_jsonl(self.dir / "chunks.jsonl", chunks)
        batches = self.make_batches()
        tokens = sum(b["tokens"] for b in batches)
        return {"documents": len(docs), "new": stats["new"], "changed": stats["changed"], "unchanged": stats["unchanged"],
                "removed": stats["removed"], "failed": stats["failed"],
                "dates_from_file_time": [d["doc_id"] for d in docs if d.get("date_source") == "file modified time"],
                "to_extract": {"documents": sum(b["docs"] for b in batches), "tokens": tokens,
                               "batches": [b["file"] for b in batches]},
                "estimate": {"usd": round(tokens / 1e6 * USD_PER_MILLION_TOKENS, 2),
                             "basis": f"rough rate of ${USD_PER_MILLION_TOKENS:.0f} per million note tokens for the whole "
                                      "build at Claude Opus API list prices"}}

    # ---------- extraction status and batches
    def doc_status(self, doc, chunks_by_doc):
        """'done', 'missing' or 'partial' for one note's extraction output."""
        out = self.output_path(doc["doc_id"])
        if not out.is_file():
            return "missing"
        want = {c["chunk_id"] for c in chunks_by_doc.get(doc["doc_id"], [])}
        try:
            rows = paths.read_jsonl(out)
        except ValueError:
            return "partial"
        if any(r.get("empty") for r in rows) and not want:
            return "done"
        got = {r.get("chunk_id") for r in rows}
        return "done" if want <= got else "partial"

    def make_batches(self):
        man = self.manifest()
        by_doc = {}
        for c in self.chunks():
            by_doc.setdefault(c["doc_id"], []).append(c)
        pending = [d for d in man.values() if self.doc_status(d, by_doc) != "done"]
        if self.batches.exists():
            for p in self.batches.glob("b*.json"):
                p.unlink()
        self.batches.mkdir(parents=True, exist_ok=True)
        groups, cur, cur_tok = [], [], 0
        for d in sorted(pending, key=lambda d: (d["platform"], d["date"] or "", d["doc_id"])):
            if cur and cur_tok + d["tokens"] > BATCH_TARGET:
                groups.append(cur)
                cur, cur_tok = [], 0
            cur.append(d)
            cur_tok += d["tokens"]
        if cur:
            groups.append(cur)
        try:
            names = {k: v["name"] for k, v in paths.registry()["platforms"].items()}
        except (OSError, ValueError, KeyError):
            names = {}
        out = []
        for i, g in enumerate(groups, 1):
            bid = f"b{i:03d}"
            payload = {"batch_id": bid, "tokens": sum(d["tokens"] for d in g), "docs": []}
            for d in g:
                payload["docs"].append({
                    "doc_id": d["doc_id"], "platform": d["platform"], "platform_name": names.get(d["platform"], d["platform"]),
                    "title": d["title"], "date": d["date"],
                    "source": str(self.source_path(d["doc_id"])).replace("\\", "/"),
                    "out": str(self.output_path(d["doc_id"])).replace("\\", "/"),
                    "lines": d["lines"], "body_start": d["body_start"], "long_lines": d["long_lines"],
                    "chunks": [{k: c[k] for k in ("chunk_id", "start_line", "end_line", "char_start", "char_end") if k in c}
                               for c in by_doc.get(d["doc_id"], [])]})
            paths.write_json(self.batches / f"{bid}.json", payload)
            out.append({"batch_id": bid, "docs": len(g), "tokens": payload["tokens"],
                        "file": str(self.batches / f"{bid}.json").replace("\\", "/")})
        return out

    def check(self):
        """Extraction completeness and relation types used."""
        from .vocab import canonical
        man = self.manifest()
        by_doc = {}
        for c in self.chunks():
            by_doc.setdefault(c["doc_id"], []).append(c)
        status = {"done": 0, "missing": [], "partial": []}
        facts = off_list = 0
        for d in man.values():
            s = self.doc_status(d, by_doc)
            if s == "done":
                status["done"] += 1
                for r in paths.read_jsonl(self.output_path(d["doc_id"])):
                    for f in r.get("facts", []):
                        facts += 1
                        if not canonical(f.get("relation"), bool(f.get("target")))[1]:
                            off_list += 1
            else:
                status[s].append(d["doc_id"])
        return {"documents": len(man), "extracted": status["done"], "missing": status["missing"],
                "partial": status["partial"], "facts": facts, "facts_with_relation_off_list": off_list}

    # ---------- reading
    def show(self, doc_id, start, end):
        p = self.source_path(doc_id)
        if not p.is_file():
            raise paths.AtlasError(f"No source for {doc_id!r}. Run `atlas.py build` (or `prepare`) first.")
        lines = p.read_text(encoding="utf-8").split("\n")
        start, end = max(1, int(start)), min(len(lines), int(end))
        out = []
        for ln in range(start, end + 1):
            s = lines[ln - 1]
            if len(s) > LONG_LINE:
                for k in range(0, len(s), LONG_LINE):
                    out.append(f"{ln}.c{k // LONG_LINE + 1}\t{s[k:k + LONG_LINE]}")
            else:
                out.append(f"{ln}\t{s}")
        return "\n".join(out)

    def passage(self, chunk):
        p = self.source_path(chunk["doc_id"])
        if not p.is_file():
            return ""
        lines = p.read_text(encoding="utf-8").split("\n")
        seg = lines[chunk["start_line"] - 1:chunk["end_line"]]
        if "char_start" in chunk and seg:
            seg = [seg[0][chunk["char_start"]:chunk["char_end"]]]
        return "\n".join(seg)
