# Kit format

```
brandkits/<brand>/
  BRAND.md            the guide a designer or model reads first
  ARCHITECTURE.md     how the site is built
  tokens.json         DTCG design tokens
  tokens.css          the same as CSS custom properties, plus @font-face for local fonts
  regen.json          subjects/formats for pick.py
  capture/            capture.py output (report, json, screenshots)
  assets/
    manifest.json     provenance and terms for every downloaded file
    official/         logos and guideline docs from the brand
    fonts/            woff2 files (openly licensed or site-served)
    site/             logos and icons saved from the live site
    samples/          real first-party artifacts to match
  out/                regenerated assets (html + png)
```

## BRAND.md sections

Keep each section short and concrete. Values come with a source tag: `[site]` (captured),
`[official]` (brand's own guideline), `[sample]` (measured from an artifact), or
`[inferred]` (your judgement, flagged).

1. **Identity:** one paragraph on what the brand is and how it presents itself now.
2. **Logo:** files in the kit, variants, clear space, backgrounds, and don'ts.
3. **Color:** roles, not swatches: surface, on-surface, primary action, secondary, accent
   and brand marks, light and dark. Note where brand-mark colors are reserved for logos.
4. **Typography:** families with their files, a scale (display to caption) with size, line
   height, weight and tracking, and which family goes where.
5. **Shape and space:** radii, spacing rhythm, grid and margins from captures and samples.
6. **Imagery:** what the samples have in common: backgrounds, rendering style (3D, photo,
   flat), lighting, grain, how text sits on images, lockups.
7. **Voice and writing:** adjectives from the source, then hard rules (case, person,
   punctuation, words to avoid), with two or three real lines quoted from the site.
8. **Observed vs. stated:** each place where the live site departs from the guideline.
9. **Usage terms:** quoted, with the source URL.
10. **Missing:** what you looked for and didn't find.

## tokens.json (DTCG)

```json
{
  "color": {
    "surface": { "$type": "color", "$value": "#ffffff", "$description": "page background [site]" },
    "primary": { "$type": "color", "$value": "#1a73e8", "$description": "filled CTA [site: about]" }
  },
  "font": {
    "display": { "$type": "fontFamily", "$value": ["Google Sans", "Arial", "sans-serif"] }
  },
  "type": {
    "display-l": { "$type": "typography", "$value": { "fontFamily": "{font.display}", "fontSize": "60px",
      "lineHeight": "72px", "fontWeight": 400, "letterSpacing": "-0.5px" } }
  },
  "radius": { "pill": { "$type": "dimension", "$value": "48px" } }
}
```

`tokens.css` mirrors it: `--color-primary`, `--type-display-l-size`, and so on, plus
`@font-face` rules pointing at `assets/fonts/*.woff2` with relative URLs, so `out/*.html` can
load them with `../tokens.css`.

## ARCHITECTURE.md

Cover the stack and evidence, rendering (SSR, CSR, server-templated, or islands), CSS strategy
(utility, modules, CSS-in-JS, or compiled atomic with obfuscated names), the token system (are
custom properties used, and how are they named), the component inventory, icon system, font
delivery, third-party origins, and page weight by type. One screen; link to `capture/report.md`
for the raw data.
