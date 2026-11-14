# Finding official brand material

## Where to look, in order

1. **Links the capture already found.** `capture/report.md` ends with brand-ish links from the
   site (about, press, brand, media, design, partner hubs). Footers are where companies hide
   them.
2. **Conventional paths:** `/brand`, `/brand-guidelines`, `/press`, `/press-kit`, `/media`,
   `/newsroom`, `/logos`, `/assets`, and subdomains `brand.`, `design.`, `press.`.
3. **Search** (run several at once): `"<brand>" brand guidelines`, `"<brand>" press kit logo`,
   `"<brand>" design system`, `"<brand>" writing style guide`, `"<brand>" voice and tone`,
   `<brand> font name`, and `"<brand>" brand guidelines filetype:pdf`.
4. **Design system sites** often carry the real tokens. Examples: Material (Google), Carbon
   (IBM), Polaris (Shopify), Fluent (Microsoft), Primer (GitHub), Atlassian Design, Spectrum
   (Adobe).
5. **Writing guides:** developer docs style guides, content style guides (Mailchimp, Microsoft
   Writing Style Guide, Google developer documentation style guide), UX writing pages inside
   design systems, and open source or comms style guides.
6. **Fonts:** check whether the brand typeface is on Google Fonts or Fontsource, or is open
   source. If it isn't, use the files the site itself serves (from capture `@font-face` src)
   only for local rendering, and note that in the kit.
7. **Samples:** the company blog's `og:image` per post (key art at 16:9), keynote or event
   pages, app store screenshots, and social profiles. Take the newest first, because brands
   drift.

## Judging sources

| Trust | Source |
|---|---|
| Official | The brand's own domains, its partner or brand portals, its design system |
| Corroborating | Its open source repos, its fonts on Google Fonts, its official social posts |
| Unreliable | "brand colors" aggregator sites, Dribbble recreations, old Wikipedia SVGs |

Aggregator hex codes are often outdated (pre-redesign) or eyedropped from compressed JPEGs.
Use them only to cross-check, and prefer values computed from the live site.

## Usage terms

Record what the source says about use: who may use the logo, clear space, minimum size,
co-branding, color and font restrictions, and "don't recreate product UI". Put them in
`fetch.py --terms` and in `BRAND.md`. Many brands forbid third parties from using their
colors or font, which is exactly why regenerated assets stay internal unless the user owns
the brand.

## Signed and expiring URLs

Brand portals often serve downloads through signed links that expire within hours. Download
the files right away with `fetch.py`. The manifest strips the signature and keeps the
stable path.
