# 执行协作者共用依赖收归宿主

## 目标

三个执行协作者（`TranslationBatchExecution`、`WordRenderExecution`、`MinerUExecution`）和宿主 `DocumentJobExecutionService` 各自保存共用依赖的引用。构造之后只要替换其中一侧，两边就会悄悄指向不同的对象。本任务把共用依赖改为只由宿主持有，协作者在调用时通过 `self._host` 读取，从结构上消除这种分叉。度量见 [research/current-state.md](research/current-state.md)。

## 范围

- 共用依赖：`settings`、`job_repository`、`file_repository`、`file_service`、`document_ir_service`、`job_resource_snapshot_service`。
- 三个协作者不再在 `__init__` 中接收和保存上述依赖。方法体内对这些依赖的 112 处读取，接收者从 `self` 改为 `self._host`。
- 宿主 `__init__` 重新持有 `job_resource_snapshot_service`。
- 夹具 `document_job_list_query_v2_publication_fixtures.py` 改为只在宿主上替换一次 `job_resource_snapshot_service`。
- 核对脚本增加一项检查：禁止在执行服务上赋值已迁出的专属依赖名。
- 更新宿主 `__init__` 中“共用依赖两边引用同一对象”的注释，以及三个协作者类 docstring 中的白名单说明；实施时检索 `.trellis/spec/`，如有相关表述一并更新。

## 非目标

- 不改方法名、方法体逻辑、错误码、事件、阶段流转和持久化格式。
- 专属依赖继续只由各自的协作者持有，不动。
- `logger` 不纳入（research §3）。
- 宿主构造签名不变；不把协作者装配移到 `main.py`。
- 不引入依赖包对象、Protocol 或只读 property。
- 不修复与本次无关的既有测试失败。

## 约束

- 改写按 AST 位置机械进行。`verify_move.py` 去掉 `_host` 一跳后，协作者的每个方法都必须与当前 `main` 等价。
- 协作者不得缓存 `self._host.<依赖>`，必须在每次使用时读取。
- 提交时只纳入本任务的文件和行。

## 验收标准

- [ ] AC-1 三个协作者的 `__init__` 不再赋值任何共用依赖；方法体中不再出现 `self.<共用依赖>`。
- [ ] AC-2 协作者方法去掉 `_host` 一跳后与基线 AST 逐一等价；`self._host.<名字>` 只落在“宿主方法白名单 ∪ 共用依赖”内。
- [ ] AC-3 宿主 `__init__` 持有全部 6 个共用依赖，且不持有任何专属依赖；宿主构造签名不变。
- [ ] AC-4 运行时验证：替换宿主上的任一共用依赖后，三个协作者读到的都是新对象。
- [ ] AC-5 定向测试结果清单与基线逐行一致；测试只改夹具中的 `job_resource_snapshot_service` 替换写法。
- [ ] AC-6 全仓检索：经协作者访问共用依赖的写法为 0；对执行服务赋值专属依赖名的写法为 0。
- [ ] AC-7 Spec 与 docstring 中关于依赖归属的表述已更新。

## 评审决策（2026-11-11 用户确认）

1. **一次完成**：三个协作者在同一次改动中完成。
2. **`job_resource_snapshot_service` 收归宿主**：宿主重新持有，夹具只替换一次。
3. **增加“禁止赋值专属依赖名”的检索检查**：放在核对脚本中，作为本任务验收项，不进入 CI。
