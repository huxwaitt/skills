#!/usr/bin/env python3
"""readme_lint.py - flag the patterns that make a README read as machine-written.

Deterministic and structural: it checks shapes and a fixed word list, not
meaning. A clean score does not make a README good; a high score means a
reader will likely skim past it. Every rule maps to a section of
references/anti-patterns.md.

Usage:
    python readme_lint.py README.md            # human-readable report
    python readme_lint.py README.md --json     # machine-readable
    python readme_lint.py README.md --strict   # exit 1 if score >= threshold

Calibration: the 17 READMEs in references/styles.md all score under the
default threshold (see that file for the scores at the time of writing).
"""
import argparse
import json
import re
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

THRESHOLD = 30

EMOJI = re.compile(
    "[\U0001F300-\U0001FAFF\U00002600-\U000027BF\U0001F000-\U0001F2FF⭐⬆↔-⇿✅❌✨]"
)

# Marketing filler: claims any project could make. Word-boundary matched, case-insensitive.
FILLER = [
    "seamless", "seamlessly", "blazing fast", "blazing-fast", "blazingly fast",
    "lightning fast", "lightning-fast", "cutting-edge", "cutting edge",
    "state-of-the-art", "enterprise-grade", "enterprise grade", "world-class",
    "best-in-class", "next-generation", "next-gen", "game-changing", "game changer",
    "revolutionary", "revolutionize", "supercharge", "supercharged", "unleash",
    "elevate your", "effortless", "effortlessly", "harness the power",
    "unlock the power", "empower", "empowers", "streamline your", "robust and scalable",
    "powerful and flexible", "powerful yet simple", "comprehensive solution",
    "one-stop", "delve", "a testament to", "look no further", "in today's fast-paced",
    "take your .* to the next level",
]
FILLER_RE = re.compile(r"\b(" + "|".join(FILLER) + r")\b", re.I)

BOILERPLATE_CONTRIB = [
    r"fork the (repo|repository|project)",
    r"create (a|your) (new )?(feature )?branch",
    r"git checkout -b feature/",
    r"commit your changes",
    r"push to the branch",
    r"open a pull request",
    r"contributions are (always )?welcome",
    r"any contributions you make are \*\*greatly appreciated\*\*",
]
BOILERPLATE_RE = re.compile("|".join(BOILERPLATE_CONTRIB), re.I)

PLACEHOLDER_RE = re.compile(
    r"(your[-_]?username|your[-_]?user|your[-_]?repo(sitory)?|your[-_]?project[-_]?name|"
    r"<your[^>]*>|\[your [^\]]+\]|\[insert [^\]]+\]|lorem ipsum|"
    r"github\.com/(username|user|yourname|your-name|example)/|you@example\.com|"
    r"\bTODO:? (add|write|fill)\b)",
    re.I,
)

CLOSER_RE = re.compile(
    r"(happy coding|made with (❤️|❤|love)|built with (❤️|❤|love)|"
    r"(give|leave) (it|us|this( repo)?) a ⭐|don'?t forget to (give|star)|"
    r"if you (find|found) this (project )?(useful|helpful).{0,40}star)",
    re.I,
)

EMPTY_MARKERS = re.compile(r"^\s*(coming soon|tbd|to be (added|determined)|todo|wip)\.?\s*$", re.I)

GENERIC_HEADINGS = {
    "features", "key features", "tech stack", "technologies", "technologies used",
    "built with", "prerequisites", "requirements", "installation", "getting started",
    "usage", "project structure", "folder structure", "directory structure",
    "contributing", "license", "acknowledgments", "acknowledgements", "roadmap",
    "contact", "support", "table of contents", "overview", "about", "about the project",
    "demo", "screenshots", "configuration", "faq", "authors", "deployment", "testing",
    "running tests", "environment variables", "api reference", "quick start", "quickstart",
}

TRADEOFF_RE = re.compile(
    r"(\bnot (a|for|designed|intended|meant|support)|\bdoes ?n[o']t\b|\bdon'?t use\b|"
    r"\bwon'?t\b|\blimitations?\b|\btrade-?offs?\b|\bnon-goals?\b|\bcaveats?\b|"
    r"\bknown (issues|problems)\b|\binstead\b|\bunlike\b|\bin return\b|\bat the cost\b|"
    r"\bif you need\b|\balternatives?\b|\bwhy not\b|\bdeprecated\b)",
    re.I,
)

WEIGHTS = {
    "emoji-heading": 4,
    "filler-word": 3,
    "bold-label-bullets": 6,
    "boilerplate-contributing": 6,
    "placeholder": 10,
    "generic-closer": 5,
    "empty-section": 5,
    "template-shaped": 10,
    "tree-dump": 6,
    "no-tradeoff-signal": 6,
    "inflated-opener": 6,
    "em-dash-density": 4,
}


def strip_code(lines):
    """Yield (lineno, line, in_code) with fenced code blocks marked."""
    in_code = False
    fence = None
    for i, line in enumerate(lines, 1):
        m = re.match(r"^\s*(```+|~~~+)", line)
        if m:
            if not in_code:
                in_code, fence = True, m.group(1)[0]
            elif m.group(1)[0] == fence:
                in_code = False
            yield i, line, True
            continue
        yield i, line, in_code


def heading_text(line):
    m = re.match(r"^\s{0,3}(#{1,6})\s+(.*?)\s*#*\s*$", line)
    if not m:
        return None, None
    text = re.sub(r"<[^>]+>|[*_`\[\]]|\(#[^)]*\)", "", m.group(2))
    return len(m.group(1)), text.strip()


def lint(text):
    lines = text.splitlines()
    findings = []

    def add(rule, line, msg):
        findings.append({"rule": rule, "line": line, "message": msg})

    prose_lines = []
    headings = []
    bullet_run = []
    tree_run = 0
    tree_start = None

    for i, line, in_code in strip_code(lines):
        if in_code:
            if re.search(r"[├└]──|\|--|`--", line):
                tree_run += 1
                tree_start = tree_start or i
            continue
        if tree_run >= 12:
            add("tree-dump", tree_start,
                f"{tree_run}-line directory tree. A file listing restates `ls`; name the 2-3 places a reader actually needs.")
        tree_run, tree_start = 0, None

        level, htext = heading_text(line)
        if level:
            headings.append((i, level, htext))
            if EMOJI.search(line):
                add("emoji-heading", i, f"Emoji in heading: {htext!r}")
            continue

        bm = re.match(r"^\s*[-*+]\s+\*\*[^*]{1,60}\*\*\s*[:—–-]", line)
        if bm:
            bullet_run.append(i)
        elif line.strip():
            if len(bullet_run) >= 4:
                add("bold-label-bullets", bullet_run[0],
                    f"{len(bullet_run)} consecutive '**Label**: blurb' bullets. Fine when each carries a real decision; slop when they list virtues.")
            bullet_run = []

        if line.strip() and not line.lstrip().startswith(("<", "[![", "![", "|")):
            prose_lines.append((i, line))

        for m in FILLER_RE.finditer(line):
            add("filler-word", i, f"Filler: {m.group(0)!r}. Replace with the evidence (a number, an output, a comparison).")
        if BOILERPLATE_RE.search(line):
            add("boilerplate-contributing", i, "Stock 'fork, branch, PR' contributing text. Say what is actually wanted, or link CONTRIBUTING.md.")
        pm = PLACEHOLDER_RE.search(line)
        if pm:
            add("placeholder", i, f"Unfilled placeholder: {pm.group(0)!r}")
        cm = CLOSER_RE.search(line)
        if cm:
            add("generic-closer", i, f"Generic sign-off: {cm.group(0)!r}")

    if len(bullet_run) >= 4:
        add("bold-label-bullets", bullet_run[0], f"{len(bullet_run)} consecutive '**Label**: blurb' bullets.")
    if tree_run >= 12:
        add("tree-dump", tree_start, f"{tree_run}-line directory tree.")

    # Placeholders inside code blocks matter too (clone URLs).
    for i, line, in_code in strip_code(lines):
        if in_code and PLACEHOLDER_RE.search(line):
            add("placeholder", i, f"Unfilled placeholder in code: {PLACEHOLDER_RE.search(line).group(0)!r}")

    # Empty sections: a heading followed by nothing (or only 'Coming soon') before the next heading.
    for idx, (ln, level, htext) in enumerate(headings):
        end = headings[idx + 1][0] if idx + 1 < len(headings) else len(lines) + 1
        body = [l for l in lines[ln:end - 1] if l.strip()]
        nxt_level = headings[idx + 1][1] if idx + 1 < len(headings) else 0
        if nxt_level > level:  # parent of a subsection; body lives below
            continue
        if not body or all(EMPTY_MARKERS.match(l) for l in body):
            add("empty-section", ln, f"Section {htext!r} is empty or 'coming soon'. Delete it until it has content.")

    # Template shape: mostly generic headings, almost none specific to this project.
    h2 = [h for _, lvl, h in headings if lvl == 2]
    if len(h2) >= 6:
        norm = [re.sub(r"[^a-z ]", "", h.lower()).strip() for h in h2]
        generic = sum(1 for h in norm if h in GENERIC_HEADINGS)
        if generic / len(h2) >= 0.85:
            add("template-shaped", headings[0][0] if headings else 1,
                f"{generic}/{len(h2)} top-level sections are generic template headings. Real READMEs grow sections from the project (e.g. 'Philosophy', 'Release cycle', 'Why not X').")

    prose = "\n".join(l for _, l in prose_lines)
    words = len(re.findall(r"\w+", prose))

    if words >= 150 and not TRADEOFF_RE.search(prose):
        add("no-tradeoff-signal", 1,
            "No trade-off, limitation, non-goal or comparison anywhere. Say what it is NOT for; that is what makes the rest believable.")

    # Opener: first prose sentence.
    first = next((l for _, l in prose_lines if not l.lstrip().startswith(("#", ">", "-", "*"))), "")
    if re.search(r"\bis an? (powerful|modern|comprehensive|robust|cutting-edge|innovative|versatile|sleek|feature-rich|lightweight yet powerful)\b", first, re.I):
        ln = next(i for i, l in prose_lines if l == first)
        add("inflated-opener", ln, "Opening sentence leads with an adjective, not a claim. Say what it does that others don't.")

    dashes = prose.count("—")
    if words >= 200 and dashes / words > 0.01:
        add("em-dash-density", 1, f"{dashes} em dashes in {words} words. The reference READMEs average close to zero.")

    # Score: each rule counts once at full weight, repeats at a third.
    score = 0
    seen = {}
    for f in findings:
        n = seen.get(f["rule"], 0)
        w = WEIGHTS[f["rule"]]
        score += w if n == 0 else max(1, w // 3)
        seen[f["rule"]] = n + 1
    findings.sort(key=lambda f: f["line"])
    return {"score": min(score, 100), "threshold": THRESHOLD, "words": words, "findings": findings}


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("path")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--strict", action="store_true", help="exit 1 when score >= threshold")
    args = ap.parse_args()
    with open(args.path, encoding="utf-8", errors="replace") as fh:
        result = lint(fh.read())
    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(f"{args.path}: score {result['score']} (threshold {THRESHOLD}), {result['words']} prose words")
        for f in result["findings"]:
            print(f"  L{f['line']:<5} {f['rule']:<26} {f['message']}")
        if not result["findings"]:
            print("  no findings")
    sys.exit(1 if args.strict and result["score"] >= THRESHOLD else 0)


if __name__ == "__main__":
    main()
