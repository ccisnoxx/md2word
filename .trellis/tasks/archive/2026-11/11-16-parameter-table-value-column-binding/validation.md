# 参数表数值列归属验证

## 三包离线回放

以 `1d6d5321` 加本任务工作树改动，通过 [固定输入与回放入口](research/samples.md) 的三份 ZIP 和提交源 PDF 指纹检查。正式 direct adapter 生成候选 DOCX，再用 `python-docx` 读取实际表格，独立核对单元格值、物理列和合并。

| 回放 | 质量证据 | 实际 Word |
| --- | --- | --- |
| SN74AC244 首轮 v4 | 5.2 表准确报出 6 项。两个器件组各有 2.1、3.15、3.85 V 跨 MIN–MAX。 | 原生 19×8 目标表，保留 27 处输入合并及对应数值。 |
| SN74AC244 重传 v4 | 整包无本规则命中。 | 原生 19×8 目标表，保留独立标注中的 21 处合法合并。两组对应数值均在 MIN，MAX 单元格独立且为空。 |
| OPA228 第 7 页 | 6.7 表报告 23 个疑似项。两处验收值分别为源行 3 的 `±5 µV` 跨 MIN–TYP，以及源行 4 的 `±100 µV` 跨 MIN–MAX。 | 保留原生 32×8 目标表、77 处输入合并和两处指定值。独立 PDF 标注分别确认原件上的 TYP、MAX。 |

[机器观测与产物指纹](../../../../../tests/tmp/parameter-table-value-columns.PMZ20U/artifacts/observations.json) · [SN74AC244 首轮 DOCX](../../../../../tests/tmp/parameter-table-value-columns.PMZ20U/artifacts/sn74-v4-ambiguous.docx) · [SN74AC244 重传 DOCX](../../../../../tests/tmp/parameter-table-value-columns.PMZ20U/artifacts/sn74-v4-matching.docx) · [OPA228 DOCX](../../../../../tests/tmp/parameter-table-value-columns.PMZ20U/artifacts/opa228-p7-location.docx)

三份包以外部输入身份回放。当前结果是离线结构与报告定位证据，正式部署、商业 Word 视觉签字和单元格几何归属未纳入本轮验证。

## 规则与交付合同

- `.venv/bin/python -m unittest tests.test_parameter_table_value_column_binding tests.test_table_header_review tests.test_document_ir_mineru_converter_layout.MinerUToDocumentIRLayoutTests.test_compound_table_continuation_reconciles_source_grid_plan_and_word`，13 项通过，含重复表头前后数据、同宽已核验续片和未关联片段、绑定单位、合法表头和原生跨列、历史报告可重读与按原版本重算。
- `.venv/bin/python -m unittest tests.test_document_job_list_publish_light_check tests.test_document_job_delivery_state_api.DocumentJobDeliveryStateApiTests.test_legacy_translation_qa_cannot_approve_unacknowledged_table_semantics tests.test_document_job_delivery_state_api.DocumentJobDeliveryStateApiTests.test_operator_approval_updates_owner_and_safe_audit_while_remaining_draft`，9 项通过。File、SQLite 用例通过实际 HTTP 断言内部下载和定位字段，分别覆盖无确认、错误摘要、旧入口、报告丢失、有效确认及单次正式发布。提交前报告到期的用例断言拒绝且无发布记录。
- `DocumentJobDeliveryStateTests.test_result_identity_invalidation_preserves_first_binding_quality_and_protects_published` 和 `test_review_cas_compares_none_result_generation_and_latest_block_delete` 均通过，覆盖换件、代次不符、已有发布保护以及 File、SQLite、模拟 MySQL 的锁内提交路径。
- 用改动前留存的 SN74AC244 首轮 DOCX、IR 和渲染元数据认证 `table-validator/v1`，8 张表逐值匹配。历史表格报告指纹为 `33f3d334ae4bec021417ad3b384ed0c56bf32e5630481d7ed65ba8386c702ac7`。
- `.venv/bin/python scripts/ops/export_openapi.py --check` 通过，180 条路径和 395 个 schema。应用冷启动与 `git diff --check` 通过。
- 扩大验证发现既有 `test_review_cas_rejects_retry_replacement_blocker_and_none_result_races` 的 mock 读取旧的 `expected_result_file_id`，触发 `KeyError`。已对照 `HEAD` 的既有调用只传 `submission`。保留该测试，新增用例直接覆盖本次审核和发布提交竞争。

独立复核检查了发布锁内的主件、报告快照、审核绑定和有效期。复现并复验两处检测漏报。后段同列重复表头保留首段数据检查，只有经核验且同宽的无表头续片继承上一片列义。异表号同宽、同表号异宽反例均未产生继承结果。
