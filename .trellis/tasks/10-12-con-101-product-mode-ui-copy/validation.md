# CON-101 实施验证与交付记录

日期：2026-10-12（America/Los_Angeles）；起始 HEAD `e03232ed8e00da345335238305770ae9e4166ab8`，实际分支 `md2word/CON-101`。

## Preflight 与授权

用户明确接受当前 prd/design/implement 并授权实施。本轮已执行 pwd/status/branch，CON-101 起始 planning，BAS-001 done 且已人工验收；manifest 与活动 Trellis 均无另一个 in_progress 任务。已准确执行当前子任务 start，Trellis/manifest 进入 in_progress。

初始非任务改动仅 `.gitignore`，SHA-256 `b0719d64dea7293460521fa0fb9b575bb3440abcdc4d567ec465adc95a39dc89`；其余为上一轮本任务规划材料，均保留。当前 HEAD 与规划时一致，业务路径无 diff，复用已读且未变的产品/ADR/状态/迁移/质量文档；再次核对当前三份规划、Spec 索引及 CON-101 范围。

## 当前基线（修改业务前）

- `.venv/bin/python -m unittest` 后接 implement.md 列出的七项既有模式资源/冲突/clone/direct QA 方法：退出 0，7 tests OK。
- `npm --prefix frontend run test:unit -- src/utils/format.test.ts src/utils/documentJobConfig.test.ts`：退出 0，2 files/12 tests passed。
- 新模块 `tests.test_document_job_modes` 在起始尚不存在，按计划先新增缺口测试，再记录未修复/修复后的对应结果；不将不存在的模块写为基线通过。
- 系统 `python3` 的 manifest 核对首次因没有 yaml 退出 1；改用已安装 PyYAML 的项目 `.venv/bin/python` 后核对通过。没有安装依赖，该环境问题不是业务测试失败。

## 实现执行与审计方式

专用 Trellis implement/check TOML 没有显式模型/推理档位，不能通过固定 Profile 审计要求；没有修改代理配置。以两个固定 debugger Profile 分别承担后端/前端实现，主会话负责 Trellis check、API 文档、Spec、最终门禁和状态收尾；实际公共合同 diff 另由 fresh critical_reviewer 只读复核。

审计 Bundle：`20261013T050906Z-con-101-a6f352f4`。派发前 WorkPlan/guard-dispatch 已通过，最终结果以有效 SUBAGENT_EXECUTION_DIGEST 为准，不能只从代理状态或自报推断验收。

## 最终实现与合同

后端仅改 modes/schema/service：两种指定历史 alias 在请求类型检查前归一，canonical 五值枚举保持；新 direct 翻译资源选择在翻译依赖和 mutation 前拒绝，术语解析对 direct 提前退出。历史 direct 字段仍惰性可读。前端共享名称、上传/详情资源与 Provider 显隐、精确 warning 分类和快照展示副本完成；保留符号规则、未知 warning 和 P0 blocker。无新路由/query key、generation、CAS、DB schema、迁移、Provider、feature flag 或质量 flag。

API 文档及从 schema 生成的 OpenAPI 同步，后者只有 17 个 description 增量，164 paths/322 schemas 与五值枚举保持。新跨层模式 Spec 由 backend/frontend index 共同引用，避免复制规则。Python 触及的注释、docstring、schema 描述和错误文本已按项目语言要求更新为中文。

## 实际运行的验证

所有命令 cwd 为仓库根；构建与浏览器产物定向到本任务系统临时目录，保留预存 frontend/dist。下列均为实际运行，不是计划。

| 命令 | 结果与边界 |
|---|---|
| `.venv/bin/python -m unittest tests.test_document_job_modes` | 主代理最终退出 0，11 tests OK（1.669s）；后端代理此前同模块也通过，主代理此次保留直接可核对输出以补审计摘要不可用后的证据边界。 |
| `.venv/bin/python -m unittest` + 下列七项方法 | 修改前基线与后端实现后均 7 tests OK；后端候选之后未再改，复用通过证据。 |
| `.venv/bin/python scripts/ops/export_openapi.py` | 退出 0，changed=true、164 paths/322 schemas；不启动 API 服务。 |
| `.venv/bin/python scripts/ops/check_release.py` | 退出 0，202 tests OK（5.935s），OpenAPI current、frontend contract/mock 通过。该集合包含既有 direct Worker/OOXML、AI/debug 权限和下载回归。 |
| `npm --prefix frontend run test:unit` | 最终退出 0，31 files/134 tests passed；此前 133 tests 的通过结果被最终新增 clone 回归后的结果取代。 |
| `npm --prefix frontend run build -- --outDir <task_tmp>/frontend-dist` | 最终退出 0，vue-tsc/Vite 通过；只存在基线中的第三方 PURE 注释与大 chunk 警告。 |
| `npm --prefix frontend run test:smoke -- --workers=1 --output=<task_tmp>/playwright-results` | 退出 1，50 passed/4 failed（5.6m）。三项为本次新增测试定位问题，已经修复；另一项页面样式测试为既有 mock 缺口，见下文。全量 smoke 不记为通过。 |
| `npm --prefix frontend run test:smoke -- core-flow.spec.ts --grep CON-101 --workers=1 --output=<task_tmp>/playwright-targeted` | 修正后退出 0，11 passed（48.2s），包含 Admin/Operator 上传与详情、legacy clone 快照、模式切换 payload、P0 blocker、375/768/1024/1440px、深色与键盘。 |
| `npm --prefix frontend run test:unit -- src/utils/documentJobConfig.test.ts` | clone 回归新增后先退出 1，失败明确为保留 source_term_version_id；补只读投影后退出 0，11 tests passed。 |
| `git diff --check` | 退出 0；另核对未跟踪文档空白/链接与 JSON/JSONL。 |
| `python3 .trellis/scripts/task.py validate .trellis/tasks/10-12-con-101-product-mode-ui-copy` | 退出 0，implement 5/check 6 条 context 全部有效；不代替行为测试。 |

七项既有定向方法完整命令：

```bash
.venv/bin/python -m unittest \
  tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_document_job_create_en2zh_binds_default_term_version \
  tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_document_job_create_ru2zh_uses_translation_mode_and_binds_default_terms \
  tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_document_job_create_zh_translation_modes_bind_language_pair_resources \
  tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_document_job_create_rejects_conflicting_mode_and_translation_mode \
  tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_document_job_create_rejects_translation_profile_language_pair_mismatch \
  tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_document_job_clone_creates_new_job_without_mutating_source \
  tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_document_job_translation_qa_marks_direct_jobs_unavailable_and_rejects_review
```

## 失败诊断与修正

- 后端代理修改前复现：HTTP alias 422、内部 alias 双字段冲突、direct 旧 term_version_id 加载、direct 创建/当前默认 clone 调用术语 resolver；新增测试在修复后通过。
- 前端代理修改前产品名称回归失败；只有两个 missing code 的候选也被新增负例检出漏出六类 translation warnings；最终按真实八类 code 精确过滤。
- 新详情 DOM 的 trace 文本在诊断与事件页签各存在一个，原测试全页面定位触发 strict violation；改为“事件预览”区域定位。切换测试原来点击 Element Plus 隐藏 switch input，改点可见控制器，仍断言真实 checked 状态和请求 payload；没有放宽业务期望。
- 全量 smoke 的第四项 `admin can edit Word page styles and save a draft version` 失败于找不到“创建验证任务”。Vite 对 `/api/v1/templates/default/layout-config?version=2` 出现 127.0.0.1:8000 ECONNREFUSED，当前与 HEAD 旧 mock 都没有补齐该响应。本任务未改页面样式页面或该 test 的行为。
- 为分类该非任务失败，将 `git show HEAD:frontend/tests/smoke/core-flow.spec.ts` 放到系统临时目录，只将此 case 标 only、将 import 改为绝对依赖路径、使用 3011 mock Vite 独立运行。原测试复现同一个 missing button/未 mock 请求错误：退出 1，1 failed。第一次临时运行因目录外的 `@playwright/test` 无法解析而没有收集测试；修正临时 import 后才得到上述复现。未更改仓库测试、页面、后端或该断言，未启动 8000 真实服务。
- 所有 CON-101 UI 场景修正后已通过。未再次全跑 54 场景：最终只改本任务展示投影和新增测试定位，相关 11 场景已直接观测；既有非任务失败已由 HEAD 测试复现，不扩大范围修复。

## AC1–AC8 对照

| AC | 证据 |
|---|---|
| AC1 | 共享五名称 unit；两角色上传/详情 DOM、四视口长名称、键盘与深色通过。模板验证、列表/筛选继续消费同一模式定义，build/type-check 与现有 unit 检查消费者；无新独立模式表。 |
| AC2 | backend test_http_historical_aliases_create_canonical_direct、test_http_conflicting_alias_and_invalid_modes_keep_errors_without_mutation、test_internal_aliases_remain_supported_and_schema_enum_remains_canonical。 |
| AC3 | backend test_direct_without_translation_configuration_executes_one_docx_without_translation_calls、test_direct_create_boundary_does_not_depend_on_translation_services；legacy/versioned eager 成功，task-level spies=0。 |
| AC4 | 逐字段拒绝、debug 权限优先级、retry/clone 及源文件/状态优先级测试；七项四方向资源回归；无 job/source bind/audit/event/queue mutation。 |
| AC5 | 两角色上传/历史详情/展开快照、切换 payload、warnings/P0 的 11 项 DOM 通过；clone source-term 新 unit 先失败再通过，原始对象保留。 |
| AC6 | direct fake MinerU→IR→DOCX 有一份 generated_word、与 result_file_id 一致，无 batch/ai_call_log/ai_debug_archive，Provider/术语/Profile payload/Prompt/翻译调用计数均 0；release 现有 Word/权限回归通过。 |
| AC7 | test_historical_direct_read_clone_and_default_retry_keep_lazy_snapshot、test_direct_symbol_rules_stay_available_for_create_retry_and_clone；历史来源/审计不变，符号规则保持，未改 generation/CAS。 |
| AC8 | API/OpenAPI/类型与三份 Spec 同步；后端/前端 unit/build、CON-101 smoke 通过，全量 smoke 的非任务失败明确分类。没有把完整 smoke 记为通过。 |

## 独立复核与处置

fresh critical_reviewer 只读追踪实际 diff、公开 schema、权限、历史快照、Worker、UI 与测试，确认一项 P2：direct clone 的展示副本遗漏 `clone.source_term_version_id`。主代理核对真实 `_build_clone_snapshot`，以 frozen 原始 clone 的新增 unit 复现，再浅复制 clone 删除该展示字段；保留来源/模板/策略和翻译路径完整字段。补 DOM fixture/断言，并重跑受影响 unit、最终全 unit/build 和 CON-101 smoke 全部通过。

reviewer 复核前后候选文件哈希一致，未观察到其仓库写入。该局部修复由主代理实施和验证，未声称修复后的代码已再次独立复核。其余公开输入、权限优先级与 direct 资源隔离没有确认的新发现；真实数据库、在线链路与 Word 不在此次复核证据内。

## 审计摘要限制

WorkPlan 与派发 guard 在各阶段均通过；但实现阶段记录的 Codex config hash 为 `79bdfc85e7653ba6f79e440fb705c08bf51997614b147be82d423a989777b095`，运行期间配置变为 `746542ace7da315715750a79a7f1c5bcc8a83df09e5c0dba855c1b70af26b074`。本任务未改该配置，也未向用户输出配置正文；审计工具按既定流程读取并校验配置。

实现 summary 和最终 digest 都退出 2：`generated plan field does not match deterministic output: codex_config_evidence`。review 阶段 summary 可生成，但不能替代整个任务 digest。没有改写旧计划来迎合新配置。audit-finalize/audit-verify 均退出 2，原因包括缺少实现 summary/Digest、Bundle 未关闭；原证据保留为 open/protected。

因此未取得属于本任务且校验通过的 SUBAGENT_EXECUTION_DIGEST，不能可靠报告聚合执行尝试数、验收通过数、独立复核数或以其保证全部写入证据。上文行为验证由实际命令结果、当前 diff 和具体复核反例支持，不把线程 completed 冒充统计验收。该审计限制不属于用户列出的业务 blocked 条件，CON-101 仍按实现交付到 review，审计问题作为残余风险报告。

## 未执行、兼容与回滚

未运行真实 MinerU/LLM、线上全栈、真实 MySQL DDL、Golden/P1 完整在线或 Microsoft Word 人工验收：没有改转换/翻译/渲染算法、DB 或发布，fake 主路径与现有 release 覆盖本任务分流风险。没有新 quality flag，也没有 feature flag。

兼容收紧是新 direct 显式翻译资源 400 拒绝；旧记录和 alias 保留。回滚无数据库动作；UI 可回退，但后端整包回滚会恢复旧 alias HTTP 拒绝和术语加载缺口，优先保留窄修复或前滚。禁止清快照、审计或覆盖既有文件。

## 运行日志摘要

系统临时日志在收口后删除，以下哈希固定本轮实际输出身份，不替代行为断言：

| 输出 | SHA-256 |
|---|---|
| backend-mode-final.log | `81b676a16ae944cc99b5b3b2847d5c16326b24de7e060be36b55312fed9b8497` |
| release.log | `b81835470af43cfafbcb2a83f153309f5a5b50ff90ab32301f5ac5a625903098` |
| frontend-unit-final.log | `ea2a2b591a96d4133f408735db817b111be24bd9503371b4a6f8d6c9d02b1998` |
| frontend-build-final.log | `c02eef8e29381b5bdd6bde58725111f75f97de1b0e17e37f4f8c1310f1468a29` |
| frontend-smoke.log | `9ef79a86ca9c6271fe1cc8fed89c6b2b1567d10f34c872785dfbc66cf2df37a0` |
| frontend-smoke-targeted.log | `1d808b8e98d968c410c3f4c5bca71b592f6a29dc3f5a4a572af717f6157f716f` |
| frontend-smoke-baseline.log | `f77b22a407a3f0dddb95ba65a4f0adade9a790d54acc5d3c045bc5566790853e` |

交付前核对仅本任务路径有变化，其他 44 个 manifest task 不变，`.gitignore` 哈希保持；3010/3011 无监听；清理 task_tmp 的构建、截图、trace、旧测试副本和临时日志，保留正式规划/验证与外部审计证据。未提交、push、归档，等待人工验收与 commit plan 授权。

## 2026-10-12 人工验收复核

用户明确接受实现、测试证据和残余风险，并授权当前任务提交、归档。收尾 preflight 确认分支 `md2word/CON-101`、CON-101=`review`、BAS-001=`done`；工作区仅当前任务的 29 个已核对路径及已识别的 `.gitignore` 用户改动，无暂存文件。父任务继续 planning，其他 44 个 manifest 任务不变。

逐项重新核对上文 AC1–AC8：五模式共享消费者、真实 HTTP alias/错误负例、direct 零翻译依赖、权限优先级和无 mutation、两角色 UI/clone 展示投影、单 DOCX/零 AI 产物、历史 retry/clone 惰性兼容，以及 API/OpenAPI/Spec 与验证结果均有对应证据。本任务有实际 schema/service/UI 修复，结论为 done；不是仅验证现有能力的 skipped_existing。

本轮不修改业务、测试、API 或 Spec 内容；使用收尾开始时的 17 个相关文件 SHA-256 核对候选未变，复用已接受的后端 11、release 202、前端 unit 134/build 与定向 smoke 11 通过证据。全量 smoke 的既有页面样式 mock 失败、审计 digest 不可用和真实线上/DB/Word 未验证仍按上文如实保留，人工已接受；不重复运行这些业务检查。现有模式合同 Spec 及 backend/frontend 导航已完成同步，收尾未发现需新增的规则。

最终轻量验证与实际提交/归档结果见后续记录；不将待执行动作记为成功。

### 提交前轻量验证

- `git diff --check`：退出 0。
- `python3 .trellis/scripts/task.py validate .trellis/tasks/10-12-con-101-product-mode-ui-copy`：退出 0，implement 5/check 6 条有效。
- `.venv/bin/python` 内联收尾核对：退出 0；29 路径 allowlist、17 个业务/测试/API/Spec 文件哈希、44 个其他 manifest 任务及父任务保持一致；JSON/JSONL、11 条 context、33 个 Markdown 链接及文档空白检查通过，`.gitignore` 哈希不变。首次附加核对因要求父任务 JSON 末尾换行而退出 1；已确认 HEAD 同样无末尾换行，父任务与收尾快照完全一致。仅将该自定义换行断言限制在 Markdown/JSONL 后通过，没有改写父任务或放宽业务测试。
