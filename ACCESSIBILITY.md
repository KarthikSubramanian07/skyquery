# Accessibility

SkyQuery's marketing and developer site targets **WCAG 2.2 Level AA**.

## What was tested

- Routes: `/`, `/developers`, `/about`, `/contact`, `/privacy`, `/404.html`
- Automated: axe-core with tags `wcag2a`, `wcag2aa`, `wcag21a`, `wcag21aa`, `wcag22aa` at 1440×900, 390×844, and 320×800
- Manual: keyboard operation (including install tabs and the mobile menu), visible focus, skip link, landmarks/headings, theme and motion controls, reduced-motion behavior, reflow at 320 px

## Known limitations

- The decorative starfield canvas is `aria-hidden`; a Pause control stops its motion for WCAG 2.2.2
- The typed terminal demo is summarized for assistive tech via a visible `figcaption` (screen-reader-only); Pause/Resume and Replay control the animation
- Content pages are static; there is no authenticated UI or form submission on the site itself

## Report a barrier

Open an issue at https://github.com/KarthikSubramanian07/skyquery/issues or follow the contacts on `/contact`.
