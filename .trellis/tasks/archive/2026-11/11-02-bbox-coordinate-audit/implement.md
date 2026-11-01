# 实施计划

前置：D1、D2 获用户确认后 `task.py start`。

## 1. 有序步骤

1. 块匹配与拟合（6 份样本）→ 坐标换算结论与残差表。
2. PDF 文字独立验证（4 份 OPA228）→ 两种假设的覆盖率对比。
3. 使用点审计 → 清单与逐项实测偏差（不改代码，临时脚本调用模块）。
4. 裁切实证（OPA228 表格块、图片块各一）→ PNG 与目视结论。
5. （D1 授权时）hostdzire 只读抽取 1–3 个近期任务的版本元数据与 bbox 统计。
6. 撰写 `research/bbox-coordinate-space.md`，含修复方案与测试清单。

## 2. 产物

- `.trellis/tasks/11-02-bbox-coordinate-audit/research/bbox-coordinate-space.md`（提交）
- `tests/tmp/bbox-audit/`：临时脚本、裁切 PNG（不提交）

## 3. 验证

- 每个结论注明数据来源（样本、版本、命令）；无法验证的项（Word 显示、未授权的线上数据）如实标注。
- 不运行产品测试（无代码改动）。

## 4. 停止条件

- 若样本显示坐标空间随版本/后端变化且无法从包内元数据判别，停止并报告，不臆测修复方案。

## 5. 实施结果（2026-11-02 北京时间）

- 步骤 1–5 全部完成，结论与证据见 `research/bbox-coordinate-space.md`；AC1–AC4 满足。
- 未改动 `app/`、`tests/` 受版本控制文件；临时脚本与裁切 PNG 位于 `tests/tmp/bbox-audit/`（已忽略，按 D2 保留供目视）。
- 生产核实按 D1 只读执行，样本为同一文档三次提交。
