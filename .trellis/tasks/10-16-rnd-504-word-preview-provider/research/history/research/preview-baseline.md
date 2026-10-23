# RND-504 只读调查与规划依据

2026-10-16，初始规划轮；未运行业务测试、预览引擎、数据库迁移或线上服务。初始调查未创建子代理；2026-10-17 的一次独立审查及修订另见 planning-review.md。

## 1. 工作区、依赖与历史

- `pwd` 确认 `/Users/sc/PycharmProjects/md2word`；`git status --short` 有父任务 task.json、工作日志、manifest 的已有修改及 SC1259/IR/TAB/归档任务未跟踪树。本轮开始有 300 个 dirty 文件，修改前已记录其保护基线；不能清理或覆盖。
- 当前根 HEAD=`4c40e6c52bde072a7ad3afab67eb425f757bd33c`，分支 `md2word/TAB-306`。`git merge-base --is-ancestor bd828da... HEAD` 退出 1，证明根目录不含 CON-103。
- CON-103 manifest=done；`.trellis/tasks/archive/2026-10/10-16-con-103-quality-review-delivery-state/completion.md` 记录人工接受、实现 `bd828da4e3a3025856afd758e0b0a686ff6ccb72`、Trellis `80b82db` 和归档。归档 `task.json` 状态为 completed。
- 已验收代码可在 Git 对象 `033cb61e3f6ac91f5d324790eb1a8ea920b783de` 只读调查；`git merge-base --is-ancestor bd828da... 033cb61` 退出 0，其历史包含 CON-103 与 CON-102。对应 checkout 为 `/Users/sc/.codex/worktrees/con102-implementation/md2word`，本轮不修改该 checkout，也不切换根分支。
- CON-103 明确保留真实 MySQL/InnoDB/部署文件系统锁的生产写者启用门，以及事件/状态不跨仓储原子提交的限制；done 不等于生产已启用。
- BAS-001 的 `docs/implementation/baseline-verification-2026-10-12.md:32` 和归档 `research/current-capabilities.md:22` 已区分开发视觉工具与任务级预览。本轮搜索重核未发现正式 Provider；delete-preview/replay preview 是不同业务。
- 通过 `rg --files --hidden .trellis/tasks` 及父任务 children 检查，无 RND-504 既有子任务。随后用 create + --parent + --no-start 建立唯一任务，不启动会话。

## 2. 已读取的权威资料

根 `AGENTS.md`、`.trellis/workflow.md`、guides/backend/frontend indexes、backend directory/database/error/quality/logging 规范及 Word 生成规则的正式 owner/质量/回归边界。

本任务完整目标资料：

- `docs/product/prd.md`：FR-010/012/013/015/016 与冻结模式、角色和状态。
- `docs/product/scope-and-decisions.md`：PD-001..020；不允许新增在线编辑、批量、双语等产品边界。
- `docs/implementation/implementation-plan.md`：R5 预览 adapter、Artifact、重试；失败不破坏 DOCX，但 blocked/禁止发布。
- `docs/implementation/codex-task-backlog.md`：RND-504 完整定义为可替换 DOCX→PDF/页面图 provider、超时/沙箱/Artifact/重试/语义解耦；RND-505/506、QA-602/605 各自 owner。
- `docs/implementation/codex-execution-guide.md` 与 `codex-task-manifest.yaml`：规划三件套、状态、依赖和门禁。
- `docs/decisions/architecture-decisions.md`：ADR-001/002/003/004/005/007/010/012/014/015/016。
- `docs/contracts/document-ir-contract.md`：IR 不携带 Word/Provider 状态，Artifact/hash/路径与版本合同。
- `docs/design/docx-rendering-template-design.md:207` 起的 Word 预览端口与 PDF/可选 PNG/页数；以实际章节为稳定索引。
- `docs/design/quality-review-release-design.md`：preview failure blocker、状态分离、授权、不可变发布、目标 API。
- `docs/engineering/testing-acceptance-strategy.md`：fake/组件/仓储/API、样本分层、线上门及 Word 人工验收。
- `docs/implementation/codex-prompts/RND-504.md`：本任务精确产物、失败/权限验收、引擎未批准时的 port/fake 边界和停止条件。
- 父任务三件套/task.json，以及 CON-103 completion/research 和 BAS-001 preview 调查记录。现有 task 文档已提供相关历史决定，无需另搜私人会话。

## 3. 当前实现与可复用合同

以下行号对应 `033cb61` 的 immutable Git blob，不能直接拿根目录同名行号当成依赖已整合证据。

| 位置 | 已确认行为 |
|---|---|
| `app/domains/document_jobs/execution.py:2295` `_render_and_save_word` | rendering→quality_checking；`:2412` integrity；`:2445` 候选写入；`:2464` prepare。无 provider/preview。 |
| 同文件 `:2493` `_finish_prepared_result` | 先 materialize receipt 描述，再 CAS succeeded，执行完成时写 result_file_id；适合接入选定主件后的 preview，不应在候选竞争前乱选输出。 |
| `result_state.py:14` / `:37` | matches_current 拒绝终态/删除/归档；prepare 首个有效候选优先；receipt 必须当前 generation/final IR 且有 integrity evidence。 |
| `models.py` DocumentJobPreparedResult / DocumentJobRecord | receipt 绑定 generation、IR 和不可变 DOCX descriptor；新增四状态字段已存在，无 preview 私有状态。 |
| `delivery_state.py:23` | published 先保护原值；换代/换件清状态；首次绑定保留本代质量；blocked 撤销已批准复核。不能另造质量/交付状态机。 |
| `repository.py:25` 起；三 adapter document_jobs | 现有执行 CAS、receipt prepare、retry、review CAS；无 preview claim/lease。file job.lock，SQLite BEGIN IMMEDIATE，MySQL SELECT FOR UPDATE；各自短事务。 |
| `files/models.py:13` | file_type 没有预览种类；metadata 可存描述，二进制不存 DB。 |
| `files/service.py:378` register_generated_content | 计算 SHA-256、写 object、保存记录与 expiry；`:801` 对同 job/type/filename 重用 object key，调用者必须使用独立 attempt 文件名。 |
| 同文件 `:433` register_result_candidate | 主件 protocol 候选先 pending metadata 后写独立 object；descriptor 进入 receipt，不能拿预览覆盖它。 |
| `files/result_registration.py:16` | materialized_file 校验不可变 descriptor、拒绝过期/删除复活，只允许主件协议候选；不能为 preview 放宽主件校验。 |
| `document_jobs/service.py:1617` / `:1636` / `:1661` | 任务文件筛选、归属/类型/expiry、当前代校验；协议主 DOCX 只认完成主指针；其他文件最终有 retry_count fallback，preview 必须专门认当前 manifest 引用。 |
| 同文件 `:1848` / `:1853` | tenant/company + owner/Admin 权限。files service 也有归属校验。 |
| `router.py:607` / `:649` / `:875` | download-url 先 require_current_user；签发 job/file/expiry HMAC Token；download 重验签和当前文件身份，无匿名文件目录。 |
| `schemas.py:99` / `:108` | 状态和 quality_summary 为只读投影；file_type 公共 response 为 string。新私有状态必须经过 presenter 白名单，不能 model_dump 后裸露。 |
| `app/core/config.py`、`app/main.py:223`、`runtime.py:70` | Settings + build_runtime 是依赖注入位置；无 Word preview backend/profile。 |
| `app/services/renderer/docx_quality.py:26` / `:53` | 轻量 ZIP/OOXML 计数、editable 和 flags，不渲染真实页面。此文件不是外部 engine 的 owner。 |

没有正式 `app/services/preview/`；在当前根与 `033cb61` 的 app/tests/scripts 受控路径搜索，未找到 WordPreviewProvider/preview_pdf/preview_pages 或任务级 DOCX→PDF 实现。

## 4. API、DB、配置与工具调查

- `033cb61:docs/api/openapi.json` 的 document-jobs 只有 files、download-url、download 等现有入口；唯一带 preview 的路径是 delete-preview，没有 Word preview/publish API。响应已有 quality_summary 任意安全 JSON；不需要在 RND-504 提前造 QA-602 路由。
- metadata 三 adapter 保存 Pydantic JSON payload，CON-103 已维护质量/复核/交付/摘要投影列。可选 preview 私有字段可复用 payload，但旧 writer 可能丢弃未知字段，须协调升级/保留兼容写者，不能宣称无迁移风险。
- `requirements.txt` 没有生产 Office/PDF/page 解码运行时依赖。`docs/dev/local-conversion-sandbox.md:171` 的 soffice/Poppler/pdf2image 是开发指导，渲染脚本指向本机插件缓存；不能作为服务器依赖或沙箱证明。本轮未安装、选择或运行这些引擎，也没有读取 .env 或输出凭据。
- `FileRetentionPolicy` 的 file_type 集合来自 DocumentFileType，新增预览类型需验证现有 retention/quota/list 行为；不另建 retention 服务。已有存储的写 object/保存 metadata 不是跨系统事务，须保留并报告部分失败窗口。
- 现有前端为手写类型，预览 UI/同步状态不在本任务；实施时复核 file_type string/JSON 消费者，不扩张生成器或页面工程。

## 5. 测试入口与证据等级

通过 `033cb61` AST 确认：

- `tests.test_document_job_execution_stages.DocumentJobExecutionStageTests`：direct quality 边界、重投、旧 generation、cancel/timeout、质量失败。
- `tests.test_document_job_result_persistence.DocumentJobResultPersistenceTests`：双 renderer、receipt 中断/物化、落选文件/Token、三 adapter、真实 file/SQLite 多进程。
- `tests.test_document_job_delivery_state.DocumentJobDeliveryStateTests`：换件/换代失效、published、review CAS、三存储投影和旧 payload。
- `tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests`：owner/Admin、files/download-url/Token、过期/错配文件、现有 action/clone/旧 QA。
- `tests.test_document_ir_word_renderer_layout.DocumentIRWordRendererLayoutTests`：正式 OOXML/integrity，不能当作预览像素证据。
- `scripts/ops/export_openapi.py --check --no-diff` 存在；不是不存在的 scripts/dev 路径。
- component runner 支持 `--sample-id`、`--output-dir`；Golden runner 默认为真实环境调用，不能伪造离线等效。

这些是入口定位，不是本轮测试通过记录。新 preview 三模块尚未实现，三件套给出待实现测试；没有 fake/MySQL/Word/S3/线上/性能或沙箱运行结论。专有样本不进入规划提交。

## 6. 差距与收敛结论

缺少 provider/生产安全配置、preview 文件类型和 manifest、选定主件后的生命周期桥接、幂等/lease/重试、quality blocked 的 preview 证据及当前引用授权，因此需增量实现，非验证并收口。端口与测试 fake 可在不选择引擎/SaaS 的前提下完成；生产引擎/字体/真实隔离及 Microsoft Word 视觉验证作为明确启用门，而不是用假输出宣称成功。

本方案不修改冻结产品范围、不新增 DDL、不实现后续页映射/页级检测/发布功能。实际实施前重新确认所需依赖提交和部署写者启用门，规划本身保持可评审。

## 7. 独立审查后的规划修订（2026-10-17）

上述源码事实不变。fresh 只读审查确认原规划存在三个合同缺口：自身预览 blocker 成功后不能解除、外部执行协议未定义、只存当前 request ID 不能防历史重放。三份文档已改为最小质量贡献 owner、word-preview-exec/v1 生产进程协议、同锁历史去重账本，并明确本地 Token 与 S3 presign 的不同读取保证。质量贡献合成仅服务已有状态和本检查恢复，不新增 QualityRun/页面规则。receipt/CAS 不放宽，legacy 无 receipt 的预览重试明确拒绝，完成任务使用独立 run deadline。原候选位置、确认依据、采纳及证据边界见 planning-review.md；本轮仍未修改业务代码或运行实现测试。
