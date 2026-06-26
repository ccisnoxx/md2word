# Translation provider batching and recovery

## Goal

降低长 PDF 英译中在 provider 返回截断或非法 JSON 时的失败率，并让失败诊断能明确指出是哪个批次、页范围、输出状态和解析错误导致任务失败。

用户价值：32 页以上或表格文本节点很多的 PDF 不应因为一次 provider 响应过大而整单失败；即使失败，也要能从审计记录快速判断是否应缩小批次、调整 token 上限或切换 provider。

## Confirmed Facts

- 线上失败样本是 32 页 PDF，MinerU 解析已成功，失败发生在 `ir_converting` 阶段的 AI 翻译 provider 调用；两次 provider 调用都发送了同一规模请求，约 1582 个 item、33301 个字符，最终因 `JSONDecodeError` 失败。
- 旧 runtime 已有页数和字符数分批策略：`DEFAULT_MAX_PAGES_PER_BATCH = 20`、`DEFAULT_MAX_CHARS_PER_BATCH = 60000`，并在总页数和字符数满足上限时单批，否则按 section/page/char 组织批次（`app/conversion/runtime/translation_runtime.py:15`, `app/conversion/runtime/translation_runtime.py:355`）。
- 当前上传配置默认支持最多 200 页 PDF，上传校验会用 `pdf_upload_max_pages` 拒绝超页文件（`app/core/config.py:59`, `app/domains/files/validation.py:45`）。
- 全局和 Translation Profile 已有 `translation_max_pages = 20`、`translation_max_chars = 60000` 配置入口（`app/core/config.py:113`，`app/domains/translation/models.py:44`）。
- legacy conversion entrypoint 会把 profile/settings 的 max pages/chars 传入旧 runtime（`app/conversion/entrypoint.py:61`），但新的 DocumentIR 翻译路径当前未消费这两个业务配置。
- 新 DocumentIR provider 适配器当前使用 `client.chat.completions.create(...)` 后只抽取 message content 并 `json.loads`，没有把 `choices[0].finish_reason`、usage token 或 raw response 元信息带入错误和审计（`app/domains/translation/provider.py:62`, `app/domains/translation/provider.py:72`）。
- 当前文档任务记录创建时使用固定 `p0_document_job_timeout_seconds` 写入 `timeout_at`，默认 1200 秒；Celery worker 也用同一个值作为全局 `task_soft_time_limit`，硬超时为该值加 60 秒（`app/domains/document_jobs/service.py:254`, `app/workers/celery_app.py:28`）。
- 单次 provider 调用有独立 HTTP timeout，来自 `translation_provider_timeout_seconds`，默认 120 秒；配置接口允许最高 600 秒（`app/core/config.py:108`, `app/domains/translation/provider_config_schemas.py:31`）。
- 当前 `DocumentJobRecord` 只有 job 级状态和 `ir_converting` 阶段，没有翻译批次状态；sqlite/mysql schema 也只有 `document_jobs` 和 MinerU callback message 表，没有 provider batch run 表（`app/domains/document_jobs/models.py:73`, `app/infrastructure/persistence/sqlite/schema.py:149`, `app/infrastructure/persistence/mysql/schema.py:392`）。
- 当前 DocumentIR 是翻译完成后才注册为 `document_ir_file_id`；异步批次 worker 若要独立执行，必须先持久化未翻译 source DocumentIR，再由批次结果汇总生成已翻译 DocumentIR（`app/domains/document_jobs/execution.py:793`, `app/domains/document_jobs/execution.py:802`）。
- DocumentIR 翻译提取当前按 block order 生成文本 item，表格 HTML 中每个 text node 都会拆成一个 item，导致 item 数可能远高于页数直觉（`app/domains/translation/document_ir_translator.py:325`, `app/domains/translation/document_ir_translator.py:361`）。
- 当前 `_TextTarget` 不包含页码，`TranslationTextItem` 也没有页码；要恢复“20 页一批”的策略，需要在 DocumentIR 翻译内部引入带 page 的批处理上下文，而不是只按 item/char 顺序切分（`app/domains/translation/document_ir_translator.py:58`, `app/domains/translation/models.py:176`）。
- 当前工作区已有一版未部署的初步改动，把 DocumentIR 请求按 item/char 拆分并让审计支持多次 AI 调用；该改动还没有实现页感知分批、provider finish_reason 捕获和截断后的自适应拆分，因此只能作为草案基础，不能视为最终方案。

## Requirements

- R1. DocumentIR 翻译应复用现有业务配置：默认 `max_pages_per_batch=20`、`max_chars_per_batch=60000`，profile 覆盖 settings；不要引入与 Translation Profile 并列的第二套页/字符配置。
- R2. 初始批次应以页范围为第一边界：页数小于等于配置上限且字符数在上限内时允许单次 provider 调用；超过页数时按页窗口分批，例如 1-20、21-40。
- R3. 页窗口内仍需有硬性安全上限：当单个页窗口因表格、列表或密集文本导致 item/char 过大时，应在保持文档顺序和 item id 顺序的前提下继续细分。
- R4. Provider 结果模型应携带响应元数据，包括至少 `finish_reason`、usage token、原始响应 id 或等价 trace 字段；解析失败时错误对象应携带这些元数据，不只抛出裸 `JSONDecodeError`。
- R5. 当 JSON 解析失败且响应元数据显示疑似截断，例如 `finish_reason=length`、内容明显缺少闭合 JSON、或输出接近 `max_output_tokens` 时，应自动把当前逻辑批次拆小后重试。
- R6. 自适应重试必须有硬上限，但任务级 provider 调用数上限不能是固定小值，应根据实际初始批次数和 200 页最大文档规模动态计算，避免大文档在正常自动拆分路径上被过早截断。
- R7. 如果 `finish_reason=stop` 但 JSON 仍非法，应按“小批次重试一次或拆小重试”的明确策略处理，不应试图从半截 JSON 中静默恢复部分翻译。
- R8. 批处理失败不应产生部分成功的 Word/DocumentIR 输出；只有所有最终叶子批次成功并通过 item id 顺序校验后，才应用翻译替换。
- R9. AI call audit 应能记录每次 provider 尝试的 `logical_batch_id`、`attempt`、`split_level`、`parent_batch_id`、页范围、item 数、字符数、`finish_reason`、失败原因和是否由截断触发重试。
- R10. 对外错误仍可保持 `translation_failed`，但内部事件和审计文件必须能定位具体失败批次，便于线上排查和后续重试策略调整。
- R11. 翻译阶段的任务超时策略应与动态 provider 调用预算联动；固定 1200 秒不应成为大文档自动恢复的主要失败原因。
- R12. 区分整体 document job 超时和单个 provider batch 调用超时：整体 job timeout 覆盖解析、翻译批次、渲染和上传；单批次 timeout 只约束该批 provider 调用和该批自适应拆分。
- R13. 翻译批次必须有持久化执行状态；单个批次失败、超时或 provider 返回非法 JSON 时，只重试该批次及其拆分出的子批次，不重跑已成功批次。
- R14. Provider batch 必须作为独立可入队任务异步执行，支持多个 batch 并发运行；批次任务完成后通过持久化状态触发 fan-in 汇总，而不是依赖单个 document job worker 的内存循环。
- R15. 异步批次流必须先保存未翻译 source DocumentIR，所有 leaf batch 成功后再生成 translated DocumentIR 并推进渲染；失败或重试期间不得覆盖已成功批次结果。
- R16. Provider batch 并发必须有双层限制：单个 document job 默认最多 4 个并发 batch，部署级总并发由专用 Celery queue/worker concurrency 控制。
- R17. 第一阶段应提供最小只读后端 JSON 接口，按 document job 查询 provider batch 状态和失败诊断；接口返回 `status`、`page_range`、`item_count`、`attempt_count`、`finish_reason`、`error`、`ai_call_log_file_ids` 等摘要字段，不返回完整 prompt/response。

## Acceptance Criteria

- [ ] 小于等于 20 页且字符数未超过上限的 DocumentIR 翻译默认只产生 1 次 provider 调用。
- [ ] 大于 20 页的 DocumentIR 翻译按页窗口产生多次 provider 调用，并保留原始 item 顺序。
- [ ] 同一页窗口内 item/char 超限时，会继续拆成更小批次且不会打乱替换目标。
- [ ] provider 返回非法 JSON 且元数据/内容形态指向截断时，会自动拆分当前批次重试，最终成功时任务成功。
- [ ] 自适应重试超过配置上限时，任务失败并在事件/audit 中包含页范围、批次 id、item/char 数、finish reason 和解析错误。
- [ ] 对 200 页以内的长文档，动态预算允许的正常重试路径不会被默认 1200 秒任务超时提前截断。
- [ ] 批次级 provider timeout 只标记该批失败/可重试，不直接丢弃其他已成功批次。
- [ ] document job 重试时会跳过已成功批次，只执行失败或未完成批次，并在所有批次成功后合并输出。
- [ ] 多个 provider batch 可以异步并发执行，且 fan-in 汇总只在所有 leaf batch 成功后发生一次。
- [ ] 同一 document job 默认不会超过 4 个 running provider batch；全局并发可以通过专用 worker/queue 调整。
- [ ] source DocumentIR 与 translated DocumentIR 分开持久化，批次重试不会丢失源结构或已成功批次结果。
- [ ] 只读 batch 状态接口可按 job 返回每个 provider batch 的状态、页范围、item 数、attempt 数、finish reason、错误摘要和 AI call log 文件 ID。
- [ ] `finish_reason=stop` 但 JSON 非法的响应不会被当成成功，也不会应用部分翻译。
- [ ] 任务成功和失败场景均能保存每次 AI 调用的审计记录；全文 debug archive 仍受现有开关和保留期控制。
- [ ] 覆盖单批、页分批、页内超限拆分、截断自适应重试、stop+非法 JSON 失败、审计多调用记录的测试。

## Out Of Scope

- 本任务不改 MinerU 解析流程。
- 本任务不把 provider 协议迁移到完全不同的 structured output API，除非后续证据证明现有 OpenAI-compatible JSON prompt 无法满足可靠性。
- 本任务不默认保存完整 prompt/response；全文归档仍必须受 `translation_debug_archive_enabled` 控制。
- 第一阶段不做前端批次可视化，也不做运维控制台增强；这些作为后续独立交付。

## Resolved Decisions

- 截断/非法 JSON 后的恢复策略偏向自动完成翻译，而不是在第一次截断迹象出现时直接失败。
- 因产品默认支持最多 200 页 PDF，provider 调用硬上限应按文档规模动态计算，不能使用固定 `40` 作为全局上限。
- 采用动态 provider 调用预算公式：`max_provider_calls = min(200, deterministic_batch_count * 12)`，其中 `deterministic_batch_count` 是页窗口和 item/char 硬切分后的初始批次数。
- 运行时策略偏向任务完成，不应让默认固定任务超时优先于自动分批恢复策略。
- 接受翻译阶段整体 timeout 动态放宽：按 `max_provider_calls * provider_timeout_seconds + buffer` 估算，并确保 worker hard limit 不低于估算值。
- 整体 document job timeout 与单个 provider batch timeout 必须分离；批次失败只应重试失败批次，不应导致已成功批次重跑。
- Provider batch 执行采用独立入队、异步并发的 task，而不是单个 document job worker 内顺序执行。
- 默认并发策略采用：单个 document job 最多 4 个 running provider batch，部署级总并发由专用 Celery queue/worker 控制。
- 分阶段交付：第一阶段只做后端能力，包括批次表、异步 batch task、并发控制、失败批次重试、fan-in 合并、审计和事件；前端批次可视化、运维控制台增强后置。
- 第一阶段增加最小只读后端 JSON 接口，用于按 job 查询 provider batch 状态和失败诊断；不做 UI。
