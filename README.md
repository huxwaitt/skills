# skills

Claude Code skills. Each folder is self-contained and ready to drop into `~/.claude/skills`.

## Install

Copy the skill's folder into your personal skills directory, so it is available in every project:

```sh
git clone https://github.com/huxwaitt/skills
cp -r skills/readme-authoring ~/.claude/skills/
```

Or copy it into one project's `.claude/skills/` to scope it to that repo. Claude Code finds the
skill from its `SKILL.md` and uses it when a request matches the description, or when you call it
by name (`/readme-authoring`).

The bundled scripts need Python 3 and nothing outside the standard library.

## Skills

| Skill | What it does |
|---|---|
| [`readme-authoring`](readme-authoring/SKILL.md) | Writes, rewrites and reviews READMEs. Recommends one of five styles drawn from READMEs engineers hold up as the best, confirms it with you, and drafts from facts it can verify in the repo. |

### readme-authoring

The skill asks which style you want before drafting. It skips the question only when it is
running unattended, for example as one step of a longer task, and then tells you which style it
picked and why. Each style links to full copies of the READMEs it is based on, in
[`references/examples/`](readme-authoring/references/examples/INDEX.md).

It comes with two scripts. `readme_lint.py` scores a README for the patterns that make it read as
machine-written (the 17 reference READMEs score 0 to 9; a typical generated one scores over 80):

```
$ python readme-authoring/scripts/readme_lint.py slop.md
slop.md: score 82 (threshold 30), 109 prose words
  L1     emoji-heading              Emoji in heading: '🚀 TaskFlow'
  L3     filler-word                Filler: 'seamlessly'. Replace with the evidence (a number, an output, a comparison).
  L7     bold-label-bullets         5 consecutive '**Label**: blurb' bullets. Fine when each carries a real decision; slop when they list virtues.
  ...
```

It checks shapes and a fixed word list, not meaning. A high score is a reliable warning, but a
clean score does not make a README good.

`readme_freshness.py` checks a commit for README drift: broken links, `npm run` and `make`
targets that no longer exist, CLI flags and environment variables that were removed or added
without being documented. It is off until you turn it on for a project:

```sh
python ~/.claude/skills/readme-authoring/scripts/readme_freshness.py enable --mode warn
```

`warn` lets the commit through and tells Claude what went stale; `block` stops the commit until
the README is fixed. `disable` turns it off again. Details are in
[`references/freshness.md`](readme-authoring/references/freshness.md).

The copies in `references/examples/` belong to their original authors and keep their own
licenses, which are listed at the top of each file.
