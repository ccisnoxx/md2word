---
doc_type: gap-analysis
status: current-vs-target
baseline_commit: e51e6ccd129f59d1b372dfc6907def1fd6bb5cd8
last_reviewed: 2026-10-03
doc_status: historical
last_verified_commit: null
owner: null
verification_scope: >-
  保留 e51e6ccd 基线与 2026-11-06 局部判断；2026-11-10 只静态复核扩展阶段、table context 及含未提交 translation_execution.py 的调用位置，其他旧判断未全面复核，未做运行或整项 AC 验收。 依据与内容身份：.trellis/tasks/11-10-documentation-evidence-governance/research/b1-implementation.md。
---

# 当前实现与目标差距

## 1. 使用说明

本文件是 Codex 开始任务前的调查清单。每个任务必须先验证当前代码是否已经变化，不得机械按本文重复实现。

> **历史调查范围**：表格中的“当前”“已有”“缺失”和第 10 节优先级均按各自注明的调查基线理解。除明确列出的局部复核外，其余条目仍为 `e51e6ccd129f59d1b372dfc6907def1fd6bb5cd8` / 2026-10-03 的历史判断，未作全面复核；保留页首历史基线与 `last_reviewed`，不据此认定其他缺口仍存在。

> **局部复核（2026-11-06，源码基线 `79f20cef`）**：当次仅更新第 5 节的 ProtectedTokenCodec、数字/单位/公式后验校验，以及第 10 节对应优先级描述。

> **局部静态复核（2026-11-10，含未提交工作区）**：本次仅补第 5 节 table context、第 8 节扩展阶段，以及翻译调用位置。核验源文件与 SHA-256 见 [B1 记录](../../.trellis/tasks/11-10-documentation-evidence-governance/research/b1-implementation.md)；没有验证环境启用、真实翻译、整项 AC、人工接受或部署，不推进 Manifest 状态。

状态：

- **已有**：目标基本具备，主要补测试/文档；
- **部分**：已有基础，需要收口；
- **缺失**：目标合同尚未形成；
- **不确定**：必须在任务 research 中确认。

## 2. 产品模式

| 能力 | 当前 | 目标 | 状态 |
|---|---|---|---|
| direct/en2zh/ru2zh/zh2en/zh2ru | `modes.py` 已定义 | 保持 | 已有 |
| zh2zh Prompt | 未定义，别名映射 direct | 不新增 | 已有 |
| 一任务一 DOCX | 当前 `result_file_id` 单值 | 明确为不变量 | 已有/补文档测试 |
| 创建页按模式显示资源 | 已区分翻译资源 | direct 文案改为原文转换 | 部分 |

## 3. MinerU 与 DocumentIR

| 能力 | 当前 | 目标 | 状态 |
|---|---|---|---|
| nested/flat content list | converter 已支持 | 保持 | 已有 |
| DocumentIR v2 | 已有 pages/layout/caption/footnote | 兼容扩展 | 已有 |
| source→IR integrity | `integrity.py` fail-closed | 扩展 table/image/page evidence | 部分 |
| caption 重新绑定 | 连续编号图片已有严格修复 | 扩展不确定 QA | 部分 |
| 空表续页处理 | 已有近期修复 | 固化 ZK7044 回归 | 部分 |
| 运行页眉页脚误分类 | role 基于 source type | 需要跨页重复归一 | 缺失/部分 |
| 跨页段落合并 | 未发现明确统一服务 | source spans + 合并 | 缺失 |
| 逻辑跨页表格 | 有 placeholder continuation/height | 需要 LogicalTableGroup | 部分 |

## 4. 表格

| 能力 | 当前 | 目标 | 状态 |
|---|---|---|---|
| HTML parser | `SimpleTableHTMLParser` | CanonicalTableGrid | 部分 |
| rowspan/colspan Word 合并 | 常规表已有 | 保持并增强 | 已有 |
| 大表 | 超阈值展开 span | 保留合并语义 | **差距** |
| 表格 QA | 主要是 DOCX 数量/形状 | 结构、粘连、跨页、blocked | 缺失 |
| reference image | MinerU block 有路径但 IR asset 主要用于 image/chart | 一等 QA Artifact | 缺失/部分 |
| HTML 缺失 | integrity 可阻断，近期有 placeholder 修复 | 内部占位+blocked+下载策略 | 部分 |
| 表格翻译 | HTML text nodes | CellRun + context | 部分 |

## 5. 翻译

| 能力 | 当前 | 目标 | 状态 |
|---|---|---|---|
| 四个 Prompt | 已有 | 保持 | 已有 |
| ID 结构验证 | 已有 | 保持 | 已有 |
| 批次/重试/拆分 | 已有 | 保持 | 已有 |
| 术语匹配/trace | 已有 | 保持并校验输出 | 部分 |
| caption/footnote 翻译 | extract 入口显式包含 text/list/table nodes，需确认 annotation | 全部 annotation | 不确定/可能缺失 |
| ProtectedTokenCodec | [纯内存 Codec](../../app/domains/translation/protected_tokens.py) 已由 DocumentIRTranslationService 经 Validator 接入正式翻译与 Worker | 复用既有检测、占位和恢复合同 | 已有（有限语法） |
| 数字/单位/公式后验校验 | [TranslationIntegrityValidator](../../app/domains/translation/integrity.py) 已统一检查 ID、占位符与恢复后逐 item 技术 inventory | 保持整批失败关闭；语义与实译质量另行验收 | 已有（有限语法） |
| table context | `TableContextBuilder` 已通过 `table_contexts` 接入 Provider 请求，`translation_table_context_enabled` 默认关闭（2026-11-10 静态复核） | 启用与语义质量须独立验收 | 已有接入，未验证运行效果 |
| 四方向正式回归 | 当前 P1 manifest 主要 en2zh | 每方向独立 | 缺失 |

局部复核依据：[DocumentIRTranslationService](../../app/domains/translation/document_ir_translator.py) 的 `build_provider_request()` 经共享准备逻辑调用 `validator.prepare()`，将编码 items 交给 Provider；同步 `translate()` 在 `validator.validate()` 成功后消费恢复结果，全部批次通过后才回填。2026-11-10 工作区中，[Document Jobs execution](../../app/domains/document_jobs/execution.py) 组合的[翻译执行协作者](../../app/domains/document_jobs/translation_execution.py)复用同一准备与校验入口，并在 fan-in 时调用 `validate_persisted()` 复核持久化结果及证据；该提取尚未提交，因此核验 SHA 为 null。具体合同见 [Codec Spec](../../.trellis/spec/backend/protected-token-codec.md) 和 [翻译完整性 Spec](../../.trellis/spec/backend/translation-integrity-validator.md)。这些实现只覆盖已支持的有限技术语法及逐项多重集一致性，不保证任意型号/公式、参数语义关联或目标语言正确；文字复核没有验证真实 Provider、四方向正式实译或线上/Word 验收。

表格上下文的静态依据为 [TableContextBuilder](../../app/domains/translation/table_context.py)、上述翻译服务、[配置默认值](../../app/core/config.py)和[应用接线](../../app/main.py)。上下文是独立的请求输入，不能仅从 `TranslationTextItem` 的 id/text 字段推断缺失；当前 Manifest 的 TR-404 仍需按 AC 与验收记录另行对账。

## 6. Renderer 与模板

| 能力 | 当前 | 目标 | 状态 |
|---|---|---|---|
| Renderer 模块化 | layout/text/table/image/quality 已拆 | 保持 | 已有 |
| Word 原生 heading/list/table/image | 已有 | 增强 | 已有 |
| 公式 | 已有简单语义处理 | 明确 OMML/降级策略 | 部分 |
| 横向宽表 | 已有 layout 能力/质量证据 | 按 CanonicalGrid 完善 | 部分 |
| Template version | API 和验证任务成熟 | 复用 | 已有 |
| DOCX OOXML QA | 已有轻量证据 | 增加 block/page/preview QA | 部分 |
| Word preview | 未在核心文档中确认 | 发布前预览 Artifact | 不确定/可能缺失 |

## 7. QA、批准和发布

| 能力 | 当前 | 目标 | 状态 |
|---|---|---|---|
| translation QA | 有队列、状态和证据 | 扩展统一 document review | 部分 |
| direct QA | 主要是人工 Golden signoff | 任务级统一 review | 缺失 |
| quality_status | quality flags 有，但独立状态未明确 | pending/passed/warning/blocked | 缺失/部分 |
| delivery_status | 未发现任务级状态 | draft/ready/published | 缺失 |
| publication record | 模板有发布，文档结果发布未确认 | 不可变发布记录 | 缺失 |
| blocked 下载提示 | 当前下载主要由 available action | 明确 warning/classification | 缺失 |
| 三栏审核 | translation QA panel 已有部分证据 | PDF/内容/Word preview 同步 | 部分 |

## 8. 状态机与事件

| 能力 | 当前 | 目标 | 状态 |
|---|---|---|---|
| 执行状态 | pending/queued/running/... | 保持 | 已有 |
| 阶段 | `DocumentJobStage` 已定义 translating、translation_validating、quality_checking 等扩展阶段（2026-11-10 静态复核） | 运行迁移、事件与整项 AC 须独立核验 | 已有类型，未核验整项完成 |
| translation batch status | 已有 | 保持 | 已有 |
| review/publish events | translation QA event 有 | 统一 review/publish | 部分 |

扩展阶段的本次依据仅为 [DocumentJobStage 定义](../../app/domains/document_jobs/models.py)；类型存在不等于所有执行路径和人工验收完成，CON-102 的 Manifest 状态保持原值。

## 9. 测试

| 能力 | 当前 | 目标 | 状态 |
|---|---|---|---|
| P0 Golden | 4 个 OPA228 | 保持 | 已有 |
| component samples | 体系已建立 | 加入 ZK7044 最小页组 | 部分 |
| P1 translation samples | 3 个 en2zh | 四方向 | 缺失 |
| frontend unit/smoke | 已有 | 增加 review/publish | 部分 |
| release/online gates | 已有 | 扩展新状态和门禁 | 部分 |

## 10. 优先级结论

### 第一优先级

1. 状态/合同冻结；
2. CanonicalTableGrid 和表格 QA；
3. 复用已接入的 ProtectedTokenCodec 与翻译完整性校验；按独立证据评估有限语法之外的技术语义和真实实译质量，不重复实现 Codec/Validator（2026-11-06 局部复核）；
4. 统一 quality/review/delivery 状态。

### 第二优先级

1. Word preview 和三栏审核；
2. 文档发布记录；
3. 四方向样本和门禁；
4. ZK7044 复杂样本回归。

### 不应优先

- 重写 UI；
- 更换框架；
- 微服务；
- 在线编辑；
- 多解析器；
- 泛 PDF。
