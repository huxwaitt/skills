# The five README styles, with reference examples

Each style is defined by **what the reader meets first**. Projects are filed under the trait they
are praised for most. Excerpts are short quotations from the READMEs as fetched in November 2026.
Links point to the live READMEs, which keep changing; three have already moved on from the version
that made them famous (noted inline).

Lint scores are `scripts/readme_lint.py` output at the time of writing (threshold 30). Every
reference README scored 0-9. A typical LLM-template README scores 60+.

## Contents
1. Minimal: say what it is, then point elsewhere
2. Code first: install, then a minimal working example
3. Demo first: show the output before explaining
4. The README is the documentation
5. Voice and personality (also works as an overlay)
6. Choosing a style: the decision table

---

## 1. Minimal: say what it is, then point elsewhere

**Reader meets:** one or two plain sentences, install pointer, links to the real docs.
**Choose when:** the project has a docs site, or is a language, platform, large app or anything
whose real documentation could never fit in one file. Also the right default for internal
services and private apps, where the reader's question is "how do I run this locally".
**Length:** 7 to 500 words. Go's README is 177 words.

**Skeleton**
```
# Name
One sentence: what it is, in plain words, no adjectives doing the work.

## Install / Download          (or "Running locally" for an app)
Pointer or 1-3 commands.

## Documentation / Contributing / License
Links. One line each.
```

**Reference examples**

- **golang/go** (score 0, 177 words): https://github.com/golang/go
  > Go is an open source programming language that makes it easy to build simple, reliable, and
  > efficient software.

  Then: where the canonical repo lives, the license, "Download and Install" (two links), and
  "Contributing" (one link). Steal: the restraint. Nothing in it can go stale.

- **suckless st** (about 700 bytes, plain text): https://git.suckless.org/st/
  > st is a simple terminal emulator for X which sucks less.

  Then Requirements ("you need the Xlib header files"), Installation (`make clean install`),
  Running, Credits. Steal: the one-line claim that carries the project's whole philosophy, and a
  file that reads perfectly in `cat`.

- **mpv** (score 6): https://github.com/mpv-player/mpv
  > **mpv** is a free (as in freedom) media player for the command line.

  Its System requirements section is unusually honest:
  > A not too crappy GPU. mpv's focus is not on power-efficient playback on embedded or
  > integrated GPUs (for example, hardware decoding is not even enabled by default).

  Steal: project-specific sections ("Release cycle", "Bug reports") instead of template ones.

- **python-poetry/poetry** (score 6): https://github.com/python-poetry/poetry
  > Poetry replaces `setup.py`, `requirements.txt`, `setup.cfg`, `MANIFEST.in` and `Pipfile` with
  > a simple `pyproject.toml` based project format.

  Steal: defining the project by what it *replaces*. That one sentence tells a Python developer
  more than any feature list.

---

## 2. Code first: install, then a minimal working example

**Reader meets:** one line of description, then runnable code within the first screen.
**Choose when:** the value shows up in under 10 lines of code or a few commands: libraries,
frameworks, scaffolders, small CLIs.
**Length:** 200 to 1,500 words; the example does the persuading.

**Skeleton**
```
# Name
One line: what it does / what it removes.

```sh
install command
```

```lang
the smallest program that does something real   <- copied from a file that runs
```

## Philosophy / Why (only if there is a real stance)
## Docs, Examples, Contributing, License (links)
```

**Reference examples**

- **expressjs/express** (score 0): https://github.com/expressjs/express
  > **Fast, unopinionated, minimalist web framework for Node.js.**

  The Philosophy section states the stance and its trade-off:
  > Express does not force you to use any specific ORM or template engine.

  Steal: "unopinionated" is itself a claim with a cost, and the README owns it.

- **create-react-app** (score 6): https://github.com/react/create-react-app
  > Create React apps with no build configuration.
  ```sh
  npx create-react-app my-app
  cd my-app
  npm start
  ```
  Its Philosophy section is the rare good use of bold-label bullets, because each bullet is a
  decision with a consequence ("**No Lock-In:** You can "eject" to a custom setup at any time.").
  It now opens with a deprecation notice; stating the project's real status first is part of
  why it stays trustworthy. Its directory tree is legitimate: it shows what the tool *generates*.

---

## 3. Demo first: show the output before explaining

**Reader meets:** a GIF, screenshot, rendered output or before/after, above or next to the
first sentence.
**Choose when:** the output is visual or best judged by eye: formatters, UI components,
TUIs, themes, editors, visualization, anything whose pitch is "look".
**Length:** short prose; the image carries the pitch. Always pair the image with text, for
accessibility and for terminal readers.

**Skeleton**
```
# Name
One line.
![what the reader is looking at, in words](demo.gif)
Two or three sentences on what just happened in the demo.
## Install
## Usage (one example per visual feature, each with its own small demo)
```

**Reference examples**

- **prettier/prettier** (score 9, 177 prose words): https://github.com/prettier/prettier
  Banner, "Opinionated Code Formatter", the list of languages, one Intro sentence, then two
  headings literally called **Input** and **Output**:
  ```js
  foo(reallyLongArg(), omgSoManyParameters(), IShouldRefactorThis(), isThereSeriouslyAnotherOne());
  ```
  followed by the reformatted version. (It used to lead with a GIF; the before/after code does
  the same job and survives a terminal.) Steal: almost no prose; input and output do the arguing.
  Note its "speed: blazing" badge links to a joke tweet; the linter flags it, a human gets the joke.

- **Closures** (score 0): https://github.com/dusty-commits/Closures (formerly vhesener/Closures)
  > Some days, you just feel like dealing with UIControl's target-action using a closure instead.
  ```swift
  button.onTap {
      // UIButton tapped code
  }
  ```
  Each feature gets one conversational sentence, one tiny snippet, one animated example.
  Steal: the rhythm (sentence, snippet, picture) repeated per feature.

---

## 4. The README is the documentation

**Reader meets:** a short pitch, a table of contents, then everything.
**Choose when:** no docs site exists or is wanted, the API surface is moderate, and readers
live on the package page (npm, PyPI, Clojars) where the README is the only doc they see.
**Length:** 2,000 to 6,000 words. Standard Readme requires a ToC past 100 lines.

**Skeleton**
```
# Name
Pitch (1-2 sentences) + the smallest working example.
## Table of contents
## Install
## Usage (task-oriented sections, each with real code and real output)
## API / Reference
## FAQ / Known problems   <- readers arrive with problems (thoughtbot)
## Contributing, License
```

**Reference examples**

- **amazonica** (score 0, 5,673 words): https://github.com/mcohen01/amazonica
  > A comprehensive Clojure client for the entire Amazon AWS API.

  Then installation and an example for every service. A Hacker News commenter called it the best
  README they had seen. Steal: completeness *of examples*, not of prose.

- **tqdm** (score 6, 5,699 words): https://github.com/tqdm/tqdm
  > Instantly make your loops show a smart progress meter - just wrap any iterable with
  > `tqdm(iterable)`, and you're done!
  ```python
  from tqdm import tqdm
  for i in tqdm(range(10000)):
      ...
  ```
  `76%|████████████████████████        | 7568/10000 [00:33<00:10, 229.00it/s]`

  Steal: real output pasted under the code. The proof beats any adjective.

- **HTTPie** (score 6): https://github.com/httpie/cli
  Famous for its large examples section. The README is now trimmed to about 380 words and points
  to httpie.io/docs. Moving the depth out once a docs site exists is the normal end of this style.

- **re-frame** (score 3): https://github.com/day8/re-frame
  Known for a long essay on the design and its philosophy. The essay now lives on the docs site;
  the README keeps the argument's spine:
  > re-frame takes a different road to the currently-pervasive idea that Views should be causal

---

## 5. Voice and personality

**Reader meets:** a person. The tone itself is the hook.
**Choose as the primary style when** the project's identity *is* the pitch: opinionated tools,
community projects, joke projects. **Otherwise use it as an overlay** on styles 1-4: one
memorable line, a quote that maps to the design, honesty that sounds like someone. Never as
decoration. A joke that doesn't connect to the project is just noise.

**Reference examples**

- **psf/black** (score 0): https://github.com/psf/black
  > “Any color you like.”
  >
  > *Black* is the uncompromising Python code formatter. By using it, you agree to cede control
  > over minutiae of hand-formatting. In return, *Black* gives you speed, determinism, and freedom
  > from `pycodestyle` nagging about formatting.

  Steal: the trade stated as a contract. The Henry Ford quote (Model T, "any color so long as
  it's black") *is* the design philosophy.

- **ohmyzsh/ohmyzsh** (score 0): https://github.com/ohmyzsh/ohmyzsh
  > Oh My Zsh is an open source, community-driven framework for managing your zsh configuration.
  >
  > Sounds boring. Let's try again.
  >
  > **Oh My Zsh will not make you a 10x developer...but you may feel like one.**

  Steal: self-awareness. It writes the dull sentence, admits it, and then does better.

- **Doom Emacs** (score 0): https://github.com/doomemacs/core (formerly doomemacs/doomemacs)
  A centered title, a link bar (Install, Documentation, FAQ, Screenshots, Contribute), a
  screenshot, then an introduction that opens:
  > It is a story as old as time. A stubborn, shell-dwelling, and melodramatic

  Steal: the above-the-fold link bar for a big project, and an intro with a narrator.

- **kelseyhightower/nocode** (score 0, about 65k stars): https://github.com/kelseyhightower/nocode
  > No code is the best way to write secure and reliable applications. Write nothing; deploy
  > nowhere.

  Then "Getting Started", "Building", "Deploying", each with an empty code block. It works because
  it parodies the template README exactly; it shows how recognisable that template is.

- **tqdm** also earns a place here for explaining its own name:
  > `tqdm` derives from the Arabic word *taqaddum* (تقدّم) which can mean "progress," and is an
  > abbreviation for "I love you so much" in Spanish (*te quiero demasiado*).

- **re-frame** opens with Terry Pratchett's family-axe passage about identity surviving gradual
  change. That maps to the library's core concept of derived values, which is why it works.

---

## 6. Choosing a style: the decision table

Work down the table; the first row that fits is the recommendation. Then decide separately
whether a voice overlay fits (see the last column).

| Signal in the repo | Recommend | Voice overlay? |
|---|---|---|
| Separate docs site exists or is planned; language, platform, large app; internal service | **Minimal** | Only a one-line claim |
| Library, framework, scaffolder or small CLI whose value shows in under 10 lines | **Code first** | If the project has a stance (Black, Express) |
| Output is visual: formatter, UI kit, TUI, theme, editor, charts | **Demo first** | Optional |
| No docs site, moderate API, readers live on the package page | **README is the docs** | Optional |
| Identity is the pitch: opinionated, community-driven, humorous | **Voice** as primary | It *is* the style |
| Existing README already has a working style | **Keep it**; revise inside the style | Keep whatever is there |

Evidence to look at before recommending: `package.json`/`pyproject.toml`/`Cargo.toml` (library or
app? has `bin`?), presence of `docs/` or a docs URL, whether the main output is visual, number of
public entry points, existing README length and tone, and who the reader is (users, contributors,
teammates).

Tie-break toward the shorter style. Moving a README from Minimal to Comprehensive later is easy;
cutting a sprawling README back is a fight.
