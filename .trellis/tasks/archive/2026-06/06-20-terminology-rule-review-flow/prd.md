# Terminology Rule Review Flow MVP

## Goal

Allow ordinary users to submit terminology rule changes for their own department without granting administrator permissions, while keeping only administrator-approved rules effective in runtime matching. The flow must support batch submission from PDF review work, item-level review, partial approval, conflict detection, version history, and a paginated live-rule browsing experience.

## What I Already Know

* The current live rule page disables formal rule creation for non-admin users in `frontend/src/pages/TermRuleWorkbenchPage.vue`.
* The live rule page currently requests `page_size: 200` through `frontend/src/api/termRules.ts`, even though the backend `GET /term-rules` endpoint already supports `page` and `page_size` with a default of 20.
* Existing term rule writes in `app/domains/term_rules/router.py` require admin access for create, update, import, sync, and delete.
* Existing term rule proposals support ordinary-user submission and admin review, but the current model is proposal-oriented and merges to a term rule set draft. This MVP needs an explicit batch + review item model for multiple rule changes submitted together.
* Existing proposal bulk review already allows partial success, which is a useful interaction precedent for item-level review.
* Existing MySQL persistence has `term_rule_proposals`, `term_rules`, `term_rule_categories`, and `term_rule_segments`; the current `term_rules` unique key is versioned by `term_rule_set_id`, `version`, and `source_term`.

## Requirements

* Keep effective terminology rules separate from pending review changes.
* Show live/effective terminology rules as a paginated list, defaulting to 20 rules per page.
* Fix the create/edit terminology rule form so its popup or drawer content can scroll vertically with the mouse when content exceeds the viewport.
* Ordinary users can submit terminology rule create and update requests, but the submitted content must not become effective until approved by an administrator.
* Ordinary users can only submit rules for their own department scope.
* Ordinary users cannot submit global rules in this MVP.
* Administrators can create and edit global rules.
* MVP administrators are super administrators: they can review submissions from all departments. Department administrator review is out of scope.
* Effective scope has two levels only:
  * `global` with `scope_id = NULL`
  * `department` with `scope_id = <department_id>`
* Runtime matching prefers the current user's department rule and falls back to the global rule when no department rule exists.
* Submissions are grouped into review batches so one PDF or business review can submit multiple rule changes together.
* A review batch contains multiple review items. Each item represents one `create`, `update`, or future `delete` change.
* Admin review supports batch-level navigation and item-level decisions.
* Admin review must support partial approval: approved items become effective immediately, while rejected or conflict items remain recorded with reasons.
* Each review item status includes at least `pending`, `approved`, `rejected`, and `conflict`.
* Batch status is derived from item statuses rather than maintained as an independent source of truth.
* Rejected items must retain administrator rejection reasons.
* Conflict items must retain conflict reasons and not write to effective rules.
* Updates to existing effective rules must not mutate the current rule before approval. They create pending review items containing the submitted snapshot and the target rule/base version.
* Approved updates write version history before updating the current effective rule.
* Approved creates create an effective rule and record version `1` history.
* Admin delete is included in the model for MVP, but only administrators can delete rules. Ordinary-user delete requests are out of scope.
* Admin delete is soft delete/inactivation, not physical deletion, and writes version history.
* Conflict detection runs before approving an item:
  * `create` conflicts when an active effective rule already exists for `scope_type + scope_id + normalized_term`.
  * `update` and `delete` conflict when the item's `base_version` does not match the current effective rule version.
  * Conflict items are marked `conflict` and require administrator handling; they must not overwrite automatically.

## Acceptance Criteria

* [ ] Ordinary users can open the terminology rule submission UI and submit one or more department-scoped create/update items without admin permissions.
* [ ] Ordinary users cannot submit global-scoped rule changes.
* [ ] Administrators can create/edit global rules and review all department submissions.
* [ ] Live rule browsing shows paginated data with default page size 20 and does not force-load hundreds of rules into one page.
* [ ] The terminology rule create/edit UI remains mouse-scrollable when the form content exceeds viewport height.
* [ ] Pending review changes do not affect rule matching, simulation, or document generation.
* [ ] Approving a create item creates an effective rule only if there is no active `scope_type + scope_id + normalized_term` conflict.
* [ ] Approving an update item updates the effective rule only if `base_version` still matches the current effective rule version.
* [ ] Approved update/delete actions write historical versions before changing the current effective record.
* [ ] A batch with mixed outcomes can have approved items effective while rejected/conflict items remain visible with reasons.
* [ ] Batch status can be derived correctly from item statuses.
* [ ] Tests cover ordinary-user submit, admin approve/reject/conflict, pagination behavior, and version-history writes.

## Definition of Done

* Targeted backend tests cover review batch/item creation, permissions, conflict detection, item-level partial approval, and version history.
* Frontend or component-level tests cover non-admin submission access, pagination state, and review action flows where local test infrastructure supports it.
* Lint/typecheck/build checks are run for touched layers, or skipped with a concrete reason.
* Public API/schema changes are documented in nearby code comments, schemas, or developer notes when the contract is not obvious.
* Existing unrelated dirty files are preserved.

## Technical Approach

Use the existing term rule domain as the implementation home, but introduce explicit review batch and review item concepts instead of stretching the current single-proposal workflow beyond its shape.

Recommended model:

* `terminology_rules` or an evolved effective-rule persistence surface: current effective rules only, including `scope_type`, `scope_id`, `normalized_term`, `current_version`, active/deleted state, and rule payload fields.
* `terminology_rule_review_batches`: one submitted batch, usually corresponding to one PDF or one business review pass; includes submitter, submitter department, status summary fields if needed for indexing, and timestamps.
* `terminology_rule_review_items`: child changes under a batch; includes action, status, target rule id, base version, submitted snapshot, conflict/rejection reason, reviewer, and timestamps.
* `terminology_rule_versions`: audit/history rows for every approved create/update/delete, linking back to review item when applicable and storing before/after snapshots.

Implementation should preserve the existing term rule proposal APIs where possible for compatibility, but the MVP can add new batch/item endpoints when the old proposal contract cannot express batch semantics cleanly.

Frontend direction:

* Replace the disabled non-admin "新建规则" path with a submission flow that creates department-scoped review batches/items.
* Keep admin-only formal global rule management explicit.
* Add pagination controls to the live rule table and stop forcing `page_size: 200`.
* Ensure long create/edit forms use an `el-drawer`/`el-dialog` body with bounded height and `overflow-y: auto`.
* Admin review UI should group by batch and allow per-item approve/reject/conflict handling, with bulk actions that still report item-level outcomes.

## Decision (ADR-lite)

**Context**: Ordinary users need to contribute terminology rules from PDF review work, often several at a time, but rules affect document output and must not become effective without administrator review.

**Decision**: Split effective rules from pending review changes. Model submissions as batches containing review items. Allow item-level partial approval. Keep ordinary users department-scoped; reserve global rule changes and all MVP review permissions for administrators. Preserve version history and require conflict checks before effectiveness changes.

**Consequences**: This adds persistence and API complexity compared with directly opening the existing admin write endpoints, but it protects runtime rule correctness, supports cross-department review, and creates an audit trail suitable for rollback and troubleshooting.

## Out of Scope

* Department administrator role or department-scoped reviewer permissions.
* Ordinary-user global rule submission.
* Ordinary-user delete rule requests.
* Automatic conflict resolution or last-write-wins behavior.
* More granular scopes beyond global and department.
* Full rollback UI beyond storing enough version history to support future rollback.

## Technical Notes

* Existing live page: `frontend/src/pages/TermRuleWorkbenchPage.vue`.
* Existing live API wrapper: `frontend/src/api/termRules.ts`.
* Existing term rule router: `app/domains/term_rules/router.py`.
* Existing proposal router/service: `app/domains/term_rules/proposals_router.py`, `app/domains/term_rules/proposals_service.py`.
* Existing term rule models/schemas: `app/domains/term_rules/models.py`, `app/domains/term_rules/schemas.py`.
* Existing MySQL schema and adapter references: `app/infrastructure/persistence/mysql/schema.py`, `app/infrastructure/persistence/mysql/term_rule_proposals.py`.
* Existing frontend proposal page: `frontend/src/pages/TermProposalsPage.vue`.
* Current branch has unrelated dirty files observed before this PRD update: `app/infrastructure/persistence/mysql/schema.py` and `tests/test_database_job_repository.py`. Preserve them unless later confirmed related.
