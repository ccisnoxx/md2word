# RND-504 实施与验证计划

## 0. 当前门与实施前置

用户于 2026-10-17 审核接受修订 2 的规划及候选实现，并明确确认三笔提交与收口计划。实现位于独立工作区 `/Users/sc/.codex/worktrees/rnd504-implementation/md2word`，分支 `md2word/RND-504`，基线 `033cb61`。本子任务已由 `task.py archive --no-commit` 归档为 completed，manifest 仅 RND-504 标 done；准确路径及工作提交见 validation.md。生产 backend 继续 disabled，不部署、不 push、不开始其他任务。

- [x] 用户审核当前 prd/design/implement 并在后续消息明确批准实现；重新核对依赖 CON-103 为 done，人工已接受。
- [x] 准备包含 `bd828da` 及 CON-102 的独立工作区，实际分支 `md2word/RND-504`、基线 `033cb61`；原根 HEAD `4c40e6c` 保持不变。
- [x] 重核全部 dirty 与任务状态，原目录 310 个 dirty 文件按字节建立保护基线；只复制本任务规划，新工作区父任务仅加当前子项，manifest 仅修改 RND-504。
- [x] 读取本任务三份文档、curated contexts、相关 Spec 和真正基线源码；如发生接口漂移，先更新规划，不借机实现后续任务。
- [x] 用户授权及前置满足后，在独立工作区执行 task.py start；返回 planning → in_progress，原目录未执行 start。

## 1. 有序实施任务

### 1.1 端口、策略与错误合同

- [x] 建立 PreviewPolicy/Result/Failure 和 WordPreviewProvider，输入仅为 DOCX bytes/策略，不导入 DocumentIR、LLM 或仓储。
- [x] 严格验证可选页面语义、正页数、资源预算和机器错误码；区分 unavailable、永久错误、暂态和 stale/busy。
- [x] 在测试中实现 fake provider/受控 executor，覆盖成功、暂态、超时、损坏输入、空/非法输出；fake 不暴露为 Settings 生产 backend。
- [x] 固化 design 中 word-preview-exec/v1 的 argv、request/result/describe schema、退出码和 profile 身份；生产 adapter 必须通过 tests-only 真实子进程的成功协议路径，不能只测 unavailable 或内存 fake。

### 1.2 私有状态和原子仓储边界

- [x] 新增可选 word_preview_state 和纯 claim/finish/reset 规则，JSON payload 缺字段可读，不改 SQL schema，不重做 CON-103 迁移。
- [x] 在同一首次 claim 原子写入有界历史去重账本，明确 key 作用域、fingerprint/冲突和 max_runs_per_result；整段当前结果有效期不淘汰已消费 key，达到上限拒绝新 key，旧 key 仍幂等返回。
- [x] 扩展仓储窄方法并同步 file/sqlite/mysql；沿用原锁/短事务和质量投影，不在锁内执行 provider/storage I/O。
- [x] 锁内比较 generation、选定 result/receipt、hash/profile、revision/token/lease；区分首次 running/uploading 和未发布 succeeded 的内部重试，保留旧执行 CAS 终态拒绝。
- [x] retry/换件清当前预览，不删历史；published/删除/归档/取消/过期尝试拒绝。legacy 无 receipt 预览重试明确 conflict，既有 DOCX 下载保持。
- [x] 实现最小 quality_state 贡献 owner，接入既有 delivery_state 的 published 检查→重置/质量合成→批准/交付失效顺序；预览只替换自身贡献，基础/其他/未知阻断保留。无 producer 的显式同值 blocked 也记录，普通进度/receipt 补丁不重复记录；成功恢复可证明基础状态，不等待后续任务或恢复旧批准。

### 1.3 Artifact 和授权

- [x] 新增三种 preview file_type，复用 FileUploadService；所有文件名服务生成且带完整 attempt 身份，避免现有同文件名对象键覆盖。
- [x] 保存 word-preview/v1 manifest、来源 hash/ID/profile、PDF/可选页面描述；输出全成功且检验通过后才提交当前 manifest。
- [x] 继承并限制保留期，文件过期/删除不可复活；部分失败保留可追踪诊断，不删 DOCX，不引入第二套清理框架。
- [x] 任务文件列表和 Token 授权只认当前提交引用，不能走同 retry_count 的宽泛 fallback；主 DOCX 仍为默认下载。
- [x] 分别验证本地读取时重校验和 S3 签发时检查；预览 presign TTL 限于既有上限/主件及文件有效期，明确已签直连 URL 不即时撤销，不额外建立下载代理。

### 1.4 应用编排与配置

- [x] 在选定 receipt 后、执行完成前接入 preview，延续主件 identity；不把外部排版进程放进 docx_quality.py 或 renderer。
- [x] 自动重试预算持久化、租约接管、重投复用；内部 retry_word_preview 校验 user/reason/request ID，只重试失败/不可用的当前主件预览，不新增 HTTP 路由或任务 generation。
- [x] 预览失败可完成 succeeded+blocked，元数据或主件存储不能确认时保持原失败/恢复合同；不得改变 integrity fail-closed。
- [x] Settings/runtime 注入默认 disabled backend、profile/required/预算；新任务快照和 clone/retry 语义按 design 固化，历史任务不自动回填。
- [x] 交付完整生产 adapter/协议校验与符合性测试；运维依赖是实现固定协议的已批准引擎/解码器 launcher 和隔离环境，不把 adapter 或协议设计留给运维。无批准引擎不安装、不裸跑、不用插件缓存兜底、不选 SaaS。
- [x] 对生产 timeout、进程组、临时目录、输入 ZIP 和输出文件执行受控 executor 测试；独立复核的 XML 编码缺口已修并通过定向回归；真实 sandbox readiness 缺口保持未启用。

### 1.5 观测、合同与收口

- [x] 记录 preview 生命周期事件和内部重试审计；公开摘要只用白名单，不含 lease token、stderr、全文、密钥或绝对路径。
- [x] 检查 detail/incident 等所有 presenter 没有泄露私有状态，默认下载和原 available actions 无回归。
- [x] 按第 3 节集中验证稳定候选，修复首轮独立复核 3 项缺口；新增行为测试保护真实合同，最终 fresh 复核确认闭合。

## 2. 计划修改文件

以下为实现范围白名单方向，最终精确清单以获批基线和实际 diff 为准；不得仅因列出目录就大范围重构。

| 文件 | 计划内容 |
|---|---|
| `app/services/preview/__init__.py`、`models.py`、`provider.py`、`sandbox_adapter.py`、`executor_protocol.py`（新增） | 端口/类型、正式执行协议/校验及可执行生产 adapter；不选 SaaS 或安装引擎。 |
| `app/domains/document_jobs/preview.py`、`preview_state.py`、`quality_state.py`（新增） | preview 编排、历史请求去重及最小可归属质量合成；不建立 QualityRun。 |
| `app/domains/document_jobs/models.py`、`repository.py` | 可选私有状态、事件类型及窄 CAS 合同。 |
| `app/infrastructure/persistence/{file,sqlite,mysql}/document_jobs.py` | 三 adapter 的 claim/finish 与既有投影；不新增 DDL。 |
| `app/domains/document_jobs/execution.py`、`result_state.py`、`delivery_state.py`、`service.py` | receipt 后接线、质量合成/批准失效顺序、换代清理、快照/clone、授权和文件过滤。 |
| `app/domains/files/models.py`、`service.py` | 新 file_type；复用登记机制，仅在现有入口确需约束时调整，不重写 storage。 |
| `app/domains/files/result_registration.py` | 首轮复核修正：带明确 marker 的 pending preview 生命周期、到期不可确认 uploaded；原 generated_word 物化限制保持。 |
| `app/core/config.py`、`runtime.py`、`app/main.py` | Settings 与运行时注入。 |
| `tests/test_word_preview_provider.py`、`test_document_job_word_preview.py`、`test_document_job_preview_persistence.py`（新增） | 端口/安全、组件/权限、三 adapter/并发故障。 |
| 既有 execution_stages/result_persistence/delivery_state、FastAPI/files/config 定向测试 | 按真实新增覆盖缺口调整，不复制已有测试。 |
| `docs/design/docx-rendering-template-design.md`、`quality-review-release-design.md` | 明确新增能力与仍属于后续任务的内容。 |
| `docs/runbooks/backend.md`、`docs/dev/backend-local-setup-and-architecture.md` | 配置、启用证据、停用、兼容写者和恢复。 |
| `.trellis/spec/backend/word-preview-contract.md`（新增）、`index.md`、`database-guidelines.md`、`word-generation-rules.md` | 固化 owner、CAS、文件绑定与验证，更新 materially stale 合同，不复制产品 PRD。 |
| `docs/api/openapi.json` / API 文档 | 运行 current 检查；仅实际公开 schema 改变时更新快照。内部字段不应导致公开 schema 漂移。 |

不计划修改 SQL schema、数据库迁移脚本、DocumentIR、MinerU、翻译 Prompt/术语、renderer 布局、前端路由/页面/generated types、部署基础设施或后续任务状态。

## 3. 定向测试和回归门禁

### 验收到测试的映射

| AC | 最小可靠验证边界 |
|---|---|
| AC1/2/8 | 新 provider 模块：正式最小 DOCX + 有效合成 PDF/PNG；fake 组件之外，必须经生产 adapter 启动真实 tests-only 子进程执行 word-preview-exec/v1，断言 request/describe/result、退出码、profile/hash、路径、timeout/kill/cleanup、预算、页面开关。真实 sandbox/引擎实证另列，不能由内存 fake 替代。 |
| AC3/7 | 应用组件：固定主件 ID/hash/字节及下载；基础 pending/warning/passed 在预览失败→成功后分别恢复，原有/未知/并发新增 blocker 保持 blocked，旧批准不恢复。包括预览已 blocked 时无 producer 写入同值 blocked，以及普通进度/receipt 补丁不误变为未知阻断。 |
| AC4 | 三 adapter 幂等：A 失败→B 失败→重启→A 重放不增加 run/attempt/provider；同 ID 不同 fingerprint 冲突、历史满额拒绝新 key/保留旧 key；claim 后、事件/manifest 前崩溃仍只消费一次。预览独立重试不调用 MinerU/LLM/renderer。 |
| AC5 | 新三 adapter 合同：并发 claim、双完成、过期接管、旧 lease/generation、重试与删除/归档/published、legacy 无 receipt、崩溃窗口；file/SQLite 用真实本地锁/事务，MySQL fake 只证明 SQL/规则。 |
| AC6 | 定向 FastAPI 集成：当前 manifest、owner/Admin/跨租户、本地伪造/过期/旧引用 Token、旧代/部分文件、无 public preview 路由；S3 mock 验证拒绝旧引用签发及有限 TTL，不声称已签 URL 可即时撤销。 |
| AC9 | 既有 execution/receipt/delivery-state 与 direct 零 AI、OOXML/原生表格；component、OpenAPI/release、线上 Golden/人工 Word 按下文分层。 |

### 获批实施后的命令

先在正确依赖基线运行受影响现有模块作为基线；实施中只在接口或故障定位确有需要时定向运行，稳定候选统一执行：

```bash
.venv/bin/python -m unittest tests.test_word_preview_provider tests.test_document_job_word_preview tests.test_document_job_preview_persistence
.venv/bin/python -m unittest tests.test_document_job_execution_stages tests.test_document_job_result_persistence tests.test_document_job_delivery_state tests.test_document_job_modes
.venv/bin/python -m unittest tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_document_job_operator_scope_and_admin_visibility tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_document_job_download_url_returns_temporary_generated_word_link tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_document_job_files_endpoint_lists_artifacts_and_authorizes_source_download tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_document_job_file_download_rejects_mismatched_and_expired_files
.venv/bin/python scripts/ops/export_openapi.py --check --no-diff
.venv/bin/python scripts/dev/run_component_pdf_regression.py --sample-id ti-opamp-opa228-p1-smoke --output-dir tests/tmp/rnd504-component
.venv/bin/python scripts/ops/check_release.py
git diff --check
```

三个新模块已交付，修正后完整 40 项通过；既有四模块及指定 API selectors 62 项通过，修正后 retention/receipt 22 项及单个 API selector 通过。component 仅运行已提交最小 OPA228 样本 1/1；正式 renderer→preview→Artifact/下载另由新增应用测试覆盖。修正后最终 release 门 202 项通过且 OpenAPI current（未变化）。具体执行、成功证据复用与外部缺口见 validation.md，不能把这些结果称为线上预览或 Word 视觉通过。

`check_release.py` 是 API/DB 合同变更的显式项目门，在稳定候选集中运行；首轮复核修正涉及共享文件登记/生命周期后补跑最终门。它已包含 OpenAPI，复用同一证据，不为每个文件/子步骤重复全门禁。无前端 UI 改动，未跑前端全量测试、build 或浏览器矩阵。

任务提示词要求的线上 Golden 命令为 `.venv/bin/python scripts/ops/run_golden_sample_regression.py`；它依赖认证、API/Worker/MinerU 与真实环境。本次未配置认证且未获部署授权，仅做离线缺凭据分支确认，没有完整 preflight 或在线提交；环境阻断、替代 OOXML/hash/component 证据及 pending 见 validation.md。未擅自启动 API/Worker/MinerU/数据库服务、连接 VPS 或部署；测试内短生命周期 fixture 不作为线上证据。生产 engine/font/sandbox 和 Microsoft Word 人工验收同样需要另行记录版本、输入/输出 hash 和当前候选。

## 4. 独立复核、回滚和完成定义

首轮 fresh 复核确认 metadata 不可确认仍完成、成功复用 key 未消费、UTF-16 活动内容拒绝缺口；按 `implementation-review.md` 修正并重验。增加 preview 的 metadata-first pending 登记与既有生命周期复用属于原可追踪/失败关闭合同的修正，不新增 SQL schema、转换链或产品功能。

- [x] 实现触及 receipt、持久化 CAS 和授权，完成两次 fresh 只读 `critical_reviewer`：首轮 3 项发现均已修正，最终复核无新确认阻断。multi-agent-orchestration 四阶段审计 finalize/verify 通过，不以实现者自检替代。
- [x] 逐 AC 在 validation.md 填真实证据与缺口；adapter_contract_ready=true（含正式子进程成功协议）、production_ready=false，backend 保持 disabled，待人工验收。
- [x] 回滚点已固化：R1 可撤回本任务未部署增量；R2 仅以兼容版本停用 backend/新重试，保留私有状态、preview/主件/审计；不回退旧 writer、不 DROP。此项记录方案，未实际部署或演练回滚。
- [x] 已核对原始不可变 receipt、发布/审核保护；disabled 不自动清 blocked。启用时先兼容 API/Worker 再获批 profile 的顺序已写 runbook，本轮未部署。
- [x] 所列文档/Spec 已同步，中文注释/docstring/开发者文本和实际 diff 已检查；临时日志/进程已清理，样本证据保留在指定 ignored 位置。
- [x] 实施阶段按授权停在 review/in_progress，随后用户明确验收并确认三笔提交计划；现按独立授权归档当前子任务、manifest done、记录会话，不部署、不 push、不开始 RND-505/506。

规划阶段完成定义（已完成）：三份文档可审阅、无阻塞性产品问题、最小 context 的路径与理由有效、task.py validate 退出 0、manifest 仅本任务条目变更、父任务仅新增本子任务引用、已有 dirty 保留；用户随后明确批准实现。

规划独立审查未再次创建任务或改变父子关系；三项确认发现及 S3 证据边界按 `planning-review.md` 追踪。当前实现的真实回归及独立复核记录在 `validation.md`，不以规划阶段的静态检查替代。

## 5. 人工验收后的收口

2026-10-17 用户明确验收并批准三笔计划：37 个实现/测试/Spec/运行文档文件先提交；本子任务 12 个文件直接以归档路径入库，连同父任务引用及 manifest 作为第二笔；最后仅更新独立工作区的 journal/index 作为第三笔。archive 与 add_session 均使用 --no-commit，逐笔核对暂存白名单后提交，不 amend、不 push。归档后修正 implement/check research 路径并重新 validate；无业务变更，复用已验收测试证据。生产仍未就绪，disabled 不清理 blocker；原目录全部 dirty 保留。
