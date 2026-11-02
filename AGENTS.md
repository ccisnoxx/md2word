<!-- TRELLIS:START -->
# Trellis Instructions

These instructions are for AI assistants working in this project.

This project is managed by Trellis. The working knowledge you need lives under `.trellis/`:

- `.trellis/workflow.md` — development phases, when to create tasks, skill routing
- `.trellis/spec/` — package- and layer-scoped coding guidelines (read before writing code in a given layer)
- `.trellis/workspace/` — per-developer journals and session traces
- `.trellis/tasks/` — active and archived tasks (PRDs, research, jsonl context)

If a Trellis command is available on your platform (e.g. `/trellis:finish-work`, `/trellis:continue`), prefer it over manual steps. Not every platform exposes every command.

If you're using Codex or another agent-capable tool, additional project-scoped helpers may live in:
- `.agents/skills/` — reusable Trellis skills
- `.codex/agents/` — optional custom subagents

Managed by Trellis. Edits outside this block are preserved; edits inside may be overwritten by a future `trellis update`.

<!-- TRELLIS:END -->

## Project Overrides

### Language

- User-facing replies should default to Chinese.
- AI-created or substantially changed code comments, docstrings, JSDoc/TSDoc, logs, exception messages, and print outputs should default to Chinese.
- Keep machine-readable fields, protocol fields, config keys, API fields, error codes, structured log keys, code identifiers, and CLI/file path literals in their required original form.
- Project documentation, Trellis specs, and task artifacts should default to Chinese. This project-specific rule overrides any generic Trellis template language notes that say documentation should or must be English, unless the target path already has a clear English convention, external publication requires English, or the user explicitly requests English.
- Do not add comments for obvious code. Comments should explain non-obvious responsibilities, boundary conditions, side effects, business rules, exception branches, and important trade-offs.
- When editing Python files, tests, scripts, or Trellis docs in this project, apply a touched-scope documentation pass: review newly added or materially changed modules, classes, functions, complex branches, exception paths, developer-visible output, and nearby touched comments/docstrings.
- If touched code contains English comments, docstrings, JSDoc/TSDoc, logs, exception messages, or print output, translate or rewrite them into Chinese unless they are external protocol text, third-party/API field names, machine-readable values, test-contract literals, or explicitly requested English text.
- Do not add comments to untouched legacy code only because the file currently has few or no comments; prefer updating the touched code and removing stale, misleading, or mechanical comments such as `START/END MODIFICATION`.
- After non-trivial Python changes, the final reply should state whether comments/docstrings/developer-visible text were added, updated, or intentionally left unchanged.

### Trellis Usage

- For simple conversation, read-only investigation, small local fixes, or low-risk single-file changes, do not ask whether to create a Trellis task and do not create one unless the user explicitly asks for one. This project-specific rule overrides generic Trellis no-task triage prompts.
- Use a Trellis task for cross-module changes, public API changes, data contract changes, configuration changes, database changes, permission changes, cache/state-sync changes, long-lived requirements, or work that needs explicit acceptance criteria.
- Once a Trellis task exists, read `prd.md`, `design.md`, `implement.md`, and the relevant `.trellis/spec/` files before writing code.
- For complex tasks, do not implement until `prd.md`, `design.md`, and `implement.md` are reviewable.

### Trellis And Ponytail

- Trellis is the authoritative owner of task classification, planning gates, task artifacts, context loading, project Specs, verification requirements, Spec updates, commits, and finish-work.
- Outside an active Trellis task, follow the global and project `AGENTS.md` rules; Ponytail may constrain implementation choices but must not expand the requested scope.
- When a Trellis task exists, its `prd.md`, `design.md`, `implement.md`, and relevant `.trellis/spec/` files override generic Ponytail minimization advice.
- Ponytail governs implementation choices only after the scope and acceptance criteria are authorized. Prefer existing code, the standard library, native platform capabilities, installed dependencies, and then the minimum new code.
- Required Trellis artifacts, project documentation, and Spec-defined checks are not optional boilerplate and must not be removed or weakened by Ponytail.
- Ponytail may propose reducing scope, but implementation of the reduced scope must wait until the PRD and acceptance criteria are updated and confirmed.
- Minimal code must not weaken correctness, security, data integrity, accessibility, public contracts, error handling, or explicit requirements.
- Ponytail's minimum runnable check is a validation floor, not a replacement for tests, type checks, builds, smoke checks, or online validation required by `implement.md` or project Specs.
- Project Specs override generic Ponytail advice when they establish a shared owner, reuse boundary, public contract, state model, or necessary abstraction.
- `trellis-check` owns correctness, security, contract, and regression review. `ponytail-review` supplements it by identifying unnecessary complexity and does not replace it.
- Ponytail's brevity guidance must not omit required reporting of changed scope, validation results, documentation status, or residual risk.
- Ponytail `ultra` requires explicit user activation and is not the project default.

### Engineering Constraints

- Confirm the real implementation before editing. Do not add guessed compatibility fallbacks or silent defaults.
- Default to the smallest sufficient solution. Do not introduce extra layers, factories, strategies, plugins, DDD, microservices, or generic frameworks for architectural appearance.
- Introduce abstraction only when real duplication, a clear testing boundary, multiple concrete implementations, a stable ownership boundary, or proven change pressure exists.
- Do not add thin wrappers that only forward fields, wrap one call, or rename another function.
- Do not hardcode secrets, tokens, private config, or real credentials. Use the existing project configuration mechanism or environment variables.
- Validate and sanitize external input at system boundaries. Use parameterized queries or existing safe project APIs for database access.

### GitHub 用途与分支整理

- 本项目将 GitHub 作为代码仓库使用，不把 GitHub Actions、CI 或状态检查作为提交、推送、合并及分支整理的前提；不得将缺少这些机制自动列为阻塞。
- 未经用户明确要求，不新增、启用或配置 GitHub Actions、CI、必需状态检查，也不因使用 GitHub 而建立额外验证流程。
- 分支整理只核对提交包含关系、差异、依赖和冲突；不因此运行项目测试、构建或发布聚合检查，也不顺带维护历史测试。

### Validation

- 实际改动代码时，只选择能够验证该改动及直接受影响合同的最小有效检查，不机械套用全仓回归或完整发布流程。
- 成功结果在相关源码、依赖、配置和夹具等输入未变时直接复用；不得仅因切换 worktree、准备提交、创建 PR 或收尾而重复运行。
- 验证失败时先区分本次产品缺陷与历史测试维护。与本次实际改动无关的旧夹具、过时断言和既有失败应分开记录、保留，不为让历史测试全部变绿而持续扩大修复或验证范围。
- 直接保护本次行为的必要回归与历史测试维护应分别说明；后者只有在当前任务确实需要或用户明确另行授权时才处理。
- 纯规则文档修改和只读分支整理默认核对文字与差异，不运行应用测试。用户明确禁止的检查不得换名、换工具或经聚合脚本间接触发。
- Trellis、Skills、`implement.md` 和 Spec 校验清单都须在上述项目边界及当前用户授权内使用；通用流程或历史计划不能自动扩大为 CI、全仓测试或完整发布门禁。
- 如未执行较重检查，简要说明实际验证范围与未验证边界，不把未执行项表述为通过。

### Git

- Do not run `git reset --hard`, `git checkout -- <file>`, history rewrites, or broad deletion unless the user explicitly requests and confirms it.
- Before committing work code, present a commit plan and get user confirmation.
- Do not include unrecognized dirty files in commits.
- Do not push automatically.
- Before running `task.py archive` or `add_session.py`, explain if it may create Trellis bookkeeping commits.
