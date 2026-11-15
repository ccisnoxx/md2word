# 实施与验证计划

## 实施顺序

1. **确认评审版本与基线。** 在批准本三件套后确认 `main@ea16ebdd` 及工作区状态。若基线推进，先对照翻译执行、审核、表格和公式 owner 的实际差异，影响本设计时先更新评审。读取相关 Specs，核对实测样本的现有路径、指纹和同源表头校核。Trellis 子任务经评审批准后启动。
2. **翻译范围及回填。** 从 TR-401 取稳定 ID 和原位回填思路。补充源 IR 范围绑定和派生题注索引，使当前 Worker 各恢复分支与本地正式入口使用同一抽取规则。沿现有结果结构保存注释 ID，验证新范围的缺项和旧范围原样恢复。让表格上下文区分表级注释与 HTML 单元格。
3. **审核、渲染归属和源证据。** 接通审核原译对照、批次和证据摘要，补调试段。核对 scoped IR 序列化往返、表转图校验、题注别名、同译文独立注释及续表代表、源账本与正式渲染认证。若无需 UI 代码，由现有通用渲染消费字段；需要显式分支时定向检查受影响的审核视图。
4. **脚注上标。** 更新共享公式渲染器。覆盖新上标、原 OMML、畸形式降级、历史降级重放和新上标证据篡改。证明原式仍走现有翻译保护。
5. **合并验证并核对交付。** 运行下列定向检查和 RS2G04 同源复验。按实际改变的抽取范围、证据及公式合同更新 Specs。检查 diff 和工作树，确认相关的 Python 注释、docstring 和开发可见文本符合项目语言约定。规划、实现、测试证据及人工签字分别记录。

实施和复核时直接阅读 [Word 生成规则](../../spec/backend/word-generation-rules.md) 的 IR-005、TABLE-002、TABLE-004、MATH-002、MATH-003、RND-502 及 COL-003 的注释约束。该文件超出上下文注入文件大小限制，相关章节以工作区原文为准。

## 验证矩阵

新增回归落在已有对应测试模块，优先用方法级 selector。下表的模块是实施后选择定向检查的入口。

| 验收 | 最小验证 | 通过条件 |
| --- | --- | --- |
| AC1 | `.venv/bin/python -m unittest tests.test_document_ir_translation`；使用带注释、空位、派生别名及独立同文的样本 | ID、顺序和原下标稳定，真实 `.text`/列表/HTML ID 保持，注释数组精确回填，源 IR 不变。 |
| AC2 | `tests.test_translation_integrity_execution`、`tests.test_translation_batch_workflow`、`tests.test_formula_translation_boundary` 的相关用例 | 既有旧根树和有效旧结果可继续汇总，旧 source 跨 retry 保持旧范围。新范围经过建批、领取、拆分或重试、重读、fan-in。测试缺注释、错归属、范围不一致，以及改写脚注中的数字、单位和公式。失败零成功目标件。 |
| AC3 | `tests.test_translation_table_context`、`tests.test_document_job_review_blocks_api`、`tests.test_document_job_review_hints`、`tests.test_formal_mineru_render_evidence` 的相关用例 | 表级与单元格上下文各自绑定；默认权限和调试脱敏保持。新审核能对照题注和脚注并核对未裁剪的译文摘要。历史审核保有旧证据。覆盖普通图、表转图、别名、续表及独立同译文位置。 |
| AC4 | `tests.test_document_job_execution_stages` 的四语言入口与 direct 夹具；必要时复用 `tests.test_conversion_sandbox_dev_tools` 的本地链路 | 正式应用阶段逐方向发出注释 item，应用 Codec 并生成可核验目标。direct 原文、归属及零翻译调用断言成立。 |
| AC5 | `tests.test_formula_rendering`、`tests.test_formula_rendering_compatibility` 的相关用例 | 检查 `document.xml` 原位置、文字及 `w:vertAlign`。验证一般数学仍有 `m:oMath`、畸形输入仍有 fallback、历史冻结报告可认证。上标去除、文字篡改或错放位置均被证据校验拒绝。 |
| AC6 | 下述 RS2G04 同源复验 | 源说明、稳定翻译 ID、译后 IR、审核及 DOCX 的原译和标记一一对账。人工未完成时单列未签字状态。 |

## RS2G04 第 6 页实物复验

- 复用 [扩展样本清单](../11-11-datasheet-quality-baseline-contracts/extended-sample-manifest.json) 中 `gsx-rs2g04-esd-page` 的 PDF、MinerU ZIP 和 content list。规划时本地 PDF 与 ZIP 已通过 SHA-256 对账。本轮实施时从清单复核输入并记录实际 commit、模式、Profile、模板和输出指纹。
- 先用同一 MinerU 包从源 IR 到正式 DOCX 做隔离 direct 对照和受控翻译回放，再按样本既有授权用隔离环境和现有服务配置做英译中实译。现有代码入口为 `scripts.dev.formal_mineru_conversion` 及已有隔离应用入口。用当前修复产生新结果，并保留原预审副本作为对照。服务、凭据或样本不可用时记录对应阶段缺测，保留已有本地证据。
- 核对 `block_0003.footnotes.0000` 至 `.0004`、`block_0005.captions.0000` 和 `block_0005.footnotes.0000` 至 `.0001`，先核身份再对照原 PDF 的文本和技术含义。检查 8.2 说明只在原归属展示一次。检查 `block_0003_context_0001.text` 末端标记的 `w:r`。目标仅允许有依据保留的专名、标准号等原文。
- 按原清单分别记录 ESD 表原始输入与同源表头校核稿。对通过同源校核的输入核对 4×4 网格、首行表头、两处合并和原 3 个标注技术 Token。原始输入的已知表头差异仍在原质量任务跟踪。检查审核视图中的单元、批次证据以及输出报告。可用时打开 Word 审阅标记和说明，OOXML 与语义、视觉签字分别记载。
- 私有样本与 DOCX 留在 `tests/tmp/` 或原批准目录。任务记录保存指纹、位置、精简观测和未验项。四方向的确定性 Provider 回归与 RS2G04 单个实译样本按各自证据报告。

## 风险与关闭条件

优先复核两个联动边界。旧根树的期望范围须在入口、恢复和审核一致。新题注的源身份须在布局计划、Word 写入和持久化认证一致。若定向证据显示影响扩大，先定位具体受影响合同，再调整验证范围。按已批准的样本和隔离权限复验。人工审阅以实际生成的 Word 稿和 SHA-256 为准。

当前状态为 `planning`。本次提交给用户的是三件套及 Trellis 上下文索引，代码实施等候本版评审。
