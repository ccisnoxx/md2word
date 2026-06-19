# Frontend Development Guidelines

> Implementation rules for the Vue 3 / Element Plus frontend in this project.

---

## Pre-Development Checklist

- Read [Layout Guidelines](./layout-guidelines.md) before changing protected workbench pages or global frontend styles.
- Search for existing page shell, panel, table, and action-bar patterns before adding new wrappers.
- Keep page-level redesigns scoped to the requested route unless a shared layout contract must change.

---

## Guidelines Index

| Guide | Description | Status |
|-------|-------------|--------|
| [Layout Guidelines](./layout-guidelines.md) | Page shell, grid, sticky controls, and visual verification rules | Active |

---

## Quality Check

- `npm run build` must pass in `frontend/` after frontend changes.
- Playwright screenshots or equivalent browser checks must cover affected workbench pages at desktop and mobile widths when layout changes.
- Check that pages have no uncontrolled horizontal overflow and that fixed/sticky controls stay inside the viewport.

---

**Language**: All documentation should be written in **English**.
