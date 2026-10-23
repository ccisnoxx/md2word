# RND-504 实施与验证计划（修订 3）

2026-10-23。当前仅规划，task/manifest=planning；本文件中的后续实施项均未执行。历史修订 2 的完成勾选只在 research/history 中保留，不能当作当前候选已通过。

## 1. 规划完成与实施前置

- [x] 执行 pwd、git status，记录现有 dirty/暂存区及 manifest/父任务基线；不 stash、不覆盖、不切分支。
- [x] CON-103 manifest done、Git 归档 completed 及人工验收可核对；当前四字段状态/下载/文件身份 22 项基线通过。
- [x] 调查目标代码、文档、Spec、API/DB/配置/脚本；找到历史已接受实现与唯一任务，复用身份，不重复 create。
- [x] 源 `931d2f6` 的独立临时快照三模块 40 项通过；完成 37 路径源/目标 blob 清单，12 路径缺失、25 路径已有。
- [x] 编写修订 3 三件套、当前调查/历史快照和最小 implement/check context，验证后停规划评审。
- [ ] 用户在后续消息明确接受本修订与剩余风险，并授权当前任务实现。
- [ ] 核对批准文档 hash、当前 HEAD/dirty、依赖及原子仓储合同无漂移；若目标变化，重新比较并更新评审。
- [ ] 准备获准目标分支/独立工作区；建议 md2word/RND-504 仅为元数据，不覆盖已有同名分支或其他 worktree。当前规划不创建/切换业务分支。
- [ ] 只有获准后，加载 trellis-before-dev、相关 Spec，再对本子任务执行 start；不启动父任务或其他任务。

## 2. 有序实施清单

1. [ ] 按 research/integration-inventory.json 和源 commit 逐 hunk 准备候选，先核验当前接口和导入闭包；不整文件覆盖，不合入 RND-505/506/QA-601 历史后续提交。
2. [ ] 复用 preview 五文件与测试 fake：端口/策略、完整输入输出验证、word-preview-exec/v1 和生产 adapter。缺部署引擎仍 disabled，不安装依赖；真实 tests-only 子进程成功路径必须运行。
3. [ ] 复用 preview_state/quality_state，新增私有可选状态和事件；接入当前 repository 的窄 claim/finish，同步三 adapter，保留 TR-406/CON-103 同 job 锁与投影，不加 DDL。
4. [ ] 适配当前 result_state/delivery_state：保留已发布检查、generation/receipt、公式报告认证和原 fallback warning；按 design §7 的非预览基础→预览贡献→批准失效顺序合成。普通 completion 不把自身 blocked 捕获为未知 blocker。
5. [ ] 复用三类 Artifact，登记采用 metadata-first pending；使用当前共享含 file_id 的生成件 key，不迁入源旧专用路径；保留源/普通 pending、generated_word 物化、到期/删除和禁止代理上传边界。
6. [ ] receipt 物化、当前公式/图片报告重验之后且 completed CAS 之前接 ensure_initial；busy/重投保持等待，存储错误显式传播；不重渲染选定主件。
7. [ ] 接入 Settings/runtime、任务策略快照与 clone/retry、内部受权 retry_word_preview；保留 direct 零翻译资源及快照不可变，不新增 HTTP 入口。
8. [ ] 现有 files/Token 过滤只认当前 manifest，覆盖部分/旧代/pending；S3 TTL 限于主件和预览。保持 CON-104 classification/warning/eligible/enabled 与下载审计，发布仍未启用。
9. [ ] 适配当前 router/事件/incident 白名单，保留公式/图片私有 evidence 和当前 canary；不复制源自由 metadata 或泄露 ledger/lease/路径。
10. [ ] 迁入并适配三组预览测试与实际需要的既有 fixture；先补新的组合回归（公式贡献、独立对象键、CON-104、TR-406），不删除旧断言来迁就接线。
11. [ ] 候选稳定后集中执行 §4 门禁。真实存储/生产沙箱/Word/Golden 未执行项逐项保留 pending，不以历史成功代替目标结果。
12. [ ] 更新相关设计/runbook/Spec，完成 Trellis check；因涉及持久化/权限/并发，安排独立只读 critical_reviewer 检查实际 diff 与尚存具体风险，并核实发现。结束在 review，不提交/push/归档或启动后续任务。

## 3. 计划修改路径及共享合同保留

完整源 37 路径及 blob 已列入 research/integration-inventory.json；下表限定责任，不授权整目录重构。计划以源改动为上限方向，允许不必修改的路径保持原样；新增路径/公开合同或迁移需求须回评审。

| 路径 | 计划工作/必须保留 |
|---|---|
| `app/services/preview/__init__.py`, `models.py`, `provider.py`, `executor_protocol.py`, `sandbox_adapter.py` | 复用源新增文件，验证当前 Python/Pydantic；完整 adapter，不以永久 unavailable 桩交付。 |
| `app/domains/document_jobs/preview.py`, `preview_state.py`, `quality_state.py` | 复用编排/ledger/纯规则；内部单独重试不触发旧转换。 |
| `app/domains/document_jobs/models.py`, `repository.py` | 私有可选 state、内部事件、窄 CAS；保留现有 TR-406 类型/方法。 |
| `app/infrastructure/persistence/file/document_jobs.py`, `sqlite/document_jobs.py`, `mysql/document_jobs.py` | 仅增加预览窄方法/必要 producer 参数，保留所有批次/receipt/复核锁与 SQL 列投影。 |
| `app/domains/document_jobs/execution.py` | receipt 后局部接线，保留 RND-502/503 原件重验、三恢复入口、错误阶段和 winner 安全摘要。 |
| `app/domains/document_jobs/result_state.py`, `delivery_state.py` | 合成顺序和换代/换件失效，保留公式 fallback 警告、first-valid receipt、进度单调和 published。 |
| `app/domains/document_jobs/service.py`, `router.py` | 内部 retry/快照/clone、当前文件授权、Token TTL/安全投影；保留 CON-104 D1，不新增 preview/publish 路由。 |
| `app/domains/files/models.py`, `result_registration.py`, `service.py` | 三类预览、metadata-first 和生命周期；沿用共享生成件 file_id 路径，不改源上传/其他生成件路径。 |
| `app/core/config.py`, `runtime.py`, `app/main.py` | 默认 disabled、策略预算与注入，不改真实部署或密钥。 |
| `tests/test_word_preview_provider.py`, `test_document_job_word_preview.py`, `test_document_job_preview_persistence.py` | 复用三组测试，补当前组合合同；测试子进程不作为生产 backend。 |
| `tests/test_document_job_result_persistence.py`, `test_fastapi_jobs_backend.py` | 最小 fixture/调用断言适配，主 DOCX 写入次数精确、预览额外文件独立计数，不削弱完整性/权限。 |
| `docs/design/docx-rendering-template-design.md`, `quality-review-release-design.md` | 实现后更新已落地边界，保留 RND-502/503 的较新规则。 |
| `docs/dev/backend-local-setup-and-architecture.md`, `docs/runbooks/backend.md` | 配置/协议/停用/恢复、真实引擎批准和兼容写者下限。 |
| `.trellis/spec/backend/word-preview-contract.md`（新增）, `index.md`, `database-guidelines.md`, `word-generation-rules.md` | 复用历史合同并按当前路径/贡献顺序修订，其他已接受合同保留。 |

OpenAPI 预期无 schema 变更；`docs/api/openapi.json` 仅当实际公开差异得到评审后更新，不能为通过快照顺手接受新接口。不计划修改 SQL schema/迁移脚本、DocumentIR、MinerU、AI/Prompt/术语、renderer 布局、前端或部署文件。确需新增非历史路径测试时仅针对本项组合负例并在实际清单说明。

## 4. 定向测试与回归门禁

### AC 与测试映射

| AC | 定向证据 |
|---|---|
| AC1/2 | provider 三层：纯输入/输出、fake 真实 DOCX 组件、正式生产 adapter→tests-only 子进程。有效 PDF/可选 PNG、坏输入/CRC/UTF-16 宏/DTD、协议/退出/profile、大小/像素/页序、路径/FIFO/symlink/hardlink、timeout/进程组/清理负例。 |
| AC3 | 应用测试固定主件 file ID/hash/receipt/下载字节；普通预览失败 blocked 与真实 insert/write/confirm 操作前后失败/响应丢失严格区分，后者不能 succeeded。 |
| AC4/5 | 三 adapter 历史账本、别名 fingerprint、并发 claim/双 finish、lease 接管/重启/deadline、旧代/取消/归档/删除/published。file 双进程与 SQLite 独立连接；fake MySQL 仅 SQL/事务调用形状。 |
| AC6 | 现有 files/download/Token 的 tenant/company/owner/Admin、partial/旧 manifest、期限、本地读取重校验和 fake S3 TTL；不称真实 S3 撤销。 |
| AC7 | 应用+纯规则组合：pending/warning/passed/未知 blocked；失败→成功只撤自身；并发同值 blocked；公式 fallback 与 preview 先后顺序；最终 receipt 的公式/图片认证不可绕过。 |
| AC8 | settings disabled/required、创建快照、clone 保留/刷新、普通 retry 原快照、legacy 无字段/无 receipt、CON-104 eligible/enabled 分离与批准失效。 |
| AC9 | 既有 execution/result/delivery/modes、generated artifact identity、TR-406 translation integrity，component/direct 样本、release/OpenAPI。 |
| AC10 | 当前目标与 source commit 分别记录 command/cwd/PYTHONPATH/SHA；真实引擎/Word/部署状态单列，不能挪用历史门禁。 |

### 获批实施后的命令

以下是计划命令，本次没有在目标运行新预览模块（目标尚无代码）。在实际实施 checkout 根目录使用其 `.venv/bin/python`，或显式现有 Python 绝对路径并令 cwd/PYTHONPATH 指向该 checkout；禁止意外跑源快照或别的分支。

```bash
env PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest tests.test_word_preview_provider tests.test_document_job_word_preview tests.test_document_job_preview_persistence
env PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest tests.test_document_job_execution_stages tests.test_document_job_result_persistence tests.test_document_job_delivery_state tests.test_document_job_modes
env PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest tests.test_document_job_download_availability tests.test_document_job_download_availability_api tests.test_document_job_delivery_state_api tests.test_generated_artifact_identity tests.test_artifact_retention
env PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest tests.test_translation_integrity_execution
env PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/dev/run_component_pdf_regression.py --sample-id ti-opamp-opa228-p1-smoke --output-dir tests/tmp/rnd504-integration-component --no-timestamp
env PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/dev/run_local_mineru_quality_matrix.py --mode direct --sample-set phase2-core --dry-run
env PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/ops/check_release.py
git diff --check
```

direct matrix 先验证样本路径及支持参数，再在有获准样本的环境运行去掉 dry-run 的真实 direct 回归；dry-run 不能记为内容回归通过。样本和 CLI 实际漂移时使用现有脚本真实参数记录，不虚报运行。主 renderer 不改，component 至少 OPA228，保留已接受 RND-502/503 的图/公式结果认证相关 selectors；无需无依据重复全部视觉样本。

`check_release.py` 包含 OpenAPI current/frontend contract/smoke mock；稳定候选跑一次，只有相关后续修改才重跑。无 UI 变更，不计划全前端 build/E2E；若实际触及公开前端合同，再补对应类型/单测/构建/定向 smoke。现有环境没有已配置 lint/typecheck 时如实记录，内存编译不称类型检查。

线上 Golden、真实引擎/validator/fonts/隔离、真实 MySQL/InnoDB/部署 FS/S3 及 Microsoft Word 人工视觉另设启用门；不能以本会话调查授权启动 API/Worker/数据库/VPS 或部署。缺认证/样本/安全授权时记录 pending、替代证据及剩余风险，仍可交付默认 disabled 的 adapter 合同；不得称 production_ready 或真实发布 E2E 通过。

## 5. 文档、Spec、回滚点与完成定义

实施前阅读当前三件套、current-state、历史 source 合同、相关 backend specs。实现后把真实差异写回当前 Spec；历史快照仅作溯源，不把旧 Word 规则覆盖到当前。Python 触及范围注释/docstring/开发者消息按 AGENTS 中文规则检查，不改协议值/错误码。更新 runbook 的 disabled 默认、profile 审批和回滚兼容下限，不扩大到生产安装指南执行。

回滚点：

- R0：本次规划只有任务文档/manifest/父关联，无业务回滚需求；恢复规划时仍需保留原 dirty 与索引。
- R1：新模块未接线，撤回本项新模块不影响主流水线。
- R2：接线后停新预览和相关写者，保持能保留 state/checks/receipt 的兼容代码；disabled 不清质量 blocker、不提升批准。
- R3：保留全部 manifest/Artifact/审计/旧文件，不改已发布件、不执行 DROP；不能回退到会丢字段或复用覆盖对象键的写者。

完成定义：所有 AC 有当前目标候选证据；新组合合同和相关回归通过；无意外业务 diff、路径/权限/状态弱化；文档/Spec 同步；独立实际 diff 复核无未关闭阻断；adapter_contract_ready 与 production_ready 分开报告；仅本任务进入 review 等待人工验收。commit plan、提交、push、归档、日志 bookkeeping、生产启用及后续任务均需另行授权。

本轮出口为三件套及 context 可评审、`task.py validate` 成功，任务保持 planning；不是上述实现完成定义。
