# 翻译完整性验证与消费合同

## 1. 范围与触发

修改正式翻译请求准备、Provider 解析、同步/Worker 回填、批次 Artifact、审计或正文默认表示时适用。`protected_tokens.py` 唯一拥有检测/占位/恢复；`integrity.py` 唯一拥有纯校验与安全 evidence；translator 负责共同准备，execution 负责持久化消费。禁止复制检测规则或建立第二条翻译链路。

## 2. 接口

```python
prepared = service.build_provider_request(..., max_chars_per_request=limit)
result = service.provider.translate(prepared.request)
validated = service.validator.validate(prepared.source_items, prepared.encoded_batch, result)
evidence = validated.evidence.bind(binding).to_dict()
checked = service.validator.validate_persisted(source_items, restored_items, evidence, binding=binding)
```

`PreparedTranslationRequest` 为 frozen/slots，含 `source_items`、真正编码的 `request`、仅内存的 `encoded_batch`；只有 `.request` 可交给 Provider。`ValidatedTranslationBatch` 含恢复 `.items`、冻结 `.evidence`，成功后才生成 `.replacements`。旧 ID-only `validate_result` 不再提供旁路。

## 3. 请求、证据与隐私合同

- 共同批次计划按实际编码文本字符数、item/page 限制切分；每个最终 batch 独立 encode。既有 `char_count` 仍表示原文，单项或既存批次编码后超限在调用前拒绝。该预算不是完整 Prompt 的 tokenizer 上限。
- 术语在原文匹配，排除与技术保护跨度相交的匹配；保留真实位置和上下文，不增加术语后验 QA。Provider 只接收编码 items，不接收 ledger。
- JSON 只能包含 `items`；每项只能有非空字符串 `id/text`。禁止强转、trim 字段、重复 JSON key、额外字段、自由文本/Markdown 包装和重排。技术完整性运行协议版本为 `translation-integrity-instructions/v1`，追加到原绑定 Prompt，不改原内容 hash。
- 核对原文与 ledger 完整对应；先验证 ID（duplicate→missing→extra→order），再逐 item 占位次数/归属并一次 decode，最后比较逐 item `Counter((kind, original_text))`。不能只比较全批集合，也不能允许保留占位符之外新增裸技术值。
- 任一失败整批抛 `TranslationIntegrityError`，只有固定中文消息、`.code` 和安全 `.evidence`，没有部分 replacements；不补原文、不修复模型输出。同步全部批次通过后才 apply；Worker 验证后才登记成功结果；fan-in 全部叶子通过后才 apply。
- `translation-integrity/v1` evidence 含 validator/codec/instruction 版本、status/stage/error、item/字符/Token 分类计数与有序 JSON 哈希；未到达的响应/恢复阶段为 null。内容不含原文、译文、Prompt、恶意返回 ID 或 ledger。`items_sha256` 为有序 items 的唯一规范化哈希实现。
- `TranslationIntegrityBinding` 由本地权威 job/batch/source/config 构造，绑定 job/batch/root/parent、attempt/generation、source file/checksum、Profile/Prompt/term hash；不能从待校验 payload 自证这些预期值。业务 batch Artifact 的 items 是恢复文本，普通审计只保存摘要。
- fan-in 必须检查真实 Artifact 字节 checksum、来源、当前代次/尝试及完整有序 ID，再调用 `validate_persisted` 重核 source/restored hash、版本/计数/binding 和技术 inventory。缺证据的活跃旧中间结果拒绝使用，历史已完成 Artifact 不重跑或补写通过标记。
- generation 门约束当前批次、译文结果及 evidence。既有重试可沿用 job 权威指针引用的同 job 不可变 source IR；源文件创建代次不等于本次消费代次。仍核对 source 指针、归属/type/source role、IR 来源和真实 checksum/size，当前批次重新绑定新 generation/attempt 与该准确 source file/checksum；不为满足错误同代假设复制同字节源件，也不复用旧译文结果。
- evidence 的计数和关联字段必须类型严格匹配：JSON 的 bool/float 不能借 Python 的 `True == 1 == 1.0` 冒充权威整数计数或 generation。此检查位于持久化证据边界，不在内部各调用方重复实现。
- 既有 DTO 和中间 `_TermMatch.context_snippet` 用字段级 `repr=False` 隐藏正文/Prompt/context/未经验证的 item ID；不清空业务值，不改变字段、序列化、相等性或 frozen/slots。`asdict` 仍含真实值，不能直接写普通日志。
- 审计 `record_success/record_failure(..., integrity=...)` 每次真实调用只记一次；调用前失败不伪造 AI 调用，审计写入失败不能被吞掉或重复记为另一次 Provider 调用。外部异常使用固定安全消息，不能把 `str(error)` 和原异常链写普通事件/日志。

## 4. 验证与错误矩阵

| 条件 | 稳定错误码 |
|---|---|
| 源输入/编码 metadata 不合法 | `translation_integrity_invalid_input` / `translation_integrity_metadata_mismatch` |
| fake 返回 DTO shape/类型/空值错误 | `translation_integrity_invalid_response` |
| 重复/缺失/额外/乱序 ID | `translation_integrity_item_duplicate/missing/extra/order`（各自完整前缀） |
| 缺失/重复/未知/错 item/损坏占位符 | `translation_integrity_placeholder_missing/duplicate/unknown/wrong_item/malformed`（各自完整前缀） |
| 恢复后逐 item 技术 inventory 不同 | `translation_integrity_technical_mismatch` |
| 活跃中间结果缺少/不匹配证据 | `translation_integrity_evidence_missing` / `translation_integrity_evidence_mismatch` |
| 编码文本超限 | `translation_request_budget_exceeded` |

Provider JSON/传输/截断保留 `translation_provider_invalid_response/failed/truncated`。同步领域错误保留 code/evidence；Worker 必须优先识别完整性错误，不能全压成通用 invalid_response。主任务顶层既有 `translation_failed`、重试/拆分预算与终态策略不因本任务改变。无新 HTTP 错误枚举、quality flag、数据库字段或 feature flag。

首次建批的编码预算失败也必须映射为顶层 `translation_failed`，由既有 `stage_failed` 事件保存 `integrity` 摘要及内部专码；此时没有真实 batch，binding 为 null，不虚构 batch 或 AI 调用日志。原阶段/CAS 失败写入规则保持不变。

## 5. 正常、缺省与非法场景

- 正常：只翻译自然语言，同 item 内完整占位符移动后技术 inventory 相同，允许恢复；真实值保留，结构/layout/assets/表格 DOM 不变。
- 缺省：direct 不进入翻译，不加载 Prompt/翻译术语/Provider；空 IR 保持原行为。历史已完成结果和旧存储 key 继续按记录读，新生成件遵守 [物理身份合同](database-guidelines.md)。
- 非法：跨 item 交换占位符、额外追加 `999 V`、伪造 passed evidence、同批第二 item 失败后仍消费第一项、让新 file_id 复用旧物理路径，均不能形成成功回填。

## 6. 必要测试与证据边界

- `tests.test_translation_integrity`：shape/ID 首错优先级、ledger 错配、占位异常/裸技术注入、计数多重集、整批原子性、安全错误、预算/术语、真实术语匹配生成 `_TermMatch` 的直接/列表 repr 与下游 trace，以及字段/asdict/hash/相等性/冻结对照。
- `tests.test_document_ir_translation`、`tests.test_protected_tokens`、`tests.test_translation_profile_prompts`：正常自然语言、结构和公开 OPA228 fixture、真实编码请求与绑定 Prompt hash。
- `tests.test_translation_integrity_execution`：Worker/fan-in 成功和失败、缺证据/错来源/代次/尝试/hash/重复项，失败零 apply/无成功 result，首次无 batch 的预算错误映射和事件摘要，以及迟到写被 CAS 拒绝后的实际字节和 checksum。
- `tests.test_generated_artifact_identity`：本地真实字节与 fake S3、重复登记和历史 key；`tests.test_conversion_sandbox_dev_tools`：本地 v2 编码请求、严格响应和 direct 保持。

有限语法以已接受 Codec 为准，不保证任意型号/公式、参数语义关联或目标语言正确。fake、P1 环境 preflight、真实供应商实译、真实 S3/MySQL 并发和 Word 人工验收是不同证据；缺失样本/认证必须报告，不能用 fake 宣称线上/四方向全通过。上线前暂停翻译入队并排空旧 Worker/活跃旧代，同步部署调用端与 Worker，不混跑缺证据结果；无 backfill。回退先停止相关执行，不恢复无校验回填或共享路径覆盖。

## 7. 错误与正确做法

错误：`provider.translate(raw_request)` 后仅比较 ID，边校验边更新 replacements；把文件里的 `status=passed` 当成验证结论。

正确：共享准备生成真实编码请求与内存 ledger，整批 Validator 成功后才使用恢复结果；落盘绑定权威来源，fan-in 从本地来源重新校验后一次回填。真实匹配隐私测试必须有实际命中、真实 context 保留，不以 mock 或零命中通过。
