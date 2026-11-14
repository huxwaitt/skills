"""Keyword search over the platform graph, with SQLite's built-in full-text index (FTS5).

No models and nothing extra to install. Facts are indexed with the names of the entities they link;
entities with their names, aliases, type and summary. Words are stemmed, so "workshops" finds
"workshop". Matching is by words, not meaning: when a search misses, Claude searches again with other
words (synonyms, names, dates) or browses with the entity and fact tools.
"""
import json
import re
import sqlite3
from pathlib import Path

TOKENIZE = "porter unicode61 remove_diacritics 2"

STOPWORDS = frozenset("""
a about above after again against all also am an and any are as at be because been before being below between
both but by can could did do does doing down during each either else ever few for from further get got had has
have having he her here hers herself him himself his how i if in into is it its itself just me more most much
my myself no nor not now of off on once only or other our ours ourselves out over own same she should so some
such than that the their theirs them themselves then there these they this those through to too under until up
upon very was we were what when where which while who whom whose why will with would you your yours yourself
yourselves tell show give know find
""".split())

WEIGHTS = {"fact_search": (1.0, 0.6), "entity_search": (2.0, 0.5)}
ID_COLUMN = {"fact_search": "fid", "entity_search": "key"}


def index(db):
    """(Re)write both search tables from the entities and facts tables. The caller commits."""
    db.executescript(f"""
      DROP TABLE IF EXISTS fact_search;
      DROP TABLE IF EXISTS entity_search;
      CREATE VIRTUAL TABLE fact_search USING fts5(fact, names, fid UNINDEXED, tokenize='{TOKENIZE}');
      CREATE VIRTUAL TABLE entity_search USING fts5(names, summary, key UNINDEXED, tokenize='{TOKENIZE}');
    """)
    names, rows = {}, []
    for key, name, typ, aliases, summary in db.execute("SELECT key, name, type, aliases, summary FROM entities").fetchall():
        names[key] = name
        rows.append((" ; ".join([name, *json.loads(aliases or "[]"), typ or ""]), summary or "", key))
    db.executemany("INSERT INTO entity_search(names, summary, key) VALUES(?,?,?)", rows)
    rows = []
    for fid, src, dst, rel, fact in db.execute("SELECT fid, src, dst, relation, fact FROM facts").fetchall():
        linked = [names.get(src, src), names.get(dst, dst) if dst else "", (rel or "").replace("_", " ").lower()]
        rows.append((fact, " ; ".join(x for x in linked if x), fid))
    db.executemany("INSERT INTO fact_search(fact, names, fid) VALUES(?,?,?)", rows)


def has_index(db):
    return db.execute("SELECT 1 FROM sqlite_master WHERE name='fact_search'").fetchone() is not None


def match_query(text):
    """Any of the question's content words, each quoted (so no word is read as FTS syntax)."""
    words = [w for w in re.findall(r"\w+", (text or "").lower()) if w not in STOPWORDS and len(w) > 1]
    return " OR ".join(f'"{w}"' for w in list(dict.fromkeys(words))[:40])


def find(db_path, table, query, limit):
    """[(id, score)] best first. Scores are BM25 (lower is better) and comparable across projects."""
    q = match_query(query)
    if not q:
        return []
    w1, w2 = WEIGHTS[table]
    db = sqlite3.connect(Path(db_path).resolve().as_uri() + "?mode=ro", uri=True)
    try:
        return db.execute(f"SELECT {ID_COLUMN[table]}, bm25({table}, {w1}, {w2}) AS s FROM {table} "
                          f"WHERE {table} MATCH ? ORDER BY s LIMIT ?", (q, int(limit))).fetchall()
    finally:
        db.close()
