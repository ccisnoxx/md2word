# 实施与验证计划

状态：PRD 三项决策已由用户确认（2026-11-11），任务已启动。

解释器统一用仓库根目录下的 `.venv/bin/python`。只跑下列定向模块，不执行 discover、聚合脚本、在线验证，也不调用真实的 Provider 或 MinerU。

## 0. 准备

1. 从最新 `main` 建分支 `refactor/mineru-execution-extraction`，记录基线提交。如果 `main` 在 `bc4226a8` 之后改过 MinerU 段，先重做 research 中的度量。
2. 从渲染任务归档目录复制 `verify_move.py`、`validation/run_targeted.sh`、`validation/summarize.py`，只改常量：
   - `MOVED_PATH`：`mineru_execution.py`；
   - 类名：Mixin 用 `MinerUExecutionMixin`，协作者用 `MinerUExecution`；
   - 迁出方法：15 个；
   - 宿主白名单方法：5 个；
   - 宿主入口：2 个；
   - 改接线新增的一跳：`mineru`；
   - 宿主不再持有的属性：`callback_message_store`、`mineru_client_factory`、`mineru_config_resolver`；
   - 渲染专属名字核对：去掉；
   - 补丁目标核对：保留，覆盖 `mineru_execution` 模块路径。
3. 定向清单：渲染任务的 21 个模块，再加 `test_job_workflow_policy` 和 `test_openapi_export`，共 23 个。先跑出基线。基线里已有的失败只记录、不修复。

## 1. 阶段一：纯搬移

1. 用脚本按 AST 位置切出 15 个方法（含装饰器），原文写入 `MinerUExecutionMixin`；导入按实际使用生成，宿主只重写受影响的导入语句。
2. 宿主继承这个 Mixin。
3. 检查：
   - `verify_move.py --stage 1`；
   - 两个模块都没有未解析的全局名，也没有未使用的导入；
   - `import app.main` 成功；
   - 定向清单与基线逐行一致；
   - `git diff --check`；
   - `git diff --stat` 中只有两个应用文件。

**评审点 A**：报告阶段一结果，确认是否继续阶段二。如果 PRD 决策 3 已确认，跳过这一步。

## 2. 阶段二：改为协作者

1. 把 Mixin 改为 `MinerUExecution`，加上 `__init__`；按 AST 位置把 16 处宿主方法调用的接收者改为 `self._host`。类 docstring 列出 5 个白名单方法。
2. 宿主：
   - 去掉基类和 3 个 MinerU 依赖属性；
   - 删除 `__init__` 中计算默认工厂的那一行；
   - 构造 `self.mineru`，并把原始的 `mineru_client_factory` 参数转交给它；
   - 2 处入口改为经 `self.mineru` 访问。
3. 回调路由的 2 处调用改为经 `mineru` 访问。
4. 测试迁移 8 处（design §6）。先改 2 处赋值。核对方法：新增行去掉 `.mineru` 这一跳后，要与删除行一一对应。
5. 检查：
   - `verify_move.py --stage 2`；
   - AC-6 全仓检索，覆盖点访问、字符串属性名和赋值；
   - 运行时确认宿主类上已没有迁出的名字；
   - `import app.main`；先单独导入 `mineru_execution`；Worker 入口 `app.workers.document_tasks` 也要能导入；
   - 定向清单与基线逐行一致。

## 3. 收尾

1. Spec：在 `directory-structure.md` 的文件列表中加入 `mineru_execution.py`。
2. 检查最终 diff 和工作区状态，确认没有混入其他会话的改动。
3. 独立只读复核，重点看：
   - 4 个共用依赖是否分叉；
   - 测试中给 `mineru_client_factory` 赋值的写法有没有静默失效；
   - 默认工厂语义是否不变；
   - 回调去重与重放路径中接收者的解析；
   - 回调路由的调用链。
4. 更新本文件的“已执行验证”，出提交计划，等用户确认，不自动推送。

## 回退点

- 阶段一后：删除新模块并恢复宿主，即回到基线。
- 阶段二后：可以回到阶段一的状态。

## 停止条件

- AST 不等价时，不靠修改核对脚本放行。
- 定向测试出现新失败，经过两轮“修复 → 定向复测”仍未解决，就停止并报告。
- 如果白名单不够用，或者需要新增宿主入口，回到设计评审。

## 已执行验证

2026-11-11，分支 `refactor/mineru-execution-extraction`，基线 `main@bc4226a8`。评审点 A 已由 PRD 决策 3 预先确认，阶段一未单独提交。

工具：沿用渲染任务的 `verify_move.py`、`validation/run_targeted.sh`、`validation/summarize.py`，只按本任务改了常量。渲染专属名字核对改为空集；遇到无法静态展开的 f-string 补丁目标时直接报错。

定向清单：23 个模块，共 523 行结果（含 subTest）。

| 关口 | 结果 |
|---|---|
| 基线 | 373 ok，35 FAIL，115 ERROR。失败集合与渲染任务基线相同，均为既有问题，只记录不修复。新加入的 `test_job_workflow_policy`、`test_openapi_export` 全部通过 |
| 阶段一 `verify_move.py --stage 1` | 核对通过：15 个方法（含 `@staticmethod`）与宿主其余方法均与基线 AST 逐一等价 |
| 阶段一导入 | 两个模块都没有未解析的全局名，也没有未使用的导入；`import app.main` 成功；未改任何测试 |
| 阶段一定向测试 | `results.tsv` 与基线逐行一致，无需归一 |
| 阶段二 `verify_move.py --stage 2` | 核对通过：协作者方法去掉 `_host` 一跳后与基线等价；只访问 5 个白名单宿主方法（16 处），没有不带调用的宿主引用；宿主只经 2 个入口访问协作者；宿主不再持有 3 个 MinerU 依赖 |
| 默认工厂 | 未传入工厂时，`mineru_client_factory` 是协作者自身的 `_build_mineru_client`；传入工厂时原样保留 |
| 阶段二导入 | 单独先导入 `mineru_execution` 成功；`import app.workers.document_tasks, app.main` 成功 |
| 类外调用方迁移 | 回调路由 2 处，测试 8 处（含 `test_mineru_download_boundary.py` 中 2 处 `mineru_client_factory` 赋值）；每处只多一跳 `.mineru` |
| AC-6 检索 | 代码与文档中经执行服务访问迁出名字和 MinerU 依赖的旧写法为 0 处；宿主类上已没有迁出名字 |
| 阶段二定向测试 | `results.tsv` 与基线逐行一致，各模块汇总一致 |
| Spec | `directory-structure.md` 文件列表已加入 `mineru_execution.py` |

未执行：全仓测试；真实 Celery Worker、MySQL 与真实 MinerU 回调的端到端运行。

## 独立复核

2026-11-11，由只读子代理复核工作区改动（基线 `bc4226a8`），结论：未发现确认的问题。

| 核查项 | 结论与证据 |
|---|---|
| 共用依赖分叉 | 构造后替换依赖的只有 `tests/test_mineru_download_boundary.py:324`、`:343`，目标已是 `execution.mineru.mineru_client_factory`；生产代码不替换 |
| 静默失效 | 迁出方法与 MinerU 依赖的旧写法为 0。`fake_mineru_client` 只在 `tests/test_fastapi_jobs_backend.py:512` 挂载，与 `:510` 传入的工厂返回同一对象；宿主原样转交工厂，读取方只修改该对象的状态，“不迁移”的判断成立 |
| 默认工厂 | `_build_mineru_client` 与基线逐字一致，读取的 `settings`、`mineru_config_resolver` 是宿主构造时传入的同一对象 |
| 补丁拦截 | 协作者只保存 `_host`，16 处宿主调用都在调用时查找；仓库中没有对这 5 个方法、迁出方法或 MinerU 依赖的 `patch.object` |
| 回调路径 | 把 `self._host.` 归一后逐方法比对源码，15 个方法全部一致；`test_mineru_download_boundary` 9 个用例通过；`test_document_job_failed_mineru_callback_is_queued_then_worker_marks_failed` 在建任务阶段就报 `KeyError: 'job_id'`，基线上以同样方式失败，属于既有问题 |
| 导入 | 先导入协作者、先导入回调路由、先导入 Worker 入口，三种顺序都成功；宿主删除的导入没有残留引用 |
| 其他调用方 | `app/`、`scripts/` 中只有回调路由 2 处，`recovery.py`、`service.py` 不涉及 |

遗留风险（设计取舍，不是缺陷）：4 个共用依赖由宿主和协作者各持一份引用，今后若只替换一侧会静默分叉。未覆盖：全仓测试；用字符串拼接的动态属性访问。
