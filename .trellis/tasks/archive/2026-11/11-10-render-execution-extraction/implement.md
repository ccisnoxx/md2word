# 实施与验证计划

状态：PRD 三项决策已由用户确认（2026-11-10），任务已启动。

解释器统一用仓库根目录下的 `.venv/bin/python`。只跑下列定向模块，不执行 discover、聚合脚本、在线验证或真实 Provider/MinerU 调用。

## 0. 准备

1. 从最新 `main` 建分支 `refactor/render-execution-extraction`，记录基线提交。如果 `main` 自 `80032c25` 后改动过渲染段，先重做 research 中的度量。
2. 从翻译任务归档目录复制 `verify_move.py`、`validation/run_targeted.sh`、`validation/summarize.py`，只改常量：
   - `MOVED_PATH = render_execution.py`；Mixin/协作者类名；17 个迁出方法；没有模块级迁出定义，也没有队列 setter；
   - 6 个宿主白名单方法；2 个宿主入口；改接线的一跳 `rendering`；
   - “宿主不再持有”的属性为 `word_renderer`、`template_read_service`、`word_preview_service`、`job_resource_snapshot_service`；
   - 新增核对：宿主模块命名空间中不存在 `ensure_renderer_integrity`、`build_renderer_evidence`；测试中所有 `app.domains.document_jobs.execution.<名字>` 补丁目标都在宿主模块中真实存在。
3. 定向清单（research §7，共 21 个模块）跑出基线结果。基线中的失败属于既有问题，只记录不修复，后续只要求结果清单不变。

## 1. 阶段一：纯搬移

1. 用脚本按 AST 位置切出 17 个方法，原文写入 `render_execution.py` 的 `WordRenderExecutionMixin`；导入按实际使用生成。
2. 宿主继承该 Mixin，删除只被渲染段使用的导入。
3. 改 4 处模块路径补丁（含 `test_document_job_execution_stages.py:534` 的 f-string）。
4. 检查：
   - `verify_move.py --stage 1`；
   - 两模块无未解析全局名、无未使用导入；
   - `import app.main`；
   - 定向清单与基线逐行一致；
   - `git diff --check`。

**评审点 A**：报告阶段一结果，并确认是否继续阶段二（若 PRD 决策 3 已确认则跳过）。

## 2. 阶段二：改为协作者

1. Mixin 改为 `WordRenderExecution`，加 `__init__`，按 AST 位置把 20 处宿主方法调用的接收者改为 `self._host`。在类 docstring 中列出 6 个白名单方法，并说明为什么必须在调用时查找。
2. 宿主：去掉基类和 4 个渲染依赖属性，`__init__` 构造 `self.rendering`（`word_preview_service` 的默认构造保留在宿主），2 处入口改为经 `self.rendering`。
3. 测试迁移（design §6）。先处理 3 处赋值和夹具，再机械改写读取与 `patch.object`。核对方法：新增行去掉 `.rendering` 一跳后，必须与删除行一一对应（夹具与新增注释除外）。
4. 检查：
   - `verify_move.py --stage 2`；
   - AC-6 全仓检索，覆盖点访问、字符串属性名、赋值与模块路径补丁；
   - 运行时确认宿主类上没有迁出名字；
   - `import app.main`，并单独先导入 `render_execution`；
   - 定向清单与基线逐行一致。

## 3. 收尾

1. Spec：
   - `word-generation-rules.md:8` 和 `:42` 的 owner 改为 `render_execution.py::WordRenderExecution._render_and_save_word`。提交前确认另一会话对该文件的改动已落地或已避开，只纳入本任务的行。
   - `directory-structure.md` 的文件列表加入 `render_execution.py`。
2. 检查最终 diff 与工作区状态，确认没有混入另一会话的改动。
3. 独立只读复核，重点：
   - 6 个共用依赖是否分叉；
   - 有没有静默失效的赋值；
   - 补丁拦截语义；
   - 页面降级循环与 prepared result 恢复路径中的接收者解析。
4. 更新本文件“已执行验证”，出提交计划等用户确认，不自动推送。

## 回退点

- 阶段一后：删除新模块、恢复宿主与 4 处补丁即可回到基线。
- 阶段二后：可回到阶段一状态。

## 停止条件

- AST 不等价时，不靠修改核对脚本放行。
- 定向测试出现新失败，两轮“修复 → 定向复测”后仍未解决，就停止并报告。
- 白名单不够用（需要访问第 7 个宿主方法），或需要新增宿主入口时，回到设计评审。

## 已执行验证

2026-11-10，分支 `refactor/render-execution-extraction`，基线 `main@80032c25`。评审点 A 已由 PRD 决策 3 预先确认，阶段一未单独提交。

工具沿用翻译任务的 `verify_move.py`、`validation/run_targeted.sh`、`validation/summarize.py`，按本任务改了常量，并新增两项核对：宿主模块不绑定 `ensure_renderer_integrity`、`build_renderer_evidence`；测试中 `app.domains.document_jobs.{execution,render_execution}.<名字>` 形式的补丁目标都真实存在（f-string 目标按循环值展开）。

定向清单为 research §7 的 21 个模块，共 510 行结果（含 subTest）。

| 关口 | 结果 |
|---|---|
| 基线 | 360 ok，35 FAIL，115 ERROR，均为既有问题，只记录不修复。最多的几类：`_build_image_loader() missing ... 'document_ir'`（54，测试按旧签名调用）、`新文件对象路径缺少固定位置的独立 file_id`（30）、`发布状态只能由原子发布端口维护`（18）、`False is not true`（17）。`test_document_job_result_persistence` 有 71 行失败，`test_rnd503_dependency_integration` 的 12 个 subTest 全部失败，所以渲染路径的回归保护主要来自 `fastapi_jobs_backend`、`execution_stages`、页面降级与占位符系列 |
| 阶段一 `verify_move.py --stage 1` | 核对通过：17 个方法与基线 AST 逐一等价，宿主其余方法逐一等价，补丁目标核对通过 |
| 阶段一导入与测试改动 | 两模块无未解析全局名、无未使用导入；`import app.main` 成功；测试只改 4 处模块路径补丁 |
| 阶段一定向测试 | 原始差异 108 行，正好是 54 处 `_build_image_loader` 异常消息中的类名 `DocumentJobExecutionService` → `WordRenderExecutionMixin`；类名归一后 510 行与基线逐行一致 |
| 阶段二 `verify_move.py --stage 2` | 核对通过：协作者方法去掉 `_host` 一跳后等价；只访问 6 个白名单宿主方法（20 处），无不带调用的宿主引用；宿主只经 2 个入口访问协作者；宿主不再持有 4 个渲染依赖 |
| 阶段二导入 | 单独先导入 `render_execution` 成功；`import app.workers.document_tasks, app.main` 成功 |
| 阶段二测试迁移 | 8 个文件共 56 处，加夹具 2 行；新增行去掉 `.rendering` 一跳后都与删除行一一对应（夹具新注释除外） |
| AC-6 检索 | 代码与文档中经执行服务访问迁出名字、渲染依赖的旧写法，以及旧模块路径补丁：0 处。另有 1 处命中在历史工作日志 `.trellis/workspace/777/journal-1.md:1502`，属于历史记录，不改写。宿主类上没有迁出名字 |
| 阶段二定向测试 | 原始差异同样只有 54 处类名变化（`WordRenderExecution`）；归一后 510 行与基线逐行一致，各模块汇总一致 |
| Spec | 更新了 `word-generation-rules.md:8`、`:42` 的 owner 表述和 `directory-structure.md` 的文件列表。`word-generation-rules.md:588` 是另一会话的改动，不属于本任务 |

未执行：全仓测试，以及真实 Celery Worker 与 MySQL 环境的端到端运行。

## 独立复核

2026-11-10，由只读子代理复核工作区改动（基线 `80032c25`）。结论：未发现确认的问题。

| 核查项 | 结论与证据 |
|---|---|
| 共用依赖分叉 | 无 `patch.object`、`setattr`、`patch.multiple` 命中。只替换宿主一侧的整体赋值仅 `tests/test_fastapi_jobs_backend.py:10643`（`document_ir_service`），其替身在 `ir_converting` 阶段即失败，到不了协作者的降级读取；复核时实际运行该用例，结果与基线一致。降级相关测试改的都是共享对象的内部属性；夹具两侧同步写法正确 |
| 静默失效 | 17 个迁出方法与 4 个渲染依赖的全部引用都经 `rendering`；宿主与别名上无残留赋值 |
| 模块级补丁 | 已无 `app.domains.document_jobs.execution.<名字>` 补丁；4 处改指 `render_execution`；其他模块路径补丁的拦截范围不变 |
| 补丁拦截语义 | 协作者只保存 `_host`，调用时查找 6 个白名单方法，没有缓存绑定方法 |
| 降级与恢复路径 | 抽查 `_render_and_save_word`、`_degrade_render_failure_page`、`_finish_prepared_result`，`self.X` 在协作者上都解析到同一对象；`word_preview_service` 注入与默认构造语义不变 |
| 导入 | 新模块只在 `TYPE_CHECKING` 下引用宿主；`preview`、`publication_provenance`、`table_evidence` 都不反向导入；全新解释器分别导入成功 |
| 基线对照 | 用 `git archive 80032c25` 导出基线，两侧运行同一批 59 个渲染相关用例，失败集合逐条一致，类名归一后错误消息一致 |

遗留风险（设计取舍，非缺陷）：6 个共用依赖由宿主和协作者各持一份引用。今后若在渲染前只替换宿主上的某个依赖（例如 `document_ir_service`），协作者仍会使用旧对象。未覆盖：全仓测试；被既有失败掩盖的渲染路径只能依靠 AST 比对与代码审读；17 个方法体只人工抽查了 3 个，其余依赖 AST 核对。
