"""Where everything lives. The knowledge base root is `<skill>/kb`, or `$PLATFORM_ATLAS_HOME` if set.

  <kb>/notes/<platform>/<as_of>-<part>.md   dated research notes (committed; the graph's only input)
  <kb>/cli/<cli>.md                         CLI command maps from scripts/cli_map.py (committed; looked up, not extracted)
  <kb>/graph/manifest.jsonl, chunks.jsonl   what was read, and its chunks (committed)
  <kb>/graph/work/                          extraction output and agent decisions (committed, so a clone builds without agents)
  <kb>/graph/sources/                       numbered copies of the notes that citations point at (rebuilt locally)
  <kb>/graph/kg.sqlite                      the graph and its keyword index (rebuilt locally in seconds)
  <kb>/graph/pages/                         saved answer pages (local)
"""
import json
import os
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parents[2]


class AtlasError(RuntimeError):
    pass


def kb_root():
    env = os.environ.get("PLATFORM_ATLAS_HOME")
    return Path(env).resolve() if env else SKILL_DIR / "kb"


def notes_dir(root=None):
    return Path(root or kb_root()) / "notes"


def cli_dir(root=None):
    return Path(root or kb_root()) / "cli"


def graph_dir(root=None):
    return Path(root or kb_root()) / "graph"


def registry():
    p = SKILL_DIR / "references" / "platforms.json"
    return json.loads(p.read_text(encoding="utf-8"))


def file_key(doc_id):
    return doc_id.replace("/", "__")


def platform_of(doc_id):
    return (doc_id or "").split("/", 1)[0]


def read_jsonl(path):
    rows = []
    p = Path(path)
    if not p.is_file():
        return rows
    with open(p, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def write_jsonl(path, rows):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8", newline="\n") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    os.replace(tmp, p)


def write_json(path, obj):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, indent=1, ensure_ascii=False), encoding="utf-8", newline="\n")
    os.replace(tmp, p)
