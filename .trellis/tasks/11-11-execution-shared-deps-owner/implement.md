# 实施与验证计划

状态：PRD 三项决策已由用户确认（2026-11-11），任务已启动。

解释器统一用仓库根目录下的 `.venv/bin/python`。只跑下列定向模块，不执行 discover、聚合脚本或在线验证，也不调用真实的 Provider 或 MinerU。

## 0. 准备

1. 从最新 `main` 建分支 `refactor/execution-shared-deps-owner`，记录基线提交。如果 `main` 在 `6101ad44` 之后改过三个协作者，先重做 research 中的度量。
2. 以 MinerU 任务归档目录中的 `verify_move.py` 为底，按 design §3 改成单阶段、三个协作者的版本；`validation/run_targeted.sh`、`validation/summarize.py` 直接沿用。
3. 定向清单：MinerU 任务的 23 个模块。先跑出基线，基线里已有的失败只记录、不修复。

## 1. 实施

1. 用脚本按 AST 位置改写 112 处 `self.<共用依赖>` 为 `self._host.<共用依赖>`，并按文件断言改写数量（翻译 34、渲染 51、MinerU 27）。
2. 删除三个协作者 `__init__` 中共用依赖的参数与赋值，清理因此变成未使用的导入；更新类 docstring，写明“共用依赖经 `self._host` 读取”。
3. 宿主：`__init__` 恢复 `job_resource_snapshot_service`；构造三个协作者时去掉共用依赖的关键字参数；更新相关注释。
4. 夹具改为只在宿主上替换一次（design §4）。
5. 检索 `.trellis/spec/`，找出关于共用依赖归属的表述，有就一并更新。

## 2. 检查

- `verify_move.py`：完成 design §3 的 1–6 项。
- 宿主与三个协作者模块无未解析全局名、无未使用导入；单独先导入各协作者模块，再导入 `app.workers.document_tasks`、`app.main`。
- 定向清单与基线逐行一致。
- `git diff --check`；`git diff --stat` 中只出现 4 个应用文件、1 个夹具，以及可能的 Spec。

## 3. 收尾

1. 独立只读复核，重点：
   - 是否有遗漏的 `self.<共用依赖>`，尤其是嵌套函数和 lambda 内的引用；
   - 有没有任何地方缓存 `self._host.<依赖>`；
   - 运行时替换检查是否覆盖了全部 6 个依赖与 3 个协作者。
2. 更新本文件的“已执行验证”，给出提交计划，等用户确认，不自动推送。

## 停止条件

- AST 不等价时，不靠修改核对脚本放行。
- 定向测试出现新失败，经过两轮“修复 → 定向复测”仍未解决，就停止并报告。
- 改写数量与度量不符时，先停下重新度量，不强行放行。

## 已执行验证

2026-11-11，分支 `refactor/execution-shared-deps-owner`，基线 `main@6101ad44`。

工具：`verify_move.py` 是本任务新写的单阶段版本，覆盖 design §3 的 1–6 项；`validation/run_targeted.sh`、`validation/summarize.py` 沿用 MinerU 任务的版本。定向清单 23 个模块，共 523 行结果。

| 关口 | 结果 |
|---|---|
| 基线 | 373 ok，35 FAIL，115 ERROR。用例与状态和 MinerU 任务阶段二结果一致，都是既有问题 |
| 改写 | 按 AST 位置改写 112 处（翻译 34、渲染 51、MinerU 27），数量与度量一致；协作者构造共删除 13 个共用依赖（参数加赋值共 26 行）；宿主构造调用删除 13 个关键字参数，并恢复 `job_resource_snapshot_service` |
| 导入与注释 | 清理因改写变成未使用的导入共 13 个；三个协作者 docstring 写明“共用依赖只由宿主持有，经 `self._host` 读取”；宿主构造处注释同步更新 |
| 静态检查 | 四个模块都没有未解析的全局名，也没有未使用的导入；协作者中不再出现 `self.<共用依赖>`（含嵌套函数与 lambda），也没有缓存 `self._host.<依赖>` 的赋值 |
| `verify_move.py` | 核对通过：方法体去掉 `_host` 一跳后与基线等价；`_host` 访问只落在“宿主方法白名单 ∪ 共用依赖”；协作者构造不保存共用依赖、保留全部专属依赖；宿主持有 6 个共用依赖、不持有专属依赖，其余方法与基线一致；全仓检索中“经协作者访问共用依赖”和“对执行服务赋值专属依赖”均为 0；运行时检查中，协作者的 `_host` 是宿主实例，协作者上访问任一共用依赖都会抛 `AttributeError` |
| 核对脚本有效性 | 在 `git archive 6101ad44` 导出的基线代码上运行时检查，报出 13 条问题（翻译 4、渲染 6、MinerU 3），说明脚本能识别改造前的状态。期间删除了一项永远会通过的检查（替换后经 `_host` 读取，读的本来就是宿主属性），改为“协作者上访问共用依赖必须报错” |
| 导入 | 三个协作者模块各自单独先导入均成功；`import app.workers.document_tasks, app.main` 成功 |
| 测试改动 | 只改夹具 `document_job_list_query_v2_publication_fixtures.py`：改为在宿主上替换一次 `job_resource_snapshot_service`，删除“两侧要一起换”的注释 |
| 定向测试 | 523 行与基线逐行一致，各模块汇总一致 |
| Spec | `translation-batch-lifecycle.md:9` 补充了共用依赖的归属；`error-handling.md:83` 的客户端工厂归属改为 `MinerUExecution._build_mineru_client`（上一任务遗漏）。`quality-guidelines.md` 的改动属于另一会话，不纳入 |

未执行：全仓测试；真实 Celery Worker 与 MySQL 环境的端到端运行。

## 独立复核

2026-11-11，由只读子代理复核工作区改动（基线 `6101ad44`）。结论：产品代码与基线行为等价，未发现回归或新的静默失效。

| 核查项 | 结论与证据 |
|---|---|
| 遗漏 | 三个协作者中 `self.<共用依赖>`、`getattr(self`、`setattr(`、`__dict__`、`vars(self` 以及带依赖名的字符串字面量均为 0；`self._host.<依赖>` 计数为翻译 34、渲染 51、MinerU 27 |
| 缓存 | 没有 `x = self._host.<依赖>` 形式的绑定；`render_execution.py` 中两个嵌套函数都在调用时经 `_host` 取值，与基线时机一致 |
| 构造顺序 | 宿主先赋值全部共用依赖，再构造协作者；协作者 `__init__` 只做赋值；MinerU 默认工厂只绑定方法，构造时不调用 |
| 装配与测试 | 没有经协作者访问或赋值共用依赖的写法；对执行服务赋值专属依赖名的写法为 0；`test_fastapi_jobs_backend.py:10643` 替换的 `document_ir_service` 现在能被渲染协作者读到；夹具在 `complete=False` 时与基线等价；相关 2 个用例单跑通过 |
| 导入与 Spec | 删除的导入没有残留引用（含字符串注解）；两处 Spec 与代码一致 |
| 核对脚本 | 5 组变异测试中 4 组能报错。确认问题：运行时“替换后读到新对象”一项永远会通过，已删除；`check_repository` 接收者正则的前导断言只作用于一个分支，已修正为覆盖 `self.execution`、`<x>.document_job_execution_service` 等写法，并用 7 条正反样例自检。修正后重跑，核对通过 |

剩余盲区：协作者 `__init__` 不参与与基线的比较，若在构造中缓存别名、但没有方法使用，脚本不会报错（复核者已人工确认三个 `__init__` 中没有这种写法）；没有检查经动态拼接的属性名做的访问；未运行全仓测试。
