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
- On first entry to a Trellis task, after a scope change, or when context is missing, read `prd.md`, `design.md`, `implement.md`, and the relevant `.trellis/spec/` files before writing code. During the same active task, reuse already loaded or injected context and reread only changed or directly relevant sections; do not reread unchanged foundational documents in every agent turn.
- For complex tasks, do not implement until `prd.md`, `design.md`, and `implement.md` are reviewable.
- The existence or age of a Trellis task does not by itself require the full implementation, review, or release workflow for every incremental fix.

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

### Validation

- After code changes, run the smallest effective validation.
- For Trellis tasks, validate according to `implement.md` and the relevant spec quality gates.
- If heavier checks are skipped, state the reason, the substitute checks, and the remaining risk.

### Incremental PDF/DOCX Fix Validation

This project expects many incremental fixes discovered from different PDF datasheets. Select validation from the verified blast radius of the current change, not from the size or age of the active Trellis task. Start at the lowest sufficient level and escalate only when evidence requires it.

#### Level A: Local Micro-Fix

Use Level A when the change has one known owner, does not alter a public API, schema, configuration contract, or cross-module data flow, and one focused regression can prove the behavior.

- The main agent may implement and check the fix directly; separate implementation and review agents are not required.
- Run one to three focused tests or a minimal reproduction, plus `git diff --check`.
- Do not run module-wide suites, release gates, Word/WPS checks, full sample conversions, or formal Spec updates by default.

#### Level B: Shared Owner or Bounded Cross-Path Fix

Use Level B when the change affects a shared parser, renderer, helper, integrity rule, or multiple known call paths, but remains bounded and does not change a public or release contract.

- Run the failing regression and the affected module tests.
- Use an independent review only when the change contains non-obvious judgment or creates a real shared-regression risk.
- Do not run the release gate by default.
- Run Word/WPS checks only when OOXML, fields, formulas, columns, pagination, or other client-visible layout behavior changes.
- When practical, batch related micro-fixes into one client-validation candidate.

#### Level C: Contract, Release, or High-Risk Change

Use the full Trellis closure workflow only when at least one of these conditions applies:

- A public API, DocumentIR/schema, template configuration, or versioned contract changes.
- Section, column, pagination, table fallback, asset identity, or content-blocking rules change.
- Word/WPS fields, OMML, or client compatibility changes.
- The work is preparing a commit, release, archive, or milestone candidate.
- Focused validation reveals an unexplained cross-module regression.

Level C may require implementation and independent review agents, integration checks, Word/WPS validation, release gates, and Spec synchronization.

#### Reuse and Escalation

- Validation is monotonic: begin with the smallest sufficient check and escalate only after an observed failure or verified risk.
- The implementation phase records checks already run; the review phase fills evidence gaps and does not blindly repeat broad suites.
- Run a release gate once per candidate and rerun it only after a relevant code, configuration, or environment change.
- Record ordinary fixes in the task status or problem matrix when needed. Update formal Specs only for stable general contracts, user-confirmed rules, or batch milestones.
- Automated tests do not replace a necessary Word/WPS check, but unchanged client-visible behavior does not require one.

### Git

- Do not run `git reset --hard`, `git checkout -- <file>`, history rewrites, or broad deletion unless the user explicitly requests and confirms it.
- Before committing work code, present a commit plan and get user confirmation.
- Do not include unrecognized dirty files in commits.
- Do not push automatically.
- Before running `task.py archive` or `add_session.py`, explain if it may create Trellis bookkeeping commits.
