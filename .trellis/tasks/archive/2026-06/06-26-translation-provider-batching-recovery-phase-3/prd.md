# Translation provider batching and recovery Phase 3

## Goal

验证 Phase 1/2 的 provider batch 恢复能力在真实或 staging 长 PDF 英译中链路中可用，并补齐上线后的运维闭环：可观测证据、排障 runbook、回归报告和现有运维入口的下一步判断。

用户价值：当长 PDF 英译中再次出现 provider 截断、非法 JSON、批次失败、重试或 fan-in 卡住时，运营和开发可以从标准报告与 Job Detail 诊断信息判断恢复机制是否覆盖问题、下一步应重试还是升级，而不是重新排查 provider batch 执行核心。

## Background

- Phase 1 后端能力已完成并归档：`.trellis/tasks/archive/2026-06/06-26-translation-provider-batching-recovery/`，核心提交 `e6adfd69`。
- Phase 2 只读诊断 UI 已完成并归档：`.trellis/tasks/archive/2026-06/06-26-translation-provider-batching-recovery-phase-2/`，核心提交 `ae7fb5e9`。
- Phase 3 应承接生产验证和运维闭环，不继续归档任务，不重复实现 Phase 1/2。
- 2026-06-26 已确认 Phase 3 MVP：验证报告、runbook、运维入口评估和批次级写操作设计占位；暂不实现 Operations Cockpit 聚合入口，也不实现任何批次级 retry/cancel/requeue/finalizer 写操作。

## Confirmed Facts

- Phase 1 设计把翻译阶段改为 fan-out/fan-in：持久化 source `DocumentIR`，创建 provider batches，独立 Celery batch task 执行，批次完成后 finalizer 合并结果（`.trellis/tasks/archive/2026-06/06-26-translation-provider-batching-recovery/design.md:5`）。
- Phase 1 已明确完成后端能力：batch persistence、async batch tasks、concurrency control、failed-batch retry、fan-in merge、audit、events、minimal read-only diagnostics API；前端可视化和 operations-console 增强被后置（`.trellis/tasks/archive/2026-06/06-26-translation-provider-batching-recovery/implement.md:7`）。
- Phase 1 diagnostics API 的 redaction 边界是不返回完整 prompt、response、source text 或 translated text（`.trellis/tasks/archive/2026-06/06-26-translation-provider-batching-recovery/design.md:147`）。
- Phase 2 确认 MVP 只落在 Job Detail “诊断” tab，并把 Incident Triage / Operations Cockpit 聚合入口、批次级 retry/cancel/requeue/fan-in 写操作排除在 MVP 外（`.trellis/tasks/archive/2026-06/06-26-translation-provider-batching-recovery-phase-2/prd.md:65`、`.trellis/tasks/archive/2026-06/06-26-translation-provider-batching-recovery-phase-2/prd.md:66`、`.trellis/tasks/archive/2026-06/06-26-translation-provider-batching-recovery-phase-2/prd.md:67`）。
- 当前代码已有 Job Detail Provider 批次区域，展示 batch summary/table，并只展示 AI call log file IDs（`frontend/src/pages/JobDetailPage.vue:221`）。
- 当前前端已有 `documentJobsApi.listTranslationBatches(jobId)`，请求 `GET /api/v1/document-jobs/{jobId}/translation-batches`（`frontend/src/api/documentJobs.ts:101`）。
- 当前 API 文档已记录 `GET /api/v1/document-jobs/{job_id}/translation-batches` 的用途、字段和 redaction 边界，并声明不提供批次级 retry/cancel/requeue/fan-in 写操作（`docs/api/document-jobs.md:220`）。
- 当前线上优先验证流程要求完整 API、Worker、MySQL、Redis/Celery、MinerU 和 Golden Sample 证据在 `hostdzire` 收集，本地不作为 full-stack 验收目标（`docs/deploy/online-first-validation-workflow.md:20`）。
- 当前 P1 翻译回归脚本会创建 en2zh document job、等待终态、读取 translation QA、下载 DOCX 并输出报告，但尚未读取 `translation-batches` diagnostics（`scripts/ops/run_p1_translation_regression.py:218`、`scripts/ops/run_p1_translation_regression.py:328`）。
- 当前 P1 翻译样本清单只有 `p1-en-001` smoke PDF 可用，两个更复杂样本仍为 `pending_pdf`，仓库内没有原 32 页失败样本（`tests/fixtures/p1_translation_samples/manifest.yaml:17`、`tests/fixtures/p1_translation_samples/manifest.yaml:28`、`tests/fixtures/p1_translation_samples/manifest.yaml:40`）。
- 当前已有 Incident Triage 和 Operations Cockpit 页面/路由，Incident Triage 能按 `translation_failed` 等 failure type 分诊并深链到 Job Detail，但尚未观察到 provider batch 专属聚合状态（`frontend/src/router/index.ts:57`、`frontend/src/router/index.ts:59`、`frontend/src/utils/incidents.ts:16`、`frontend/src/utils/operationsCockpit.ts:51`）。
- 当前 Ops namespace 明确偏只读/受控预览，不执行真实 provider calls、translation providers 或 Word generation；这限制了 Phase 3 若涉及批次级写操作，必须先做权限、接口、审计和幂等设计（`docs/api/ops.md:23`）。

## Requirements

- R1. Phase 3 必须使用新任务目录 `.trellis/tasks/06-26-translation-provider-batching-recovery-phase-3/`，不得修改或继续 Phase 1/2 归档任务。
- R2. 验证范围应优先覆盖真实或 staging 长 PDF 英译中链路，而不是重复单元测试中已覆盖的 batch 执行核心。
- R3. 长 PDF 回归必须使用原 32 页失败样本或等价长 PDF；若样本不能提交到仓库，验证记录必须只写非敏感摘要：样本来源标识、页数、job id、运行环境、commit/deployment id、批次数和结果，不保存 PDF、全文、prompt 或 provider response。
- R4. 回归证据必须读取 `GET /api/v1/document-jobs/{job_id}/translation-batches`，并记录每个 job 的 `generation`、batch 总数、状态计数、页范围、attempt、`finish_reason`、`truncation_retry`、`retryable`、`provider_call_budget`、错误摘要和 AI call log file id 数量。
- R5. 对长 PDF 成功场景，报告必须证明不再出现单个超大 provider request 导致整单失败：至少记录多个 batch 或记录 batch 规模在配置上限内，并确认所有当前 leaf batch 成功后 job succeeded。
- R6. 对截断/非法 JSON 场景，如果真实 provider 复现了 `finish_reason=length`、非法 JSON 或疑似截断，报告必须记录 split/retry 过程和最终 fan-in 结果；如果真实 provider 未复现截断，报告必须明确“长样本成功但未触发截断恢复”，并把截断恢复证据指向现有自动化测试或后续受控注入验证。
- R7. 如需要改脚本，优先扩展 `scripts/ops/run_p1_translation_regression.py` 或新增相邻 ops 脚本，使其能采集 batch diagnostics 并输出到 `report.json` / `report.md`；脚本不得下载或内联 AI call log/debug archive 正文。
- R8. 更新运维 runbook，写清楚 operator/admin 如何从 Job Detail Provider 批次区域判断：截断拆分、失败批次、重试耗尽、running/queued 卡住、fan-in 未推进、AI call log file id 关联和可用任务级 retry。
- R9. runbook 必须说明当前允许的操作边界：使用任务级 retry/cancel/archive/clone 等现有动作，不提供批次级 retry/cancel/requeue/finalizer 写操作。
- R10. 评估 Incident Triage / Operations Cockpit 是否需要 provider batch 聚合入口；MVP 允许只产出设计判断和深链建议，不要求实现新页面或聚合 API。
- R11. 如果评估认为需要批次级 retry/cancel/requeue/finalizer 操作，本阶段只产出权限、接口、审计、幂等和安全边界设计，不直接实现写操作。
- R12. 验证产物应能纳入现有 Acceptance Center / release evidence 流程，至少提供可手工登记的报告路径、摘要、blockers 和 warnings。
- R13. 保持 Phase 1/2 redaction 边界：不展示或保存完整 prompt、provider response、source text、translated text、PDF 原文、密钥、签名 URL 或对象存储定位。
- R14. 不处理无关 `.agents`、`.codex`、`.trellis` churn；如这些目录已有无关改动，不纳入本任务提交范围。
- R15. MVP 的实现范围限定为：
  1. 扩展或新增 ops 回归脚本，采集长 PDF en2zh job 的 `translation-batches` diagnostics 到报告。
  2. 在 `hostdzire` 或等价 staging 上用原 32 页失败样本或私有等价长 PDF 跑一次回归，产出脱敏报告。
  3. 更新 `docs/runbooks/backend.md`，补充 provider batch diagnostics 排障流程。
  4. 写一份轻量评估，判断 Incident Triage / Operations Cockpit 是否只需要深链到 Job Detail，还是需要后续聚合入口。
  5. 如发现需要批次级写操作，仅写设计，不实现。

## Acceptance Criteria

- [ ] 新任务目录存在，Phase 3 PRD 经用户确认 MVP scope 后再创建 `design.md` / `implement.md` 并进入实现。
- [ ] 线上或 staging 验证报告记录运行环境、commit/deployment id、样本标识、页数、job id、job 终态、result file id、耗时和 operator/admin 可复核路径。
- [ ] 长 PDF 英译中回归报告包含 `translation-batches` 摘要：generation、batch 总数、状态计数、页范围、attempt、finish_reason、truncation_retry/retryable、provider_call_budget、error 摘要和 AI call log file id 数量。
- [ ] 如果长样本触发截断或非法 JSON，报告能显示 split/retry/fan-in 路径并确认最终成功或给出明确失败 blocker；如果未触发截断，报告明确记录未触发，并引用现有截断自动化覆盖。
- [ ] 运维 runbook 增加 provider batch diagnostics 排障步骤，覆盖截断、失败、重试、fan-in 卡住和任务级 retry 边界。
- [ ] Incident Triage / Operations Cockpit 评估产物给出是否进入 MVP 的明确结论；若不进 MVP，说明保留 Job Detail 深链的理由和后续触发条件。
- [ ] 若提出批次级写操作，只有设计文档，没有新增执行 endpoint、按钮、队列 mutation 或 provider call。
- [ ] 所有新增报告、runbook、脚本输出都遵守 redaction 边界，不包含完整 prompt/response/source/translated text/PDF 内容/密钥/签名 URL。
- [ ] 验证通过本任务相关的最小本地检查；真实链路验证在 `hostdzire` 或 staging 收集，若无法执行则明确 blocker 和下一步。

## Out Of Scope

- 不重做 provider batch 执行核心、batch planner、异步 task、失败批次重试、fan-in finalizer 或 provider adapter。
- 不改 provider 协议，不迁移 structured output API。
- 不重复实现 Phase 2 Job Detail 只读诊断 UI。
- 不展示完整 prompt、provider response、source text、translated text、PDF 原文或 debug archive 内容。
- 不直接实现批次级 retry/cancel/requeue/finalizer 写操作。
- 不把真实长 PDF、客户文件、密钥或签名 URL 提交到仓库。
- 不处理无关 `.agents`、`.codex`、`.trellis` churn。

## Resolved Decisions

- Phase 3 MVP 先做验证报告、runbook 和运维入口评估，不实现 Operations Cockpit 聚合入口。
- 批次级 retry/cancel/requeue/finalizer 写操作只允许做设计占位，不进入本阶段实现。
- 长 PDF 样本可来自私有 staging/hostdzire 环境；仓库只保存脱敏摘要和报告，不提交真实 PDF 或全文证据。

## Notes

- 这是 planning 阶段产物；未运行 `task.py start`，未进入实现。
- MVP scope 已确认；进入实现前仍需 review `design.md` / `implement.md` 并运行 `task.py start`。
