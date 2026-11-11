# 结构重构：组合根、用例编排、协作者解耦、Renderer/Evidence 与大型页面拆分

## 目标

在不改变外部行为的前提下，降低后端组合根、任务编排、执行协作者、Word 渲染证据和前端大型页面的结构复杂度，让每一块职责都有唯一的明确 owner，后续改动可以局部完成、局部验证。

基线：`claude/project-restructuring-8ed7ff@0c9a7923`（与 `main` 同步）。

## 来源需求（用户原始五项）

1. 拆分 `app/main.py` 组合根。
2. 将任务编排进一步拆成明确的 Use Case/Workflow。
3. 减少协作者通过 `_host` 调用宿主私有方法的耦合。
4. 拆分超大 Renderer 和 Evidence 模块。
5. 拆分大型 Vue 页面组件。

## 任务映射与顺序

| 子任务 | 对应需求 | 依赖 | 可并行 |
|---|---|---|---|
| `11-11-sr-1-host-decoupling` | 3 | 无 | 与 sr-4、sr-5 并行 |
| `11-11-sr-2-job-use-cases` | 2 | sr-1 完成并合入 | 与 sr-4、sr-5 并行 |
| `11-11-sr-3-composition-root` | 1 | sr-1、sr-2 完成并合入（两者都会改变装配方式） | 与 sr-4、sr-5 并行 |
| `11-11-sr-4-renderer-evidence` | 4 | 无 | 是 |
| `11-11-sr-5-vue-pages` | 5 | 无 | 是 |

用户已确认采用"后端先行"：sr-1 → sr-2 → sr-3 串行；sr-4、sr-5 与后端无文件重叠，可在独立会话/worktree 中并行推进。

## 范围约束

- 纯结构重构：HTTP 路径、请求/响应 schema、OpenAPI、错误码、事件 payload、日志字段、数据库/文件持久化格式、Celery 任务名、生成的 DOCX 内容均不得改变。
- 不新增依赖、不引入 DI 容器/插件/通用框架；只做按职责的模块拆分与显式依赖注入。
- 不顺带修复与本次结构无关的行为问题；发现的问题单独记录。
- 测试只在被测对象的私有入口改名/迁移时同步修改调用点，不改断言语义。

## 非目标

- `translation_execution.py` 内部（2039 行）的进一步拆分：本轮第 2 项聚焦 `DocumentJobService`（3829 行）的用例化，Worker 端 `execute_job` 已是阶段分发结构。如需继续拆分，另起任务。
- 前端 1500 行以下页面、以及 1500–2000 行的第二批页面（见 sr-5）。
- 持久化适配器（`infrastructure/persistence/*/document_jobs.py`）的拆分。

## 跨子任务验收标准

- [ ] 五个子任务各自的验收标准全部满足，且每个子任务的提交可以单独回滚。
- [ ] `tests.test_openapi_export` 通过，OpenAPI 输出与基线一致。
- [ ] `.trellis/spec/backend/directory-structure.md` 与（如涉及）`.trellis/spec/frontend/index.md` 反映新的模块归属。
- [ ] 最终集成审查：在全部子任务合入后的同一分支上，跑一次各子任务列出的定向测试集合并记录结果。
