# Principles: the essays, the community consensus, and what the classics share

Read this when you need to justify a choice, when the user asks *why*, or before writing a README
for a project that matters. SKILL.md carries the working rules; this is where they come from.

## Contents
1. The essays
2. What engineers agree on (Hacker News, Lobsters, awesome-readme)
3. Seven traits of the classic READMEs (measured on 17 of them)
4. The root cause, in one paragraph

---

## 1. The essays

### Readme Driven Development (Tom Preston-Werner, 2010)
https://tom.preston-werner.com/2010/08/23/readme-driven-development.html

- "Write your Readme first." Before code, tests or specs.
- "A perfect implementation of the wrong specification is worthless."
- "The Readme should be the single most important document in your codebase."
- The README is the middle ground between heavy waterfall specs and no documentation. Keeping
  design in one short file discourages overspecification.

**Use it for:** new projects. If a README is being written before or alongside the code, it is a
design document: the usage examples are the API proposal. Write them as you wish the API worked,
then flag every place the code disagrees.

### Art of README (Stephen Whitmore)
Original: github.com/hackergrrl/art-of-readme (gone from GitHub as of Nov 2026; a copy is at
https://benbridle.com/art-of-readme/)

- **Cognitive funnelling:** order content broad to specific. Name and one-liner, then usage, then
  API detail, then the long tail. A reader should be able to stop at any point having learned the
  most important thing so far.
- The ideal README is as short as it can be without being any shorter.
- Quoting Ken Williams: "the documentation, not the code, defines what a module does."
- Its worked scenario: a developer searching a package registry for a 2D collision detection
  module, deciding in seconds from each README whether to keep reading. Write for that reader.

### Standard Readme (Richard Litt)
https://github.com/RichardLitt/standard-readme/blob/main/spec.md

A spec, not a template. Its rules worth enforcing anywhere:
- Short description **under 120 characters**, on its own line, matching the package manager's
  `description` field and the GitHub description.
- Table of contents required unless the README is **under 100 lines**.
- Install needs a code block; Usage needs a code block; CLI usage gets its own subsection.
- **No broken links.** (This is what `readme_freshness.py` enforces at commit time.)
- Section order: Title, Banner, Badges, Short Description, Long Description, ToC, Security,
  Background, Install, Usage, Extra Sections, API, Maintainers, Thanks, Contributing, License.

**Use it as a checklist of what might be missing, never as the outline.** Following its order
blindly produces exactly the template-shaped README that section 4 below warns about.

### How to Write a Great README (Caleb Thompson, thoughtbot)
https://thoughtbot.com/blog/how-to-write-a-great-readme

- "Technical writing is still writing, and need not be dry and boring."
- Open with a short bolded description, or an image that relates to the name or function.
- Give **known problems** (hard-to-satisfy dependencies, common errors) their own section with
  the fix. Readers often arrive *with* a problem.
- Badges reflect on the project: "a failing master build can give them pause."

### ARCHITECTURE.md (Alex Kladov)
https://matklad.github.io/2021/02/06/ARCHITECTURE.md.html

Not about READMEs, and that is the point: architecture does not belong in the README.
- For projects of roughly 10k to 200k lines, add an ARCHITECTURE file next to README and
  CONTRIBUTING.
- "Keep it short: every recurring contributor will have to read it."
- "A codemap is a map of a country, not an atlas of maps of its states."
- Name important files and types but don't link them (links rot; symbol search doesn't).
- State invariants, especially deliberate absences ("the parser never touches the filesystem").

**Use it for:** when a README is accreting module descriptions and directory trees, move them to
ARCHITECTURE.md and leave one line in the README pointing there.

### Older baselines (cited on Hacker News)
- GNU Coding Standards: name, version, description, pointer to install instructions, notes on
  unusual files, license.
- Software Release Practice HOWTO: description, website, build notes, file roadmap, install
  steps, credits, news.

---

## 2. What engineers agree on

From the Hacker News threads "How to write a great README" (item 36773022) and "What's the best
documentation you've ever read?" (17399340), the Lobsters thread on awesome-readme, and the
awesome-readme list itself (https://github.com/matiassingers/awesome-readme, about 21k stars):

1. **First two lines: what it is and why you would care.** A "What problem does this solve?"
   section was singled out as a reusable structure.
2. **Show it working immediately.** One install command, then the smallest real example.
3. **Readable as raw text in a terminal.** Minimal HTML, light Markdown. The suckless READMEs
   were praised specifically for reading well locally.
4. **Not marketing.** Appsmith's README was rated 4/10 on HN for reading like a product page and
   burying setup. Common complaints: contributor-avatar walls, emoji, tracking pixels.
5. **Images alongside prose, never instead of it.** Mermaid diagrams preferred to static images
   because they stay editable and render on GitHub.
6. **Large projects need a table of contents** and should hand off to a docs site.
7. Examples praised individually: amazonica ("relevant examples for every piece of the library"),
   mpv (opens with what it is), node-postgres (examples right away), re-frame (worth reading even
   if you'll never use it).

---

## 3. Seven traits of the classic READMEs

Measured on the 17 reference READMEs in styles.md (downloaded and analysed November 2026).

1. **The first line is a claim specific to this project.** st: "a simple terminal emulator for
   X which sucks less." tqdm: "just wrap any iterable with `tqdm(iterable)`, and you're done!"
   Each says what the project is *betting on*. Test: could this sentence describe a competitor?
   If yes, rewrite it.
2. **They state the cost.** Black: "you agree to cede control over minutiae of
   hand-formatting. In return…". mpv: "A not too crappy GPU." Express: "does not force you to use
   any specific ORM." Create React App leads with its own deprecation. Saying what you are not is
   what makes the rest believable.
3. **Proof instead of adjectives.** tqdm pastes the real progress bar. Closures shows
   `button.onTap { }` on the first screen. Prettier shows Input, then Output.
4. **Length fits the project, not a template.** st is 700 bytes, Go 177 words, amazonica and
   tqdm about 5,700 each. Headings range from 0 to 64. Sections grow out of the project:
   "Philosophy", "Release cycle", one section per AWS service.
5. **One author's voice, with opinions.** "Sounds boring. Let's try again." (Oh My Zsh).
   "Any color you like." (Black). A Pratchett passage that maps to the library's core idea
   (re-frame).
6. **They know what the README is for.** Go, Poetry, HTTPie and re-frame hand off to a docs site
   early. amazonica and tqdm deliberately make the README the reference. Both are choices.
7. **Zero emoji headings across all 17.** Em dashes are close to absent too.

---

## 4. The root cause, in one paragraph

A machine-written README is assembled from what is in the repository and from the average README
in the training data. The things that make the classics good mostly are not in the repository:
why the project exists, what was deliberately left out, what it is bad at, who should use
something else, and what running it actually looks like. Emoji, adjectives and template headings
are what fills the space where that information should be. So the fix is not stylistic polish.
It is getting that information: from the user, from commit history and issues, from actually
running the thing, or, failing all of those, by leaving the claim out rather than inventing it.
