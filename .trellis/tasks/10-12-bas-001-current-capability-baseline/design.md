# BAS-001 调查与证据设计

## 当前实现与目标边界

目标是事实可追溯、命令可复现、结果有证据等级，不是提前达到全部产品 PRD。实现证据及局限由 `research/current-capabilities.md` 维护；业务代码保持现状。

正式数据流：

```text
PDF → Files/DocumentJobs → MinerU ZIP
→ MinerUToDocumentIRService → source inventory / DocumentIR v2 / image assets
→ direct：跳过翻译；translation：source IR → batches/Provider → target IR
→ DocumentIRWordRenderer → generated_word → result_file_id → 后端授权下载
```

本地正式入口是 `scripts/dev/formal_mineru_conversion.py`；legacy runtime 的测试只能证明仍复用的纯规则，不能替代正式 converter/renderer 的证据。现有 translation QA 从 artifacts 读取证据并更新任务字段，尚未形成统一 review、质量/交付维度及不可变文档发布。

核验数据流：

```text
当前代码 + OpenAPI 快照 + 测试 + manifests + 历史任务
→ 有界事实矩阵 + 命令/环境清单
→ 获批后的本地定向执行 / 受限复现
→ 脱敏结果摘要 + 未验证边界 + backlog 建议
→ baseline-verification-<实际日期>.md → 人工验收
```

## 六项核验方式

| 能力 | 当前证据 | 实施阶段的核验 |
|---|---|---|
| Word Preview | 开发文档有 soffice 视觉链；任务模型、router、OpenAPI、前端 client 没有任务级 preview | 重核路由/文件类型/adapter；记录工具与产品接口差别，不安装或选定 Provider。 |
| Publication | 配置发布、translation QA 和内部下载存在；无任务 publish action/record | 比对 schemas、API 与 available actions；不调用发布或更改 QA。 |
| Caption/footnote | translator 的抽取与回填分支均不含 annotation；测试锁定数组原文 | 使用 fake Provider 既有测试；只读复现显式数组及 text 副本，区分 IR 翻译和 Word 可见 annotation。 |
| 跨页段落 | converter 逐块建 IR；renderer 对每个 paragraph 新建段落 | 用两个页面上可续接的合成 paragraph 通过 converter 观察块数、text、page/source index；不新增 merger。 |
| 表格 reference | asset 登记仅 image 类型；table metadata 不保留 reference path | 合成有效 HTML table 加 reference image，对照 image block，经 converter 观察 assets/asset_ref；不新增资产类型。 |
| DB migration | MySQL bootstrap+列/索引 maintenance；sqlite bootstrap；shadow copy 搬迁 | 读取初始化顺序，运行 fake MySQL 既有维护测试；记录无 version ledger/up/down，不连接真实数据库。 |

临时探针只放系统临时目录，使用公开/合成输入和现有 API；报告保留可复现命令、输入摘要及输出，不提交一次性脚本或生成 DOCX。探针输出不提升为生产或 Word 视觉验收。

## 证据合同

每条记录包含：能力/任务 ID、目标条款、当前行为、文件路径与符号/行号、命令与工作目录、代码版本、输入来源、环境前提、退出码、关键输出、结论、未验证项。
证据分为 `static_confirmed`、`run_pass`、`run_fail`、`historical`、`not_run`、`blocked_by_environment`；只是报告标签，不新增 API/DB 状态。
无实现结论必须包含搜索范围，并由模型、router/OpenAPI、调用链或前端至少两处交叉支撑，不能只凭类名无命中。
测试失败是报告结果，不是获准修复。报告可完成核验并揭示失败，但不能声称 release-ready；残余风险需人工接受。

## 模型、API、DB、前端与兼容

| 边界 | BAS-001 影响 |
|---|---|
| DocumentJob / DocumentIR | 只读；不加 quality/review/delivery、source spans、preview、publication 字段。 |
| API / OpenAPI / 错误映射 | 不修改 endpoint、schema、状态码或快照；release 快照检查失败原样记录，不自动 export。 |
| DB / migration | 不对真实 DB 初始化 schema；无 DDL、backfill、迁移或降级，只记录现有机制与后续先决条件。 |
| 状态机 / 权限 | 不增加动作或转换；不改变 owner/admin、下载授权、QA 保存语义或审计。 |
| frontend | 不修改页面/类型/按钮；记录现有后端 actions 消费链和未有 publish 合同的事实。 |
| 配置 / 依赖 | 不改环境、运行时配置、资源 seed、lockfile，不安装升级依赖；区分代码默认与已观察环境。 |

`app/core/config.py` 的 file/local_file/disabled 是代码默认，不是本机或生产实际配置。不要实例化带私有环境的 runtime 来探测数据库。

## 幂等、并发、generation 与不可变性

- 核验重跑使用独立临时输出目录，不覆盖历史 run、发布文档或旧报告。同日报告存在时先确认归属，再按 run 标识追加证据。
- Job 的 `retry_count`、batch `generation` 和 compare-and-set 保持原样；不重试线上任务、不改变并发控制、不推导新的 generation 合同。
- template seed hash 不等于文档发布不可变合同；明确区分资源不可变性和缺失的 PublicationRecord。
- manifest 仅更新 BAS-001，父任务只追加子关系；写入前核对当前值，出现并发改动时保留并合并本任务增量。

## 安全、隐私与可观测性

默认离线、无业务外部写入。P0/P1 `--preflight` 也会认证并访问运行系统，不能当纯离线校验；完整脚本会上传 PDF/创建任务，P1 还可能开启全文 debug、调用 LLM。
报告不保留 JWT、API Key、连接串、签名 URL query、用户正文、私有配置内容或生产数据 dump；历史路径/commit 只作证据索引，未知内容不复制。
不绕过 callback 校验、zip/path containment、文件归属与到期检查、内容 integrity 或审计。无需新增日志/指标；沿用脚本退出码、脱敏报告和现有测试输出。

## 差距路由与依赖建议

- RND-504、QA-605、IR-203、IR-206、TR-401 均有明确剩余目标，不建议整项跳过。
- CON-101 复用五模式和 alias；IR-201 复用 package/integrity；RND-502 复用 OMML；IR-204/RND-503 复用题注重关联和并排图片基础，仅核对剩余合同。
- RND-503 的无边框布局表格建议与现有 COL-003 制表位实现有差异；记录并建议后续聚焦可见行为，不在这里改 renderer 或裁决技术替换。该差异不影响 BAS-001 的只读核验。
- CON-103 / QA-605 的迁移准备应在首次数据合同变更之前设计，不能等 REL-703 上线时才处理；建议在相关计划加 migration 前置评审，暂不改 DAG 或创建额外任务。
- TR-401 可复用现有 IR annotation；是否将 IR-204 从硬依赖改为协调/集成依赖，由后续任务依据绑定合同评审，本任务只提出建议。

## 迁移、回滚与停止

无业务迁移、feature flag 或服务发布。回滚只撤销本任务新增规划/报告和 BAS-001 manifest 增量，移除父任务本次追加子关系；保留 DOC-001、历史证据、`.gitignore` 和并发修改，不批量 reset/clean。
若需要改业务、断言、gate 或使用专有样本才能继续，保存失败证据并回到范围评审。PRD 五类停止条件适用；当前新旧差距通过记录/路由解决，无需修改冻结决策。

## 2026-10-12 执行授权与结果补记

用户已明确审核并接受三份规划，授权实现 BAS-001。上文“本会话只规划/待获批”描述的是前一规划轮次；本轮已准确 start 子任务并执行既有基线和三项合成探针。实际结果见 `docs/implementation/baseline-verification-2026-10-12.md` 与本任务 `validation.md`、`research/reproduction-evidence.md`。

按本轮明确要求运行 P1 `--preflight`，因缺认证信息退出 1；未调用真实 Provider。根据“更新受影响 Spec”要求，为 database-guidelines 的现有 schema 段补充 MySQL maintenance 顺序和 fake 证据边界；只补当前事实，不建立迁移合同、不更改业务。API 当前性检查通过，API 文档/快照不变。没有触发五类停止条件。

交付状态为 manifest `review`、Trellis `in_progress`；规划已接受不等于实施已人工验收。等待人工验收和提交授权，不 done、不 archive、不提交、不 push。

## 2026-10-12 人工验收与收尾授权

用户已明确接受 BAS-001 的实现、测试证据和残余风险，并确认当前 commit plan，授权只提交、归档当前任务，不 push、不启动后续任务。上文 planning/review/in_progress 和等待授权的语句保留为阶段历史。

BAS-001 新交付六项事实、当前基线报告与可复现证据，整项报告此前不存在；最终 manifest 使用 `done`，不是 `skipped_existing`。Trellis 通过 archive 转为 `completed`；操作结果及 AC 复核见 `validation.md`。无新业务、Spec 合同或测试需求，复用已接受的业务测试证据，仅运行收尾轻量验证。
