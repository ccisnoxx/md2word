# Translation Term Governance Diff Gap Audit

## Goal

对照 Phase 2 closeout、已归档 Translation Term Set 任务和当前代码，审计 `translation-term-governance-diff` 方向是否仍存在第一版实现缺口，避免重复实现已经完成的 diff/preflight/proposal compatibility 能力，并给出后续最小任务边界。

## Requirements

- 本任务只做 planning / gap audit；写完 `prd.md`、`design.md`、`implement.md` 后先 review，不执行 `task.py start`。
- 不实现新功能，不改业务代码，不运行 pdf-mineru 解析、真实翻译 provider 或 Word 生成主流程。
- 必须读取并对照：
  - Phase 2 closeout。
  - `translation-term-set-management`。
  - `translation-term-set-governance-hardening`。
  - `translation-term-governance-diff`。
  - `translation-term-proposal-review-governance-linkage`。
  - 当前 Translation Term Set / proposal review 相关前后端代码、API 文档和测试。
- 必须判断以下第一版能力是否已完成：
  - Translation Term Set version diff。
  - publish preflight 和冲突/阻断提示。
  - pending Translation Term Proposal compatibility preview。
  - proposal review 批量 approve/reject。
  - proposal review 与 Translation Term Set governance 页面双向联动。
- 必须明确逐条 Translation Term CRUD 是否是 diff 第一版的必要前置。
- 如果仍有缺口，只拆一个最小后续任务；不要扩大到完整治理平台、自动 rebase、逐条 CRUD 或新主流程能力。

## Acceptance Criteria

- [x] 已创建 `translation-term-governance-diff-gap-audit` planning task。
- [x] 已读取 Phase 2 closeout、相关归档任务和当前实现证据。
- [x] 已确认第一版 diff/preflight/proposal compatibility 能力在当前代码中已经存在。
- [x] 已确认 proposal review 批量审核和治理页联动在当前代码中已经存在。
- [x] 已明确逐条 Translation Term CRUD 不是第一版 diff 的必要前置。
- [x] 已给出后续推荐边界：优先做浏览器级 smoke/acceptance，而不是重复实现 diff。

## Notes

- Review gate：用户确认文档范围后，才允许执行 `task.py start`。
