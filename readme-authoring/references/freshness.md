# README freshness checks at commit time

Optional, per project, **off by default**. When enabled, every `git commit` Claude runs (and,
optionally, every commit a human runs) is checked for README staleness first.

## Contents
1. Config file
2. Turning it on and off
3. What happens on a commit
4. The checks, and their known false positives
5. Responding to a finding (freshness mode)

---

## 1. Config file: `.claude/readme-authoring.json`

```json
{
  "style": "code-first",
  "freshness": {
    "enabled": true,
    "mode": "warn",
    "readme": "README.md",
    "extraSurface": ["src/commands/*.ts"],
    "ignore": ["examples/*"],
    "ignoreChecks": ["stale-version"]
  }
}
```

| Key | Default | Meaning |
|---|---|---|
| `style` | `null` | The style the user confirmed (`minimal`, `code-first`, `demo-first`, `comprehensive`, `voice`, optionally `+voice`, e.g. `code-first+voice`). Read before any revision so the README keeps its style. |
| `freshness.enabled` | `false` | Master switch. The hook is a no-op while false. |
| `freshness.mode` | `"warn"` | `warn`: the commit proceeds and Claude gets the findings to follow up on. `block`: the commit is denied until the README is updated or the skip is used deliberately. |
| `freshness.readme` | `"README.md"` | Path of the README to guard, relative to the repo root. |
| `freshness.extraSurface` | `[]` | Extra globs that count as public surface (see `surface-touched`). |
| `freshness.ignore` | `[]` | Globs never counted as surface. |
| `freshness.ignoreChecks` | `[]` | Check names to silence entirely. |

This file is safe to commit (it holds no machine paths), so a team shares the setting.

## 2. Turning it on and off

Always confirm with the user before enabling; it adds a hook to their settings.

```sh
python <skill>/scripts/readme_freshness.py enable [repo] --mode warn|block \
       --target claude|git|both --scope local|project
python <skill>/scripts/readme_freshness.py disable [repo] [--remove-hooks]
python <skill>/scripts/readme_freshness.py status [repo]
```

- `--target claude` (default) registers a `PreToolUse` hook on `Bash` in
  `.claude/settings.local.json`, and adds that file to `.gitignore`. The hook command holds
  absolute paths to this machine's Python and to the script, which is why it defaults to the
  local (uncommitted) settings file. Use `--scope project` only if every teammate has the skill
  at the same path.
- `--target git` installs `.git/hooks/pre-commit` (respects `core.hooksPath`) for commits made
  outside Claude. An existing pre-commit hook is never overwritten; the script prints the line
  to add instead.
- `disable` flips `enabled` to false. `--remove-hooks` also removes every hook entry this script
  added, and nothing else.
- After enabling, tell the user that the hook takes effect once Claude Code reloads settings
  (opening `/hooks` once, or a restart, if it doesn't fire right away).

## 3. What happens on a commit

The hook script reads the Bash command, ignores anything that isn't a `git commit` (including
`--dry-run` and `--amend --no-edit`), finds the repo (it follows `cd X && git commit` and
`git -C X commit`), loads the config, and returns immediately if disabled.

If the command stages files itself (`git add … && git commit`, `git commit -a`), unstaged and
untracked changes are included in the check, because they will be in the commit.

| Result | warn mode | block mode |
|---|---|---|
| No findings | silent | silent |
| Findings | commit proceeds; user sees a one-line notice; Claude receives the report as context | commit denied; Claude receives the report as the reason |

**Skip for one commit:** prefix the command with `README_FRESHNESS_SKIP=1` (for the git hook,
set it in the environment). Only do this after reviewing the findings and concluding the README
needs no change, and tell the user why.

If the README itself is part of the commit, warnings are dropped (the author is already on it)
and only hard errors remain. If the script itself crashes, it prints a note and lets the commit
through; a freshness check must never wedge a commit with its own bug.

## 4. The checks

| Check | Severity | Fires when | Known false positives |
|---|---|---|---|
| `broken-link` | error | A Markdown or HTML link in the README points at a local file that doesn't exist (or is deleted in this commit). Root-relative `/x` resolves from the repo root, as on GitHub. | Links to files generated at build time. Add the file, or silence with `ignoreChecks`. |
| `missing-script` | error | Code in the README runs `npm/pnpm/yarn/bun run X` with no `X` in package.json, or `make X` with no such target. Only code blocks and inline code are read, never prose ("make sure"). | Makefiles using `include` or pattern rules are skipped entirely. |
| `removed-flag` | error | The diff removes a quoted `--flag` from source, it no longer appears anywhere in the code, and the README still documents it. | A flag defined without quotes (e.g. derived from a field name, as in clap's `#[arg(long)]`) is invisible to this check. |
| `removed-env` | error | Same for environment variables read via `process.env`, `os.environ`, `os.getenv`, `env::var`, `os.Getenv`, `ENV[]`, `System.getenv`, or listed in `.env.example`. | Env vars read through a config library. |
| `stale-version` | warn | The README pins this package (`name@x.y.z`, `name==x.y.z`, `name = "x.y.z"`, `[name "x.y.z"]`) at a version other than the manifest's. | Deliberate pins in a "migrating from v1" section. |
| `undocumented-flag` | warn | The diff adds a quoted `--flag` the README never mentions, and the README documents flags at all. | Internal or hidden flags. |
| `undocumented-env` | warn | The diff adds an env var the README never mentions, and the README documents env vars at all. | Internal or test-only variables. |
| `surface-touched` | warn | Files that usually change what a user sees (manifests, Makefile, Dockerfile, compose files, `.env.example`, `cli.*`, `cli/`, `bin/`, `cmd/`, `__main__.py`, plus `extraSurface`) are in the commit and the README is not. | A dependency bump in package.json. This is the noisiest check: a prompt to look, not a claim of staleness. |
| `missing-readme` | warn | No file at `freshness.readme`. | n/a |

Calibration: a whole-README audit (`check --full`) on express, black, prettier, fzf, ripgrep,
httpie, tqdm, bat, poetry and vite produced zero findings after the two fixes noted in the
script (code-only `make` detection, root-relative links).

## 5. Responding to a finding (freshness mode)

When the hook's report arrives as context or a denial reason, or the user asks "is the README up
to date":

1. Run `python <skill>/scripts/readme_freshness.py check --json` (add `--worktree` if the
   commit stages files itself) to get the structured list.
2. Read the diff (`git diff --cached`, or `git diff HEAD` with `--worktree`) and the README
   sections each finding points at.
3. For each finding, decide: **stale** (fix the README), **false positive** (leave it, note why),
   or **needs the user** (e.g. a new flag whose purpose isn't clear from the code).
4. Edit the README in its recorded `style`. Change only what the diff made stale: a freshness
   fix is not a rewrite. Never "freshen" by adding filler; run `readme_lint.py` on the result.
5. Stage the README with the commit and retry (block mode), or make a follow-up commit
   (warn mode).
6. Use `README_FRESHNESS_SKIP=1` only when every finding was a false positive, and say so.
7. Report in one or two lines: what changed in the README, or why nothing needed to.
