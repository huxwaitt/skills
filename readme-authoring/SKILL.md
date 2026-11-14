---
name: readme-authoring
description: >
  Write, rewrite, review or freshness-check a project README. Recommends one of five proven
  styles and confirms it with the user, drafts from verified facts only, and strips AI-sounding
  tells. Optional commit hook flags stale READMEs. Use for any README request, when a task ends
  with documenting a project, or when a README freshness hook fires.
---

# readme-authoring

A README answers a stranger's questions in order: *What is this? Should I care? How do I start?
What will bite me?* The READMEs engineers admire answer them with a specific claim, real
evidence, a stated cost, and a length that fits the project. Machine-written READMEs answer
them with adjectives, a template, and invented output. This skill exists to produce the first
kind.

Three modes:
- **Author:** new README, or a rewrite of one that isn't working.
- **Revise:** targeted changes to a README that already has a working style.
- **Freshness:** a commit (or the user) asks whether the README still matches the code.

Supporting files (read when the step says so, not up front):
- `references/styles.md`: the five styles, skeletons, annotated excerpts from 17 reference READMEs, and the decision table.
- `references/principles.md`: the essays and community consensus, and the seven traits.
- `references/anti-patterns.md`: machine-written tells, the contrast table, the rewrite recipe.
- `references/freshness.md`: config, the commit hook, each check and its false positives.
- `scripts/readme_lint.py`: scores a README for machine-written tells.
- `scripts/readme_freshness.py`: freshness checks, the hook entry points, enable/disable.

Run scripts with `python <this skill's dir>/scripts/<name>.py`.

---

## Author mode

### 1. Gather facts, not adjectives

Read the repo the way a reader's questions demand:
- **What it is:** manifest (`package.json`, `pyproject.toml`, `Cargo.toml`, `go.mod`): name,
  description, `bin` entries, exports. Entry points. Existing README, docs folder, docs URL.
- **How to start:** install path, the smallest real usage. **Run it** where that is safe and
  read-only (`--help`, `--version`, an example script, the test suite) and keep the real output.
  If running isn't possible, copy usage from tests, examples or CI config, which are known to run.
- **The cost:** requirements, platform limits, what it deliberately doesn't do, known problems.
  Look in issues, commit messages, comments marked TODO, FIXME or "not supported", and config
  validation errors.
- **The claim:** what it does that alternatives don't. Commit history and the original README
  often say it plainly.

Then list what only the author can know and you could not find: usually the claim, the
trade-off, and who it's for. In **interactive** mode, ask for the missing pieces in the same
question as the style (step 2). Never ask about things the repo already answers. In
**autonomous** mode, use the plainest accurate sentence the evidence supports and leave out
what it doesn't support.

**Hard rule: nothing invented.** No benchmark, user count, output block, badge, compatibility
claim or roadmap item that you did not verify. A missing claim makes a README shorter; an
invented one makes it untrustworthy, and the reader can't tell which claims are which.

### 2. Recommend a style, then confirm it

Read `references/styles.md` section 6 (decision table) and pick one of:
`minimal`, `code-first`, `demo-first`, `comprehensive` (the README is the docs), `voice`, plus
an optional `+voice` overlay. If `.claude/readme-authoring.json` already records a `style`, or
the existing README has a working style, recommend keeping it.

**Interactive (default):** confirm with one `AskUserQuestion` call:
- Question names the project and the evidence behind the recommendation, e.g. "README style for
  `fastq`? It's a small Node library with two exports and no docs site, so I'd lead with code."
- 2-3 options, **recommended first with "(Recommended)" in the label**, each with a one-line
  description and a `preview` showing the first ~12 lines of *this project's* README in that
  style (real name, real install command, real first example), not a generic skeleton.
- If facts from step 1 are missing (claim, trade-off), add them as a second question in the same
  call, offering your best inferred wording as the first option.

Wait for the answer. Record it: `style` in `.claude/readme-authoring.json` (create the file with
only `style` if it doesn't exist, and keep any existing keys).

**Autonomous: decide without asking** when any of these is true:
- `AskUserQuestion` is unavailable (headless `-p` run, subagent, workflow agent, scheduled or
  cloud routine);
- the README is one deliverable inside a long, multi-step task the user handed over end to end
  ("build X and document it", a `/loop`, a workflow run, a task list you are working through);
- the user said not to stop or ask, or asked you to just write it;
- a style is already recorded in the config.

Then pick the recommended style, draft, record it in the config, and in the final report give
one line with the style, the reason, and how to switch ("Used code-first: small library, value
shows in 6 lines. Say the word for minimal or comprehensive."). Do not block a long task on a
README question.

### 3. Draft

Follow the chosen style's skeleton and steal from its reference examples in styles.md. Rules
that hold in every style:

1. **First line: a claim specific to this project.** Test: could it describe a competitor? Then
   rewrite it. A claim that rules something out is stronger ("no build configuration",
   "which sucks less").
2. **Evidence before adjectives.** A real command and its captured output beat any description.
   Use the smallest example that does something a reader would want.
3. **State the cost** somewhere above the fold or in its own section: a requirement, a non-goal,
   "when not to use this", a known problem with its fix.
4. **Sections grow from the project.** Start from the style's skeleton, add sections only when
   this project needs them (Philosophy, Why not X, Release cycle, Known problems), and drop
   template sections that would be empty or generic. Use a ToC past about 100 lines.
5. **Length fits the reader.** Hand off to a docs site or ARCHITECTURE.md rather than
   accreting. No directory trees except of generated output.
6. **Readable raw.** Minimal HTML, no emoji headings, light Markdown, alt text on every image,
   images always paired with prose.
7. **Voice, if used, maps to the project.** One line that embodies the design (Black's "Any
   color you like.") beats ten jokes. When in doubt, plain and honest is the voice.
8. **Links and commands must resolve.** Every relative link points at a real file; every
   `npm run`/`make` target exists.

### 4. Verify

```sh
python <skill>/scripts/readme_lint.py README.md
python <skill>/scripts/readme_freshness.py check --full
```
- The lint score should be under 15. For each remaining finding, either fix it or be able to
  say why it is deliberate (see anti-patterns.md: the markers are signals, not crimes).
- Freshness `--full` must report no errors (broken links, missing scripts).
- Re-read the first screen as the stranger: is the claim specific, is there a working example,
  is the cost stated? If any is missing, go back to step 1, not to adjectives.

### 5. Report

Keep it short: the style used (and why, in autonomous mode), what you could not verify and left
out, the lint score, and any question only the user can answer. Offer, in one line, to turn on
commit-time freshness checks if they aren't on (see below).

---

## Revise mode

For "add X to the README", "update the install section", "tighten this":
1. Read the recorded `style` (config) or infer it from the README; keep it.
2. Change only what was asked, under the same rules (verified facts, no filler).
3. Lint the result. If the score *rose*, the edit introduced tells; fix them.

For "this README sucks / reads like AI", use the rewrite recipe in `references/anti-patterns.md`
section 5. It is Author mode with the existing README as a fact source, and every fact in it
gets verified first.

---

## Freshness mode

Triggered when a hook report about README freshness arrives (as added context, or as the reason
a commit was denied), or the user asks whether the README is current. Follow
`references/freshness.md` section 5. In short: get the findings
(`readme_freshness.py check --json`), read the diff, classify each finding as stale, false
positive or needs the user, fix only what the diff made stale (in the recorded style), stage it
with the commit or follow up, and report in a line or two. Use `README_FRESHNESS_SKIP=1` only
after concluding every finding is a false positive, and say so.

### Turning commit checks on or off

Freshness checks are **opt-in per project**. Offer them; never enable them silently. When the
user agrees, ask two things (one `AskUserQuestion` call, recommendations first): **mode**: warn
(recommended: commits proceed, you follow up) or block; **target**: Claude's commits only
(recommended) or also the user's own commits via a git pre-commit hook. Then:

```sh
python <skill>/scripts/readme_freshness.py enable --mode warn --target claude
python <skill>/scripts/readme_freshness.py status
```
`disable [--remove-hooks]` reverses it. Tell the user what was written (config file, hook in
`.claude/settings.local.json`, `.gitignore` line) and that the hook is live after Claude Code
reloads settings (`/hooks` once, or a restart, if it doesn't fire right away).
