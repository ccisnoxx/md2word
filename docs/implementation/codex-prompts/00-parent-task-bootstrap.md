# Trellis 父任务与状态清单初始化

## 一次性准备

```bash
cd /Users/sc/PycharmProjects/md2word
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
