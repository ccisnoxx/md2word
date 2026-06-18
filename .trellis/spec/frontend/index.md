# Frontend Development Guidelines

> Vue 3 + Element Plus + SCSS conventions for the internal workbench frontend.

---

## Overview

This directory documents frontend implementation conventions that future UI work should preserve.

---

## Pre-Development Checklist

- Read [UI System Guidelines](./ui-system-guidelines.md) before changing shared layout, page shells, Element Plus styling, or main-flow job UI.
- Search for existing `--app-*` tokens and shared page classes before adding new colors, spacing, shadows, or layout helpers.
- Keep API calls, router guards, upload flow, polling, permission checks, and backend action availability logic out of presentation-only changes.

---

## Quality Check

- `cd frontend && npm run build`
- Run `cd frontend && npm run test:unit` when TypeScript utilities or shared formatting helpers could be affected.
- Run `cd frontend && npm run test:smoke` when the local Playwright browser cache is available and the change touches `/jobs`, `/jobs/new`, or `/jobs/:id` interactions.

---

## Guidelines Index

| Guide | Description | Status |
|-------|-------------|--------|
| [UI System Guidelines](./ui-system-guidelines.md) | Visual tokens, page templates, and Element Plus styling boundaries | Current |
