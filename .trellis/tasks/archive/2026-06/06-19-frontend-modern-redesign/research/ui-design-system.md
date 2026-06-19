# md2word frontend design research

## Source

Generated from `.codex/skills/ui-ux-pro-max/scripts/search.py` for:

- `document conversion internal operations workbench modern dark mode animation productivity --design-system`
- `dashboard responsive dark mode animation accessibility --stack vue`
- `animation accessibility dark mode --domain ux`
- Supplemental searches for SaaS/admin dashboard product, color, style, and typography.

## Key Takeaways

- Product fit: internal operations dashboard / productivity workbench, not a marketing landing page.
- Recommended UI direction: data-dense SaaS workbench with restrained glass surfaces, strong status colors, and micro-interactions.
- Avoid turning the first screen into a hero landing page; operators need scanning, filtering, and repeated action.
- Palette: keep a professional neutral base, shift toward teal focus/action accents with orange reserved for primary conversion/upload actions and warnings.
- Typography: continue system sans by default unless font loading is intentionally added. Plus Jakarta Sans is the preferred visual target if external fonts are acceptable later.
- Motion: use 150-300ms ease-out micro-interactions, entrance animation for page panels, async feedback for loading states, and no decorative infinite animation.
- Accessibility: semantic elements in Vue templates, dynamic ARIA where state changes, visible focus states, WCAG contrast, and `prefers-reduced-motion` support.

## Feasible Direction

Use one global design refresh rather than a page-by-page rewrite:

- Refresh `main.scss` tokens for light and dark themes.
- Update protected app shell for a more modern, compact, animated command-center feel.
- Update login page to match the new brand system.
- Update primary job list/create surfaces and upload/status components so the core conversion workflow feels cohesive.
- Preserve existing route, permission, API, store, and business behavior.

## Anti-Patterns To Avoid

- Decorative animations that keep running after page load.
- Single-hue palette dominated only by blue, slate, purple, beige, or orange.
- Large marketing hero sections inside the authenticated workbench.
- Cards nested in cards or oversized rounded cards in dense operational views.
- Static ARIA on interactive stateful controls.
