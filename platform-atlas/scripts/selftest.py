"""Offline self-test: runs the whole pipeline on a throwaway knowledge base, with hand-written agent output.

  python -I <skill>/scripts/selftest.py

Checks that notes are dated by `as_of`, that a later note's fact replaces an earlier one, that lookups
print as-of dates and citations, that a fresh clone (no sources, no kg.sqlite) rebuilds, and that pages
go stale when facts change. Uses no network and no models.
"""
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

NOTE_1 = """---
title: Example Cloud: build
platform: example
part: build
as_of: 2026-01-10
---
# Example Cloud: build (as of 2026-01-10)

## 7. Connectivity
- **Example MCP Server is in preview.** The Example MCP Server exposes the Example Data API as MCP tools. Source: https://example.com/mcp
- **Example CLI signs in with OAuth.** Run `ex auth login` to sign in. Source: https://example.com/cli
"""

NOTE_2 = """---
title: Example Cloud: build
platform: example
part: build
as_of: 2026-06-01
---
# Example Cloud: build (as of 2026-06-01)

## 7. Connectivity
- **Example MCP Server is GA.** The Example MCP Server became generally available on 2026-05-20. Source: https://example.com/mcp-ga
"""


def ex(chunk, date, facts, ents):
    return {"chunk_id": chunk["chunk_id"], "doc_id": chunk["doc_id"], "date": date, "entities": ents, "facts": facts}


def main():
    tmp = Path(tempfile.mkdtemp(prefix="atlas-selftest-"))
    os.environ["PLATFORM_ATLAS_HOME"] = str(tmp)
    try:
        from kg import kg_build, kg_store, pages
        from kg.corpus import Corpus
        (tmp / "notes" / "example").mkdir(parents=True)
        (tmp / "notes" / "example" / "2026-01-10-build.md").write_text(NOTE_1, encoding="utf-8")
        (tmp / "notes" / "example" / "2026-06-01-build.md").write_text(NOTE_2, encoding="utf-8")
        c = Corpus()
        prep = c.prepare()
        assert prep["documents"] == 2 and len(prep["to_extract"]["batches"]) == 1, prep
        man = c.manifest()
        assert man["example/2026-01-10-build"]["date"] == "2026-01-10", man
        chunks = {ch["doc_id"]: ch for ch in c.chunks()}
        mcp = {"name": "Example MCP Server", "type": "MCPServer", "summary": "MCP server for Example Data API."}
        cli = {"name": "Example CLI", "type": "CLI", "summary": "Example's command-line tool."}
        oauth = {"name": "OAuth 2.0", "type": "Protocol", "summary": "Auth protocol."}
        r1 = ex(chunks["example/2026-01-10-build"], "2026-01-10", [
            {"source": "Example MCP Server", "target": None, "relation": "HAS_STATUS",
             "fact": "Example MCP Server is in public preview.", "valid_at": "2026-01-10", "invalid_at": None, "lines": [10, 10]},
            {"source": "Example CLI", "target": "OAuth 2.0", "relation": "AUTHENTICATES_WITH",
             "fact": "Example CLI signs in with OAuth via `ex auth login`.", "valid_at": None, "invalid_at": None, "lines": [11, 11]},
        ], [mcp, cli, oauth])
        r2 = ex(chunks["example/2026-06-01-build"], "2026-06-01", [
            {"source": "example mcp server", "target": None, "relation": "STATUS",
             "fact": "Example MCP Server became generally available on 2026-05-20.", "valid_at": "2026-05-20",
             "invalid_at": None, "lines": [10, 10]},
        ], [{**mcp, "name": "example mcp server"}])
        for doc_id, row in (("example/2026-01-10-build", r1), ("example/2026-06-01-build", r2)):
            c.output_path(doc_id).parent.mkdir(parents=True, exist_ok=True)
            c.output_path(doc_id).write_text(json.dumps(row) + "\n", encoding="utf-8")
        assert c.check()["extracted"] == 2
        b = kg_build.Builder()
        b.dedupe_candidates()
        edges = b.edge_candidates()
        assert edges["new_groups"] == 1, edges
        task = json.loads(Path(edges["tasks"][0]).read_text(encoding="utf-8"))
        old, new = task["groups"][0]["facts"][0]["fid"], task["groups"][0]["facts"][1]["fid"]
        (b.work / "edges" / "decisions" / Path(edges["tasks"][0]).name).write_text(json.dumps(
            {"groups": [task["groups"][0]["group_id"]],
             "decisions": [{"fid": old, "invalidated_by": new, "invalid_at": "2026-05-20"}]}), encoding="utf-8")
        b.summary_tasks()
        stats = b.build()
        assert stats["facts"] == 3 and stats["replaced"] == 1, stats
        s = kg_store.Store()
        line = s.search("mcp server status", platform="example", current_only=True)
        assert "generally available" in line and "as of 2026-06-01" in line and "[example/2026-06-01-build:L10-L10]" in line, line
        assert "public preview" not in line, line
        hist = s.entity("Example MCP Server")
        assert "ENDED 2026-05-20" in hist, hist
        assert "generally available" in s.episode("example/2026-06-01-build:L10-L10")
        assert "Example CLI" in s.path("Example CLI", "OAuth 2.0")
        st = kg_store.status()
        row = [p for p in st["platforms"] if p["platform"] == "example"][0]
        assert row["parts"]["build"] == "2026-06-01" and row["current_facts"] == 2, row
        saved = pages.save(s, ["Example MCP Server"], "# Example MCP Server\n\nGA. [example/2026-06-01-build:L10-L10]")
        assert saved["as_of"] == "2026-06-01" and pages.get(s, ["Example MCP Server"])["stale"] is False
        # Fresh clone: committed files only (no sources, no graph) must rebuild without agents.
        shutil.rmtree(c.sources)
        (c.dir / "kg.sqlite").unlink()
        again = kg_build.Builder().build()
        assert again["facts"] == 3 and "notes_changed_since_extraction" not in again, again
        assert "generally available" in kg_store.Store().episode("example/2026-06-01-build:L10-L10")
        # A changed note is reported, not silently rebuilt.
        p = tmp / "notes" / "example" / "2026-06-01-build.md"
        p.write_text(NOTE_2 + "- **Extra.** Extra claim. Source: https://example.com/x\n", encoding="utf-8")
        assert kg_build.Builder().build()["notes_changed_since_extraction"] == ["example/2026-06-01-build"]
        print("selftest ok")
        return 0
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
