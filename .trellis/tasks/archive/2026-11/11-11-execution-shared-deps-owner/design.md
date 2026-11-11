# 设计

基线 `main@6101ad44`。访问点与测试耦合见 [research/current-state.md](research/current-state.md)。

## 1. 目标归属

| 依赖 | 改造前 | 改造后 |
|---|---|---|
| `settings`、`job_repository`、`file_service` | 宿主 + 三个协作者各一份 | 仅宿主 |
| `file_repository`、`document_ir_service` | 宿主 + 渲染协作者 | 仅宿主 |
| `job_resource_snapshot_service` | 渲染协作者 + 翻译协作者 | 仅宿主 |
| 专属依赖（如 `word_renderer`、`callback_message_store`、`translation_batch_repository`） | 各自协作者 | 不变 |
| `logger` | 各自 `getLogger("business")` | 不变 |

协作者读取共用依赖统一写成 `self._host.<依赖>`，在每次使用时查找。这与现有“宿主方法在调用时经 `self._host` 查找”的约定一致，不引入新机制。

## 2. 改写方式

- 用脚本按 AST 位置定位协作者方法体内的 `self.<共用依赖>`（排除 `__init__`），把 `self.` 改为 `self._host.`，共 112 处：翻译 34、渲染 51、MinerU 27。
- 删除三个协作者 `__init__` 中共用依赖的参数与赋值；宿主构造协作者时不再传这些关键字参数。
- 宿主 `__init__` 恢复 `self.job_resource_snapshot_service = job_resource_snapshot_service`。
- 协作者的类型标注导入如果因此变成未使用，就一并删除。

改写对象只有接收者，方法体其余部分不变，所以 `verify_move.py` 去掉 `_host` 这一跳后，可以直接与基线（当前 `main`）逐方法比对。

## 3. 核对脚本

在前三次的 `verify_move.py` 基础上改为“单阶段、三个协作者”版本：

1. 对每个协作者：除 `__init__` 外的每个方法，去掉 `_host` 一跳后与基线等价；方法集合不变。
2. `self._host.<名字>` 只能落在“该协作者的宿主方法白名单 ∪ 6 个共用依赖”内。
3. 协作者的 `self.<名字>` 只能是自身方法或 `__init__` 中赋值的属性，而且 `__init__` 不赋值任何共用依赖。
4. 宿主 `__init__` 赋值全部 6 个共用依赖，不赋值任何专属依赖；宿主其余方法与基线 AST 一致。
5. 全仓检索：`.translation_batches|rendering|mineru.<共用依赖>` 为 0；对执行服务（及常见别名）赋值专属依赖名为 0。
6. 运行时检查：构造真实 runtime，逐个替换宿主上的 6 个共用依赖，断言三个协作者读到的都是新对象。这项检查写在核对脚本里，不新增仓库测试。

## 4. 测试改动

只改夹具 `document_job_list_query_v2_publication_fixtures.py:151-153`：

```python
# 改造前
execution.rendering.job_resource_snapshot_service = snapshots if complete else None
execution.translation_batches.job_resource_snapshot_service = execution.rendering.job_resource_snapshot_service
# 改造后
execution.job_resource_snapshot_service = snapshots if complete else None
```

同时删除“替换时两侧要一起换”的注释。

`test_fastapi_jobs_backend.py:10643` 不用改：改造后它替换的宿主 `document_ir_service` 会自动作用到渲染协作者。

## 5. 关键取舍

**通过宿主读取，而不是共享依赖对象。** 依赖包对象同样能消除分叉，但要新增一层结构，三个协作者和宿主的构造也都得改。`self._host` 的约定已经存在，沿用它的改动最小。

**不用只读 property 或 `__setattr__` 拦截。** 这些手段只能让分叉报错，两份引用依然存在。对“赋值专属依赖名”这类静默失效，用核对脚本里的检索覆盖就够了，不必在运行时加防护。

**代价。** 协作者对宿主的耦合点从“若干方法”扩大到“若干方法加 6 个属性”。这些都写进白名单，由脚本核对。协作者不能脱离宿主单独构造，但现状也是如此。

## 6. 兼容与回退

纯结构调整，不涉及数据，回退即还原提交。实施前如果 `main` 上协作者有新改动，先重做度量。
