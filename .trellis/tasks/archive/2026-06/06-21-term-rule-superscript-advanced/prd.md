# Fix Term Rule Superscript Preview And Advanced Creation

## Goal

Restore the draft term-rule creation experience so operators can trust segment preview output and can explicitly create advanced term rules from the Term Rule Set draft page.

## What I Already Know

* The user reports that when creating a term rule, some segments selected as superscript still preview as subscript.
* The user also remembers an advanced term-rule creation path, but the current create flow appears simple-only.
* `frontend/src/components/TermPreview.vue` renders `subscript` as `<sub>` and `superscript` as `<sup>`.
* `frontend/src/components/TermSegmentEditor.vue` is reused by draft rule creation, term proposals, and review flow forms.
* `frontend/src/pages/TermRuleSetPage.vue` currently has one `新增规则` button and a lower `YAML 高级编辑兜底` collapse.
* Backend term-rule creation auto-generates `custom_html` and `custom_markdown` from segments when they are omitted.

## Requirements

* Draft rule creation/editing preview must reflect the selected `render_type` immediately, including `superscript`.
* The preview component must keep native `<sub>` / `<sup>` tags in normal inline flow so browser default vertical offsets are preserved.
* The Term Rule Set draft page must provide a clear advanced creation entry, not only the basic structured rule button.
* Advanced creation must remain scoped to draft rule editing and reuse the existing `custom_markdown` / `custom_html` fields instead of changing backend API contracts.
* Existing draft publish, preflight, diff, YAML fallback, and proposal flows must remain behavior-compatible.

## Acceptance Criteria

* [ ] In the draft rule dialog, changing a segment from subscript to superscript updates both previews to superscript before saving.
* [ ] Creating an advanced draft rule is discoverable from the Draft 规则 action area.
* [ ] Advanced mode exposes custom Markdown and custom HTML fields as part of the primary dialog flow.
* [ ] Basic draft rule creation remains available and unchanged for normal segment-based rules.
* [ ] Targeted frontend tests cover superscript preview and advanced creation visibility.
* [ ] Frontend build or the smallest applicable targeted check passes.

## Definition of Done

* Tests added/updated where risk is meaningful.
* Lint / typecheck / build run where practical.
* No backend API contract changes unless evidence shows they are necessary.
* Documentation/comments updated only if behavior or non-obvious logic changes.

## Out of Scope

* Changing term-rule publish, default-version, rollback, preflight, or diff semantics.
* Reworking term proposals or review flow unless the shared segment editor fix requires it.
* Replacing the YAML advanced fallback.
* Adding a new backend rule mode field or changing request/response schemas.

## Technical Approach

Keep the fix frontend-scoped unless backend evidence proves otherwise. Fix `TermPreview` layout so native subscript/superscript offsets are not neutralized by flex layout, then update `TermRuleSetPage.vue` to offer explicit basic and advanced draft-rule creation paths using the existing form state and API payload.

## Technical Notes

* Relevant files inspected:
  * `frontend/src/components/TermPreview.vue`
  * `frontend/src/components/TermSegmentEditor.vue`
  * `frontend/src/pages/TermRuleSetPage.vue`
  * `frontend/tests/smoke/term-rule-set-dialog.spec.ts`
  * `app/domains/term_rules/yaml_codec.py`
  * `app/domains/term_rules/versioning_service.py`
* Relevant spec:
  * `.trellis/spec/frontend/index.md`
* Existing smoke coverage checks dialog viewport behavior, but not segment render-type switching or advanced creation discoverability.
