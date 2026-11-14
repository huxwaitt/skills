# Anti-patterns: what makes a README read as machine-written

Each entry: the pattern, why it fails, the fix, and the `readme_lint.py` rule that catches it
(if any). The surface markers are not wrong in themselves. Create React App uses bold-label
bullets and HTTPie has a wall of badges. They work there because each bullet carries a real
decision. **Judge by content; use the linter to find places to look.**

Background: developers now treat this style as a signal to stop reading. The readme-unslop
linter write-up (https://dev.to/hiegbr/i-wrote-a-small-linter-that-flags-ai-sounding-readmes-here-is-its-real-output-3gpb)
scored ripgrep and fzf at 0. Hacker News commenters call emoji-heavy READMEs a heuristic for
"someone wasting my time."

## Contents
1. Surface tells (cheap to fix, easy to spot)
2. Structural tells (the template)
3. Content failures (the real problem)
4. The contrast table
5. Rewrite recipe

---

## 1. Surface tells

| Pattern | Fix | Lint rule |
|---|---|---|
| Emoji in headings (🚀 Features, 📦 Installation) | Plain headings. None of the 17 classics use them. | `emoji-heading` |
| Filler: "seamless", "blazing-fast", "robust", "powerful", "enterprise-grade", "effortless" | Replace each with its evidence: a number, an output, a comparison, or delete the sentence | `filler-word` |
| Opener: "X is a powerful, modern…" | Lead with the claim: what it does that alternatives don't | `inflated-opener` |
| Sign-offs: "Happy coding!", "Made with ❤️", "⭐ Star this repo" | Delete | `generic-closer` |
| Em dashes everywhere | Commas, colons, full stops | `em-dash-density` |

## 2. Structural tells

| Pattern | Why it fails | Fix | Lint rule |
|---|---|---|---|
| The same section set for every project: Features, Tech Stack, Prerequisites, Installation, Usage, Project Structure, Contributing, License, Acknowledgments, Roadmap | Signals no one decided what *this* reader needs | Grow sections from the project: Philosophy, Why not X, Release cycle, Known problems | `template-shaped` |
| Five "**Easy to use**: Intuitive commands" bullets | Lists virtues every project claims | Keep a bullet only if it states a decision with a consequence ("**No lock-in:** eject at any time") | `bold-label-bullets` |
| Full directory tree | Restates `ls`; rots on the next refactor | Name the 2-3 places a reader needs, or move to ARCHITECTURE.md. Exception: a tree of what the tool *generates* (Create React App) | `tree-dump` |
| "Roadmap: Coming soon", empty FAQ | Promises without content | Delete until there is content | `empty-section` |
| "Fork, branch, commit, push, PR" | Tells nobody anything they don't know | Say what contributions are wanted, how to run the tests, or link CONTRIBUTING.md | `boilerplate-contributing` |
| Tech stack list (React, Node, PostgreSQL) for a library | The reader cares what it does, not what it's made of | Keep only runtime requirements the reader must install | none |

## 3. Content failures (the real problem)

These are why a README is machine-written in effect, even with every surface tell removed.

1. **Invented evidence.** Commands never run, sample output typed rather than captured,
   benchmark numbers with no source, badges for CI that doesn't exist, `yourusername` clone URLs.
   Lint rule: `placeholder` (partial). **Rule: every command in the README has been run, or is
   copied from a test/CI file that runs it; every output block was captured, not imagined.**
2. **No trade-off.** Every feature is a pure positive; nothing is ruled out. Lint rule:
   `no-tradeoff-signal`. Fix: a non-goals line, a "when not to use this", a comparison, a known
   problem.
3. **Uniform depth.** Every section gets the same three bullets; a 200-line script gets a
   300-line README. Fix: depth where readers need it, links elsewhere, delete the rest.
4. **Written from the code outward.** "This project contains a `utils/` folder with helper
   functions." Fix: write from the reader's questions inward: Should I use this? How do I start?
   What will bite me?
5. **No point of view.** Generic enthusiasm instead of an author. Fix: state the opinion the
   project embodies (Black's "cede control", Express's "unopinionated").

## 4. The contrast table

| | Classic READMEs | Typical LLM README |
|---|---|---|
| Structure | Grown from the project | Same template every time |
| Claims | Specific and testable ("no build configuration") | Adjectives any project could use |
| Evidence | Real output, real commands | Unrun commands, invented output, placeholders |
| Trade-offs | Up front | Absent |
| Depth | Uneven on purpose | Uniform |
| Voice | One person or team | Upbeat, no point of view |
| Direction | From the reader's question | From the codebase |

## 5. Rewrite recipe (for an existing slop README)

1. Run `python scripts/readme_lint.py README.md` and keep the findings list.
2. Extract the **facts**: every real command, flag, config key, requirement, link. Verify each
   against the code (does the script exist, does the flag exist, does the link resolve). Facts
   that don't verify are dropped or fixed, never kept on faith.
3. Find the **claim**: the one thing it does that alternatives don't. If you cannot find it in
   the code or history, ask (interactive) or write the plainest accurate sentence (autonomous).
4. Find the **cost**: a limitation, non-goal or requirement. Same sourcing rule.
5. Pick the style (styles.md) and rebuild around the claim, the smallest real example, the cost.
6. Delete sections that answer no question a reader would ask.
7. Re-lint. Target: under 15, with every remaining finding a deliberate choice you can defend.
