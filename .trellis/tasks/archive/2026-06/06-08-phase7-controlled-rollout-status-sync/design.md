# Phase 7 Controlled Rollout Status Sync Design

## Decision

Represent Phase 7 as a task queue with explicit blocked states rather than implying that task creation authorizes execution.

## Status Model

- `accepted_no_live`: planning, implementation, or preflight accepted without external send.
- `prepared_blocked`: task artifacts exist but execution or acceptance is blocked.
- `planning_scaffold`: planning exists but required operator inputs are missing.
- `blocked_dependency`: task cannot proceed until another acceptance exists.

## Sources Of Truth

- Trellis parent task tree: child task inventory.
- `phase7-task-status.md`: operator-facing queue and hard stops.
- CodeStable roadmap/items: cross-session status snapshot.

## Non-Goals

- No task archive.
- No git commit.
- No live execution.
- No product code changes.
