---
doc_status: active
last_verified_commit: null
owner: null
verification_scope: >-
  全文辅助/模板用途、原指令结构与Manifest定义的静态对照；仅追加治理字段和导语，未执行提示词、创建任务、修改状态或验收产品。原文字节、TR-406旧依赖差异及合并关系见 ../../../.trellis/tasks/archive/2026-11/11-10-documentation-evidence-governance/research/b4-preparation.md；45项实现证据沿用同目录manifest-reconciliation.md原范围。
---

# Trellis 父任务与状态清单初始化

本页是父任务首次初始化辅助；原“首次全部 todo”、创建及状态迁移步骤是使用条件，不表示现在应重建父任务或重置状态。使用前按 [Manifest](../codex-task-manifest.yaml) 和实际 Trellis 记录确认；本批不执行原命令，原模板完整保留。

## 一次性准备

```bash
cd ${PROJECT_ROOT}
git status --short
python3 ./.trellis/scripts/init_developer.py sc
python3 ./.trellis/scripts/task.py create \
  "Datasheet 文档交付质量完善" \
  --slug datasheet-docx-delivery-quality
```

将仓库中的：

```text
trellis-bootstrap/prd.md
trellis-bootstrap/design.md
trellis-bootstrap/implement.md
trellis-bootstrap/task-map.md
```

复制到新建父任务目录，并运行：

```bash
python3 ./.trellis/scripts/task.py validate <父任务目录名>
```

父任务负责范围、依赖和最终集成，不作为日常大规模实现任务。每个 Codex 提示词会在该父任务下创建一个独立子任务。

## 状态清单

确认文件存在：

```text
docs/implementation/codex-task-manifest.yaml
```

首次合入时，全部任务应为 `todo`。不要一次性把任务批量改为 `in_progress`。

## 基线规则

- 每项依赖必须先合并到基线分支并更新为 `done` 或经人工接受的 `skipped_existing`；
- 新任务从包含全部依赖的最新基线创建分支；
- 规划会话更新为 `planning`；
- 实施会话更新为 `in_progress`，完成后更新为 `review`；
- 人工验收后才更新为 `done` 并归档 Trellis 任务；
- 不自动 push。
