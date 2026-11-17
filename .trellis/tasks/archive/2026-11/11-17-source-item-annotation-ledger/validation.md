# 来源账本实施与验证记录

任务已完成本地实施及定向验证，工作提交为 `29592706baa1e6ed60431b9ce1d838c516f30be2`。本地提交和归档复用下列验证结果。

## 已验证行为

- 列表 v2 校验真实源顺序和逐项摘要，包含空位、等量替换、重复文本位置与 legacy 一对多。旧 v1 和无账本 IR 保留历史读取路径。
- 题注和脚注按位置保留。已知同源别名只输出一次，独立同文项在实际 DOCX 中仍各占一段。正文附注和表格附注均有持久化反例。
- 已验证的翻译结果按稳定 ID 原位登记目标摘要。Worker 在登记译后 IR 前核对已认证译文、真实字段和来源映射。测试覆盖单独漏项的恢复，以及目标文字与摘要同时漂移、派生题注改绑时的拒绝。
- 只有可信数据恢复并复核通过后才记录 `source_ir_integrity:ledger_recovered`。可确定的损坏在 `source_ir_integrity` 下失败。参数列 `row_ambiguous` 继续以 warning 交付。
- 显式脚注字符串槽各保留其来源位置。同组富文本 runs 仍按已有连续规则合并。正文只从题注派生时，以同一题注位置渲染并保留原正文或标题样式。

## 实际命令与结果

| 命令 | 结果 |
| --- | --- |
| `.venv/bin/python -m unittest tests.test_document_ir_layout_contract tests.test_mineru_artifact_validator.MinerUArtifactValidatorTests.test_v2_list_ledger_accounts_for_empty_items tests.test_mineru_artifact_validator.MinerUArtifactValidatorTests.test_list_consumer_dropping_non_empty_item_fails_closed tests.test_mineru_artifact_validator.MinerUArtifactValidatorTests.test_legacy_list_dict_projects_in_order_to_multiple_outputs tests.test_mineru_artifact_validator.MinerUArtifactValidatorTests.test_list_consumer_dropping_non_empty_item_recovers_from_frozen_source` | 15 项通过 |
| `.venv/bin/python -m unittest tests.test_document_ir_mineru_converter_layout tests.test_formal_mineru_render_evidence` | 42 项通过 |
| `.venv/bin/python -m unittest tests.test_document_ir_translation tests.test_translation_integrity_execution` | 40 项通过 |
| `.venv/bin/python -m unittest tests.test_table_value_pdf_binding_delivery` | 3 项通过 |
| `.venv/bin/python -m unittest tests.test_document_ir_word_renderer_layout tests.test_preview_page_mapping` | 补充 69 项通过，覆盖正文及图表附注渲染、历史页映射和账本损坏冲突 |
| `.venv/bin/python -m unittest tests.test_page_degradation tests.test_render_page_degradation tests.test_document_job_review_blocks_api` | 首轮 29 项有 3 项失败。其中 1 项是旧注释夹具仍携带新账本，已修正夹具并定向复跑。其余 2 项在干净 HEAD 复现，保留原状。 |
| `.venv/bin/python -m unittest tests.test_document_job_review_blocks_api` | 修正旧夹具后 4 项通过 |
| `git diff --check` 及用 `.venv/bin/python` 对本任务 Python 文件执行 `ast.parse` | 通过 |

两项在干净 HEAD 上复现的降级失败及原命令见[独立基线记录](baseline-failures.md)。

## 未验证范围

本地测试走现有测试运行时、合成 MinerU 包、测试翻译 Provider、实际 DOCX 及持久化重读。未验证线上 MinerU 和真实翻译 Provider、生产 MySQL/队列/对象存储、实际 Word/WPS 客户端排版，以及完整发布流程或全仓测试。两项基线失败场景仍无通过结果。
