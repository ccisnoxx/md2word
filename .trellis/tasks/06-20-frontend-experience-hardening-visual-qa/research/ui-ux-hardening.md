# UI/UX Hardening Research Notes

## Source

Generated with local `ui-ux-pro-max` search for a dense SaaS operations workbench and visual QA hardening.

Commands used:

```bash
python3 .codex/skills/ui-ux-pro-max/scripts/search.py "SaaS operations workbench dense enterprise workflow visual QA" --design-system -p "md2word Frontend Hardening" -f markdown
python3 .codex/skills/ui-ux-pro-max/scripts/search.py "design system consistency responsive QA accessibility visual regression operations workbench" --domain ux -n 8 -f markdown
```

## Applicable Takeaways

- Responsive testing should include common breakpoints, especially mobile, tablet, and desktop widths.
- Operations tables need explicit mobile handling: the page should not overflow; the table wrapper may scroll internally.
- Loading states should be visible for waits over roughly `300ms`.
- Hover and focus states should clearly identify interactive controls without causing layout shift.
- Keyboard focus and accessible labels matter for command palettes, drawers, and icon-only controls.
- Light-mode contrast and border visibility need explicit checking.

## Filtered-Out Suggestions

The design-system search returned several marketing-oriented suggestions such as enterprise gateway landing sections, large hero patterns, vibrant block-based styling, large animated sections, and prominent sales CTAs.

Those suggestions do not fit this project positioning. This task should follow the existing Trellis frontend layout guidelines instead: dense operations surfaces, compact command headers, existing `--app-*` tokens, no hero sections, no decorative gradients, and no marketing-style page structure.

## Recommended Local Direction

Use this research as a QA checklist, not as a new visual identity:

- preserve the current quiet operations console direction
- check responsive fit at `375px`, `768px`, and `1440px`
- use existing page shell and panel patterns
- keep all operator-visible high-frequency copy Chinese-first
- add or update Playwright smoke coverage only where it proves real UI hardening
