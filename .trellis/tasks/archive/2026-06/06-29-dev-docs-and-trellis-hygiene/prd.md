# Dev docs and Trellis hygiene

## Goal

清理会误导后续规划和开发判断的文档/Trellis 噪音，包括空 `docs/dev` 文件、陈旧路径、无效索引链接和已完成但仍显示 in_progress 的 bootstrap 指南任务。

## Evidence

- Several `docs/dev/*.md` files are empty, including `document-ir-v1.md`, `template-config-package-v1.md`, `translation-ai-audit-debug.md`, and related term/template docs.
- `docs/dev/backend-dev-docs-index.md` references old absolute paths and empty documents.
- `.trellis/tasks/00-bootstrap-guidelines/prd.md` has checked-off completion items while `task.json` still reports `in_progress`.

## Requirements

- R1. Keep this task behavior-preserving; do not change product code or runtime behavior.
- R2. Remove, fill, or explicitly mark empty docs as deferred so they are not mistaken for current guidance.
- R3. Fix stale absolute paths and broken/empty index references.
- R4. Align Trellis bootstrap task state with its actual completion status after review.
- R5. Preserve useful historical context and avoid deleting active task evidence.

## Acceptance Criteria

- [ ] Empty `docs/dev` files are either completed, removed, or marked with a clear deferred status and owner/context.
- [ ] `docs/dev/backend-dev-docs-index.md` links only to valid current docs or clearly labeled deferred docs.
- [ ] Stale absolute paths are replaced with repository-relative or current hostdzire/project paths where appropriate.
- [ ] `00-bootstrap-guidelines` is reviewed and either archived or updated with remaining work made explicit.
- [ ] A docs-only validation pass confirms no intended product behavior changed.

## Out Of Scope

- Refactoring backend/frontend code.
- Rewriting all developer documentation.
- Archiving unrelated active tasks.
