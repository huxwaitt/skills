---
name: brandkit-builder
description: >
  Build a brand kit from a website: map its frontend architecture and in-use design tokens,
  find official brand guidelines, writing rules, logos and fonts online, collect sample
  artifacts, and regenerate on-brand assets that hold up next to the real ones. Use when given
  a site to "brand-kit", reverse-engineer a design system, or make assets in a brand's style.
---

# brandkit-builder

A brand kit answers three questions: what the brand *says* it is (official guidelines), what
it *actually ships* (computed styles on the live site), and what its finished work *looks
like* (real artifacts). Assets regenerated from all three are convincing; assets made from
any one alone look like fan art.

Scripts are Python standard library only, plus any installed Chrome, Edge or Chromium
(override with `BRANDKIT_BROWSER`). Run them with `python -I <skill>/scripts/<name>.py`.

| Script | Does |
|---|---|
| `capture.py URL --out KIT [--pages ...]` | Renders the site in light and dark, extracts architecture and computed tokens, takes screenshots, saves inline logos and icons, writes `capture/report.md` |
| `fetch.py --kit KIT --into DIR --source PAGE --terms "..." [name=]URL...` | Downloads assets into `assets/DIR/`, dedupes by hash, records provenance and usage terms in `assets/manifest.json` |
| `palette.py IMG...` | Measures colors in samples or renders (corners, dominant colors, luminance) |
| `pick.py KIT [--seed N]` | Picks a random asset brief (format, composition, subject, scheme, sample to match) |
| `render.py HTML PNG --size WxH` | Renders an asset to PNG; fails if a web font didn't load |

## 1. Capture what the site ships

```sh
python -I <skill>/scripts/capture.py https://example.com --out brandkits/example --pages /about /pricing
```
Add 2-4 pages of different types (marketing, product, docs or about); a homepage alone
under-samples the system. If the site is a sparse app shell (Google Search is), the
company's about or marketing site carries most of the brand. Read `capture/report.md` and
the screenshots. Treat obfuscated variable names (`--nkmQOe`) as values only; name tokens by
role yourself.

## 2. Find what the brand publishes (if online)

Follow `references/research.md`: brand portals, press kits, design systems, writing style
guides, fonts. Prefer official sources and record each one's usage terms. Download with
`fetch.py` into `official/` (logos, guideline PDFs), `fonts/` (only openly licensed or
site-served files), and `samples/` (5-10 recent first-party artifacts: key art, social cards,
slides). Look at every sample, drop any that are co-branded, partner-made or atypical, and run
`palette.py` on the rest so imagery colors are measured.

## 3. Write the kit

Layout and templates are in `references/kit-format.md`. The essentials:
- `BRAND.md`: identity, logo rules, color roles, type scale, shape, imagery, voice and writing
  rules, usage terms, and **observed vs. stated** wherever the live site and the guidelines
  disagree.
- `tokens.json` (DTCG format) and `tokens.css`, with every value traceable to the capture or a
  source.
- `ARCHITECTURE.md`: stack, rendering model, CSS strategy, component inventory, asset
  pipeline (from the report).
- `regen.json`: subjects drawn from the brand's real current products and campaigns.

Every value needs a source: capture, URL or sample file. If you couldn't find something, say
so in the kit rather than inventing it.

## 4. Regenerate

```sh
python -I <skill>/scripts/pick.py brandkits/example [--kind page]   # random brief; page = full web page
# write brandkits/example/out/<slug>.html from BRAND.md + tokens.css + the sample to match
python -I <skill>/scripts/render.py brandkits/example/out/<slug>.html brandkits/example/out/<slug>.png --size 1200x630   # or 1440xfull for pages
```
Then Read the PNG next to the sample it should match and run the checklist in
`references/regeneration.md`. Iterate until it passes; two or three rounds is normal.

**Guardrails.** Never generate sign-in pages, payment or checkout flows, account or security
notices, receipts, or anything that could pass as an official communication; `pick.py` won't
offer them and you shouldn't build them on request either. Don't publish or share a
regenerated asset of a brand the user doesn't own; it is for internal mockups, pitches and
design exploration. Say so when handing it over, along with the brand's own usage terms from
the kit.

## 5. Report

Say where the kit is, show one regenerated asset next to its sample, list what was official
vs. observed vs. missing, and quote the usage terms in one line.
