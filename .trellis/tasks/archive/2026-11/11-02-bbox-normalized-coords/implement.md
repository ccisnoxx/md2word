# 实施计划

## 1. 有序任务

1. 记录基线：`tests.test_document_ir_mineru_converter_layout`、`tests.test_mineru_artifact_validator`、`tests.test_document_ir_word_renderer_layout`、`tests.test_image_group_rendering`、`tests.test_document_job_review_hints`（若存在）及表格占位相关测试的失败集合。
2. `layout_signals`：坐标空间识别、`pdf_point_bbox`、常量。
3. `layout_plan`/`render_plan`/`logical_table_plan`：`LayoutPage.landscape`。
4. `table_placeholder`、`review_content`：改经 `pdf_point_bbox`。
5. 测试：按 design 第 6 节新增；对因页尺寸修正而变化的既有期望逐条核对原因后更新。
6. 本地真实样本回归（`tests/tmp/bbox-audit/`）：页尺寸与 OPA228_P1 裁切目视。
7. 规格：`word-generation-rules.md` 中涉及页面几何/坐标的条目补充坐标合同。

## 2. 验证

- 定向测试集与基线对比；不跑全仓回归与前端（前端无改动）。

## 3. 回滚点

单一功能提交，回退即恢复旧推导；无数据迁移。

## 4. 实施结果与验证（2026-11-02 北京时间）

- 实现：`layout_signals` 识别 `mineru_normalized_1000`（版本 ≥ 3.1、有 page_size、页内 bbox 全在 [0,1000]），页几何 1000×1000、方向取 PDF 页尺寸；新增唯一换算 `pdf_point_bbox`。`LayoutPage.landscape` 替代 render_plan/logical_table_plan 的宽 > 高判断。表格占位裁切与复核位置投影经换算函数；占位绑定解码对无标记旧 IR 沿用原始值校验（兼容已持久化数据）。
- 新增 `tests/test_bbox_coordinate_space.py` 7 例通过（识别与回退、换算、横版 section、缺 HTML 表格按 PDF 点裁切且绑定保留原始 bbox、复核投影新旧页面）。
- 回归：converter_layout、review_hints、page_layout_characterization、artifact_validator、word_renderer_layout、image_group_rendering + 新文件共 213 例，1 失败 28 错误与修改前基线集合一致。
- 真实样本（本地 `mineru_result/` 6 份）：均为 1000×1000 并带标记、方向 portrait 与 PDF 一致，栏位分类与正确页宽差异归零；OPA228_P1 chart/table 经 `pdf_point_bbox` + Poppler 实际裁切，目视与源对象一致（`tests/tmp/bbox-audit/crops/after_*.png`，未入库）。
- 规格：IR-002 按源 PDF 证据修订（取代“bbox 与物理页同比例、只允许单一比例缩放”的前提）。
- 未做：Word 目视、全仓回归；已持久化旧 IR 中历史错误裁切的占位图不迁移（保持可读）。
