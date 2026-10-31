# TR-403 实现与本地验证

日期：2026-10-21；实际分支 `md2word/TR-403`。用户已批准 revision 3。本文记录实现证据，不替代人工验收、线上实译或 Word 签字。实施准入见 [preflight](implementation-preflight.md)，候选复核见 [review](implementation-review.md)。

## 结果与未完成门禁

本地完整性、双入口、物理身份及隐私定向验证通过；P1 环境 preflight 未通过，translation-core 矩阵未运行。普通 CI 没有调用真实外部模型。尚未运行真实 S3/MySQL 并发、线上四方向实译和 Word/WPS 人工验收；不以 fake 宣称这些已通过。

原实现子代理执行审计因本机会话配置指纹在执行期间变化而不能完整聚合；旧 plan 不改写，配置不恢复。主会话直接执行了 128 项集中定向测试，并在 P2 修正后执行 50 项受影响回归与最终 release，取得不依赖子代理自报的本地检查证据。独立审查审计与其覆盖范围另见 review。

## 已实现的边界

- `protected_tokens.py` 继续唯一拥有有限检测/编码/恢复规则；新 `integrity.py` 对源项与 ledger、typed DTO、ID 首错优先级、占位次数/归属和恢复后逐 item 技术多重集负责。成功结果冻结，失败不返回部分 replacements。
- 同步、正式 Worker 与本地 adapter 共用准备和 Validator。按实际编码文本预算切批，保留原文 char_count；Provider 只收到编码 DTO。固定完整性协议附加在已绑定 Prompt 后，原 Prompt 快照 hash 不变。
- Worker 只登记验证后恢复文本与安全 evidence；fan-in 从本地权威 job/batch/source/config 构造预期 binding，验证真实字节 checksum/size、来源、generation/attempt、完整有序 ID、哈希/计数/类型和逐项技术 inventory。所有叶子通过才 apply。
- 首次尚无 batch 的预算失败保持顶层 `translation_failed`；既有 `stage_failed.payload.integrity` 保存 `translation_request_budget_exceeded` 和摘要，binding=null，不伪造 batch 或 AI log。
- 生成件 object_key 增加本次 file_id 层，覆盖共享文件服务的 source IR、batch result、目标 IR、主 DOCX 等生成件；同名多次登记不覆盖已登记字节。上传 key、下载名、旧 key 按记录读取、安全片段和 S3 prefix 保持。
- 审计只记录哈希、计数、版本和受信关联；恶意返回 ID 仅留 hash。外部异常固定安全消息；每次真实调用一次审计，预检零调用不伪造记录，审计失败可见且不重复记录。
- 既有 DTO、新准备/验证结果和真实术语匹配产生的 `_TermMatch.context_snippet` 均有字段级 repr 隐私控制；业务值、dataclass 字段、asdict、相等性、frozen/slots 和快照 hash 保留。asdict 仍为敏感内容，不可写普通日志。

## AC1–AC12 证据

下表均位于本次实际运行的测试集合。名称是定位锚点，不把子测试数量相加作为唯一用例总数。

| 验收 | 定向证据 | 结论与边界 |
|---|---|---|
| AC1 | `test_legal_natural_language_and_in_item_token_movement`、`test_worker_restores_before_persistence_and_fan_in_revalidates` | 合法自然语言、同 item 移动、重复技术值正常恢复。 |
| AC2 | `test_id_first_error_priority_is_duplicate_missing_extra_then_order`、`test_fake_provider_dto_shape_cannot_bypass_validation`、`test_strict_json_rejects_wrappers_duplicate_keys_extra_fields_and_coercion` | 缺失/额外/重复/乱序、类型/额外字段/包装/重复 key 显式失败；不 trim/coerce。 |
| AC3 | `test_input_and_metadata_are_checked_before_response`、`test_placeholder_ownership_count_and_syntax_are_fail_closed`、`test_source_literal_collision_is_restored_once` | ledger、空 ledger 保留串、缺失/重复/未知/损坏/错项均拒绝，字面碰撞仅恢复一次。 |
| AC4 | `test_supported_technical_categories_roundtrip_and_reject_extra_literals`、`test_inventory_is_per_item_and_preserves_multiplicity_and_category` | 数字/范围/单位/地址/位字段/公式/型号及既有类别逐项多重对账，保留占位后追加裸技术值失败；语法限于已接受 Codec。 |
| AC5 | `test_second_item_technical_failure_returns_no_partial_and_changes_nothing`、`test_bad_second_item_or_later_batch_never_applies_partial_replacements`、`test_bad_second_item_is_atomic_and_preserves_specific_retryable_codes` | 失败第二项/后批次均零 apply，无成功结果，源数据不变；修正 fake 后既有失败批次可重新请求成功。 |
| AC6 | `test_worker_restores_before_persistence_and_fan_in_revalidates`、`test_fan_in_rejects_missing_evidence_origin_generation_attempt_hash_shape_and_technical_changes`、`test_fan_in_rejects_overlap_between_successful_leaf_batches` | 同一核心、恢复后落盘、消费前重核；缺证据/错关联/代次/尝试/哈希/类型/重叠拒绝。既有截断拆分和翻译重试回归通过。 |
| AC7 | `test_success_and_integrity_failure_each_have_one_redacted_log`、`test_arbitrary_provider_exception_text_is_not_audited_or_rethrown`、`test_invalid_dto_shape_does_not_break_safe_failure_audit`、`test_first_plan_budget_failure_keeps_translation_code_and_safe_evidence`、`test_audit_failure_is_visible_and_never_recorded_twice` | 正常/失败安全 evidence，恶意正文/ID 不进普通审计/事件；预检无假调用；首次计划错误分类与摘要闭合。 |
| AC8 | `test_encoded_budget_splits_deterministically_and_keeps_source_char_count`、`test_single_encoded_item_budget_failure_happens_before_provider_and_audit`、`test_protected_spans_exclude_terms_without_changing_natural_term_offsets`、Prompt profile 模块 | 实际编码预算、确定性批次、保护跨度排除、原 Prompt hash 与协议可追溯。非完整 Prompt tokenizer 预算。 |
| AC9 | `test_opa228_public_fixture_uses_formal_converter_fake_provider_and_validator` | 公开 OPA228 最小 MinerU fixture 的正式 converter→fake→Validator→目标 IR；pages/layout/assets/表格 DOM/span/公式保真。非四方向实译。 |
| AC10 | `tests.test_document_job_modes`、5 项既有 FastAPI Worker 用例、retention 用例、默认 release | direct 零 Provider/Prompt/翻译术语、现有主 DOCX/权限下载相关回归、历史 Artifact、截断/重试保持；新 generation 不消费旧译文。源码确认未改发布规则/权限状态机。非全站人工权限验收。 |
| AC11 | `tests.test_generated_artifact_identity`、两项 `test_late_old_generation...` / `test_late_old_attempt...` | local_file/local_object 真实临时字节、fake S3，同名重复生成件和历史 key；晚到旧执行被既有 CAS 拒绝后胜出/历史字节与 checksum 不变。不是完整分布式 lease fencing 或真实 S3 并发证明。 |
| AC12 | `test_existing_dto_repr_hides_text_prompt_context_and_untrusted_id`、`test_real_term_match_context_is_hidden_without_changing_trace`、正常结果冻结测试 | 真实术语准备/匹配/context/filter/dedupe/trace 路径有实际命中；spy 只观察，不替换匹配/context 逻辑。直接/列表/trace repr 无标记，真实 context、asdict、位置、相等性、frozen/slots 保留。 |

## 实际命令及结果

所有 Python 命令均加 `PYTHONDONTWRITEBYTECODE=1`，不写 pycache。

### 基线

```bash
.venv/bin/python -m unittest tests.test_document_ir_translation tests.test_protected_tokens
```

实施前 35 tests / OK，退出 0。

### 主会话集中定向门

```bash
.venv/bin/python -m unittest \
  tests.test_translation_integrity tests.test_document_ir_translation \
  tests.test_protected_tokens tests.test_translation_profile_prompts \
  tests.test_translation_integrity_execution tests.test_generated_artifact_identity \
  tests.test_artifact_retention.DocumentFileRetentionTests \
  tests.test_document_job_modes tests.test_conversion_sandbox_dev_tools \
  tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_document_job_en2zh_worker_translates_ir_and_saves_ai_audit_artifacts \
  tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_document_job_en2zh_translation_failure_records_ai_call_log_without_full_text \
  tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_document_job_en2zh_truncated_batch_is_split_and_fanned_in \
  tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_document_job_retry_translation_failure_resumes_after_mineru_and_filters_old_files \
  tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_document_job_en2zh_debug_full_text_is_admin_only
```

128 tests / OK，退出 0，3.896 秒。之后仅 execution.py 和其 integration 测试发生 P2 修正；核心 71 项与存储/retention 8 项输入未再变化，复用通过证据。

### P2 修正后的受影响门

```bash
.venv/bin/python -m unittest \
  tests.test_translation_integrity_execution \
  tests.test_conversion_sandbox_dev_tools tests.test_document_job_modes \
  tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_document_job_en2zh_worker_translates_ir_and_saves_ai_audit_artifacts \
  tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_document_job_en2zh_translation_failure_records_ai_call_log_without_full_text \
  tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_document_job_en2zh_truncated_batch_is_split_and_fanned_in \
  tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_document_job_retry_translation_failure_resumes_after_mineru_and_filters_old_files \
  tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_document_job_en2zh_debug_full_text_is_admin_only
```

50 tests / OK，退出 0，3.688 秒。随后把新测试无 DOCX 断言的类型名改为真实 `generated_word`，业务未变；下列单测再次通过（1 test / OK），无需重复整套：

```bash
.venv/bin/python -m unittest tests.test_translation_integrity_execution.TranslationIntegrityExecutionTests.test_first_plan_budget_failure_keeps_translation_code_and_safe_evidence
```

初始 fixture lambda 参数/空 target 指针预期错误先修正；可靠反例已在业务修正前明确得到 `document_ir_failed != translation_failed` 的断言失败，业务修正后通过。核心先前 TDD 也确认裸 999 V、真实匹配 repr 和 persisted bool/float 类型反例失败后再修正，不靠削弱断言通过。

### 项目默认 release 门

```bash
.venv/bin/python scripts/ops/check_release.py
```

初始候选退出 0、202 tests / OK（6.125 秒）；独立复核暴露 P2 后输入已变化，因此最终候选再次执行，退出 0、202 tests / OK（5.548 秒）。OpenAPI 一致性通过，changed=false、164 paths/322 schemas；脚本既有 mock frontend contract/smoke 检查通过。未改 generated types。只有临时 loopback HTTP 测试夹具，没有启动常驻业务 API、MySQL/Redis/Celery、浏览器或模型。现有 Starlette/httpx 与旧 HTTP 状态常量弃用警告保留，未为本任务修改依赖。

### 环境门与未运行项

```bash
.venv/bin/python scripts/ops/run_p1_translation_regression.py --preflight
```

实际退出 1。manifest 样本检查 available=3/required=1/missing=[]；`p1_auth_missing`、`p1_runtime_unreachable`。缺 P1_TRANSLATION_PASSWORD/P1_TRANSLATION_BEARER_TOKEN，在认证 session 构造处停止；不代表模型或运行时 HTTP 故障已被实测。未重试相同环境，未读取私密凭据或启动服务绕过。阻断来源是既有环境，不是本次代码失败。

未执行 `run_local_mineru_quality_matrix.py --mode <mode> --sample-set translation-core`：该样本集合不存在，已注册的仅 phase2-core/ru2zh-acceptance，方向仅 direct/en2zh/ru2zh；不为 TR-403 越界建设 TR-407 样本体系。公开 fixture 和 fake 测试只补本地组件证据。

未运行真实供应商付费模型、真实 S3/MySQL、全仓全套、浏览器 E2E/前端 build 或 Word/WPS 人工检查。无 API/DB/前端业务变化，未加不相关检查。没有新的 quality flag、feature flag、配置或依赖，故没有默认值/snapshot/移除条件和 DB backfill/兼容窗口要实现。

### 最终轻量检查

收口已实际执行：`git diff --check` 退出 0；`python3 .trellis/scripts/task.py validate .trellis/tasks/10-21-tr-403-translation-integrity-validator` 退出 0，implement/check 各 8 entries，All validations passed。context 仅新增 Validator Spec，其余已有相关上下文保留；无全仓无差别加载。新未跟踪任务/源码/Spec 文本另检查行尾和最终换行，无错误。

起始 1466 个文件逐一核对：24 个原路径变更、8 个新路径均属于本任务预期集合，无越界路径；非 TR-403 manifest 文本完全一致。原 parent task、journal、backlog、CON-104 及其他任务文件保持初始哈希。实际 HEAD 仍为 c8fd2afc7dfea349b7fbc3e1f516d85adcb57536，分支 md2word/TR-403；无暂存文件，无提交/push/archive。manifest=review，Trellis=in_progress，人工验收 pending。

## 兼容、并发与回滚

- 无 OpenAPI/HTTP DTO/数据库 schema/迁移/前端路由/query key/URL/generated types 改动，无第二套状态机或新权限。内部 prepare 返回值和本地 request v2 是本次明确的兼容变化。
- 历史完成件按旧登记 key 读；活跃旧中间结果缺 integrity 则 fail-closed，不补写 passed。上线先暂停翻译入队/排空旧 Worker 和活跃旧代，再同步部署调用端与 Worker，不混跑；无 backfill 或历史重写。
- generation/attempt 及已有状态条件更新继续权威；新 key 保证物理字节隔离，不把 CAS 拒绝当作存储不可覆盖证明。既有 retry 沿用权威不可变 source IR，其创建代次可以旧于消费代次；新 batch/result/evidence 必须绑定当前 generation 与准确 source file/checksum。无新增事务、锁或调度算法，不声称解决全局 lease fencing。
- 主任务失败产品策略、目标语言/术语后验 QA、上下文/新回填 ID、正式矩阵仍范围外。一个任务一个用户主 DOCX、direct 零 AI、MinerU 唯一入口、原生表格及下载/批准/发布边界保持。
- 回滚先暂停相关翻译执行，允许撤回 Validator/接线差异但不恢复无校验回填；保留物理隔离和 repr 隐私，不能恢复共享路径覆盖。无 DB 逆迁移、覆盖已发布文件或删除审计。需修改冻结语义时停止并回到规划，不在当前任务实现。
