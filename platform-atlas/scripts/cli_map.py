"""Map an installed CLI's command tree into `<kb>/cli/<cli>.md`, dated, for grep-style lookups.

  python -I <skill>/scripts/cli_map.py az            map one CLI (see CLIS below for the names)
  python -I <skill>/scripts/cli_map.py --all         map every installed CLI in CLIS
  python -I <skill>/scripts/cli_map.py az --raw "ad sp"   print the raw help for one path (to tune parsing)
  python -I <skill>/scripts/cli_map.py --list        show which CLIs are installed and their versions

It runs each CLI's own help, so the map matches the installed version. It records the version and
today's date; `atlas.py cli-find` prints both with every hit. Each map has: the top-level groups, the
groups listed in `expand` one level down, and the full help of the commands in `full` (sign-in and
configuration, which agents need most). Standard library only.
"""
import argparse
import datetime
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from kg import paths  # noqa: E402

# help: argv after the command, with {path} replaced by the command path ("" at the top).
CLIS = {
    "aws": {"platform": "aws", "install": "winget install -e --id Amazon.AWSCLI", "version": ["--version"],
            "help": ["{path}", "help"], "env": {"AWS_PAGER": "", "PAGER": "more"},
            "expand": ["bedrock", "bedrock-runtime", "bedrock-agent", "bedrock-agent-runtime", "bedrock-agentcore",
                       "bedrock-agentcore-control", "iam", "sts", "sso", "sso-oidc", "sso-admin", "identitystore",
                       "organizations", "lambda", "stepfunctions", "events", "secretsmanager", "s3api", "sagemaker",
                       "q", "qbusiness", "configure"],
            "full": ["configure sso", "sso login", "login", "configure export-credentials"]},
    "az": {"platform": "azure", "install": "winget install -e --id Microsoft.AzureCLI  (MSI needs admin; without admin: uv tool install azure-cli==<version> --python 3.13 --prerelease=allow)", "version": ["version", "-o", "json"],
           "help": ["{path}", "-h"],
           "expand": ["account", "ad", "ad sp", "ad app", "role", "identity", "cognitiveservices", "ml", "apim",
                      "functionapp", "logicapp", "keyvault", "network private-endpoint", "search", "resource", "group",
                      "deployment", "containerapp", "monitor"],
           "full": ["login", "account get-access-token", "ad sp create-for-rbac", "role assignment create",
                    "identity federated-credential create"]},
    "azd": {"platform": "azure", "install": "winget install -e --id Microsoft.Azd", "version": ["version"],
            "help": ["{path}", "--help"], "expand": ["auth", "env", "ai", "pipeline"], "full": ["auth login", "up"]},
    "gcloud": {"platform": "gcp", "install": "winget install -e --id Google.CloudSDK", "version": ["version"],
               "help": ["{path}", "--help"], "env": {"CLOUDSDK_CORE_DISABLE_PROMPTS": "1", "PAGER": "", "CLOUDSDK_PAGER": ""},
               "expand": ["auth", "config", "iam", "iam service-accounts", "iam workload-identity-pools", "projects",
                          "services", "ai", "ai models", "ai endpoints", "ai reasoning-engines", "run", "functions",
                          "secrets", "beta mcp", "alpha mcp", "apigee", "organizations", "resource-manager"],
               "full": ["auth login", "auth application-default login", "auth print-access-token",
                        "iam service-accounts add-iam-policy-binding", "iam workload-identity-pools create-cred-config"]},
    "bq": {"platform": "gcp", "col0": True, "headerless": True, "install": "ships with the Google Cloud SDK", "version": ["version"],
           "help": ["{path}", "help"], "expand": [], "full": ["query"]},
    "databricks": {"platform": "databricks", "headerless": True, "install": "winget install -e --id Databricks.DatabricksCLI",
                   "version": ["version"], "help": ["{path}", "--help"],
                   "expand": ["auth", "bundle", "apps", "serving-endpoints", "vector-search-endpoints",
                              "vector-search-indexes", "genie", "catalogs", "schemas", "tables", "functions", "grants",
                              "connections", "service-principals", "account", "workspace", "jobs", "pipelines",
                              "warehouses", "secrets", "api", "lakeview", "database"],
                   "full": ["auth login", "auth token", "auth profiles", "bundle deploy", "apps deploy", "api"]},
    "snow": {"platform": "snowflake", "install": "uv tool install snowflake-cli  (or: pip install snowflake-cli)",
             "version": ["--version"], "help": ["{path}", "--help"],
             "expand": ["connection", "sql", "cortex", "object", "stage", "snowpark", "spcs", "app", "streamlit",
                        "notebook", "git", "dbt", "auth", "helpers", "logs"],
             "full": ["connection add", "connection test", "sql", "cortex complete", "auth keypair setup"]},
    "oci": {"platform": "oci", "sticky": True, "install": "uv tool install oci-cli  (or the Windows installer script from docs.oracle.com)",
            "version": ["--version"], "help": ["{path}", "--help"],
            "expand": ["iam", "iam policy", "iam dynamic-group", "iam domain", "identity-domains", "generative-ai",
                       "generative-ai-inference", "generative-ai-agent", "generative-ai-agent-runtime", "db",
                       "fn", "api-gateway", "integration", "vault", "secrets", "session", "setup", "raw-request"],
            "full": ["setup config", "session authenticate", "setup repair-file-permissions", "raw-request"]},
    "sf": {"platform": "salesforce", "install": "npm install -g @salesforce/cli", "version": ["--version"],
           "help": ["{path}", "--help"], "listing": ["commands", "--json"],
           "full": ["org login web", "org login jwt", "org login access-token", "agent", "agent create", "agent preview",
                    "api request rest"]},
    "pac": {"platform": "microsoft-copilot", "headerless": True, "install": "winget install -e --id Microsoft.PowerAppsCLI  (or: dotnet tool install --global Microsoft.PowerApps.CLI.Tool)",
            "version": [], "help": ["{path}", "help"],
            "expand": ["auth", "env", "solution", "copilot", "connector", "connection", "admin", "org", "pages",
                       "code", "pipeline"],
            "full": ["auth create", "auth list", "copilot", "solution export", "env select"]},
    "m365": {"platform": "microsoft-copilot", "install": "npm install -g @pnp/cli-microsoft365", "version": ["version"],
             "help": ["{path}", "--help"], "expand": ["entra", "spo", "teams", "pp", "flow", "copilot", "cli"],
             "full": ["login", "setup"]},
    "gemini": {"platform": "google-ai", "install": "npm install -g @google/gemini-cli", "version": ["--version"],
               "help": ["{path}", "--help"], "expand": ["mcp", "extensions"], "full": ["", "mcp add"]},
    "agy": {"platform": "google-ai", "install": "irm https://antigravity.google/cli/install.ps1 | iex  (installs to %LOCALAPPDATA%/agy/bin)",
            "version": ["--version"], "help": ["{path}", "--help"], "expand": [], "full": [""]},
    "codex": {"platform": "openai", "install": "npm install -g @openai/codex", "version": ["--version"],
              "help": ["{path}", "--help"], "expand": ["mcp", "cloud"], "full": ["", "login", "exec", "mcp add"]},
    "claude": {"platform": "anthropic", "install": "npm install -g @anthropic-ai/claude-code  (or the native installer)",
               "version": ["--version"], "help": ["{path}", "--help"], "expand": ["mcp", "plugin"],
               "full": ["", "mcp add", "setup-token"]},
}

ANSI = re.compile(r"\x1b\[[0-9;?]*[ -/]*[@-~]")
def _search_path():
    """PATH plus, on Windows, the registry's machine and user PATH, so CLIs installed this session resolve."""
    parts = os.environ.get("PATH", "").split(os.pathsep)
    if os.name == "nt":
        import winreg
        for hive, key in ((winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment"),
                          (winreg.HKEY_CURRENT_USER, "Environment")):
            try:
                with winreg.OpenKey(hive, key) as k:
                    parts += os.path.expandvars(winreg.QueryValueEx(k, "Path")[0]).split(os.pathsep)
            except OSError:
                pass
    return os.pathsep.join(dict.fromkeys(p for p in parts if p))


SEARCH_PATH = _search_path()


def which(name):
    for n in (name, name + ".cmd", name + ".exe"):
        hit = shutil.which(n, path=SEARCH_PATH)
        if hit:
            return hit
    return None


def run(exe, argv, env=None, timeout=90):
    e = {**os.environ, "PATH": SEARCH_PATH, "NO_COLOR": "1", "TERM": "dumb", "COLUMNS": "200", "PYTHONIOENCODING": "utf-8", **(env or {})}
    try:
        p = subprocess.run([exe, *argv], capture_output=True, text=True, encoding="utf-8", errors="replace",
                           timeout=timeout, env=e, stdin=subprocess.DEVNULL)
    except (OSError, subprocess.TimeoutExpired) as x:
        return f"(could not run: {x})"
    out = (p.stdout or "") + ("\n" + p.stderr if p.stderr and len(p.stdout or "") < 200 else "")
    out = ANSI.sub("", out).replace("\r", "")
    out = re.sub(r".\x08", "", out)  # man-page overstrike (bold) from `aws help`
    home = str(Path.home())
    for h in {home, home.replace("\\", "/")}:  # keep local paths out of maps that get shared
        out = re.sub(re.escape(h), "~", out, flags=re.I)
    return out


def help_argv(spec, path):
    out = []
    for a in spec["help"]:
        if a == "{path}":
            out += path.split() if path else []
        else:
            out.append(a)
    return out


BOX = "│┃|┌┐└┘╭╮╰╯├┤─━+�"
HEADER_WORDS = re.compile(r"^(?:available\s+)?(?:commands|subcommands|subgroups|groups|services|topics|management commands)"
                          r"|^[A-Za-z][\w &/-]{0,40}\s(?:commands|groups)$|^any of the following commands", re.I)
ENTRY = re.compile(r"^(\s*)(?:[*o•]\s+|-\s+(?!-))?([A-Za-z][\w:.\-]*)(?:\s+[\[<][^\]>]+[\]>])*(?:\s*:\s+|\s{2,})(\S.*)$")
BULLET = re.compile(r"^\s*(?:[*o•]|-(?!-))\s+([A-Za-z][\w:.\-]*)\s*$")
NAME_ALONE = re.compile(r"^\s+([a-z][\w:.\-]*)\s*$")
UNDERLINE = re.compile(r"^\s*([*=^~\-])\1{2,}\s*$")


def _clean(line):
    """A help line without box-drawing borders, trailing padding or the replacement character."""
    s = line.replace("�", "")
    s = re.sub(r"^\s*[│┃|]", " ", s)
    s = re.sub(r"[│┃|]\s*$", "", s)
    return s.rstrip()


def _is_header(line):
    s = line.strip(" " + BOX + ":").strip()
    return bool(s) and len(s) < 60 and HEADER_WORDS.match(s) is not None


def parse(text, path="", headerless=False, col0=False, sticky=False, cli=""):
    """[(name, description)] from the command sections of a help text.

    Handles `Commands:` sections (click, cobra, clap, commander, yargs, argparse, az), rich/typer boxes,
    man-page `* name` bullets (aws), and, with `headerless`, CLIs that list commands without a section
    header (pac, databricks group headings). `col0` accepts entries that start at column 0 (bq); `sticky` keeps
    reading after the first command header through free-text category headings (oci); `cli` strips a leading
    CLI name from entries ("gemini mcp  Manage MCP servers")."""
    out, seen = [], set()
    parts = path.split()
    skip = {"help", "usage", "version", *(p.lower() for p in parts[-1:])}
    in_sec = headerless
    for raw in text.splitlines():
        if UNDERLINE.match(raw) or set(raw.strip()) <= set(BOX + " "):
            continue
        line = _clean(raw)
        if cli:
            line = re.sub(rf"^(\s+){re.escape(cli)}\s+(?=[a-z])", r"\1", line)
        if _is_header(line):
            in_sec = True
            continue
        if not in_sec:
            continue
        m = ENTRY.match(line)
        b = BULLET.match(line)
        indented = line[:1].isspace() or raw.lstrip()[:1] in "│┃|"
        if m and (indented or col0 or m.group(1) or line.lstrip()[:1] in "*•"):
            name, desc = m.group(2), m.group(3).strip()
        elif b:
            name, desc = b.group(1), ""
        elif NAME_ALONE.match(line) and (not out or out[-1][1]):
            name, desc = NAME_ALONE.match(line).group(1), ""
        else:
            if line and not indented and not headerless and not sticky and line.lstrip()[:1] not in "*•":
                in_sec = False  # a new non-command section (Options:, Examples:, Global Flags: ...)
            elif out and line.strip() and indented and not line.strip().startswith("-") and len(out[-1][1]) < 300:
                out[-1] = (out[-1][0], (out[-1][1] + " " + line.strip()).strip())  # wrapped description
            continue
        if name.startswith("-") or name.lower() in skip or name in seen or len(name) > 60:
            continue
        if parts and name == parts[0]:
            continue
        seen.add(name)
        out.append((name, desc))
    return [(n, d if len(d) <= 220 else d[:217].rstrip() + "...") for n, d in out]


def version_of(exe, spec):
    if not spec.get("version"):
        text = run(exe, [])
    else:
        text = run(exe, spec["version"])
    m = re.search(r"\d+\.\d+(?:\.\d+)?(?:[-.\w]*)?", text)
    return (m.group(0) if m else text.strip().splitlines()[0][:80] if text.strip() else "unknown")


def map_cli(name, max_full=4000):
    spec = CLIS[name]
    exe = which(name)
    if not exe:
        return {"cli": name, "installed": False, "install": spec["install"]}
    today = datetime.date.today().isoformat()
    ver = version_of(exe, spec)
    env = spec.get("env")
    lines = ["---", f"cli: {name}", f"platform: {spec['platform']}", f"as_of: {today}", f"version: {ver}",
             f"install: {spec['install']}", "---",
             f"# `{name}` command map (as of {today}, version {ver})", "",
             f"Generated by `scripts/cli_map.py {name}` from the installed CLI's own help. Search it with "
             f"`atlas.py cli-find \"<words>\" --cli {name}`; run `{name} <command> --help` for full usage.", ""]
    counts = {}
    if spec.get("listing"):
        text = run(exe, spec["listing"], env)
        try:
            cmds = json.loads(text[text.index("["):])
        except ValueError:
            cmds = []
        lines += [f"## All commands ({len(cmds)})", ""]
        for c in sorted(cmds, key=lambda c: c.get("id", "")):
            cid = c.get("id", "").replace(":", " ")
            lines.append(f"- `{name} {cid}`: {(c.get('summary') or c.get('description') or '').strip().splitlines()[0] if (c.get('summary') or c.get('description')) else ''}")
        counts["listing"] = len(cmds)
    else:
        opts = {k: spec.get(k, False) for k in ("headerless", "col0", "sticky")}
        opts["cli"] = name
        top = parse(run(exe, help_argv(spec, ""), env), **opts)
        lines += [f"## `{name}` ({len(top)} top-level)", ""] + [f"- `{name} {n}`: {d}" for n, d in top] + [""]
        counts[""] = len(top)
        names = {n for n, _ in top}
        for path in spec.get("expand", []):
            if path.split()[0] not in names and top:
                continue
            sub = parse(run(exe, help_argv(spec, path), env), path, **opts)
            if not sub:
                continue
            counts[path] = len(sub)
            lines += [f"## `{name} {path}` ({len(sub)})", ""] + [f"- `{name} {path} {n}`: {d}" for n, d in sub] + [""]
    for path in spec.get("full", []):
        text = run(exe, help_argv(spec, path), env).strip()
        if not text or text.startswith("(could not run") or re.search(r"(?i)unknown (command|option)|is not a .*command|invalid choice", text[:400]):
            continue
        if len(text) > max_full:
            text = text[:max_full] + "\n... (truncated)"
        lines += [f"## Full help: `{name} {path}`".replace(" `", " `").rstrip(), "", "```text", text, "```", ""]
    out = paths.cli_dir() / f"{name}.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8", newline="\n")
    return {"cli": name, "installed": True, "version": ver, "file": str(out), "sections": counts}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cli", nargs="?")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--raw")
    a = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    if a.list:
        rows = []
        for n, s in CLIS.items():
            exe = which(n)
            rows.append({"cli": n, "platform": s["platform"], "installed": bool(exe),
                         "version": version_of(exe, s) if exe else None, "install": s["install"]})
        print(json.dumps(rows, indent=1))
        return 0
    if a.cli and a.raw is not None:
        exe = which(a.cli)
        print(run(exe, help_argv(CLIS[a.cli], a.raw), CLIS[a.cli].get("env")) if exe else f"{a.cli} is not installed")
        return 0
    names = list(CLIS) if a.all else [a.cli]
    if not names or names == [None]:
        ap.error("name a CLI or pass --all")
    unknown = [n for n in names if n not in CLIS]
    if unknown:
        ap.error(f"unknown CLI {unknown}; known: {', '.join(CLIS)}")
    print(json.dumps([map_cli(n) for n in names], indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
