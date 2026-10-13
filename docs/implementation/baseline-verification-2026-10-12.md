---
doc_type: baseline-verification
status: accepted
baseline_commit: fcea60ff8c131edff7fd5ba360e1bf4e37ec4227
verified_on: 2026-10-12
timezone: America/Los_Angeles
task_id: BAS-001
---

# BAS-001 当前能力与测试基线

## 1. 结论、身份与证据等级

六项不确定能力已形成事实结论；本地 release、IR、fake MySQL、API、component、前端单测和构建通过。P1 在线预检因缺认证信息阻断；当前线上转换/翻译、真实 MySQL DDL 和 Microsoft Word 人工质量没有验证。本报告完成 BAS-001 的证据交付，不代表目标产品能力已齐备或当前版本可发布。

- 仓库/cwd：`/Users/sc/PycharmProjects/md2word`；分支：`md2word/BAS-001`；HEAD 见 front matter。
- 本地基线执行时间：2026-10-12 21:14 PDT，等于 2026-10-13 04:14 UTC；不存在日期/版本混用。
- Trellis：`.trellis/tasks/archive/2026-10/10-12-bas-001-current-capability-baseline`；父任务 `10-12-datasheet-docx-delivery-quality`。
- 开始时 manifest BAS-001=`planning`、DOC-001=`done`；DOC-001 归档 `archive/2026-10/10-12-doc-001-documentation-package-index/task.json` 的 `meta.human_acceptance` 已接受。用户本轮明确批准三份规划。扫描任务记录未见冲突的 `in_progress` 实现任务。
- 初始 dirty：`.gitignore`（非本任务）；父 `task.json`、manifest、本任务未跟踪目录（上一轮本任务规划）。`.gitignore` SHA-256 为 `b0719d64dea7293460521fa0fb9b575bb3440abcdc4d567ec465adc95a39dc89`，保留不动。
- 已执行准确子任务 `task.py start`，Trellis 保持 `in_progress`；manifest 在执行后为 `review`，`resolution=null`。人工验收前不 `done`、不 `skipped_existing`、不 archive。
- 环境：macOS 27.0.1 arm64，Python 3.11.15，Node v24.16.0，npm 11.13.0；FastAPI 0.136.3、Pydantic 2.13.4、python-docx 1.2.0、PyMySQL 1.2.0、Vitest 3.2.4、Vite 6.4.2。未安装/升级依赖；未安装 pytest 不影响既有 unittest 入口。component 沿用本地 Settings 的模板/版式文件解析；本次未读取/输出其私有配置正文，未记录有效配置快照，因此该通过结论限于当前环境，跨环境字节级复现仍受配置与资源差异影响。

`static_confirmed` 表示实现/合同交叉证据；`run_pass` 表示本次实跑；`historical` 只适用于归档所列版本；`blocked_by_environment` / `not_run` 不作通过证据。这些标签不新增业务状态。

规划静态证据及搜索范围见 [current-capabilities.md](../../.trellis/tasks/archive/2026-10/10-12-bas-001-current-capability-baseline/research/current-capabilities.md)，合成输入、完整代码和实际输出见 [reproduction-evidence.md](../../.trellis/tasks/archive/2026-10/10-12-bas-001-current-capability-baseline/research/reproduction-evidence.md)。下文源码路径相对仓库根，行号对应本报告 HEAD。

## 2. 六项事实与目标差距

| 能力 | 当前事实与权威证据 | 本次验证与剩余边界 |
|---|---|---|
| Word Preview | `docs/dev/local-conversion-sandbox.md:171` 已有 soffice→PDF→PNG 开发视觉链。`app/domains/document_jobs/models.py:87`、`schemas.py:14`、`router.py`、`docs/api/openapi.json`、`frontend/src/api/documentJobs.ts` 无任务级 Word preview 模型、动作与 API。delete-preview/replay preview 不是 Word 预览。 | `static_confirmed`；release 确认当前 OpenAPI。未安装/运行预览引擎。RND-504 仍需任务级 Provider/Artifact/失败重试合同，不能整项跳过。 |
| Publication | 资源/模板版本发布已有；DocumentJob 的 `result_file_id` 单值，translation QA 字段存在，但无文档 PublicationRecord。`service.py:415` 的 available actions 不含 publish；`:434/:512` direct QA 不可用且更新返回 409；`:564/:1547` 下载按 owner/result/file/expiry 校验，未以 QA 状态阻断。 | release 的 QA、授权下载及三项 API 定向测试通过。QA-601/QA-605 仍需统一 review、quality/delivery 与不可变发布；当前资源发布不能证明文档发布不可变，当前下载不能证明新 quality blocked 分类已经存在。 |
| caption/footnote 翻译 | `app/services/document_ir/models.py:76` 已有数组；`mineru_converter.py:339` 首 caption 可复制成 text；`app/domains/translation/document_ir_translator.py:435/:530` 只抽取/回填 text/list/html。`tests/test_document_ir_translation.py:192` 明确断言 annotation 数组不变。 | IR 30 项通过；合成 table 的 Provider IDs 只有 `block_0001.text` / `block_0001.html.0000`，text 副本变化，captions/footnotes 仍原文。TR-401 缺显式 annotation 单元及回填；不改现有断言。 |
| 跨页段落 | `mineru_converter.py:119` 预处理题注及空表 placeholder 后逐块建 IR；`layout_signals.py:153` 只处理表续页；models layout 无 source_spans；`app/services/renderer/word_renderer.py:344` 每块创建段落。 | 两页续接文本经正式 converter/renderer 得到两个 IR 块、两个 Word 段落，保留 page/source index 0/0、1/1。自然分页不等于语义合并。IR-203 仍需 merger 和来源合同。 |
| table reference asset | `mineru_converter.py:160` 仅 image 类型进入 asset 登记；`:324` metadata 不保留 table reference 路径；`app/domains/document_jobs/execution.py:801/:828` 消费 image_assets、登记 hash/file 并建 archive。 | 合成有效 HTML table + img_path 得到 asset_ref=null；同路径普通 image 登记一项 asset。原始 ZIP 中有图片不等于一等 QA asset。IR-206 缺表引用登记，复用既有 files/hash 链。 |
| DB migration | `app/infrastructure/persistence/mysql/schema.py:503` 顺序为建表→maintenance→补列→post-column→删旧索引→补索引，`:521` 查询 INFORMATION_SCHEMA 再 ALTER。sqlite `schema.py:233` 为 bootstrap。无版本 ledger/up/down；shadow_copy 脚本是 metadata 后端搬迁。 | fake MySQL 缺列测试 1 项通过，仅证明维护 SQL/形状；未连真实 DB，不能断言 DDL 原子回滚或并发初始化安全。CON-103/QA-605 首次持久化变更必须先有迁移设计；REL-703 再负责上线演练。 |

无实现结论来自 `app/**`、`frontend/src/**`、`tests/**`、`scripts/**`、`docs/api/**`、`docs/dev/**` 和 Trellis 历史的有界搜索，并交叉核对模型、路由/快照、调用链与前端；不以单一类名未命中作结论。

Gap analysis 的另外两种“未明确”也已定位：`models.py` 中不存在独立 quality/review/delivery 字段（CON-103）；“caption 扩展不确定 QA”是目标增量，现有 `mineru_converter.py::_reassociate_numbered_image_captions` 只处理严格同组连续编号，非任意跨页/多语言绑定。converter/layout 30 项包含既有绑定及空表正反例；没有将这些子能力升级为完整 IR-204 验收。

## 3. 当前基线命令账本

所有命令从仓库根运行一次。以下 A–H 对应完整命令，输出摘要/退出码均来自本次进程，不来自历史日志。

```bash
# A release：OpenAPI + frontend contract/mock + 36 个 unittest target
.venv/bin/python scripts/ops/check_release.py
# B IR/translation：release 默认未覆盖的两个模块
.venv/bin/python -m unittest tests.test_document_ir_translation tests.test_document_ir_mineru_converter_layout
# C fake MySQL：release 默认未覆盖的缺列维护测试
.venv/bin/python -m unittest tests.test_database_job_repository.PersistenceAdapterTests.test_mysql_schema_maintenance_adds_missing_translation_term_columns_without_if_not_exists
# D API：release 默认未覆盖的 direct QA、翻译失败审计、retry 旧 generation 产物过滤
.venv/bin/python -m unittest tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_document_job_translation_qa_marks_direct_jobs_unavailable_and_rejects_review tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_document_job_en2zh_translation_failure_records_ai_call_log_without_full_text tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_document_job_retry_translation_failure_resumes_after_mineru_and_filters_old_files
# E component：按用户要求执行无附加参数的现有 runner
.venv/bin/python scripts/dev/run_component_pdf_regression.py
# F P1：按用户本轮要求执行；不是 formal 模式，也不是完整任务回归
.venv/bin/python scripts/ops/run_p1_translation_regression.py --preflight
# G frontend unit
npm --prefix frontend run test:unit
# H frontend build：原有 dist 已存在，使用已批准计划的独立输出目录
npm --prefix frontend run build -- --outDir /var/folders/m5/j06tv2sn1hn93d6f33j559jm0000gn/T/md2word-bas001-fyx7e_tp/frontend-dist
```

| ID | 退出码 / 等级 | 实际结果 | 进程耗时 |
|---|---|---|---:|
| A | 0 / run_pass | OpenAPI current，164 paths / 322 schemas，frontend-contract/mock 通过，202 tests OK | 9.161s |
| B | 0 / run_pass | 30 tests OK | 0.186s |
| C | 0 / run_pass | 1 test OK，fake MySQL | 0.690s |
| D | 0 / run_pass | 3 tests OK；provider unavailable 为故意注入的失败场景，符合断言 | 1.627s |
| E | 0 / run_pass | 1/1 succeeded，DOCX openable=true | 0.170s |
| F | 1 / blocked_by_environment | manifest 3 available、required=1、missing=[]；auth/runtime 被认证缺失阻断 | 0.137s |
| G | 0 / run_pass | 31 files、127 tests passed | 1.376s |
| H | 0 / run_pass | vue-tsc + Vite 完成，1920 modules transformed | 6.559s |

F 的精确 blocker 为 `p1_auth_missing`、`p1_runtime_unreachable`。runtime error 为“请设置 P1_TRANSLATION_PASSWORD，或设置 P1_TRANSLATION_BEARER_TOKEN。”配置 base_url=`http://127.0.0.1:8000`，认证缺失发生在 readiness 请求之前；**没有证据证明服务不可达或宕机**。没有填入/读取凭据、启动 API/Worker 或重试，也未调用真实 MinerU/LLM。此环境限制不妨碍本任务用 fake/adapter 完成事实核验，因此 BAS-001 不标 blocked。

E 使用 committed minimized public fixture `tests/fixtures/component_pdf_samples/samples/texas-instruments/op-amp/ti-opamp-opa228-p1-smoke/mineru`，走 formal adapter、direct 模式，不重新请求 MinerU。run=`tests/tmp/component_pdf_regression/20261013T041428Z`；DOCX SHA-256=`0cb07410273bef812b2580e0e341442c60eab4478ca679271ce4efaebda308af`。openable 检查仅验证 ZIP 包含 `[Content_Types].xml`，不能充当 Word 视觉/复杂表格/图片/公式验收。输出摘要已固化，临时 DOCX/JSON/build/log 在交付前清理，原有 component run 和 frontend/dist 保留；DOCX ZIP 时间戳可能导致重跑哈希变化。

本次警告均保留并解释：Starlette TestClient/httpx 及 413/422 常量弃用；VueUse 两处 PURE 注释被 Rollup 移除；Vite 主 JS 1,843.50 kB 超过默认 chunk warning；临时 outDir 位于工程外的清理提示。没有改阈值、依赖或代码压制警告。合成 probes 的三个已有 layout flags 及来源见复现文档；component runner 的摘要不报告完整 IR/质量 flags；补查本次 IR 产物得到 4 blocks、`quality_flags=["middle_json_missing"]`。fixture 仅有 content list，没有 layout/middle 页尺寸文件，`app/services/document_ir/layout_signals.py:41–43` 因无尺寸来源写入这一已有 flag；未修复或清除，1/1 succeeded 不能解释为无质量标记或页尺寸验收通过。

## 4. 未运行项目与历史证据

| 类别 / 现有命令 | 本次状态、原因和可用替代证据 |
|---|---|
| `.venv/bin/python scripts/ops/run_golden_sample_regression.py --preflight` / 去掉 `--preflight` 的完整 run | not_run：未提供线上环境与认证；完整 run 会上传/建任务和调用外部解析。release 中 manifest 测试通过，仅覆盖样本治理。当前四份 PDF 为 OPA228 P1/P2/P6/P7（gs-003/004/006/008）。 |
| `P1_TRANSLATION_FORMAL=1 .venv/bin/python scripts/ops/run_p1_translation_regression.py --preflight` / 去掉 `--preflight` 的完整 run | not_run：本次只执行 F，且认证缺失。F required=1 不等于 formal 门禁通过；现有三个 en2zh 样本为 P1/P2/P7，不覆盖四语言。fake translation 测试不能代替真实 LLM。 |
| `.venv/bin/python scripts/ops/check_release.py --runtime-url <获授权API地址> --golden-sample-preflight` | not_run：未有当前运行环境授权/凭据；A 未携带 runtime 参数，不能报告线上 readiness 通过。 |
| `npm --prefix frontend run test:smoke -- --workers=1` | not_run：没有 UI/路由变更，规划不启动 Vite/Playwright；31 单元文件与构建不代替浏览器交互验收。 |
| `scripts/dev/run_local_mineru_quality_matrix.py`、Microsoft Word 人工验收 | not_run：component 已给出当前可运行样本入口；没有新增需全矩阵解释的改动，不扩大样本范围。matrix 仅支持 direct/en2zh/ru2zh 与 phase2-core/ru2zh-acceptance，目标文档的 translation-core/zh2en/zh2ru 不能照抄为现有命令。Word 人工视觉未执行。 |
| 真实 MySQL migration/concurrency/down | not_run：本任务不改变 DB，未连接真实服务；C 仅为 fake maintenance。 |

历史单独引用，不当作当前 HEAD pass：

- [P0 Golden audit](../../.trellis/tasks/archive/2026-06/06-29-p0-golden-sample-release-evidence-closure/acceptance-audit.md)：2026-06-29 `20d496ed1df0c1d3eee94c0e6dfac0c0e6653ed3`，4/4 及 Admin signoff；gs-004 的 manual_list_markers:10 / unstyled_heading_candidates:17 有人工接受理由。
- [P1 formal audit](../../.trellis/tasks/archive/2026-06/06-29-p1-translation-beta-formal-sample-gate/formal-sample-gate-audit.md)：同版本三份 en2zh 3/3 和人工签字，`translation_batch_truncation_not_observed` 保留 warning；小样本未观测到真实截断。P2 当时仍 blocked，不能称所有发布门禁都通过。
- [2026-08 release 记录](../../.trellis/tasks/archive/2026-08/08-20-fix-mineru-table-placeholder-regression/implement.md)：202 项通过仅适用当时版本。本次 A 独立重跑 202 项，结果来源不同。

## 5. Backlog 建议（不改任务状态和 DAG）

| 任务 | 建议 | 剩余验收 / 原因 |
|---|---|---|
| BAS-001 | 验证并收口；不建议整项 SKIPPED_EXISTING | 旧记录不能代替当前报告，本次才形成六项可复现基线。等待人工验收 review。 |
| CON-101 | 缩小到剩余文案、资源显隐及全入口核验 | `app/domains/translation/modes.py` 已有五模式、legacy zh2zh→direct 和四方向；不重新实现模式表。 |
| IR-201 | 复用 package/integrity，只补目标资源/evidence/warning 合同 | 已有 ZIP/path/source integrity，不能再建 PDF 解析路由。 |
| IR-203 / IR-206 / TR-401 | 保留功能任务 | 对应 paragraph merger、table reference、annotation 翻译的实跑缺口。 |
| RND-504 / QA-601 / QA-605 | 保留功能任务，复用本地视觉工具、QA、file/hash 与后端 actions | 尚缺产品级预览、统一审核、成品不可变发布。 |
| RND-502 / IR-204 / RND-503 | 先验证已存在子能力，再限定增量 | 共享 OMML、严格题注重关联、并排图片已经存在，release renderer tests 与 B 提供基础证据；仍缺目标完整质量/绑定验收，不能整项跳过。RND-503 布局表格目标与当前 COL-003 制表位方案应在后续评审对齐。 |
| TR-401 → IR-204 | 评估是否可改为协调/集成依赖，暂不改硬依赖 | annotation 字段已存在，翻译抽取可复用；绑定规则是否阻塞翻译稳定 ID，由后续任务评审。 |
| CON-103 / QA-605 / REL-703 | 首次数据变更前安排迁移设计，REL-703 保留上线演练 | 当前无版本化迁移，必须明确前滚/backfill/兼容窗口/回滚，不能把 bootstrap 当完成迁移治理。 |
| TR-407 / REL-701 | 扩展现有脚本/样本门禁，沿用现有入口 | 当前 P1 只有 en2zh 三样本；没有四方向通过证据。 |

没有证据充分的整任务 `SKIPPED_EXISTING` 候选。以上缩小范围只建议复用已有子能力，不授权跳过剩余验收或更改其他任务。

## 6. 合同、安全、兼容与回滚

本次不修改 app/frontend/tests/scripts、OpenAPI、配置、依赖、seed、样本、数据库或业务状态机。API 文档经 A 验证与运行源码一致，无需重新导出；项目事实由本报告和任务证据补充，数据库 Spec 只补已有 maintenance 的说明。与批准计划相比，仅按用户本轮要求增加 P1 预检及这段事实 Spec 同步；没有新增业务或持久化合同。

- 模块化单体、单任务单主 DOCX、MinerU 唯一解析入口、direct 跳过 Provider/Prompt/术语、可解析 HTML 原生表格均保持现有源码。release/定向证据覆盖相应既有路径；本次没有新解析器、AI 路由或降级截图。
- quality blocked / translation unreviewed 可内部下载而不得批准/发布、前端消费后端发布资格是冻结目标。现有统一质量/发布合同尚缺；本报告明确该缺口，不虚构目标规则已落地，不以新条件阻断内部下载。
- 无新事务、锁、幂等键、generation、重试或错误映射。已有 `retry_count` / batch generation / CAS 不变；D 验证翻译失败与旧产物过滤，但不宣称全部真实并发交错已验证。资源 seed 不可变不等于缺失的 PublicationRecord 不可变。
- 前端路由/query key/URL 状态/types 未变，没有第二套状态机。没有中文转中文 Prompt、双语 DOCX、在线编辑/修表、批量任务或知识库。
- 临时存储、fake MySQL/Provider、公开最小 fixture 和合成探针足以完成本任务；单测中的 loopback test server 不是真实外部服务。本次无生产写入、真实 MinerU/LLM 调用或专有样本使用；未人工查看或输出凭据。既有 component 入口 `scripts/dev/formal_mineru_conversion.py:141` 调用 `Settings()`，按 `app/core/config.py:18` 自动加载本地 `.env`；这条配置读取路径实际存在，不能声称整个进程未读取本地配置或凭据字段。
- 不降低 owner/admin、审计、技术 Token、内容完整性、路径安全或任何 gate；不保存连接串、token、正文 debug、签名 URL。测试里的故意失败不做修复。无 feature flag、snapshot 更改、backfill、兼容窗口或 DB 回滚操作。
- 文档回滚仅撤本任务报告/证据/Spec 补充和 BAS-001 manifest 增量；父任务仅撤本次 child 关系。保留 `.gitignore`、DOC-001、历史审计和用户文件，不使用 reset/clean。由于未动业务，无服务回滚。
- 停止条件仍为依赖不满足、不可消解冻结冲突、必须破坏性迁移/覆盖发布/删除审计、必须改变冻结规则，或授权缺失且 fake 无法完成。当前均未触发。缺线上凭据的后续动作是在获授权环境运行在线 gate，不在 BAS-001 获取秘密或启动服务。

## 7. 逐条验收与完成门

| PRD 条目 | 证据 / 本次结果 |
|---|---|
| AC1 | 第 1–3 节提供 HEAD、分支、依赖、dirty、环境、命令；六项实现交叉路径齐全。 |
| AC2 | 第 2 节分别区分工具/产品 Preview、资源/文档 Publication、分页/段落合并、maintenance/版本迁移。 |
| AC3 | A–H 全部实跑；五类测试各有命令/结果；线上、浏览器、Word 未运行原因与版本边界在第 4 节。 |
| AC4 | 三个正式入口合成探针、B/C/D 与 A 的既有测试，支持当前行为；完整可复现代码/输出在任务 research，不以 fake 代替真实服务。 |
| AC5 | 第 5 节逐任务说明复用/缺口/依赖建议；未改其他任务。没有整任务跳过候选。 |
| AC6 | 范围 diff 确认业务、配置、OpenAPI、样本不变；其他 manifest task 完整对象保持，gitignore 哈希保持。 |
| AC7 | 三份规划获批并追加执行说明；implement/check 最小 context、task.py validate、文档链接和差异检查见任务 validation.md。manifest review，Trellis in_progress，不提交/push/archive。 |

本地证据完整，但当前线上、真实 MySQL、四语言及 Word 人工质量风险仍需后续门禁验收。本文已于 2026-10-12 获人工接受，不构成产品发布判定。

## 附录：本次原始输出摘要校验

完整临时日志在摘要确认后清理；以下 SHA-256 用于标识本次采集，不用于替代测试结论，也不要求未来日志逐字节一致。

| 命令 | 开始时间（UTC） | 日志 SHA-256 |
|---|---|---|
| A | 2026-10-13T04:14:16.578953+00:00 | `3e49b12daea9fdbc893a8702644a7dd82804519f3b49ada365040811395158ce` |
| B | 2026-10-13T04:14:25.740965+00:00 | `7b04a58ac7745e3eb967218883536dc30781cf135b989e6fd067c3830bb5bb72` |
| C | 2026-10-13T04:14:25.927676+00:00 | `9471936f73f5b6dda3b48e2974cd18dcce098d1d4fe3646e87a4e1d4ce053a15` |
| D | 2026-10-13T04:14:26.617933+00:00 | `d5f8c33fc1d60c1e613c9022ff1a5f71df49a4588d814af6dab0e27e055d0cc0` |
| E | 2026-10-13T04:14:28.245217+00:00 | `9f5b7a764d8788cabc9b3471b0bdfef67eba933dad5a940ef13d6c62a94b2346` |
| F | 2026-10-13T04:14:28.415833+00:00 | `d717dda950104a6d202725de6e3a73ce500312b7e4eb0fdfcac5edb17564a0e8` |
| G | 2026-10-13T04:14:16.578957+00:00 | `2fb12335dda3d2e2e2dd22dd4a58d9e43f33896aea8a778af3b88d3c41011b4b` |
| H | 2026-10-13T04:14:17.955028+00:00 | `192f3ebc636621d8dfd4a77c7c8c089994a164ea221af53f828b08655ea46053` |

## 人工验收与收尾（2026-10-12）

用户已接受 BAS-001 的实现、全部测试证据及已列残余风险，并授权当前任务提交、归档；不 push、不启动后续任务。AC1–AC7 逐项证据已复核，报告前文的 review/in_progress 是执行交付时状态；最终 manifest 为 `done`，Trellis 已归档为 `completed`。本报告与复现证据是本轮新交付，因此不适用 `skipped_existing`。

收尾仅变更验收记录、归档引用及日志；原始命令、结果、日志哈希和未验证范围保持不变，不重跑无变化的业务测试。轻量门禁和归档操作证据见任务 `validation.md`。
