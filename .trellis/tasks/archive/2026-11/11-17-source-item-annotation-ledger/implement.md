# 实施计划

## 开始条件

- 用户审阅 PRD、设计和本计划后明确授权实施。再运行 `task.py start`。当前为规划阶段。
- 核对当前分支与工作区，保留已有的 direct 克隆语言改动及任务目录。读取三份规划文档和清单中的相关规范。Word 生成规则超过自动注入上限，实施与复核均从磁盘定向读取 INPUT-004、IR-004、IR-005、TEXT-004、FIELD-002 及适用的持久化重读规则。再核对翻译完整性和 Worker 的发布边界。

## 实施顺序

1. **账本合同与列表冻结（AC1、AC2、AC5）。** 在 DocumentIR 完整性边界建立 v2 解码、摘要和对账。由 `mineru_content.py` 的权威列表分支提供源索引、冻结输出及明确的一对多映射。`mineru_converter.py` 从冻结投影建立 v2 账本与列表字段，核对闭合范围和真实内容。对旧件保持 v1 计数结果和无账本分支，记录可安全恢复与必须失败的不同结果。
2. **注释位置与 direct 渲染（AC3、AC5）。** 在 `caption_reconciler.py` 和脚注提取入口保留源位置、已证实的拼接与派生关系。转换器写入受控注释范围与账本，对账前不按文本去重。以已验证注释位置驱动渲染计划、Word 写入、证据认证及占位表的别名选择。主列表与注释范围的裁剪只跟随现有已认证的降级块移除。用单个同文脚注用例贯穿 MinerU、IR、Word 和持久化重读。
3. **翻译回填与发布（AC4、AC5）。** 在 `DocumentIRTranslationService` 共享账本目标核验与回填，接入同步翻译和 `translation_execution/artifacts.py` 的 fan-in。用真实已核验 replacement 固定目标摘要，回填后重算并验证未改源事实。确定性缺项和错误映射在登记译后 IR、发布证据和切任务指针前收口。旧批次身份、存储与失败语义沿用原合同。
4. **持久化重读及失败证据（AC5、AC6）。** 在正式 IR/渲染证据入口调用共享验证，保证新件恢复时按创建合同复算。增加受控的完整性错误与恢复 warning 投影。表格参数列和已有表格证据走原路径。完成验证后，把实际账本和错误合同写回 Word 生成规则及翻译完整性规范。

## 定向验证

在上述链路接通后统一执行。优先在已有测试模块增加覆盖缺口的用例。

| 命令 | 范围 |
| --- | --- |
| `.venv/bin/python -m unittest tests.test_document_ir_layout_contract tests.test_mineru_artifact_validator.MinerUArtifactValidatorTests.test_v2_list_ledger_accounts_for_empty_items tests.test_mineru_artifact_validator.MinerUArtifactValidatorTests.test_list_consumer_dropping_non_empty_item_fails_closed` | 替换、删除、换位、同文位置、空项、legacy 展开、恢复与失败，及旧 v1 / 无账本证据重读。 |
| `.venv/bin/python -m unittest tests.test_document_ir_mineru_converter_layout tests.test_formal_mineru_render_evidence` | 注释源位置、合法题注修复及表前条件、Word 同文保留、持久化主件复算与拒绝。增加新件连数组一起丢账本的拒绝用例，确认历史成功输出的证据合同。 |
| `.venv/bin/python -m unittest tests.test_document_ir_translation tests.test_translation_integrity_execution` | 同步翻译与正式 fan-in。覆盖翻译内容改变、同文脚注、唯一映射、缺项、错绑、回填后内容损坏以及未写成功目标件。 |
| `.venv/bin/python -m unittest tests.test_table_value_pdf_binding_delivery` | 参数列 `row_ambiguous` 的 warning 及交付回归。 |
| `git diff --check` | 变更边界。结合工作区状态核对仅涉及本任务的文件、中文触及范围和证据脱敏。 |

实施时按新增用例的实际位置补齐命令。现有缺项回归应覆盖无可信恢复值时失败，另用有可信冻结值的用例证明恢复。选定的历史证据应来自观察到的 v1 和无账本行为，包括字段省略和持久化重算，不能只验证 Pydantic 能读取。按实际运行记录测试结果与未验证范围。本计划以本地定向验证为准。

## 复核与回退点

- 独立复核重点覆盖版本分派、整账本被移除、账本与已核验回填结果绑定、回填失败后无部分成功发布、同文位置和已证实的别名之间的边界。
- 写入、译后和读取支持应作为一个兼容单元交付。若转换规则出现问题，须先确保已存在的 v2 产物继续能读，再决定是否回退新写；原产物和绑定证据保留。校验或恢复无法证明内容时让该次产物失败，既有成功件沿现有结果切换规则保留。
