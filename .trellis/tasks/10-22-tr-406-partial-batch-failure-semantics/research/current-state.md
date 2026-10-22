# TR-406 调查证据（2026-10-22）

## 1. 工作区、真源与依赖

- 首条执行 pwd 和 git status --short，工作区 `/Users/sc/PycharmProjects/md2word`，分支 `md2word/TR-403`，HEAD `596a2de7ed29edb7fdb378d91c17bda09b7f1066`。
- 既存 dirty 为父任务 task.json、workspace/777 的 index/journal、CON-104 prompt、backlog、manifest；另有其他 active/archive task 未跟踪目录。创建前保存所有既存 dirty/untracked 文件哈希及 manifest/父 task 原字节到系统临时目录，只允许 TR-406 区块与父 children 的必要追加。
- 已读根 AGENTS.md、用户补充规则、RTK.md、workflow、guides/backend/frontend index、translation-integrity、database、error、quality、logging、mode Spec 与跨层指南；相关 Skill 为 trellis-start、trellis-brainstorm、clean-code-design。历史事实已在正式任务/Spec/提交中，依 session-insight 规则无需读会话全文。
- 已读用户指定 11 份文档：产品 PRD、scope-and-decisions、implementation-plan、backlog（完整 TR-406 定义含四项要求）、execution-guide、manifest、architecture-decisions、document-ir-contract、translation-design、testing-acceptance-strategy、rollout-and-migration；另读父任务三件套、CON-102 归档 design/task/batch-generation-fix-validation、TR-403 归档 task/research 和 TR-405 待审 design。
- manifest：TR-406 原 todo/path=null；TR-403=done/implemented、CON-102=done，归档均 completed，有人工验收记录，无 skipped_existing 推断。对应准确归档路径在 manifest。
- `git merge-base --is-ancestor`：f46a3bcf148e6abc16a0011b6e7079d7f723130b→HEAD 退出0；52810b61adef98ca424cdd8b2b677991dc222cce、4d3068260c7fe5b1dab2ef46bfeb83f8963e98dc→HEAD 均退出1。通过 git show 直接读取 CON-102 验收源码，确认阶段与主任务锁/receipt，且其批次领取/finalizer/条件写仍有本任务所列缺口。
- 全 task.json 检索无既有 TR-406/slug；复用父 `.trellis/tasks/10-12-datasheet-docx-delivery-quality`，执行 create --parent --no-start，生成 `.trellis/tasks/10-22-tr-406-partial-batch-failure-semantics`。未切分支或激活。

## 2. 当前源码定位

| 位置（当前 HEAD） | 观察 |
|---|---|
| app/domains/document_jobs/execution.py:1056、1092 | generation=job.retry_count，新代从 source 建根批次；调用预算 min(200, deterministic_count*12)，attempt 默认来自 settings。 |
| 同文件 :1161、1315 | 入口核 job 代次/status/stage；claim 允许 pending/queued/failed，只检查状态+generation，attempt_count 从旧快照加一，不核不可重试或预算。 |
| 同文件 :1357、1438 | 失败先尝试疑似截断 split，再基于预算/attempt 标 retryable；split 父写在孩子前。 |
| 同文件 :1530 | finalizer 使用 status!=split 当叶子，先等 pending/queued/running，再 retryable，再最终失败。全 split 返回 running。 |
| 同文件 :1579、1733、1757 | fan-in 重核权威来源/字节/checksum/binding/当前 generation 与 attempt，再覆盖对账，一次 apply；不补原文。 |
| 同文件 :1861、1929 | enqueue 的 pending 候选不核调用预算；lease 回收仅状态+generation，不隔离旧 attempt。 |
| app/domains/document_jobs/models.py:181 | batch 已有 job_retry_count/generation/root/parent/status/attempt/max_attempts/lease/result。主模型当前不含 CON-102 新 stage/receipt 或 CON-103 四状态。 |
| app/domains/document_jobs/service.py:382、632、1147 | 当前代批次列表、用户 retry_count+1，现有恢复优先 result/target/raw；当前 HEAD 不是 CON-102 原子 retry 版本。 |
| 同文件 :70、1571 | allowlist 不含 translation_batch_result；source IR 和 target IR 按权威指针/当前代选择。不能把 source 下载与目标成功混为一谈。 |
| app/infrastructure/persistence/file/document_jobs.py:283、sqlite/:371、mysql/:388 | 批次更新为 read→状态/generation检查→写，没有 attempt 条件；file 无该操作锁，sqlite 未显式BEGIN IMMEDIATE，MySQL查询无FOR UPDATE。 |
| app/domains/translation/document_ir_translator.py:135 | 同步 deep copy，全部批次验证后才 apply，已有原子回填语义，无需重写。 |
| app/domains/translation/audit.py:190 | 全文归档只在 save_full_text 时写，沿 settings TTL；默认1天、默认开关false（config.py:115）。常规审计已脱敏。 |
| app/domains/document_jobs/schemas.py:227、router.py:348 | GET批次已有安全 DTO；无权威执行结论。先 list 后二次取job兜generation，需一致快照。 |
| frontend/src/utils/translationBatches.ts、pages/JobDetailPage.vue:1024 | split/failed统称attention，原 item统计包括父子；展示原始reason和attempt，没有终态/停止语义。 |
| scripts/dev/formal_mineru_conversion.py、scripts/ops/run_p1_translation_regression.py | 正式本地 adapter 与P1安全批次诊断已存在；无需第二流水线或新增真实Provider测试。 |

## 3. 实际只读反例

使用 `.venv/bin/python`、`PYTHONDONTWRITEBYTECODE=1`，调用 `tests.test_translation_integrity_execution.TranslationIntegrityExecutionTests.make_case()` 构建 fake Provider/临时文件仓储，结束执行清理，不修改任何业务源码或真实 metadata：

1. 原叶子设置 failed/attempt=1/max=1/retryable=false，添加 running 兄弟，调用真实 `_finalize_translation_generation`（屏蔽入队副作用）：结果 job.status=running。
2. 同一失败叶子再投递 `execute_translation_batch`，仅屏蔽 finalizer：结果 status=succeeded、attempt_count=2、max_attempts=1、fake Provider调用=1。证明重复消息绕过终态/上限。
3. 同批次保存旧 running attempt1 快照，再置 running attempt2，用旧快照的 generation 执行 update_translation_batch_if_current(allowed_statuses={running},status=failed)：更新被接受，current_attempt仍2、错误来自旧attempt。证明当前接口无法隔离同代尝试；未声称已复现真实 MySQL 竞态。

真实外部 Provider 调用数为0。上述探针与代码一致，CON-102验收实现未修批次端口，故不是只因当前缺基线产生的虚假缺口。split崩溃、并发总预算和UI细节为源码机制确认的实施验证项，本轮未模拟全部交错，不写成已通过。

## 4. 实际基线

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest \
  tests.test_translation_integrity_execution \
  tests.test_document_ir_translation \
  tests.test_generated_artifact_identity \
  tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_document_job_en2zh_translation_failure_records_ai_call_log_without_full_text \
  tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_document_job_en2zh_truncated_batch_is_split_and_fanned_in \
  tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_document_job_retry_translation_failure_resumes_after_mineru_and_filters_old_files
```

实际结果：37 tests，1.412s，OK，退出0。存在既有 Starlette/httpx/HTTP状态名弃用警告，负例输出预期失败日志，未隐藏或修改。该结果只证明当前成功/失败/evidence/源件复用基线，不代表未来TR-406新增语义通过。

## 5. 取舍与证据边界

- 用户允许主任务失败或质量blocked择明确规则；本计划选叶子终败→执行failed、无partial主件，完整质量blocked草稿规则保持，不改变冻结PRD。
- translation-design“只重试失败批次”与TR-403同代证据约束通过区分同代自动恢复/跨代用户retry消解；实施同步文档，不重新绑定旧结果。TR-405更广QA retry尚待审，不纳入本任务。
- 需要局部三adapter原子条件更新，已有实际旧attempt反例支撑；不是队列重写。无新DDL/配置/外部依赖，线上锁/事务启用门保留。
- 未运行release、前端、浏览器、component/matrix、真实MySQL/S3、P1外调、线上Golden或Microsoft Word；无业务改动无需本轮重跑重门禁。规划只新增三件套/研究/context与TR-406状态，后续实施门禁详implement.md。
