# Entity summary agent instructions (one task file)

Graphiti-style step: each important entity keeps a short summary that reflects its facts. Your task file (path given in your task) lists entities with their facts in date order; each fact starts with the date it became true.

For each entity write a summary of 2 to 4 sentences (at most 80 words): what it is and which vendor provides it, why it matters to someone building agents on that platform (access, auth, roles, connectivity), and its most important current facts (status, key limits, current name). Where a later fact replaced an earlier one, give the current value. Use only the facts given. Do not copy URLs into the summary.

Write `<graph dir>/work/summaries/decisions/<task file name>` (same file name as the task) with the Write tool:
`{"summaries": [{"key": "...", "summary": "..."}]}`, one per entity, `key` copied exactly. Read only your task file. No helper scripts.

Final reply: `summaries S`.
