// Runs inside the rendered page. Returns one JSON object describing frontend architecture
// and the design tokens actually in use (computed styles, not just declared ones).
(async () => {
  const $$ = (s, r = document) => Array.from(r.querySelectorAll(s));
  const W = window, D = document, html = D.documentElement;
  const vw = innerWidth, vh = innerHeight;
  const bump = (m, k, w = 1) => { if (k !== undefined && k !== null && k !== '') m[k] = (m[k] || 0) + w; };
  const top = (m, n = 25) => Object.entries(m).sort((a, b) => b[1] - a[1]).slice(0, n)
    .map(([value, weight]) => ({ value, weight: Math.round(weight) }));
  const meta = n => (D.querySelector(`meta[name="${n}"],meta[property="${n}"]`) || {}).content || null;
  const visible = el => {
    const r = el.getBoundingClientRect();
    if (r.width < 1 || r.height < 1) return null;
    const cs = getComputedStyle(el);
    if (cs.visibility === 'hidden' || cs.display === 'none' || +cs.opacity === 0) return null;
    return { r, cs };
  };
  const all = $$('body *');
  const attrNames = new Set();
  for (const el of all.slice(0, 5000)) for (const a of el.attributes) attrNames.add(a.name);
  const classes = all.slice(0, 5000).map(e => (typeof e.className === 'string' ? e.className : '')).join(' ');
  const srcs = $$('script[src]').map(s => s.src);
  const anySrc = re => srcs.some(s => re.test(s));

  // ---- frameworks and tooling -------------------------------------------------------
  const fp = {};
  const hit = (name, ok, evidence) => { if (ok) fp[name] = evidence; };
  hit('Next.js', W.__NEXT_DATA__ || W.next || anySrc(/\/_next\//), W.__NEXT_DATA__ ? '__NEXT_DATA__' : '/_next/ assets');
  hit('Nuxt', W.__NUXT__ || W.$nuxt || anySrc(/\/_nuxt\//), '__NUXT__ or /_nuxt/');
  hit('Remix', W.__remixContext, '__remixContext');
  hit('Gatsby', W.___gatsby || D.getElementById('___gatsby'), '___gatsby');
  hit('SvelteKit', Object.keys(W).some(k => k.startsWith('__sveltekit')), '__sveltekit_*');
  hit('Svelte', /\bsvelte-[a-z0-9]{5,}/.test(classes), 'svelte-xxxx classes');
  hit('Astro', D.querySelector('astro-island,[data-astro-cid],[class*="astro-"]'), 'astro-island/data-astro-cid');
  hit('Angular', D.querySelector('[ng-version]'), (D.querySelector('[ng-version]') || {}).getAttribute?.('ng-version'));
  hit('AngularJS', W.angular, 'window.angular');
  hit('Vue', W.__VUE__ || D.querySelector('[data-v-app]') || [...attrNames].some(a => a.startsWith('data-v-')), 'data-v-* / __VUE__');
  const reactRoot = all.slice(0, 2000).find(e => Object.keys(e).some(k => k.startsWith('__reactFiber') || k.startsWith('__reactContainer')));
  hit('React', reactRoot || D.querySelector('[data-reactroot]') || W.React, reactRoot ? 'fiber keys on DOM nodes' : 'data-reactroot/window.React');
  hit('Preact', W.preact || all.slice(0, 2000).some(e => '__k' in e && '_dom' in (e.__k || {})), 'preact vnode');
  hit('Ember', W.Ember, 'window.Ember');
  hit('jQuery', W.jQuery, W.jQuery && W.jQuery.fn && W.jQuery.fn.jquery);
  hit('Alpine.js', W.Alpine || attrNames.has('x-data'), 'x-data');
  hit('htmx', W.htmx || [...attrNames].some(a => a.startsWith('hx-')), 'hx-* attributes');
  hit('Lit', W.litElementVersions || W.litHtmlVersions, 'lit versions global');
  hit('Google Wiz/Closure', attrNames.has('jscontroller') || attrNames.has('jsaction') || attrNames.has('jsname'), 'jscontroller/jsaction/jsname attributes');
  hit('Polymer', W.Polymer, 'window.Polymer');
  hit('Stencil', D.querySelector('[s-id],.hydrated') && W.customElements, 'hydrated custom elements');
  hit('WordPress', D.querySelector('link[href*="wp-content"],script[src*="wp-content"],meta[name=generator][content*=WordPress]'), 'wp-content');
  hit('Shopify', W.Shopify, 'window.Shopify');
  hit('Webflow', html.getAttribute('data-wf-page'), 'data-wf-page');
  hit('Squarespace', W.Static && W.Static.SQUARESPACE_CONTEXT, 'SQUARESPACE_CONTEXT');
  hit('Wix', W.wixBiSession || D.querySelector('meta[name=generator][content*=Wix]'), 'Wix generator');
  hit('Framer', D.querySelector('[data-framer-name],[data-framer-component-type]'), 'data-framer-*');
  hit('Tailwind CSS', (classes.match(/\b(?:sm:|md:|lg:)?(?:px|py|mt|mb|gap|text|bg|rounded|flex|grid)-[a-z0-9\[\]./-]+/g) || []).length > 80, 'utility class density');
  hit('Bootstrap', /\b(col-(?:sm|md|lg)-\d+|btn-primary|navbar-expand)/.test(classes), 'col-*/btn-primary');
  hit('Material (MDC/Angular Material)', /\b(mdc-|mat-|mdl-)/.test(classes), 'mdc-/mat- classes');
  hit('Material Web components', D.querySelector('md-filled-button,md-outlined-button,md-icon,md-text-button'), 'md-* elements');
  hit('styled-components', D.querySelector('style[data-styled]') || /\bsc-[a-zA-Z]{5,}/.test(classes), 'data-styled');
  hit('Emotion', D.querySelector('style[data-emotion]') || /\bcss-[a-z0-9]{5,}/.test(classes), 'data-emotion');
  hit('CSS Modules (hashed)', (classes.match(/\b[A-Za-z]+_[A-Za-z]+__[A-Za-z0-9_-]{5}\b/g) || []).length > 10, 'Name_class__hash');
  hit('Google Tag Manager', W.google_tag_manager || anySrc(/googletagmanager/), 'gtm');
  hit('Google Analytics', W.gtag || W.ga || anySrc(/google-analytics|gtag\/js/), 'gtag/ga');
  hit('Service worker', navigator.serviceWorker && navigator.serviceWorker.controller, 'controller active');

  // ---- document structure ------------------------------------------------------------
  const landmarks = {};
  for (const t of ['header', 'nav', 'main', 'footer', 'aside', 'section', 'article', 'form', 'dialog', 'iframe'])
    landmarks[t] = $$(t).length;
  for (const r of ['banner', 'navigation', 'main', 'contentinfo', 'search', 'dialog'])
    landmarks[`role=${r}`] = $$(`[role="${r}"]`).length;
  const custom = {};
  for (const el of all) if (el.tagName.includes('-')) bump(custom, el.tagName.toLowerCase());
  let shadowRoots = 0, maxDepth = 0;
  for (const el of all.slice(0, 8000)) {
    if (el.shadowRoot) shadowRoots++;
    let d = 0, p = el; while ((p = p.parentElement)) d++; if (d > maxDepth) maxDepth = d;
  }
  const headings = $$('h1,h2,h3,h4').filter(visible).slice(0, 40)
    .map(h => ({ level: h.tagName, text: h.innerText.trim().slice(0, 120) }));

  // ---- declared CSS: variables, @font-face, breakpoints, keyframes ------------------------
  const sheets = [], vars = {}, fontFaces = [], media = {}, keyframes = new Set();
  let crossOrigin = 0;
  const walk = (rules, href) => {
    for (const r of rules) {
      if (r.type === CSSRule.STYLE_RULE) {
        if (/^(:root|html|body|:host)\b/.test(r.selectorText))
          for (const p of r.style) if (p.startsWith('--')) vars[p] = r.style.getPropertyValue(p).trim();
      } else if (r.type === CSSRule.FONT_FACE_RULE) {
        fontFaces.push({ family: r.style.getPropertyValue('font-family').replace(/["']/g, ''), weight: r.style.getPropertyValue('font-weight'),
          style: r.style.getPropertyValue('font-style'), src: r.style.getPropertyValue('src').slice(0, 400), sheet: href });
      } else if (r.type === CSSRule.MEDIA_RULE) {
        for (const m of (r.conditionText || r.media.mediaText).matchAll(/(min|max)-width:\s*([\d.]+)(px|em|rem)/g)) bump(media, `${m[1]}-width: ${m[2]}${m[3]}`);
        walk(r.cssRules, href);
      } else if (r.type === CSSRule.KEYFRAMES_RULE) keyframes.add(r.name);
      else if (r.cssRules) walk(r.cssRules, href);
    }
  };
  for (const s of D.styleSheets) {
    let rules = null;
    try { rules = s.cssRules; } catch (e) { crossOrigin++; }
    sheets.push({ href: s.href || '(inline)', rules: rules ? rules.length : null });
    if (rules) walk(rules, s.href || 'inline');
  }
  const rootCS = getComputedStyle(html);
  for (const k of Object.keys(vars)) vars[k] = rootCS.getPropertyValue(k).trim() || vars[k];

  // ---- computed tokens over visible elements ----------------------------------------------
  const T = { textColor: {}, bgColor: {}, borderColor: {}, fontFamily: {}, fontSize: {}, fontWeight: {},
    lineHeight: {}, letterSpacing: {}, radius: {}, shadow: {}, spacing: {}, gap: {}, transition: {} };
  const firstFamily = f => f.split(',')[0].replace(/["']/g, '').trim();
  let sampled = 0;
  for (const el of all) {
    if (sampled > 4000) break;
    const v = visible(el); if (!v) continue;
    const { r, cs } = v;
    if (r.bottom < 0 || r.top > vh * 4) continue;
    sampled++;
    const area = Math.min(r.width * r.height, vw * vh) / 1000;
    const ownText = [...el.childNodes].filter(n => n.nodeType === 3).map(n => n.textContent.trim()).join('').length;
    if (ownText) {
      bump(T.textColor, cs.color, ownText);
      bump(T.fontFamily, firstFamily(cs.fontFamily), ownText);
      bump(T.fontSize, cs.fontSize, ownText);
      bump(T.fontWeight, cs.fontWeight, ownText);
      bump(T.lineHeight, cs.lineHeight, ownText);
      if (cs.letterSpacing !== 'normal') bump(T.letterSpacing, cs.letterSpacing, ownText);
    }
    if (cs.backgroundColor !== 'rgba(0, 0, 0, 0)') bump(T.bgColor, cs.backgroundColor, area);
    if (parseFloat(cs.borderTopWidth) > 0 && cs.borderTopStyle !== 'none') bump(T.borderColor, cs.borderTopColor);
    if (cs.borderTopLeftRadius !== '0px') bump(T.radius, cs.borderTopLeftRadius);
    if (cs.boxShadow !== 'none') bump(T.shadow, cs.boxShadow);
    for (const p of ['paddingTop', 'paddingLeft', 'marginTop', 'marginBottom']) if (cs[p] !== '0px' && cs[p] !== 'auto') bump(T.spacing, cs[p]);
    if (cs.gap && cs.gap !== 'normal' && cs.gap !== '0px') bump(T.gap, cs.gap);
    if (cs.transitionDuration !== '0s') bump(T.transition, `${cs.transitionDuration} ${cs.transitionTimingFunction}`);
  }
  const tokens = {}; for (const k in T) tokens[k] = top(T[k], k === 'shadow' ? 10 : 25);
  tokens.pageBackground = getComputedStyle(D.body).backgroundColor;

  // ---- typography roles ------------------------------------------------------------------
  const typeOf = el => { const cs = getComputedStyle(el); return { family: cs.fontFamily, size: cs.fontSize, weight: cs.fontWeight,
    lineHeight: cs.lineHeight, letterSpacing: cs.letterSpacing, color: cs.color, transform: cs.textTransform,
    sample: (el.innerText || el.value || el.placeholder || '').trim().slice(0, 80) }; };
  const roles = {};
  for (const [role, sel] of Object.entries({ h1: 'h1', h2: 'h2', h3: 'h3', body: 'p', link: 'a', button: 'button,[role=button]',
    nav: 'nav a,header a', input: 'input[type=text],input[type=search],textarea,input:not([type])', small: 'small,footer a,footer span', label: 'label' })) {
    const el = $$(sel).find(e => visible(e) && (e.innerText || e.value || e.placeholder || '').trim());
    if (el) roles[role] = typeOf(el);
  }

  // ---- component samples -----------------------------------------------------------------
  const sig = cs => [cs.backgroundColor, cs.color, cs.borderTopLeftRadius, cs.borderTopWidth, cs.borderTopColor, cs.fontWeight].join('|');
  const comps = {};
  const sample = (name, sel, max = 8) => {
    const seen = new Set(), out = [];
    for (const el of $$(sel)) {
      const v = visible(el); if (!v) continue;
      const s = sig(v.cs); if (seen.has(s)) continue; seen.add(s);
      const cs = v.cs;
      out.push({ text: (el.innerText || el.getAttribute('aria-label') || el.value || '').trim().slice(0, 60), w: Math.round(v.r.width), h: Math.round(v.r.height),
        bg: cs.backgroundColor, color: cs.color, border: `${cs.borderTopWidth} ${cs.borderTopStyle} ${cs.borderTopColor}`, radius: cs.borderTopLeftRadius,
        padding: cs.padding, font: `${cs.fontWeight} ${cs.fontSize}/${cs.lineHeight} ${firstFamily(cs.fontFamily)}`, shadow: cs.boxShadow });
      if (out.length >= max) break;
    }
    if (out.length) comps[name] = out;
  };
  sample('button', 'button,[role=button],a[class*=btn],a[class*=button],input[type=submit]');
  sample('input', 'input:not([type=hidden]):not([type=checkbox]):not([type=radio]),textarea,select,[role=combobox]');
  sample('chip/tag', '[class*=chip],[class*=tag],[class*=pill],[class*=badge]');
  sample('card', '[class*=card],article');

  // ---- logos, icons, imagery -------------------------------------------------------------
  const host = location.hostname.replace(/^www\./, '').split('.')[0].toLowerCase();
  const brandish = el => {
    const s = [el.id, typeof el.className === 'string' ? el.className : (el.className && el.className.baseVal), el.getAttribute('alt'), el.getAttribute('aria-label'),
      el.getAttribute('title'), el.getAttribute('src'), el.closest('a') && el.closest('a').getAttribute('aria-label')].join(' ').toLowerCase();
    return /logo|brand|wordmark/.test(s) || s.includes(host);
  };
  // Inline SVGs usually take their fill from CSS; bake computed fill/stroke in so the file stands alone.
  const bakeSvg = svg => {
    const clone = svg.cloneNode(true), src = [svg, ...svg.querySelectorAll('*')], dst = [clone, ...clone.querySelectorAll('*')];
    src.forEach((n, i) => { const cs = getComputedStyle(n);
      if (n !== svg && cs.fill && cs.fill !== 'none' && !dst[i].getAttribute('fill')) dst[i].setAttribute('fill', cs.fill);
      if (cs.stroke && cs.stroke !== 'none' && !dst[i].getAttribute('stroke')) dst[i].setAttribute('stroke', cs.stroke); });
    return clone.outerHTML.slice(0, 200000);
  };
  const logos = [];
  for (const el of $$('svg,img,picture img,[role=img]')) {
    const v = visible(el); if (!v) continue;
    const score = (brandish(el) ? 3 : 0) + (v.r.top < 400 ? 1 : 0) + (el.closest('header,[role=banner]') ? 1 : 0)
      + (v.r.width >= 60 ? 2 : 0) - (v.r.width < 32 ? 3 : 0);
    if (score < 3) continue;
    logos.push({ score, tag: el.tagName.toLowerCase(), w: Math.round(v.r.width), h: Math.round(v.r.height), top: Math.round(v.r.top),
      alt: el.getAttribute('alt') || el.getAttribute('aria-label'), src: el.currentSrc || el.src || null,
      svg: el.tagName.toLowerCase() === 'svg' ? bakeSvg(el) : null });
  }
  logos.sort((a, b) => b.score - a.score || b.w * b.h - a.w * a.h);
  const images = [];
  for (const img of $$('img')) { const v = visible(img); if (v && img.currentSrc && !img.currentSrc.startsWith('data:')) images.push({ src: img.currentSrc, alt: img.alt, w: img.naturalWidth, h: img.naturalHeight }); }
  for (const el of all.slice(0, 3000)) { const b = getComputedStyle(el).backgroundImage; const m = b && b.match(/url\("?([^")]+)"?\)/); if (m && !m[1].startsWith('data:')) images.push({ src: m[1], alt: '(background)', w: null, h: null }); }
  const iconSystems = {};
  if (D.querySelector('.material-icons,.material-icons-outlined,[class*=material-symbols]')) iconSystems['Material Icons/Symbols (font)'] = $$('.material-icons,[class*=material-symbols]').length;
  if (D.querySelector('i.fa,i[class*="fa-"]')) iconSystems['Font Awesome'] = $$('i[class*="fa-"]').length;
  iconSystems['inline svg'] = $$('svg').length;
  iconSystems['svg <use> sprites'] = $$('svg use').length;

  // ---- fonts actually loaded ---------------------------------------------------------------
  await D.fonts.ready;
  const loadedFonts = [...D.fonts].filter(f => f.status === 'loaded').map(f => `${f.family.replace(/["']/g, '')} ${f.weight} ${f.style}`);

  return {
    url: location.href, title: D.title, lang: html.lang, dir: html.dir || 'ltr',
    meta: { description: meta('description'), themeColor: meta('theme-color'), ogTitle: meta('og:title'), ogImage: meta('og:image'),
      ogSiteName: meta('og:site_name'), twitterSite: meta('twitter:site'), generator: meta('generator'), viewport: meta('viewport'),
      colorScheme: meta('color-scheme') || rootCS.colorScheme },
    icons: $$('link[rel*=icon],link[rel=mask-icon],link[rel=manifest]').map(l => ({ rel: l.rel, href: l.href, sizes: l.sizes && l.sizes.value })),
    frameworks: fp,
    scripts: { external: srcs.length, inline: $$('script:not([src])').length, modules: $$('script[type=module]').length,
      origins: [...new Set(srcs.map(s => { try { return new URL(s).origin; } catch (e) { return s; } }))] },
    structure: { elements: all.length, maxDepth, shadowRoots, landmarks, customElements: top(custom, 40), headings },
    css: { sheets, crossOriginSheets: crossOrigin, inlineStyleBlocks: $$('style').length, styleAttrs: $$('[style]').length,
      variables: vars, variableCount: Object.keys(vars).length, fontFaces: fontFaces.slice(0, 80), breakpoints: top(media, 20), keyframes: [...keyframes].slice(0, 50) },
    tokens, typography: roles, components: comps, loadedFonts: [...new Set(loadedFonts)],
    logos: logos.slice(0, 8), images: images.slice(0, 60), iconSystems,
    links: [...new Set($$('a[href]').map(a => a.href))].filter(h => /brand|press|media|newsroom|about|design|style|guideline|logo|asset/i.test(h)).slice(0, 60),
  };
})()
