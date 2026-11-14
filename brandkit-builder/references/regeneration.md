# Regenerating assets that hold up

## Build

- Write one self-contained HTML file per asset in `out/`, sized exactly to the format
  (`html, body { width: Wpx; height: Hpx; margin: 0; overflow: hidden }`), linking
  `../tokens.css`.
- **Real fonts or nothing.** Load the kit's woff2 files. `render.py` exits non-zero if a font
  fails. A fallback to Arial is the most common tell.
- **Real logos, unmodified.** Use the files from `assets/official` or `assets/site` as `<img>`.
  Never redraw, recolor, stretch, or rebuild a logo out of text in the brand font.
- **Exact values from tokens:** colors, radii, tracking. Don't eyeball them.
- **Imagery:** build visuals in CSS or SVG (gradients, shapes, grain via an SVG
  `feTurbulence` filter, glass with `backdrop-filter`) in the style the samples show. Don't
  paste a sample image into the output.
- **Copy:** follow the voice rules: case, length, punctuation. Read two real headlines from
  the site and match their length and rhythm. Subjects come from `regen.json`. Invent product
  facts only when the brief says the asset is a mockup, and keep them plausible but
  obviously not announcements (no dates, prices or specs that read as real news).

## Check (Read the PNG beside the sample)

1. Squint test: at thumbnail size, do the composition, color temperature and contrast match the
   sample family?
2. Type: same family, weight and tracking as the samples' headlines? Headline sizes in
   brand key art are usually 4-6% of canvas width.
3. Margins: the logo and text sit on the same safe area as in the samples (usually 6-10% of the
   short side).
4. Logo: correct variant for the background, clear space respected, no recoloring.
5. Color: no off-palette hues; brand-mark colors appear only in the mark unless the guide
   allows otherwise.
6. Detail: grain, soft shadows and gradients are present if the samples have them, and absent
   if the samples are flat.
7. Copy: passes the writing rules (sentence case, no exclamation marks unless the brand uses
   them).
8. No overflow and no clipped text (`render.py` reports `overflow`).

Fix the largest difference first and re-render. Stop when a stranger would have to look twice.

## Guardrails

Allowed: internal mockups, pitch decks, design exploration, testing a template system, and
assets for a brand the user owns or is authorized to work on.

Not allowed: sign-in pages, payment or checkout, account or security notices, receipts or
invoices, emails or notices presented as coming from the brand, fake press releases with
real-seeming news, and anything aimed at deceiving people about who made it. Decline those
even when asked, and don't publish brand-imitating assets to public URLs.
