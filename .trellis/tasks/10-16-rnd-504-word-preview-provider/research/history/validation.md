# RND-504 实现与验证记录

2026-10-17 实现、定向验证及最终独立复核已完成并获用户验收，用户另行确认三笔提交计划。当前 manifest 为 done，Trellis 子任务已归档 completed。未写明通过的项均不能当作已验收证据；生产 backend 保持 disabled，adapter_contract_ready=true、production_ready=false。

## 工作区与授权

- 用户于 2026-10-17 接受修订 2 的规划并授权开始实现；范围仅 RND-504，不部署、不提交、不 push。
- 原目录 `/Users/sc/PycharmProjects/md2word`：分支 `md2word/TAB-306`，HEAD `4c40e6c52bde072a7ad3afab67eb425f757bd33c`，实现开始前保护 310 个 dirty 文件的字节，不 stash、不覆盖。
- 独立工作区 `/Users/sc/.codex/worktrees/rnd504-implementation/md2word`，分支 `md2word/RND-504`，HEAD `033cb61e3f6ac91f5d324790eb1a8ea920b783de`；基线工作树干净。
- 此基线包含人工已接受 CON-103 的 `bd828da`，manifest 为 done，归档任务 completed；包含 CON-102。没有从原目录复制其他业务 dirty 或 `.env`。
- 只复制 RND-504 规划目录。父任务仅追加当前子项，manifest 仅更新当前条目；不复制其他任务状态或日志变化。
- 新工作区 `task.py validate` 退出 0（implement/check 各 7 条），`task.py start` 成功返回 planning→in_progress；session pointer 指向当前子任务。

## 验证入口与证据等级

验证使用原目录已有虚拟环境的 Python，cwd/PYTHONPATH 均明确指向独立工作区；未复制环境配置或客户样本。稳定候选集中运行 implement.md 中的定向与项目门禁，实施中仅运行接口/故障所需小范围检查。模型/Agent TOML 配置不是运行时模型遥测，fake MySQL 不证明真实 InnoDB，受控 launcher 不证明实际隔离或排版。

实施前四组既有模块（execution_stages/result_persistence/delivery_state/modes）由实现 worker 执行，报告 58 项通过；最终定向结果另行补齐。无已配置 lint/typecheck 时如实披露，不能将 compile 说成类型检查。

## 已确认的外部环境缺口

2026-10-17 仅检查环境键的存在性，没有输出或复制任何密钥：GOLDEN_SAMPLE_BASE_URL、BEARER_TOKEN、PASSWORD、ADMIN_TOKEN 均未配置，独立工作区无 `.env`。调用现有脚本的 `_build_auth_preflight_check(RegressionConfig())`（只做无凭据分支，不运行 runtime 检查、不联网），返回 `ok=false`、`golden_sample_auth_missing`，退出 1。

因此未运行线上 Golden 提交/轮询、未启动本地 API/Worker/MinerU/数据库、未连接 VPS、未部署。完整 Golden preflight 也未执行；不能把这个离线 auth 检查称为完整 preflight。真实 engine/validator/font/sandbox、真实 MySQL/InnoDB/部署 FS 和 Microsoft Word 人工视觉证据均为 pending，生产不得启用。

## 首轮候选的成功证据（修正前）

- 新增模块首轮 32 项：provider 9、应用 13、persistence 10。未变范围复用先前整组 30 项、最终受影响 provider/应用 21 项及新增 CRC/ZIP ratio/事件摘要 2 个 selector 的成功证据；不是声称重复执行了同一整组 32 项。
- 四组既有模块加 implement.md 的 4 个 FastAPI selectors：62 项通过；主件重写 spy 精确观察 generated_word，保留“不写/恰好一次”并另外检查 manifest 追加，没有放宽原保证。
- compileall 与 git diff --check 通过；无 backend lint/typecheck 配置入口，venv 无 ruff/mypy/pyright，未称通过。
- component：`run_component_pdf_regression.py --sample-id ti-opamp-opa228-p1-smoke --output-dir tests/tmp/rnd504-component`，1/1 通过。输出 DOCX 53,165 bytes，SHA-256 为 `sha256:3dc90d8e3ecb3a9ec7d77cd01a9c74aeb8a750b98160addba2e7ca039195026e`，报告及 DOCX/IR 在 ignored `tests/tmp/rnd504-component/20261016T163804Z`，为本轮评审保留。
- `check_release.py` 退出 0：202 tests / 5.167s，OpenAPI current、changed=false、164 paths/322 schemas，frontend-contract/frontend-smoke-mock 通过；复用此 OpenAPI 证据，未额外重复 standalone check。
- 主会话实际加载 Settings（不读取 .env）确认 backend=disabled、required=false、render_pages=false；没有修改生产配置或部署。
- 首轮独立复核后仍确认 3 项合同缺口，因此上述成功结果不能作为候选已满足全部 AC 的结论。具体反例、修正和 fresh 复核见 `implementation-review.md`；修正后的受影响验证将另行记录，旧证据只在相关输入未变时复用。

## 工作树与资源核对

主会话已确认原目录 310 个 dirty 文件字节全部一致、无新增/缺失，原 branch/HEAD 不变。独立工作区相对 `033cb61` 的 manifest 仅 RND-504 block 变化，父任务仅追加当前 child，其余字段相同，暂存区为空。未发现本轮 word-preview executor、component 或 release 监听进程残留。worker 的 5 个一次性测试日志已删除；component 输出为供评审保留的证据，不属于临时垃圾。

implement/check context 各保持 7 条，用现行 `word-preview-contract.md` 替换历史 preview-baseline 注入项；历史研究保留且由三份任务文档引用。更改后 `task.py validate` 退出 0。首轮只读复核期间 1188 个受控文件变化 0。

## 修正后最终验证

首轮独立复核发现 1 项 P1、2 项 P2：metadata 登记失败被降级完成、成功复用 key 未消费、UTF-16 活动内容绕过。修正及最终 fresh 复核结论详见 implementation-review.md。修正前 3 个最小 selector 按预期失败（22 个失败子场景），修正后通过。

下列命令均在独立工作区，以 `PYTHONPATH=/Users/sc/.codex/worktrees/rnd504-implementation/md2word`、`/Users/sc/PycharmProjects/md2word/.venv/bin/python` 执行，没有改用原目录源码：

| 实际检查 | 结果与适用边界 |
|---|---|
| `-m unittest tests.test_word_preview_provider tests.test_document_job_word_preview tests.test_document_job_preview_persistence` | 完整 40 项 / 16.335s 通过，含正式 adapter 启动 tests-only subprocess 的协议成功路径。 |
| `-m unittest tests.test_artifact_retention tests.test_document_job_result_persistence` 对应模块 | 22 项实际测试通过；原命令附带一个复数拼错的 API selector，另有 1 个 loader error，没有将整条错误命令报为通过。 |
| `-m unittest tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_file_retention_mark_expired_updates_metadata_without_removing_object` | 修正 selector 后仅重跑该单项，1 项通过，成功的 22 项未重复。 |
| 受影响业务与测试 `compileall -q`、`git diff --check` | 通过；不代表 lint/typecheck。 |
| `scripts/ops/check_release.py`，修正后稳定候选 | 退出 0，202 项 / 5.684s；OpenAPI current，changed=false，164 paths/322 schemas；frontend-contract/frontend-smoke-mock 通过。 |
| component `ti-opamp-opa228-p1-smoke` | 复用上节 1/1 成功证据，修正未改变 renderer/样本输入；不把 renderer component 称为真实 Word engine 通过。 |

首轮四模块及 API 62 项证据仅复用于未变的 execution/delivery/modes/授权合同；修正后的 file lifecycle/receipt 使用 22+1 和 release 门覆盖。没有重复 standalone OpenAPI、前端全量 build/E2E 或浏览器矩阵：本任务无公开 API schema/UI 变更，已有合同门能直接覆盖相关边界。无 backend lint/typecheck 配置，未安装额外工具或称其通过。

## AC 证据与缺口

| AC | 当前证据与结论 |
|---|---|
| AC1 | 新应用模块消费正式最小 DOCX，PDF/页面开关、manifest/source identity/hash 正确；fake 只作组件边界。离线合同通过，真实排版不在此结论内。 |
| AC2 | provider 及正式子进程协议覆盖损坏/空输入、页数/PNG/预算、退出/超时/终止清理、路径/输出完整性；补齐编码宏/DTD。通过离线合同。 |
| AC3 | 应用/receipt 回归与独立复核确认主件 ID/hash/receipt/字节不改，provider 失败留证后 blocked/internal_draft；登记不可确认按原 oss_failed，不能误完成。 |
| AC4 | 三 adapter 与重建 runtime 验证 A→B→重启→A、成功 alias 重放/异参/cap、provider/attempt 不增长；独立 retry 不调用 MinerU/LLM/renderer。通过。 |
| AC5 | file/SQLite 实际临时竞争与恢复、fake MySQL 调用合同、lease/stale/换代/终态负例通过；真实 InnoDB 与部署 FS 仍 pending。 |
| AC6 | 新应用和指定 API/receipt 测试、独立复核确认 tenant/company/owner/Admin、当前引用、本地 Token、旧/部分文件拒绝、默认主 DOCX；S3 是签发时授权+有限 TTL，真实服务仍 pending。 |
| AC7 | disabled/required、快照/clone/legacy、仅解除自身 blocker 与基础/未知/并发贡献保留通过；不恢复批准或发布，无 public preview/retry/publish 路由。 |
| AC8 | 生产 adapter 正式协议 subprocess 符合性成功，默认 disabled，adapter_contract_ready=true；实际 engine/validator/fonts/sandbox 尚无批准/证据，production_ready=false。 |
| AC9 | 既有定向回归、最小 component、最终 release/OpenAPI、Spec/文档同步通过；线上 Golden 缺认证、真实 Word 视觉及生产集成待验，不宣称全环境验收完成。 |

## 独立复核、兼容与回滚

两次 fresh 只读复核有实际发现与修正闭环，最终确认三项闭合、无新确认阻断。首轮 1188、最终 1189 个 tracked/non-ignored 文件复核前后逐字节一致，复核者无持久化写入。审计 `20261016T162019Z-rnd-504-implementation-a6c51176` 已 closed，digest/verify 通过：四阶段计划/交付均通过、两次独立复核、无活跃 worker。接受复核交付不等于业务人工验收。

本任务不新增 SQL/schema/迁移、公开 HTTP 路由或 OpenAPI schema；仅在既有 payload 增加可选 preview/quality 状态、文件类型和窄 CAS，旧 payload 可读。所有写者必须升级为兼容版本；旧 writer 可能丢私有状态，禁止以回退旧 writer 作回滚。未部署候选可撤回本任务增量；部署后的停用方案是兼容代码关闭 backend/新请求，保留 receipt、主件、preview、发布/审核与审计，不 DROP、不清 blocker、不覆盖旧二进制。

继承 CON-102 的物理回收边界：retention 已将 pending 标 deleted 后，迟到对象写入可能残留二进制，之后 retention 跳过墓碑；uploaded 确认仍拒绝，当前 manifest 不引用且应用不签发下载。保留 metadata/key 不等于已物理回收。最终 reviewer 核对基线合同后撤回临时 P2，保留为真实限制，不建立额外清理框架。

生产仍 disabled/required=false/render_pages=false；未复制密钥、未发起外部转换/SaaS/VPS 调用。tests-only 子进程和短生命周期 HTTP fixture 不代表线上服务。真实 MySQL/InnoDB、部署 FS、真实 S3、获批 engine/validator/fonts/sandbox、线上 Golden、Microsoft Word 人工视觉未执行，不可据本轮开启生产。

## 实现评审门状态（历史）

准确任务路径：`.trellis/tasks/10-16-rnd-504-word-preview-provider`；父任务复用 `10-12-datasheet-docx-delivery-quality`。manifest 仅 RND-504 为 review，resolution 保持 null；Trellis in_progress，等待人工验收，未开始 RND-505/506。

新建/实质变更的注释、docstring、开发者消息按中文处理，机器协议字段、标识符和测试合同字面量保持原格式。没有改无关旧代码文字。临时日志已删除，测试资源已结束；唯一保留非源码为 ignored component 报告/DOCX/IR，供本轮评审，路径与 hash 见上节。未执行 finish/archive/add_session、stage、commit、push 或部署。

最终 `task.py validate .trellis/tasks/10-16-rnd-504-word-preview-provider` 退出 0，implement.jsonl/check.jsonl 各 7 entries、All validations passed；`git diff --check` 通过。收口时再次确认原目录 310 个 dirty 文件逐字节一致、无新增/缺失，原 branch/HEAD 不变。独立工作区 manifest 除 RND-504 外逐字节一致，父 task.json 仅 children 追加本任务，暂存区为空；最终复核后 app/tests 字节没有变化。

实际业务/测试增量共 29 个文件：preview port/协议/adapter 5 个，document_jobs 新模块 3 个及既有接线 7 个，files 3 个，三仓储 adapter 3 个，config/runtime/main 3 个，新测试 3 个与既有测试 2 个。准确路径如下，避免将目录白名单当成实际改动。

```text
app/core/config.py
app/core/runtime.py
app/main.py
app/services/preview/__init__.py
app/services/preview/executor_protocol.py
app/services/preview/models.py
app/services/preview/provider.py
app/services/preview/sandbox_adapter.py
app/domains/document_jobs/preview.py
app/domains/document_jobs/preview_state.py
app/domains/document_jobs/quality_state.py
app/domains/document_jobs/delivery_state.py
app/domains/document_jobs/execution.py
app/domains/document_jobs/models.py
app/domains/document_jobs/repository.py
app/domains/document_jobs/result_state.py
app/domains/document_jobs/router.py
app/domains/document_jobs/service.py
app/domains/files/models.py
app/domains/files/result_registration.py
app/domains/files/service.py
app/infrastructure/persistence/file/document_jobs.py
app/infrastructure/persistence/mysql/document_jobs.py
app/infrastructure/persistence/sqlite/document_jobs.py
tests/test_word_preview_provider.py
tests/test_document_job_word_preview.py
tests/test_document_job_preview_persistence.py
tests/test_document_job_result_persistence.py
tests/test_fastapi_jobs_backend.py
```

## 人工验收与授权收口

2026-10-17 用户明确验收 RND-504，并确认仅本任务三笔本地提交、manifest done、归档本子任务及记录会话；保留原目录全部 dirty，生产 backend 继续 disabled，不部署、不 push、不开始其他任务。此前停 review/in_progress 的约束已按后续明确授权进入收口，历史记录不改写。

- 工作提交：`931d2f65738f7592a5b3e2dd4c528f9e1b2a0e19`，精确 37 个获批实现/测试/Spec/运行文档文件；业务与测试字节自最终复核后未变，复用已验收验证证据。
- 已执行 `task.py archive .trellis/tasks/10-16-rnd-504-word-preview-provider --no-commit`，确认任务 status=completed，completedAt=2026-10-17，HEAD 仍为上述工作提交，脚本没有产生提交。
- 当前准确任务路径：`.trellis/tasks/archive/2026-10/10-16-rnd-504-word-preview-provider`。12 个任务文件保留，两个 context 的 research 引用已改为归档路径；旧路径在规划/历史命令中只作历史证据。
- manifest 仅 RND-504 从 review 置 done、更新归档路径与人工验收 resolution；父任务仅保留当前 child 引用，父任务与其他任务状态不变；当前子任务活动指针由 archive 清除。
- 第二笔仅纳入上述 12 个归档任务文件、父 task.json、manifest 共 14 个文件；第三笔仅纳入独立工作区 workspace/777/index.md 与 journal-1.md。add_session 使用 --no-commit 并记录工作提交，不修改原目录日志。
- 真实引擎/validator/fonts/sandbox、MySQL/InnoDB、部署 FS、真实 S3、线上 Golden 与 Word 人工视觉的未验证边界继续保留；人工验收不等于允许生产启用。临时日志无残留，ignored component 报告/DOCX/IR 保留供验收追溯，ignored .developer 仅初始化本独立工作区的既有777身份，不纳入提交。

归档后再次执行 `task.py validate` 退出 0，implement/check 各 7 entries、All validations passed；`task.py current --source` 返回 none（退出 1 是该命令的无当前任务表示），确认没有启动其他任务；`git diff --check` 通过。没有重新运行未变化的业务测试或生产门，当前收口仅改变任务文档、context 路径与元数据。
