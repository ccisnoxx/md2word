# Fix Draft Term Rule Dialog Scrolling

## Goal

Fix the Draft rule create/edit dialog in the Term Rule Set workbench so users can scroll the full form with the mouse when the dialog content is taller than the viewport.

## What I Already Know

* User reproduction path: click "术语规则", click "新建规则" to enter the terminology workbench, then in "Draft 规则" click "新增规则"; the "新增 draft rule" configuration dialog cannot be scrolled with the mouse.
* The affected page is `frontend/src/pages/TermRuleSetPage.vue`.
* The affected modal is `<el-dialog v-model="ruleDialog.visible" :title="ruleDialogTitle" width="760px" class="rule-dialog">`.
* The form contains several vertical sections, including `TermSegmentEditor`, preview, grid controls, custom markdown/HTML, and notes.
* The page currently tries to style `:deep(.rule-dialog .el-dialog__body)` with `max-height` and `overflow-y: auto`, but the observed behavior shows the mouse wheel scroll contract is still broken in the rendered UI.
* Frontend layout guidelines require page-level layout changes to keep controls inside the viewport and verify affected workbench behavior.

## Requirements

* The "新增 draft rule" dialog must keep its header and footer usable while allowing the form body to scroll vertically.
* The same fix must apply to the "编辑 draft rule" dialog because it uses the same component state and form.
* The scrollable region should be owned by this page's markup/CSS rather than relying only on Element Plus internal dialog body selectors.
* The fix must not change draft rule create/edit business behavior or API payloads.
* The fix must remain responsive on desktop and narrow viewports.

## Acceptance Criteria

* [ ] Opening "新增 draft rule" on the Term Rule Set page allows mouse-wheel vertical scrolling through the full form when the form exceeds viewport height.
* [ ] Dialog footer actions remain reachable.
* [ ] Editing an existing draft rule has the same scroll behavior.
* [ ] No API or backend behavior changes.
* [ ] Frontend build or targeted frontend verification is run, or any skipped verification is explained.

## Definition of Done

* Code change is scoped to the affected frontend page unless verification reveals a shared dialog contract problem.
* Existing page style tokens and Element Plus conventions are preserved.
* Relevant frontend checks are run.
* Residual risk is reported.

## Technical Approach

Wrap the draft rule form in an explicit page-owned scroll container inside the dialog body, for example `.rule-dialog-scroll`, and move the max-height/overflow behavior onto that wrapper. Keep the existing dialog footer slot outside the scroll container so Save/Cancel remain visible.

## Out of Scope

* Changing term rule persistence, permissions, review flow, or draft rule APIs.
* Redesigning the Term Rule Set page.
* Changing other dialogs unless the same bug is found in direct shared code.

## Technical Notes

* Affected file: `frontend/src/pages/TermRuleSetPage.vue`.
* Relevant component inside the form: `frontend/src/components/TermSegmentEditor.vue`.
* Relevant spec: `.trellis/spec/frontend/layout-guidelines.md`.
