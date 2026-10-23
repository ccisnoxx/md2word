# RND-502 实施计划

版本：1；2026-10-23；只规划，不执行实现、不 start、不提交或 push。

## 1. 实施前门

- [ ] 人工批准本版本 prd/design/implement；只授权 RND-502 的当前范围。
- [ ] 重查 BAS-001=done、当前 HEAD/dirty 和 RND-501 状态；保留全部既存文件和暂存区。建议分支 `md2word/RND-502`，本轮未创建/切换。
- [ ] 阅读任务三件套、research 和 Spec（Word 的 MATH-001/002/003、TEXT-003/004、TABLE-001/002、QUALITY-001/003/004 及冲突矩阵；数据库结果登记、错误映射和 direct 资源合同）。
- [ ] 若 RND-501 已集成，先对照其结果接口/context owner 修订最小接线；不为当前任务集成其他 backlog 业务。
- [ ] 准确激活当前子任务并同步 manifest in_progress（仅在后续实现授权会话执行）。

## 2. 有序实施清单

1. [ ] 将现有有限公式 parser 收敛到共享 `docx_rules/formula.py`；定义片段及解析/降级结果、稳定 reason，先补未知命令、作用域、tag、text 空格和符号保真测试。只修当前数学子集，不扩展全功能引擎。
2. [ ] 接入 HTML/普通文本分段：识别数学边界再解析；原位置输出 OMML/semantic run/带提示的 literal 原式。去掉分数触发整段 OMML 和公式前术语替换，普通正文样式/符号规则只执行一次。
3. [ ] 保留 converter semantic inline/annotation 的原式和边界；不改 schema、ID、layout、table spans 或翻译 codec。加入源→IR→fake translation→DOCX 的完整链路断言。
4. [ ] 在单次 RenderContext 内记录公式出现及锚点；提供兼容 bytes 的 result 接口，在线、本地消费同一 DOCX/报告。
5. [ ] evidence/analyzer 对账真实 OOXML，登记受控降级，保留未登记残留检查；私有报告和事件安全摘要分离。新增 evidence 明确版本，历史重放无新字段仍走旧比较。
6. [ ] 将公式报告随候选一起登记，在共用结果状态 owner 的锁内完成阶段合并选中 receipt 的摘要；不把 warning 放进致命 flags，不提升 pending/blocked，不覆盖其他摘要。
7. [ ] 验证 legacy 恢复、新报告损坏、同代竞争和新代重试；确认一个主件、同一 DOCX/IR/report/hash 和 expiry/owner/审计安全均保持。
8. [ ] 完成下述集中验证、文档/Spec 和中文开发者文本检查；独立复核数据/并发/权限相关 diff，修复确认问题后只复跑相关检查。
9. [ ] 最终检查 allowlist、diff 和 status；实现结束只到 manifest review / Trellis in_progress，等待人工验收与 commit plan 确认，不 done/archive/push。

## 3. 计划修改文件

| 文件 | 变化目的 |
|---|---|
| `app/conversion/docx_rules/formula.py`（新） | 迁移有限 parser、数学分段和明确 outcome，唯一公式入口 |
| `app/services/renderer/text_renderer.py` | 混排、semantic run、受控原文降级、caption 路径接通 |
| `app/services/renderer/table_renderer.py` | cell/annotation 接通与公式前术语改写移除；表格结构算法不变 |
| `app/services/renderer/semantic_text.py`、`app/conversion/docx_rules/text_semantics.py` | 保持兼容导出/普通文本规则；仅必要的数学边界与保真映射调整 |
| `app/conversion/docx_rules/mineru_content.py`、`app/services/document_ir/mineru_converter.py` | semantic inline/annotation 源公式保留，按确认证据最小调整 |
| `app/services/renderer/word_renderer.py` | 单次上下文、公式锚点、render result 和 bytes 兼容入口 |
| `app/services/renderer/docx_quality.py`、`app/services/renderer/evidence.py` | 版本化报告、真实 XML 对账、受控/静默残留区分、安全摘要 |
| `app/domains/document_jobs/execution.py` | 结果消费、候选/legacy 重放校验、事件安全投影 |
| `app/domains/document_jobs/result_state.py` | 同 job 锁内从选定 receipt 合并公式质量摘要，不重写状态机 |
| `scripts/dev/formal_mineru_conversion.py` | 同一次正式 renderer 结果/诊断进入本地侧车，不复制渲染规则 |
| `tests/test_formula_rendering.py`（新） | parser、混排、失败原因与内容保真定向测试 |
| `tests/test_document_ir_word_renderer_layout.py`、`tests/test_document_ir_mineru_converter_layout.py` | 正式链路全入口/内容/OOXML 对照 |
| `tests/test_document_job_execution_stages.py`、`tests/test_document_job_result_persistence.py` | 候选/receipt/legacy/重放/三 adapter 状态投影 |
| `tests/test_document_job_delivery_state.py`、`tests/test_document_job_download_availability_api.py` | 质量摘要单调、下载/批准/权限合同 |
| `tests/test_conversion_sandbox_dev_tools.py`、`tests/test_golden_sample_manifest.py` | 本地报告接线、残留分析与既有证据兼容 |
| 现有 component fixture/manifest（确有必要时） | 最小、允许提交的公式结构样本；不用专有 PDF 全文 |
| `docs/design/docx-rendering-template-design.md`、`.trellis/spec/backend/word-generation-rules.md` | 同步已实现公式子集、受控原式、证据及门禁，不提前声称通过 |
| 当前任务文件、RND-502 manifest | 实际验收证据及状态，其他任务状态不变 |

不计划改 router、OpenAPI schema、数据库 adapter/schema/migration、前端、资源 seed、Provider/翻译 codec、发布 API。若需要扩大这些写范围，先更新规划并评审。

## 4. 定向测试矩阵

| 覆盖 | 必须断言 | 对应 AC |
|---|---|---|
| 解析正常 | frac/root/scripts/Greek/styles/overline/boxed 的具体节点与可见值，不只检查零残留 | AC1/2 |
| 已确认反例 | 合法简单 tag 保留主体 OMML 和可见编号，复杂/畸形 tag 才原文降级；`x^2+3` 作用域；text 空格；vee 语义 | AC2 |
| 所有内容入口 | heading/paragraph/list/block/table cell/caption/context/note，重复公式次数，HTML 样式、顺序及正文不进入 OMML | AC1/3/6 |
| 降级负例 | unknown、malformed、matrix/cases、嵌套 wrapper；原式逐字/特殊字符保留、稳定 reason、可见提示和 warning；空源不伪成功 | AC4/5 |
| 误判边界 | UNC/路径、金额、escaped dollar、普通 underscore、XML/HTML 字符、长混排；普通符号规则仍有效 | AC6 |
| 翻译/来源 | 合成 MinerU 包包含非空表格和公式，fake Provider 往返/最终 IR；direct 翻译资源/Provider 零调用 | AC7/10 |
| 诊断和隐私 | IR hash/位置与真实 XML 锚点对账，漏式/错式拒绝；事件无原式、私有条目、路径；未登记残留不被抑制 | AC5 |
| 质量/权限 | fallback 主件可下载；pending/blocked 不提升、passed→warning、其他摘要键保留，unreviewed/blocked 不批准不发布，owner/admin 边界 | AC8 |
| 恢复/并发 | renderer 双调用无串扰；同代选中报告不被迟到候选替换；新代旧摘要清空；legacy 原 evidence 恢复，新版本坏报告显式失败 | AC9 |

实施后先运行：

```bash
.venv/bin/python -m unittest tests.test_formula_rendering
.venv/bin/python -m unittest tests.test_document_ir_word_renderer_layout tests.test_document_ir_mineru_converter_layout tests.test_golden_sample_manifest
.venv/bin/python -m unittest tests.test_document_job_execution_stages tests.test_document_job_result_persistence tests.test_document_job_delivery_state tests.test_document_job_download_availability_api tests.test_conversion_sandbox_dev_tools
.venv/bin/python -m unittest tests.test_protected_tokens tests.test_document_ir_translation tests.test_translation_integrity tests.test_translation_batch_failure_semantics
```

测试 selector 以实施时实际文件为准；当前没有 `tests.test_formula_rendering`，不得将未执行的新测试写成通过。fake 翻译只证明技术保真，不代表四语种翻译质量已验收。三 adapter 使用现有 fake/unit，真实 MySQL 并发不由本任务单测证明。

## 5. 回归门禁

```bash
git diff --check
.venv/bin/python scripts/ops/check_release.py
.venv/bin/python scripts/dev/run_component_pdf_regression.py
.venv/bin/python scripts/dev/run_local_mineru_quality_matrix.py --mode direct --sample-set phase2-core
.venv/bin/python scripts/ops/run_golden_sample_regression.py
python3 .trellis/scripts/task.py validate .trellis/tasks/10-23-rnd-502-formula-omml-fallback
```

- release 包含现有 OpenAPI current 检查；无新 API，快照预期零合同变化。无需无关 frontend build/smoke。
- component 已知最小 OPA228 fixture 无公式/表格，不能只跑该 runner 声称公式已验证；必须另外运行上述合成 MinerU 全链路公式+非空表格用例。若 fixture 可授权，增加最小离线公式样本并在 manifest 记录预期，不提交全文。
- 本地 matrix/Golden 先检查实际脚本参数、样本库存和授权；有缺失/环境阻断就保存 preflight/日志及原因，不编造成功，不为消 flag 换旧 runtime。
- Word 质量：按 MATH/TEXT/TABLE/FIELD/STYLE 冲突矩阵检查公式编号、混排、表格换行、上下标、字体和版面。公司实际 Microsoft Word 人工签字记录版本、样本、当前代码和 DOCX SHA-256；WPS/LibreOffice 只作补充。线上 Golden、Word/真实环境未跑时保持待验，不替代正式门禁。
- 不为本轮规划运行上述全套实现门禁；目前仅 9 项现有公式基线与合成探针，详 planning-validation。

## 6. 文档、Spec、回滚点和完成定义

- [ ] 更新 MATH-002/003 和 QUALITY-001/004：明确受控降级不是静默残留，warning 不等于 fatal，不把所有 `quality_flags` 升为 fatal；保持 source payload missing 和真内容丢失的失败关闭。
- [ ] 更新公式支持表、错误 reason、私有/公开证据边界和 legacy 版本读法；检查 touched 注释/docstring/异常/开发者输出，默认中文，协议字段保持原文。
- [ ] 回滚点 A：共享数学入口/混排实现可撤回，旧 renderer 完整保留行为基线；B：报告与接线可撤回且历史字段保留；C：只从既有 receipt 派生摘要，不删除候选/产物/审计。回滚不得变截图默认或改已发布件。
- [ ] PRD AC1–AC11 逐条有测试/人工证据；定向、样本和发布门的失败已诊断，未运行项和风险准确列明。
- [ ] 对结果/权限/并发的实际 diff 做独立只读复核；无确认残留后 inspect final diff/status，排除原有 staged 删除、其他任务、日志及 manifest 非 RND-502 条目。
- [ ] 所有 task/context/文档可校验，停人工验收门；仅用户验收后按后续明确 commit plan 决定提交/归档，不自动 push。
