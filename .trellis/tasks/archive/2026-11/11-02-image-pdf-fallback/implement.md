# 实施计划

前置：D1–D4 获确认；按 D4 确定实现基点（推荐 PR #18、#19 合并后从 `main` 重建本分支，再 `task.py start`）。

## 1. 有序任务

1. 基线：在实现基点运行 `test_mineru_artifact_validator`、`test_image_normalization_pipeline`、`test_document_job_failure_diagnostic`、`test_bbox_coordinate_space`、`test_document_ir_mineru_converter_layout`、`test_image_group_rendering`，记录失败集合。
2. 测试先行：验证器分类、转换回退成功/失败、端到端（design 第 4 节）。
3. 验证器：可回退分类、待回退标记、`resolve_image_fallback`。
4. converter：页面几何后的回退裁切与资产生成。
5. 登记与白名单：`execution` metadata、`evidence.py`。
6. 本地真实样本目视（`tests/tmp/`，不入库）。
7. 规格：IMAGE-001、INPUT-002 补充回退规则。

## 2. 验证

- 定向测试与基线对比；不跑全仓回归与前端。

## 3. 回滚点

回退提交即恢复“图片错误硬失败”；无数据迁移。

## 4. 实施结果与验证（2026-11-02 北京时间）

- 基点：PR #18、#19 合并后的 `main` `a61f4550`。
- 验证器：`_validate_asset(defer_fatal=True)` 推迟可回退错误；`complete_validation` 标记 `_mineru_image_fallback`；`resolve_image_fallback` 统一结算（成功降级为 warning 并追加 `image_asset_pdf_fallback`，失败恢复中止）。路径安全与超限不推迟。
- converter：页面几何后 `_crop_image_fallbacks` 逐块裁切再统一结算；源 PDF 加载器缓存后与表格占位共用；新回退只接受已确认的归一化坐标页（实施中发现旧推导页尺寸巧合等于 PDF 页时会把归一化值误当 PDF 点，故收紧）。
- 登记：`origin=pdf_region_crop` 与 `pdf_fallback` metadata；报告白名单加 `image_asset_pdf_fallback`。
- 测试：新增 `tests/test_image_pdf_fallback.py` 7 例通过（含“已有其他中止错误时待回退图片恢复为中止”）；对比集 146 例（基线 139 + 7），1 失败 27 错误与基线一致；P0a 诊断测试（无裁切器时回退失败）结果不变。
- 审阅修正：`complete_validation` 因其他错误中止时，先把待回退图片恢复为中止错误再抛出，保证报告与回退功能引入前一致。
- 真实样本：OPA228_P1 删除图表图片后经真实 Poppler 回退，裁切与源图表一致（`tests/tmp/p04/fallback_chart.png`，未入库）。
- 未做：Word 目视、全仓回归；扫描/旋转页回退保持失败。
