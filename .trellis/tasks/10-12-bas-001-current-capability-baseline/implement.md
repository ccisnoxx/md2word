# BAS-001 执行计划（已人工验收）

## 当前门与顺序

本会话只完成规划；没有运行以下业务测试，没有生成正式 baseline-verification 报告，没有 `task.py start`。下一次明确批准本规划后才能进入执行。全程只处理 BAS-001，不提交、不 push、不归档，除非用户另行授权。

1. [x] 重核 `pwd`、`git status --short`、HEAD、分支、DOC-001 人工验收和 BAS-001 状态；已有规划文件先全部读取。保存未识别改动摘要及必要哈希，不 stash。
2. [x] 复用 `research/current-capabilities.md`；如 HEAD 变化，只重新调查受影响证据。核验六项能力、API/前端入口、配置默认和 schema 维护。记录路径/符号，避免重复实现。
3. [x] 读取现有测试 setup 和脚本参数；确认 fake Provider/fake MySQL 与临时存储边界，记录 Python/Node/npm 及已安装依赖版本，不读取 secret、不安装升级。
4. [x] 建立报告命令表；复核 release 的 `DEFAULT_UNITTEST_TARGETS`，只补不重叠的定向测试。所有计划内容稳定后执行一次本地基线组。
5. [x] 通过正式 converter 与 fake translator 做三项最小临时复现：annotation 数组与 text 副本；两页 paragraph 不合并；有效 HTML table reference 与普通 image asset 的差别。记录精确输入、命令和输出，不新增业务/测试代码。
6. [x] 执行下述本地测试、component、frontend unit/build，保存退出码、摘要和环境分类。失败先定位；不修业务、不改断言、不盲重跑。相关输入未变时复用成功证据。
7. [x] 汇总 Golden/P1 历史 run；在线条件不满足则明确未运行。不得为了凑基线启动本地 API/MySQL/Redis/Worker 或 Playwright。
8. [x] 产出 `docs/implementation/baseline-verification-<实际日期>.md`，填写 AC1–AC7、差距路由、跳过/缩小/依赖建议及未验证边界。
9. [x] 执行文档与范围验收、Trellis context 校验，检查临时目录和工作树；仅更新 BAS-001 manifest 为 `review`，Trellis 子任务执行阶段保持 `in_progress`。等待人工验收，不修改其他任务状态，不自动 done/skipped_existing。

## 计划修改文件

| 文件 | 变更 |
|---|---|
| `docs/implementation/baseline-verification-<date>.md` | 执行交付：六项事实、命令结果、历史边界、backlog 建议。若 2026-10-12 执行则使用该日期。 |
| `docs/implementation/codex-task-manifest.yaml` | 仅 BAS-001 状态/path/notes，resolution 在人工验收前保持 null。 |
| 本任务 `prd.md`、`design.md`、`implement.md` | 本会话规划与获批后的必要证据同步。 |
| 本任务 `research/current-capabilities.md`、`planning-validation.md` | 调查和规划验收证据；实施结果写正式报告。 |
| 本任务 `task.json`、`implement.jsonl`、`check.jsonl` | planning、分支、context 和任务范围。 |
| 父任务 `task.json` | 仅由 create --parent 追加子任务关系，父任务状态不变。 |

不计划修改 `app/**`、`frontend/**`、`tests/**`、`scripts/**`、`resources/**`、OpenAPI、依赖、配置和其他任务。原 gap analysis 保留为起点，不把目标状态改成当前事实；建议集中写报告。若需新增长期测试或更改 Spec，先给出具体缺口并回到评审。

## 本地基线命令与结果记录

以下均从仓库根执行，前端命令显式切到 frontend。**当前结果均为 `not_run`（规划阶段）**，不能用本表当通过证据。

### Release（一次）

```bash
.venv/bin/python scripts/ops/check_release.py
```

检查 OpenAPI 当前性、frontend types/mock 合同及默认测试集合。总实施计划 R0 明确要求此基线，因此保留一次默认 release 检查；不额外跑全仓 unittest discover。默认集合已包含 renderer layout、Golden/P1 manifests 等，不重复单跑这些已覆盖模块。不要加 runtime URL 或 golden preflight。

### Release 未包含的定向证据

```bash
.venv/bin/python -m unittest tests.test_document_ir_translation tests.test_document_ir_mineru_converter_layout
.venv/bin/python -m unittest tests.test_database_job_repository.PersistenceAdapterTests.test_mysql_schema_maintenance_adds_missing_translation_term_columns_without_if_not_exists
.venv/bin/python -m unittest tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_document_job_translation_qa_marks_direct_jobs_unavailable_and_rejects_review tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_document_job_en2zh_translation_failure_records_ai_call_log_without_full_text tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_document_job_retry_translation_failure_resumes_after_mineru_and_filters_old_files
```

分别核验 translator 当前合同、正式 converter、MySQL maintenance 和直接任务 QA/翻译失败/retry 旧产物过滤。执行前再核对默认 release 集合，若已覆盖则引用同一次运行结果。fake MySQL 不证明真实 MySQL DDL 原子性、并发初始化或 down migration。

### Component（已提交最小样本）

```bash
.venv/bin/python scripts/dev/run_component_pdf_regression.py --sample-id ti-opamp-opa228-p1-smoke --output-dir <本任务临时目录>/component
```

将尖括号替换为本次 `tempfile.mkdtemp` 或 `mktemp -d` 实际目录并记录命令，不使用字面占位参数。样本属于 committed public/minimized fixture，translation_mode=direct，走 formal adapter。runner 的 succeeded/openable 只证明烟测，不证明复杂表格、图片、公式或分页。

可选观察入口（仅存在已授权本地包、且有 distinct 未解风险才执行）：

```bash
.venv/bin/python scripts/dev/run_local_mineru_quality_matrix.py --mode direct --sample-set phase2-core --sample-id <已确认样本ID> --output-dir <本任务临时目录>/matrix
```

不使用 `--allow-blockers`；dry-run 不能算转换通过。当前 runner 不支持目标文档示例 `translation-core`，也不支持 zh2en/zh2ru，不能照抄未来命令。既有 component 已足够建立可运行样本基线，不为本任务强制遍历整个本地样本库。

### Frontend

```bash
cd frontend && npm run test:unit
cd frontend && npm run build -- --outDir <本任务临时目录>/frontend-dist
```

package.json 的 build 包含 `vue-tsc --noEmit && vite build`，outDir 仅将构建输出定向到任务临时目录，不改变源码或配置。记录第三方注释/chunk warning，不能静默屏蔽。Node/npm 与 node_modules 已存在不代表依赖可用；失败如实分类。

现有浏览器入口是 `cd frontend && npm run test:smoke -- --workers=1`，Playwright 会启动 Vite 3010 并运行 Chrome。此任务无 UI 行为改动，不执行浏览器矩阵或本地 smoke，记录 `not_run`；若未来显式要求运行，优先 `tests/smoke/core-flow.spec.ts --project=chrome`，不能称为线上真实 E2E。

## 在线与人工结果边界

现有命令清单（本计划默认不执行）：

```bash
.venv/bin/python scripts/ops/run_golden_sample_regression.py --preflight
.venv/bin/python scripts/ops/run_golden_sample_regression.py
P1_TRANSLATION_FORMAL=1 .venv/bin/python scripts/ops/run_p1_translation_regression.py --preflight
P1_TRANSLATION_FORMAL=1 .venv/bin/python scripts/ops/run_p1_translation_regression.py
.venv/bin/python scripts/ops/check_release.py --runtime-url <获授权API地址> --golden-sample-preflight
```

前提是获授权的环境、admin 身份、MySQL/Celery readiness、可用 MinerU/LLM、样本与成本/全文 debug 授权。预检也有认证/网络访问；完整 runner 有上传/创建任务等外部写入。不探查或输出凭据。
默认取仓库归档报告作 historical：P0 四样本和 P1 三个 en2zh 样本在 `20d496e` 的 2026-06-29 结果；不得写成当前 HEAD/四语言通过。Microsoft Word 人工验收另列 `not_run`，不拿 LibreOffice/ZIP 可打开替代。

## 报告最小结构

1. 基线身份、依赖、环境/样本来源和边界。
2. 六项事实矩阵：目标、真实入口/路径/符号、现有行为、静态/执行证据、剩余缺口。
3. 命令账本：cwd、精确参数、版本、日期、退出码、结果摘要、产物哈希/位置、未运行原因。
4. 历史与当前分列，真实服务与 fake、OOXML 与视觉、预检与完整 run 分列。
5. backlog 建议：任务 ID、复用/缩小/跳过/依赖建议、未满足验收及理由。不自动修改其他任务。
6. 风险、停止条件、回滚、业务保全与 AC 对应证据。

## 回归门禁、文档与 Spec

- 规划本轮仅执行 task.py validate、路径/JSONL/任务元数据/manifest 检查、diff/空白检查；不运行业务 suite。
- 执行阶段按上述一次基线组，无代码变更不额外加 broad regression、全 E2E、安全扫描、镜像或部署检查。失败保留 baseline 分类，不通过重复运行获得偶然绿灯。
- `.trellis/spec/backend/database-guidelines.md` 与 `word-generation-rules.md` 已描述多数当前缺口，本任务不改合同。执行收口时评估是否发现新的稳定事实；默认只在报告记录路径，确需修改过期 Spec 则提出精确范围复审，不能把目标实现当 current。
- 范围 diff 必须只包含允许文档与 task 元数据。OpenAPI 快照、状态模型、资源和样本字节不变；其他 manifest 任务/依赖不变，初始 `.gitignore` 哈希不变。
- `git diff --check` 不覆盖未跟踪文件，补查本任务新文档尾空白和 context 路径。最终 `python3 .trellis/scripts/task.py validate .trellis/tasks/10-12-bas-001-current-capability-baseline`。

## 回滚点与完成定义

在规划登记后、测试证据采集后、正式报告交付前三个点检查本任务增量。仅撤本任务文档和 BAS-001 状态增量；父 task.json 只撤本次 child 追加。不修改已有报告、审计、发布件和用户改动。
任务临时输出摘要落入报告后删除本任务生成目录/日志/构建产物，保留需要人工审阅的证据时说明路径与保留理由；不清理既有 tests/tmp、缓存或依赖。
完成条件是 AC1–AC7 有真实证据、失败/未运行已准确分类、建议可审阅及 manifest review；并非所有未来能力已实现或所有线上门禁通过。`done` / `skipped_existing` 只能由人工接受后设置。

## 2026-10-12 执行记录（覆盖上文规划阶段的 not_run 标记）

用户已批准上述计划并要求执行。已在既有 `md2word/BAS-001` 完成前置重核；DOC-001 done，BAS-001 planning，没有其他冲突实现任务。先执行一次基线组，再准确 `task.py start` 和 manifest in_progress；完成证据收口后 manifest review、Trellis 保持 in_progress。

- release：202 tests + OpenAPI/frontend contract/mock 通过；IR 30、fake MySQL 1、API 定向 3 通过；component 1/1；frontend 31 files/127 tests 与 build 通过。未重复跑已有覆盖的模块。
- 用户新要求 P1 `--preflight` 已实跑，退出 1；样本 3/3 可用，但缺认证信息使 auth/runtime 前置失败，未发 readiness 请求。不是服务宕机证据，不重试，不启动服务。
- 三项正式入口合成探针通过，实际确认 annotation、paragraph、table reference 缺口；完整复现代码只保存在 research 文档，临时脚本清理。
- component 按用户本轮命令使用默认 output-dir，实际只产生一个新 run；已识别原有两个 run 并保留。frontend 原 dist 已存在，沿用本计划 outDir 隔离，不覆盖。
- 计划文件增量：正式 baseline 报告、`research/reproduction-evidence.md`、`validation.md`；database-guidelines 仅补已核实现状，获用户本轮受影响 Spec 同步要求授权。没有脚本/测试/业务/API/DB 改动。
- 详细命令、退出码、warning、未运行项、AC1–AC7、后续建议和回滚点以正式报告为准。文档检查、独立复核和清理以 validation.md 为准。

本轮停在 commit plan，用户尚未接受实施交付，不提交、不 push、不 archive。

## 2026-10-12 人工验收与收尾授权

用户已明确接受 BAS-001 的实现、测试证据和残余风险，并确认当前 commit plan，授权只提交、归档当前任务，不 push、不启动后续任务。上文 planning/review/in_progress 和等待授权的语句保留为阶段历史。

BAS-001 新交付六项事实、当前基线报告与可复现证据，整项报告此前不存在；最终 manifest 使用 `done`，不是 `skipped_existing`。Trellis 通过 archive 转为 `completed`；操作结果及 AC 复核见 `validation.md`。无新业务、Spec 合同或测试需求，复用已接受的业务测试证据，仅运行收尾轻量验证。
