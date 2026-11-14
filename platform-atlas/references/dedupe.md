# Entity resolution agent instructions (one task file)

Graphiti-style step: decide which extracted entity names are the same real-world thing. Your task file (path given in your task) holds groups; each member has a normalized `key`, the `names` used, `type`, number of episodes, the `platforms` whose notes mention it, and sample summaries.

Merge only members that clearly refer to the same thing:
- Spelling variants, abbreviations and the vendor-qualified vs bare form of one product are the same ("AgentCore Gateway", "Amazon Bedrock AgentCore Gateway").
- An old name and a new name of a renamed product are **not** merged: the graph keeps both, linked by a `REPLACED` fact, so history and old-name searches still work.
- Same-named things from different vendors are different ("Azure service principal" and "Databricks service principal"; "Snowflake MCP server" and "Databricks managed MCP servers"). So are a product and its API, its CLI, its SDK or its MCP server, and a role and the permission it grants.
- A model family and one model version are different.
- When unsure, keep them separate.

The canonical key is the member key with the vendor's current, fullest correct name.

Write `<graph dir>/work/dedupe/decisions/<task file name>` (same file name as the task) with the Write tool:
`{"groups": ["<every group_id in the task, reviewed or not merged>"], "merges": [{"canonical": "amazon bedrock agentcore gateway", "members": ["agentcore gateway", "amazon bedrock agentcore gateway"]}]}`
List every `group_id` you reviewed in `groups` (so they are not sent again); list only actual merges in `merges` (members include the canonical). Read only your task file. No helper scripts.

Final reply: `groups G, merges M`.
