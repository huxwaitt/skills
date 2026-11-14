#!/usr/bin/env python3
"""readme_freshness.py - catch a README going stale at commit time.

Opt-in per project. Off unless .claude/readme-authoring.json says
"freshness": {"enabled": true}. Subcommands:

  check      Run the checks now (staged changes by default) and print findings.
  hook       Claude Code PreToolUse hook entry point (reads hook JSON on stdin).
  git-hook   git pre-commit entry point, for commits made outside Claude.
  enable     Turn the check on: write the config and register the hook(s).
  disable    Turn it off: set enabled=false and remove the hook(s) this script added.
  status     Show the current config and whether the hooks are registered.

Checks (see references/freshness.md for the rationale behind each):
  broken-link       README links to a local file that does not exist        error
  missing-script    README runs `npm run X` / `make X` that is not defined   error
  removed-flag      README documents a --flag the diff removed from code     error
  removed-env       README documents an env var the diff removed from code   error
  stale-version     README pins a version of this package != the manifest   warn
  undocumented-flag diff adds a --flag the README (which documents flags)
                    never mentions                                          warn
  undocumented-env  diff adds an env var the README (which documents env
                    vars) never mentions                                    warn
  surface-touched   public-surface files changed but README not in commit   warn
  missing-readme    no README at the configured path                        warn

Bypass for one commit: prefix the command with README_FRESHNESS_SKIP=1
(the hook reads the command string; the git hook reads the environment).
"""
import argparse
import fnmatch
import json
import os
import re
import shlex
import subprocess
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

CONFIG_REL = os.path.join(".claude", "readme-authoring.json")
SCRIPT_PATH = os.path.abspath(__file__).replace("\\", "/")
HOOK_MARKER = "readme_freshness.py"

DEFAULT_CONFIG = {
    "style": None,
    "freshness": {
        "enabled": False,
        "mode": "warn",
        "readme": "README.md",
        "extraSurface": [],
        "ignore": [],
    },
}

SURFACE_GLOBS = [
    "package.json", "*/package.json", "pyproject.toml", "setup.py", "setup.cfg",
    "Cargo.toml", "Makefile", "justfile", "Justfile", "Dockerfile",
    "docker-compose*.yml", "docker-compose*.yaml", "compose*.yml", "compose*.yaml",
    ".env.example", ".env.sample", "action.yml", "action.yaml",
    "**/cli.*", "**/cli/*", "**/__main__.py", "bin/*", "cmd/*", "cmd/*/*",
]
DOC_EXT = (".md", ".rst", ".txt", ".adoc", ".org")

FLAG_RE = re.compile(r"""["'`](--[a-z][a-z0-9]*(?:-[a-z0-9]+)*)(?:[=\s"'`])""")
README_FLAG_RE = re.compile(r"(?<![\w/-])(--[a-z][a-z0-9]*(?:-[a-z0-9]+)*)")
ENV_PATTERNS = [
    r"process\.env\.([A-Z][A-Z0-9_]{2,})",
    r"process\.env\[\s*[\"']([A-Z][A-Z0-9_]{2,})",
    r"import\.meta\.env\.([A-Z][A-Z0-9_]{2,})",
    r"os\.environ(?:\.get)?\s*[\(\[]\s*[\"']([A-Z][A-Z0-9_]{2,})",
    r"os\.getenv\(\s*[\"']([A-Z][A-Z0-9_]{2,})",
    r"env::var(?:_os)?\(\s*\"([A-Z][A-Z0-9_]{2,})",
    r"os\.(?:Getenv|LookupEnv)\(\s*\"([A-Z][A-Z0-9_]{2,})",
    r"ENV\[\s*[\"']([A-Z][A-Z0-9_]{2,})",
    r"System\.getenv\(\s*\"([A-Z][A-Z0-9_]{2,})",
    r"Environment\.GetEnvironmentVariable\(\s*\"([A-Z][A-Z0-9_]{2,})",
]
ENV_RE = re.compile("|".join(ENV_PATTERNS))
ENVFILE_RE = re.compile(r"^([A-Z][A-Z0-9_]{2,})\s*=")
SCRIPT_RUN_RE = re.compile(r"(?<![\w-])(npm|pnpm|yarn|bun)\s+run\s+([\w:.@/-]+)")
# `make` only as a command: start of a code line (optionally after a `$ ` prompt) or after && ; |
MAKE_RE = re.compile(r"(?:^\s*(?:\$\s+)?|(?:&&|;|\|\|)\s*)(?:sudo\s+)?make((?:\s+[\w.-]+)+)", re.M)
LINK_RE = re.compile(r"!?\[[^\]]*\]\(\s*<?([^)\s>]+)>?(?:\s+\"[^\"]*\")?\s*\)")
REF_LINK_RE = re.compile(r"^\s*\[[^\]]+\]:\s*<?(\S+?)>?(?:\s|$)", re.M)
HTML_SRC_RE = re.compile(r"""(?:src|href)\s*=\s*["']([^"']+)["']""", re.I)


# ---------------------------------------------------------------- utilities

def git(root, *args, check=False):
    r = subprocess.run(["git", "-C", root, *args], capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    if check and r.returncode != 0:
        raise RuntimeError(r.stderr.strip())
    return r.stdout if r.returncode == 0 else ""


def repo_root(path):
    out = git(path, "rev-parse", "--show-toplevel").strip()
    return out or None


def load_config(root):
    cfg = json.loads(json.dumps(DEFAULT_CONFIG))
    p = os.path.join(root, CONFIG_REL)
    if os.path.exists(p):
        try:
            with open(p, encoding="utf-8") as fh:
                user = json.load(fh)
        except (OSError, ValueError) as e:
            print(f"readme-authoring: ignoring unreadable {CONFIG_REL}: {e}", file=sys.stderr)
            return cfg
        cfg["style"] = user.get("style", cfg["style"])
        cfg["freshness"].update(user.get("freshness", {}))
    return cfg


def save_config(root, cfg):
    p = os.path.join(root, CONFIG_REL)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as fh:
        json.dump(cfg, fh, indent=2)
        fh.write("\n")
    return p


def matches(path, globs):
    path = path.replace("\\", "/")
    return any(fnmatch.fnmatch(path, g) or fnmatch.fnmatch(os.path.basename(path), g) for g in globs)


def read(path):
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            return fh.read()
    except OSError:
        return None


# ---------------------------------------------------------------- change set

def change_set(root, include_worktree):
    """Return (changed: {path: status}, added_lines, removed_lines) for source files."""
    base = ["diff", "--no-color", "--no-ext-diff"]
    if include_worktree and git(root, "rev-parse", "--verify", "-q", "HEAD").strip():
        spec = ["HEAD"]
    else:
        spec = ["--cached"]
    changed = {}
    for line in git(root, *base, "--name-status", *spec).splitlines():
        parts = line.split("\t")
        if len(parts) >= 2:
            changed[parts[-1]] = parts[0][0]
    added, removed = [], []
    cur = ""
    for line in git(root, *base, "-U0", *spec).splitlines():
        if line.startswith("+++") or line.startswith("---"):
            continue
        if line.startswith("diff --git"):
            cur = line.split(" b/", 1)[-1]
            continue
        if line.startswith("+"):
            added.append((cur, line[1:]))
        elif line.startswith("-"):
            removed.append((cur, line[1:]))
    if include_worktree:
        for path in git(root, "ls-files", "--others", "--exclude-standard").splitlines():
            changed.setdefault(path, "A")
            text = read(os.path.join(root, path))
            if text is not None and len(text) < 500_000:
                added.extend((path, l) for l in text.splitlines())
    return changed, added, removed


def tokens(lines, rx, envfile=False):
    found = set()
    for path, line in lines:
        if path.endswith(DOC_EXT):
            continue
        if envfile and matches(path, [".env.example", ".env.sample", "*.env.example"]):
            m = ENVFILE_RE.match(line)
            if m:
                found.add(m.group(1))
            continue
        for m in rx.finditer(line):
            found.add(next(g for g in m.groups() if g))
    return found


def still_in_code(root, token):
    out = git(root, "grep", "-I", "-l", "-F", "--", token)
    return any(not p.endswith(DOC_EXT) for p in out.splitlines())


# ---------------------------------------------------------------- checks

def manifest_versions(root):
    out = []
    pkg = read(os.path.join(root, "package.json"))
    if pkg:
        try:
            d = json.loads(pkg)
            if d.get("name") and d.get("version"):
                out.append((d["name"], d["version"]))
        except ValueError:
            pass
    for fname, section in (("pyproject.toml", r"\[(?:project|tool\.poetry)\]"), ("Cargo.toml", r"\[package\]")):
        t = read(os.path.join(root, fname))
        if not t:
            continue
        m = re.search(section + r"(.*?)(?:\n\[|\Z)", t, re.S)
        if m:
            n = re.search(r"^name\s*=\s*\"([^\"]+)\"", m.group(1), re.M)
            v = re.search(r"^version\s*=\s*\"([^\"]+)\"", m.group(1), re.M)
            if n and v:
                out.append((n.group(1), v.group(1)))
    return out


def code_text(text):
    """Only the parts of a README a reader would execute: fenced blocks and inline code spans."""
    parts = re.findall(r"^\s*(?:```|~~~)[^\n]*\n(.*?)^\s*(?:```|~~~)", text, re.S | re.M)
    prose = re.sub(r"^\s*(?:```|~~~)[^\n]*\n.*?^\s*(?:```|~~~)", "", text, flags=re.S | re.M)
    parts += re.findall(r"`([^`\n]+)`", prose)
    parts += re.findall(r"^(?: {4}|\t)(.+)$", prose, re.M)  # indented code blocks (st, rst-ish)
    return "\n".join(parts)


def run_checks(root, cfg, include_worktree=False, full=False):
    fcfg = cfg["freshness"]
    readme_rel = fcfg.get("readme", "README.md")
    readme_path = os.path.join(root, readme_rel)
    findings = []

    def add(sev, check, msg, line=None):
        findings.append({"severity": sev, "check": check, "message": msg, "line": line})

    text = read(readme_path)
    if text is None:
        add("warn", "missing-readme", f"No README at {readme_rel}.")
        return readme_rel, findings
    lines = text.splitlines()
    readme_dir = os.path.dirname(readme_path)

    def line_of(needle):
        for i, l in enumerate(lines, 1):
            if needle in l:
                return i
        return None

    changed, added, removed = ({}, [], []) if full else change_set(root, include_worktree)
    deleted = {p for p, s in changed.items() if s == "D"}

    # broken-link: local targets only.
    targets = set(LINK_RE.findall(text)) | set(REF_LINK_RE.findall(text)) | set(HTML_SRC_RE.findall(text))
    for t in sorted(targets):
        if re.match(r"^([a-z][a-z0-9+.-]*:|//|#|\{|\$)", t, re.I):
            continue
        clean = t.split("#")[0].split("?")[0]
        if not clean:
            continue
        base = root if clean.startswith("/") else readme_dir  # GitHub resolves /x from the repo root
        full_path = os.path.normpath(os.path.join(base, clean.lstrip("/")))
        rel = os.path.relpath(full_path, root).replace("\\", "/")
        if not os.path.exists(full_path) or rel in deleted:
            add("error", "broken-link", f"Links to {clean}, which does not exist.", line_of(t))

    # missing-script: npm/pnpm/yarn/bun run X, make X.
    pkg = read(os.path.join(root, "package.json"))
    scripts = None
    if pkg:
        try:
            scripts = json.loads(pkg).get("scripts", {}) or {}
        except ValueError:
            scripts = None
    code = code_text(text)
    if scripts is not None:
        for tool, name in sorted(set(SCRIPT_RUN_RE.findall(code))):
            if name not in scripts:
                add("error", "missing-script", f"`{tool} run {name}`: no '{name}' script in package.json.",
                    line_of(f"run {name}"))
    mk = read(os.path.join(root, "Makefile")) or read(os.path.join(root, "makefile"))
    if mk and "include " not in mk:
        targets_def = set()
        for m in re.finditer(r"^([^\s:#=][^:#=]*?)\s*::?(?!=)", mk, re.M):
            targets_def.update(m.group(1).split())
        if any("%" in t for t in targets_def):  # pattern rules: can't verify targets statically
            targets_def = None
        for group in MAKE_RE.findall(code) if targets_def is not None else []:
            for tgt in group.split():
                if tgt.startswith("-") or "=" in tgt or not re.match(r"^[\w.-]+$", tgt):
                    break
                if tgt in targets_def:
                    continue
                add("error", "missing-script", f"`make {tgt}`: no '{tgt}' target in the Makefile.",
                    line_of(f"make {tgt}"))

    # stale-version: README pins a version of *this* package that differs from the manifest.
    for name, version in manifest_versions(root):
        n = re.escape(name)
        pat = re.compile(
            rf"(?:{n}@|{n}==|{n}\s*=\s*\"|\"{n}\"\s*:\s*\"[\^~]?|\[{n}\s+\"|{n}:)v?(\d+\.\d+(?:\.\d+)?(?:[-.\w]*)?)")
        for m in pat.finditer(text):
            pinned = m.group(1).rstrip(".")
            if pinned != version and not version.startswith(pinned + "."):
                add("warn", "stale-version", f"README pins {name} {pinned}; manifest says {version}.",
                    line_of(m.group(0)))

    if not full:
        readme_in_commit = readme_rel.replace("\\", "/") in changed
        readme_flags = set(README_FLAG_RE.findall(text))
        readme_words = set(re.findall(r"[A-Z][A-Z0-9_]{2,}", text))

        add_flags, rm_flags = tokens(added, FLAG_RE), tokens(removed, FLAG_RE)
        for f in sorted(rm_flags - add_flags):
            if f in readme_flags and not still_in_code(root, f):
                add("error", "removed-flag", f"README documents {f}, which this change removes from the code.", line_of(f))
        if readme_flags:
            for f in sorted(add_flags - rm_flags - readme_flags):
                add("warn", "undocumented-flag", f"New flag {f} is not mentioned in the README.")

        add_env = tokens(added, ENV_RE, envfile=True)
        rm_env = tokens(removed, ENV_RE, envfile=True)
        for e in sorted(rm_env - add_env):
            if e in readme_words and not still_in_code(root, e):
                add("error", "removed-env", f"README documents {e}, which this change removes from the code.", line_of(e))
        known_env = tokens([(p, l) for p, l in added + removed], ENV_RE, envfile=True)
        documents_env = bool(readme_words & (known_env | {"PATH", "HOME"})) or re.search(r"environment variables?", text, re.I)
        if documents_env:
            for e in sorted(add_env - rm_env - readme_words):
                add("warn", "undocumented-env", f"New environment variable {e} is not mentioned in the README.")

        surface = SURFACE_GLOBS + list(fcfg.get("extraSurface", []))
        ignore = list(fcfg.get("ignore", []))
        touched = sorted(p for p in changed if matches(p, surface) and not matches(p, ignore))
        if touched and not readme_in_commit:
            shown = ", ".join(touched[:6]) + (f" (+{len(touched) - 6} more)" if len(touched) > 6 else "")
            add("warn", "surface-touched", f"Public-surface files changed ({shown}) but {readme_rel} is not in this commit.")

        if readme_in_commit:  # the author is already updating it; keep only hard errors
            findings = [f for f in findings if f["severity"] == "error"]

    ignore = set(fcfg.get("ignoreChecks", []))
    findings = [f for f in findings if f["check"] not in ignore]
    return readme_rel, findings


def render(readme_rel, findings):
    out = [f"README freshness ({readme_rel}): {len(findings)} finding(s)"]
    for f in findings:
        loc = f" L{f['line']}" if f.get("line") else ""
        out.append(f"  [{f['severity']}] {f['check']}{loc}: {f['message']}")
    return "\n".join(out)


# ---------------------------------------------------------------- hook modes

COMMIT_RE = re.compile(r"(?:^|[;&|(\s])git(?:\s+-[cC]\s+\S+|\s+--[\w-]+(?:=\S+)?)*\s+commit\b")


def commit_target(command, cwd):
    """Best-effort: the directory a `git commit` in this command line will run in."""
    target = cwd
    m = re.search(r"(?:^|[;&|]\s*)cd\s+(\"[^\"]+\"|'[^']+'|\S+)\s*&&[^;|]*\bgit\b", command)
    if m:
        target = os.path.join(cwd, m.group(1).strip("\"'"))
    m = re.search(r"\bgit\s+-C\s+(\"[^\"]+\"|'[^']+'|\S+)[^;&|]*\bcommit\b", command)
    if m:
        target = os.path.join(target, m.group(1).strip("\"'"))
    return target


def stages_in_command(command):
    head = command[: COMMIT_RE.search(command).start() + 1]
    return bool(re.search(r"\bgit\s+add\b", head)) or bool(re.search(r"\bcommit\b[^;&|]*\s-(\w*a\w*)\b", command))


def cmd_hook(_args):
    try:
        payload = json.load(sys.stdin)
    except ValueError:
        return 0
    if payload.get("tool_name") != "Bash":
        return 0
    command = (payload.get("tool_input") or {}).get("command", "")
    if not COMMIT_RE.search(command) or re.search(r"\bREADME_FRESHNESS_SKIP=1\b", command):
        return 0
    if re.search(r"\bcommit\b[^;&|]*--(amend\b[^;&|]*--no-edit|dry-run)", command):
        return 0
    root = repo_root(commit_target(command, payload.get("cwd") or os.getcwd()))
    if not root:
        return 0
    cfg = load_config(root)
    if not cfg["freshness"].get("enabled"):
        return 0
    readme_rel, findings = run_checks(root, cfg, include_worktree=stages_in_command(command))
    if not findings:
        return 0
    report = render(readme_rel, findings)
    style = cfg.get("style") or "not recorded"
    instructions = (
        f"{report}\n\nRun the readme-authoring skill in freshness mode on {readme_rel} "
        f"(recorded style: {style}). Fix real staleness in the README; leave false positives alone. "
    )
    if cfg["freshness"].get("mode") == "block":
        reason = instructions + (
            "Then retry the commit with the README change staged. If, after review, the README "
            "genuinely needs no change, retry with the command prefixed by README_FRESHNESS_SKIP=1 "
            "and tell the user why.")
        print(json.dumps({"hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason}}))
    else:
        print(json.dumps({
            "systemMessage": f"README freshness: {len(findings)} finding(s), sent to Claude for review.",
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "additionalContext": instructions + "The commit is proceeding (warn mode); "
                "follow up with a README commit if the review finds real staleness."}}))
    return 0


def cmd_git_hook(_args):
    if os.environ.get("README_FRESHNESS_SKIP") == "1":
        return 0
    root = repo_root(os.getcwd())
    if not root:
        return 0
    cfg = load_config(root)
    if not cfg["freshness"].get("enabled"):
        return 0
    readme_rel, findings = run_checks(root, cfg)
    if not findings:
        return 0
    print(render(readme_rel, findings), file=sys.stderr)
    if cfg["freshness"].get("mode") == "block":
        print("Commit blocked. Update the README, or re-run with README_FRESHNESS_SKIP=1.", file=sys.stderr)
        return 1
    return 0


def cmd_check(args):
    root = repo_root(args.path)
    if not root:
        print("not a git repository", file=sys.stderr)
        return 2
    cfg = load_config(root)
    if args.readme:
        cfg["freshness"]["readme"] = args.readme
    readme_rel, findings = run_checks(root, cfg, include_worktree=args.worktree, full=args.full)
    if args.json:
        print(json.dumps({"readme": readme_rel, "findings": findings}, indent=2))
    else:
        print(render(readme_rel, findings))
    return 1 if any(f["severity"] == "error" for f in findings) else 0


# ---------------------------------------------------------------- enable / disable

def settings_path(root, scope):
    return os.path.join(root, ".claude", "settings.local.json" if scope == "local" else "settings.json")


def hook_command():
    py = sys.executable.replace("\\", "/")
    return f'"{py}" "{SCRIPT_PATH}" hook'


def ensure_gitignored(root, rel):
    gi = os.path.join(root, ".gitignore")
    existing = read(gi) or ""
    if rel in existing.splitlines():
        return False
    with open(gi, "a", encoding="utf-8") as fh:
        if existing and not existing.endswith("\n"):
            fh.write("\n")
        fh.write(rel + "\n")
    return True


def register_claude_hook(root, scope):
    p = settings_path(root, scope)
    data = {}
    if os.path.exists(p):
        with open(p, encoding="utf-8") as fh:
            raw = fh.read().strip()
        data = json.loads(raw) if raw else {}
    pre = data.setdefault("hooks", {}).setdefault("PreToolUse", [])
    for group in pre:
        for h in group.get("hooks", []):
            if HOOK_MARKER in h.get("command", ""):
                h["command"] = hook_command()
                break
        else:
            continue
        break
    else:
        pre.append({"matcher": "Bash", "hooks": [{
            "type": "command", "command": hook_command(), "timeout": 30,
            "statusMessage": "Checking README freshness"}]})
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2)
        fh.write("\n")
    notes = [f"registered PreToolUse hook in {os.path.relpath(p, root)}"]
    if scope == "local" and ensure_gitignored(root, ".claude/settings.local.json"):
        notes.append("added .claude/settings.local.json to .gitignore")
    return notes


def unregister_claude_hook(root):
    notes = []
    for scope in ("local", "project"):
        p = settings_path(root, scope)
        if not os.path.exists(p):
            continue
        with open(p, encoding="utf-8") as fh:
            raw = fh.read().strip()
        if not raw:
            continue
        data = json.loads(raw)
        pre = data.get("hooks", {}).get("PreToolUse", [])
        kept, dropped = [], 0
        for group in pre:
            before = len(group.get("hooks", []))
            group["hooks"] = [h for h in group.get("hooks", []) if HOOK_MARKER not in h.get("command", "")]
            dropped += before - len(group["hooks"])
            if group["hooks"]:
                kept.append(group)
        if dropped:
            data["hooks"]["PreToolUse"] = kept
            if not kept:
                del data["hooks"]["PreToolUse"]
            if not data["hooks"]:
                del data["hooks"]
            with open(p, "w", encoding="utf-8") as fh:
                json.dump(data, fh, indent=2)
                fh.write("\n")
            notes.append(f"removed hook from {os.path.relpath(p, root)}")
    return notes


def git_hook_file(root):
    hooks_dir = git(root, "rev-parse", "--git-path", "hooks").strip()
    hooks_dir = os.path.join(root, hooks_dir) if not os.path.isabs(hooks_dir) else hooks_dir
    return os.path.join(hooks_dir, "pre-commit")


def register_git_hook(root):
    p = git_hook_file(root)
    body = f'#!/bin/sh\n# {HOOK_MARKER} (readme-authoring skill)\nexec "{sys.executable.replace(chr(92), "/")}" "{SCRIPT_PATH}" git-hook\n'
    if os.path.exists(p):
        if HOOK_MARKER in (read(p) or ""):
            with open(p, "w", encoding="utf-8", newline="\n") as fh:
                fh.write(body)
            return [f"refreshed git pre-commit hook at {p}"]
        return [f"left existing git pre-commit hook at {p} untouched; add this line to it yourself:\n"
                f'    "{sys.executable}" "{SCRIPT_PATH}" git-hook || exit 1']
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(body)
    os.chmod(p, 0o755)
    return [f"installed git pre-commit hook at {p}"]


def unregister_git_hook(root):
    p = git_hook_file(root)
    if os.path.exists(p) and HOOK_MARKER in (read(p) or "") and (read(p) or "").startswith("#!/bin/sh\n# " + HOOK_MARKER):
        os.remove(p)
        return [f"removed git pre-commit hook at {p}"]
    return []


def cmd_enable(args):
    root = repo_root(args.path)
    if not root:
        print("not a git repository", file=sys.stderr)
        return 2
    cfg = load_config(root)
    cfg["freshness"]["enabled"] = True
    cfg["freshness"]["mode"] = args.mode
    if args.readme:
        cfg["freshness"]["readme"] = args.readme
    notes = [f"wrote {os.path.relpath(save_config(root, cfg), root)} (enabled, mode={args.mode})"]
    if args.target in ("claude", "both"):
        notes += register_claude_hook(root, args.scope)
    if args.target in ("git", "both"):
        notes += register_git_hook(root)
    print("\n".join(notes))
    return 0


def cmd_disable(args):
    root = repo_root(args.path)
    if not root:
        print("not a git repository", file=sys.stderr)
        return 2
    cfg = load_config(root)
    cfg["freshness"]["enabled"] = False
    notes = [f"wrote {os.path.relpath(save_config(root, cfg), root)} (disabled)"]
    if args.remove_hooks:
        notes += unregister_claude_hook(root) + unregister_git_hook(root)
    print("\n".join(notes))
    return 0


def cmd_status(args):
    root = repo_root(args.path)
    if not root:
        print("not a git repository", file=sys.stderr)
        return 2
    cfg = load_config(root)
    print(json.dumps(cfg, indent=2))
    for scope in ("local", "project"):
        p = settings_path(root, scope)
        print(f"{os.path.relpath(p, root)}: {'hook registered' if HOOK_MARKER in (read(p) or '') else 'no hook'}")
    gp = git_hook_file(root)
    print(f"git pre-commit: {'installed' if HOOK_MARKER in (read(gp) or '') else 'not installed'}")
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)

    c = sub.add_parser("check")
    c.add_argument("path", nargs="?", default=".")
    c.add_argument("--readme")
    c.add_argument("--worktree", action="store_true", help="include unstaged and untracked changes")
    c.add_argument("--full", action="store_true", help="whole-README audit, ignore the diff")
    c.add_argument("--json", action="store_true")
    c.set_defaults(fn=cmd_check)

    sub.add_parser("hook").set_defaults(fn=cmd_hook)
    sub.add_parser("git-hook").set_defaults(fn=cmd_git_hook)

    e = sub.add_parser("enable")
    e.add_argument("path", nargs="?", default=".")
    e.add_argument("--mode", choices=["warn", "block"], default="warn")
    e.add_argument("--target", choices=["claude", "git", "both"], default="claude")
    e.add_argument("--scope", choices=["local", "project"], default="local")
    e.add_argument("--readme")
    e.set_defaults(fn=cmd_enable)

    d = sub.add_parser("disable")
    d.add_argument("path", nargs="?", default=".")
    d.add_argument("--remove-hooks", action="store_true")
    d.set_defaults(fn=cmd_disable)

    s = sub.add_parser("status")
    s.add_argument("path", nargs="?", default=".")
    s.set_defaults(fn=cmd_status)

    args = ap.parse_args()
    try:
        sys.exit(args.fn(args))
    except Exception as exc:  # a hook must never wedge a commit on its own bug
        if args.cmd in ("hook", "git-hook"):
            print(f"readme-authoring freshness check skipped (internal error: {exc})", file=sys.stderr)
            sys.exit(0)
        raise


if __name__ == "__main__":
    main()
