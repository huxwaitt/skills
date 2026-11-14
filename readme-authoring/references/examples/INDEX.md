# Reference READMEs (full copies)

Each file is an unmodified copy of a source README, pinned to a commit and fetched on 2026-11-13.
A header at the top of each file gives the exact source URL, the copyright holders and the license.
All rights stay with the original authors. Copies are included for study under each project's license.

**Don't load all of these.** Open the one or two that match the chosen style. amazonica and tqdm run to
about 5,700 words each. `styles.md` has annotated excerpts and says what to take from each one.

| File | Style | Words | License | Study it for |
|---|---|---|---|---|
| `golang__go.md` | Minimal | 177 | BSD-3-Clause | Restraint: nothing in it can go stale |
| `suckless__st.txt` | Minimal | ~110 | MIT | A one-line claim carrying a philosophy; reads perfectly as plain text |
| `mpv-player__mpv.md` | Minimal | 1,087 | GPL-2.0-or-later | Honest requirements; sections specific to the project |
| `python-poetry__poetry.md` | Minimal | 503 | MIT | Defining the project by what it replaces |
| `expressjs__express.md` | Code first | 894 | MIT | Tagline as a stance; Philosophy section with a stated trade-off |
| `react__create-react-app.md` | Code first | 1,332 | MIT | Three commands to a running app; bold-label bullets done right; deprecation stated first |
| `prettier__prettier.md` | Demo first | 222 | MIT | Input/Output headings instead of prose |
| `dusty-commits__Closures.md` | Demo first | 1,045 | MIT | A sentence, a snippet and an animation for each feature |
| `mcohen01__amazonica.md` | README is the docs | 5,673 | EPL-1.0 | An example for every service |
| `tqdm__tqdm.rst` | README is the docs | 5,699 | MPL-2.0 and MIT | Real output pasted under the code; explains its own name |
| `httpie__cli.md` | README is the docs (now trimmed) | 379 | BSD-3-Clause | Handing depth off to a docs site once one exists |
| `day8__re-frame.md` | README is the docs (essay moved to docs) | 522 | MIT | A long-form argument kept short; a quote that maps to the design |
| `psf__black.md` | Voice | 1,071 | MIT | The trade-off stated as a contract |
| `ohmyzsh__ohmyzsh.md` | Voice | 3,173 | MIT | Self-aware tone: "Sounds boring. Let's try again." |
| `doomemacs__core.md` | Voice | 1,647 | MIT | Link bar above the fold; an intro with a narrator |
| `kelseyhightower__nocode.md` | Voice (parody) | 141 | Apache-2.0 | How recognisable the template README is |
| `RichardLitt__standard-readme.md` | Meta | 835 | MIT | A spec README that follows its own spec |

Linter calibration can be reproduced:
`for f in references/examples/*.*; do python scripts/readme_lint.py "$f" | head -1; done`
