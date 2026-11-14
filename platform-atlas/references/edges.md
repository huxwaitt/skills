# Fact resolution agent instructions (one task file)

Graphiti-style step: facts between the same two entities, or facts about one entity with the same relation type (for example every `HAS_STATUS` fact about one service), came from different notes or passages. Each fact carries `doc_date`, its note's **as-of date**. For each group, in date order, decide for each fact:
- `duplicate_of`: it says the same thing as an earlier fact in the group (same meaning, same values) -> the earliest such `fid`.
- `invalidated_by`: a later fact makes it no longer true -> the later `fid`, with `invalid_at` = the date the later fact became true (its `valid_at`, else its `doc_date`). Typical cases: a status moves on (preview to GA, GA to deprecated or retired); a limit, price, version, endpoint or install command changes; a role, permission or product is renamed; a recommended auth method or default changes.
- Otherwise the fact stands; leave it out.

Facts that add detail without contradicting are not duplicates. Facts about different things are neither. Two facts with the same as-of date that disagree are a source conflict, not a replacement: leave both standing. A status, limit, version or price for the same thing normally has one current value: the one from the latest as-of date replaces the earlier ones.

Write `<graph dir>/work/edges/decisions/<task file name>` (same file name as the task) with the Write tool:
`{"groups": ["<every group_id in the task>"], "decisions": [{"fid": "f1a2b3c4d5e", "duplicate_of": "f9e8d7c6b5a"}, {"fid": "f0011223344", "invalidated_by": "f5566778899", "invalid_at": "2026-10-14"}]}`
Read only your task file. No helper scripts.

Final reply: `groups G, decisions D`.
