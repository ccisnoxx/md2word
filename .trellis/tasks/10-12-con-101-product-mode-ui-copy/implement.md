# CON-101 实施与验证计划

状态：规划待评审；本文件所有实现和业务验证均为后续计划，不表示已执行。当前只完成调查、三份规划、context、manifest 与规划校验。验收定义见 [prd.md](prd.md)，边界方案见 [design.md](design.md)。

## 开始门

- [ ] 用户在本轮规划摘要之后明确批准最新三份文档，才可在后续会话对本子任务执行 start。
- [ ] 重新核对 cwd、分支、dirty、manifest CON-101 可继续且 BAS-001 done/人工接受 skipped_existing；保留 `.gitignore` 与并发修改。
- [ ] 读取任务三文档、research 与最小 context；若代码自 `e03232e` 已变，只重新调查相关变更。
- [ ] 若不能在既定 scope 内满足验收，先改计划并重新评审，禁止提前实现 CON-102..104 或其他 backlog。

## 有序任务清单

### 1. 补模式输入合同（AC2、AC8）

- [ ] 在既有 modes owner 保留所有历史 alias；schema 对两种指定历史输入做窄的前置归一化，维持五值 Literal、None 和非法值语义。
- [ ] service 的双字段一致性比较使用规范值，不在 router、前端、测试 loader 另建 alias 表。
- [ ] 最小回归先表达 HTTP alias 的当前缺口，确认因请求 validation 拒绝而失败；实现后在最终验收中通过。不要将未知值断言改成成功。

### 2. 收口 direct 新写入边界（AC3、AC4、AC7）

- [ ] 创建/重试/克隆在现有权限和状态校验之后、相关资源加载/持久化之前拒绝 direct 显式翻译字段。
- [ ] direct 术语解析提前返回，不进入 TermVersionService；保留符号规则服务，不能把 term_rule_set 误禁。
- [ ] 保持 debug 的 403/400 优先级；拒绝时验证无 job/source bind/queue mutation。
- [ ] 遗留 direct 的快照读、默认重试和 keep-source clone 不重载翻译资源；保留其历史字段和审计；当前默认资源 clone 只解析普通资源。
- [ ] Worker 已有 direct 跳过翻译，先以 fake/spy 验证，不为本任务改造 execution、batch、CAS 或 renderer。

### 3. 收口 UI（AC1、AC5）

- [ ] 更新共享五模式名称与 direct 无 AI 说明；同步任务配置“符号与排版规则”称呼，不改上传页视觉体系。
- [ ] 保留已有资源选择、清空与 payload guard；direct 只隐藏已知翻译资源 warning，未知 warning/P0 blockers 继续显示。
- [ ] direct 详情隐藏翻译资源/旧翻译术语、Provider/AI 区，配置 JSON 使用无副作用的局部展示投影；保留普通诊断和原始后端数据。
- [ ] 核对 JobCreate、Jobs、JobTable、模板验证和 retry/clone 现有共享消费者，只改确有独立旧文案的地方。
- [ ] 翻译模式功能不变，全局治理入口不因当前 direct 任务消失。

### 4. 类型、文档与 Spec（AC8）

- [ ] schemas/前端类型补字段适用范围说明；规范枚举不变，alias 不进入新示例。
- [ ] 更新 `docs/api/document-jobs.md`：五种名称、canonical direct 创建例、direct 不加载翻译资源、400/403/422、历史任务只读兼容。
- [ ] 对 `docs/api/templates.md` 的验证入口及相关当前产品说明做定向文案扫描，有陈旧内容才改；归档历史、冻结禁止条款、兼容代码/测试不做文本清零。
- [ ] 用现有 export_openapi 脚本生成必要快照，禁止手工修改生成 JSON。
- [ ] 在 backend/frontend index 增加简短的本任务合同引用或规则段，固化服务端 alias、direct 零翻译调用、符号规则区别和只读 UI 投影；如需独立 Spec，应保持小范围，不复制整份产品 PRD。更新相关中文注释/docstring/错误文案，机器标识保留。

### 5. 稳定候选验证与审查

- [ ] 完成所有范围内修改后统一执行下方选定验证；只有诊断失败/防止边界错误继续扩散时提前做最小检查。
- [ ] Trellis check 检查正确性、兼容、权限和文档；因为实际候选会修改公共请求接受范围及错误边界，安排独立只读 reviewer，聚焦 alias/新选择拒绝/历史快照副作用。不能把自查当独立审查。
- [ ] 若委派，按 multi-agent-orchestration 管理固定 profile、只读/写入所有权、中文报告及验证后的 SUBAGENT_EXECUTION_DIGEST；本轮规划未委派实现或审查。
- [ ] 检查 actual diff、生成快照、敏感数据、未识别 dirty；清理仅本任务临时报告/截图/服务。
- [ ] 完成后 manifest 仅 CON-101 → review，Trellis 保持 in_progress，等待人工验收；不自动 done/skipped_existing/归档/提交/push。

## 计划文件

| 文件 | 计划改动/责任 |
|---|---|
| `app/domains/translation/modes.py` | 复用归一化 owner；如需公开兼容子集则在此定义，保留全部历史 alias，触及文档改中文。无需为改而改枚举。 |
| `app/domains/document_jobs/schemas.py` | 创建 alias 请求归一化、字段适用说明。 |
| `app/domains/document_jobs/service.py` | mode 一致性、direct 新资源意图校验、术语提前返回及实际受影响 create/retry/clone 调用点。 |
| `frontend/src/utils/format.ts` | 五名称与既有模式能力复用。 |
| `frontend/src/utils/documentJobConfig.ts` | 必要的当前模式 warning/快照展示纯函数，形成小的可测边界。 |
| `frontend/src/components/PdfUploadPanel.vue` | 名称说明、符号规则称谓、提示和模式切换。 |
| `frontend/src/pages/JobDetailPage.vue` | 资源/Provider 区条件展示、快照投影、retry/clone 文案。 |
| `frontend/src/api/types.ts` | canonical 类型保持，补 direct 字段限制说明。 |
| `tests/test_document_job_modes.py`（拟新增） | 聚焦 alias HTTP、direct 隔离/拒绝/历史兼容；复用 `test_fastapi_jobs_backend` 的 fake runtime 和上传 helper，避免复制整个 fixture。 |
| `frontend/src/utils/format.test.ts`、`documentJobConfig.test.ts` | 共享模式名称、warning 精确过滤、投影不修改输入，翻译路径不变。 |
| `frontend/tests/smoke/core-flow.spec.ts` | direct 控件/详情隐藏与切换 payload 的真实 DOM 行为；更新旧“direct 显示翻译资源提示”预期。 |
| `docs/api/document-jobs.md`、`docs/api/openapi.json` | 维护源文档与生成合同同步。 |
| `.trellis/spec/backend/index.md`、`.trellis/spec/frontend/index.md` | 实现验收后固化简短模式合同或导航，不能在规划阶段声称目标已实现。 |

只读依赖：`execution.py`、`jobs/resource_snapshots.py`、`translation/term_version_service.py`、config_summary、models、repositories/schema、现有 Worker/Prompt 测试与导出脚本。预计不修改。`JobsPage.vue`、`JobCreatePage.vue`、`JobTable.vue`、`TemplateDetailPage.vue`、`docs/api/templates.md` 仅当共享更新未覆盖陈旧文案时做局部同步。若需改 Worker 生命周期/数据库/全局配置，先回规划门。

## 定向测试矩阵

| 风险/验收 | 最小可靠观测 |
|---|---|
| API alias 未真正贯穿请求边界（AC2） | TestClient + fake runtime，逐个 alias，单字段/相符双字段/冲突；响应、snapshot、事件都是 canonical；未知、空串、非字符串仍 422。 |
| Direct 触发翻译依赖（AC3、AC6） | 初始化 fake runtime 后再装 spy，避免把进程级 seed/readiness 查询算成任务调用；TermVersionService、Profile payload 解析（translation_profile_snapshot_from_record）/Prompt loader、Provider 调用计数为 0；同时断言 direct 创建/执行成功与单 generated_word。共享快照组装器对 None 的普通分支不等同实际翻译资源加载。 |
| UI 隐藏被当作后端校验（AC4） | 逐字段非空 direct 输入以及 Admin/Operator debug true；正确 400/403，源文件未绑定，队列/job 无新项。file/缺省服务与 versioned fake 路径均覆盖同一边界。 |
| 历史字段导致 retry/clone 回归（AC7） | 合成历史 direct 快照含旧术语/Profile 元数据，读取与保留快照动作不重载，源快照/审计不变；显式新选择拒绝。 |
| 误伤四方向/权限（AC4、AC6） | 现有 en2zh/ru2zh/zh2en/zh2ru 绑定、冲突、语言不匹配与 debug/clone 权限测试；不调用真实模型或重测翻译质量。 |
| 显示/请求仍漏出 AI（AC1、AC5） | Vitest 验证共享纯函数，mock API Playwright 验证 Admin/Operator 上传/详情、翻译→direct 清空、payload 无翻译资源、Provider 区及展开 snapshot 不含 AI 项。 |
| 误吞一般错误/变更宽度（AC5） | 精确 warning fixture + 未知 warning + P0 blockers；375/768/1024/1440px 检查长 direct 名称不溢出，至少深色一个样本，键盘仍可切换模式。 |
| 合同漂移（AC8） | OpenAPI 导出/check、前端手写类型检查、vue-tsc/Vite 与实际 diff。 |

新增测试应先在未修复代码上因目标缺口失败，修复后通过；已有 direct Worker 和四方向断言复用，不为每一层复制同样测试。不得使用源码字符串存在作为隐藏或交互验收。

## 验证命令与回归门禁

以下从仓库根运行，均为后续实施计划。本轮不执行。

```bash
# 新的边界测试模块；现有 fake runtime，不启动后端或外部 Provider
.venv/bin/python -m unittest tests.test_document_job_modes

# 未被 release 默认集合覆盖的模式资源/错误回归
.venv/bin/python -m unittest \
  tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_document_job_create_en2zh_binds_default_term_version \
  tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_document_job_create_ru2zh_uses_translation_mode_and_binds_default_terms \
  tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_document_job_create_zh_translation_modes_bind_language_pair_resources \
  tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_document_job_create_rejects_conflicting_mode_and_translation_mode \
  tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_document_job_create_rejects_translation_profile_language_pair_mismatch \
  tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_document_job_clone_creates_new_job_without_mutating_source \
  tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_document_job_translation_qa_marks_direct_jobs_unavailable_and_rejects_review

# 仅 schema 描述/模型有变时导出；后面的 release 已检查 current
.venv/bin/python scripts/ops/export_openapi.py
.venv/bin/python scripts/ops/check_release.py

# 前端 Spec 的稳定候选门禁：全 unit 包含上述定向单测，不重复先后全跑
npm --prefix frontend run test:unit
npm --prefix frontend run build
npm --prefix frontend run test:smoke -- --workers=1

git diff --check
python3 .trellis/scripts/task.py validate .trellis/tasks/10-12-con-101-product-mode-ui-copy
```

`check_release.py` 是 API 变更按 execution-guide 与父计划要求的既定门禁，只在稳定候选执行一次；其已包含 direct 创建、P0 Worker/OOXML、en2zh Provider、debug 权限、clone 权限、OpenAPI 和前端 mock 合同，不另跑同项。前端 index 明确要求完整 unit/build/smoke，因此使用一次完整门禁包含定向场景；需要诊断时可先 `npm --prefix frontend run test:unit -- src/utils/format.test.ts src/utils/documentJobConfig.test.ts` 或 smoke `core-flow.spec.ts --grep 'CON-101'`，修改后仅重跑失败和直接受影响项。

构建若已存在用户 dist，输出到独立系统临时目录（`npm --prefix frontend run build -- --outDir <本任务临时目录>/frontend-dist`）；Playwright 产物用任务临时目录，完成后清理，不删除预存产物。

mock 前端 smoke 使用既有 config 的本地 Vite 和 fake API，不启动真实后端/MySQL/Redis/Worker，不作为 P0 线上完成证据。项目 online-first 规则下，不启动本地全栈或为本任务部署 VPS。若当前执行环境不允许启动 mock UI/Chrome，则记录具体限制、用单测/build 作替代，并将 DOM 隐藏/响应式保留为未验证，不能称完成全部 UI 验收。

不计划全仓 unittest discover、真实四方向翻译/Golden/P1 在线、真实 MySQL 迁移或 Microsoft Word 人工验收：此次不改变翻译算法、转换/渲染结构、DB 或发布功能；fake 主路径及现有 release 证据直接覆盖模式分流风险。只有新差异暴露转换/渲染问题才按相关 Spec 追加样本，不能无理由扩展范围或重跑 BAS-001 全部基线。

## 停止、风险与回滚点

- R0（实施前）：依赖和最新规划未获接受则停止。当前可回退的范围只有本子任务材料、CON-101 manifest 增量和父 children 关系。
- R1（schema/service 后）：alias、400/403/422、历史 direct、零翻译调用测试失败时先诊断，不进入 UI 掩盖后端问题。不能用删除 alias、默默忽略非法选择或降低资源 hash 检查使测试通过。
- R2（UI 后）：只回退本任务展示和纯函数，不改源快照或用户配置；重新暴露旧文案不等同 API 回滚。
- R3（交付前）：API 回滚会重新失去 HTTP alias 并恢复旧 direct 加载缺口，优先保留窄修复/前滚；无 DB rollback、无清历史文件动作。生产回滚/发布需另获对应授权。
- PRD 定义的五类停止条件全程适用；若真实客户端依赖 direct 显式翻译字段，先回评审说明收紧影响，不引入静默兼容加载。

## 完成定义

AC1–AC8 有可信对应证据；所有选定检查通过，或明确列出环境阻塞且不冒称相关验收通过；独立 API 复核完成或如实报告缺口；API/Spec/注释同步；无未知 dirty 被覆盖；只有任务内源与正式证据，无临时服务/产物；manifest 仅 CON-101 为 review。用户验收后才决定 done、提交、归档，push 需单独授权。

本轮规划完成定义：三份文档可评审、调查证据可复现、context 仅必要 Spec/research、`task.py validate` 成功，停在 planning。它不等同上述实施完成定义。

## 2026-10-12 实施授权

用户已明确接受当前三份规划并授权 CON-101 实施。本子任务已 start 为 in_progress；上文 planning/待评审语句保留为规划阶段记录。实施和验证后 manifest 仅标 review，人工验收前不归档、提交或 push。

## 2026-10-12 人工验收与收尾授权

用户已人工审查并接受 CON-101 的实现、测试证据和残余风险，同时确认当前任务 commit plan 并授权提交及归档。AC1–AC8 的逐项核验见 [validation.md](validation.md)。本任务补齐了实际差距，manifest 由 review 改为 done，不属于 skipped_existing。上文规划/实施门的状态描述保留为阶段历史；收尾不新增功能、不修改其他任务状态、不 push。
