# list-ready-once 候选接入记录

日期：2026-11-06。执行位置仅为 `/Users/sc/PycharmProjects/md2word-wt/list-loading-performance`，基线 `25860865812ef5bb9159a449aaa7df0a6dfcb815`。来源工作区只读，未提交、推送、归档、记账或访问生产。

## 来源与冻结身份

来源：`/Users/sc/PycharmProjects/md2word-wt/list-ready-once`，分支 `codex/list-ready-once`，HEAD `1f4a90adcf824608e9e603190434a0c8f78b118f`。来源为未提交候选，不能仅以 HEAD 标识补丁。

读取来源后，接入前再次读取并核对下列五个 SHA-256、来源 HEAD 与 tracked patch SHA；两次完全一致。三个产品/测试文件接入后再次与冻结字节比较，完全一致。目标原有两个 tracked 文件同时与目标 HEAD 和来源 HEAD 比较一致，新增测试在目标原先不存在，因此未覆盖并行修改。

| 文件（相对来源工作区） | SHA-256 |
| --- | --- |
| `app/infrastructure/persistence/document_job_list_query.py` | `061ab44e5b9c88490103ee7701dcd96f389d5d2bda2f349dd6f1ea9923fd6aeb` |
| `tests/test_document_job_list_query.py` | `412fe67dcded6b990840c2f593043ff1dc4b101a00241d54da719da87dd580cf` |
| `tests/test_document_job_list_query_readiness.py` | `27bb5bef6e96d146585cc6aead7b845244a143a8b45a55b9789315baf7710823` |
| `.trellis/tasks/11-06-list-ready-once/validation.md` | `210d79108204e45cbf5c803a4e2096fa56b8660a6406d6d46d24749db6c833de` |
| `.trellis/tasks/11-06-list-ready-once/review-fix-tests.log` | `dcfce30c6ad372f736b7e08a595a2464c06f7d1c99c38889a86b19ca7ff57564` |

两 tracked 文件执行 `git diff --binary HEAD -- app/infrastructure/persistence/document_job_list_query.py tests/test_document_job_list_query.py` 的原始补丁 SHA-256 为 `8a0b42eb130534f4a1a935ec9ecb96e2f4c215f21741da4e8f8425fef31af0ff`。新增测试身份由上表单独固定。

## 实际接入范围与合同

- 只接入上表前三个文件；本轮没有二次改写 SQL 或测试。
- 将两条全表 shape 校验与原文件 ID 检查合为请求内首条聚合；仍逐请求在仓储原快照执行，不是启动缓存。既有候选记录的正常查询从 13 条 SELECT 降为 11 条。
- 完整 shape 校验域为 V 可见任务及其完成态主件门控所关联文件；任务可见性字段不可靠仍失败，可靠隐藏任务及无关坏文件不再阻断。此变化已属于来源设计，不应描述为全库 shape 校验语义完全不变。
- 同时保留 shape 失败先于 ID 不匹配、原 file_id collation 寻址、业务字段二进制比较、同请求 as_of 及后续文件 JSON 解析保护。全量 verify 仍负责无关数据及 payload 一致性。
- 未接入 list-key-columns，没有 schema、投影版本、迁移、API 或前端变更。两份 Spec 同步由主会话负责，本子代理未改 Spec。

## 复用证据与本轮检查

来源 `review-fix-tests.log` 实际记录 `Ran 61 tests in 4.581s` 和 `OK`；包含 readiness、v2 SQL、list query、v2 service、incident publish light check、v2 writers 六模块。来源记录还有测试客户端及 HTTP 状态常量弃用告警，没有失败。本轮只读核对原日志，不将其写为本轮新跑结果。

来源与目标 HEAD 之间的 app/tests 变化为表格占位及失败诊断相关文件；共享 SQL、全部 persistence adapter、文件 owner、document_jobs 的 service/incidents/list_query/models、上述六模块及 `requirements.txt`/`requirements/` 均无差异。接入文件又与来源候选字节相同，没有产生新的列表行为或夹具交叉变化。因此按任务的成功结果复用约束复用 61 项结果，本轮不重复运行应用测试。

本轮新检查：来源双读 SHA/HEAD/补丁一致；目标接入前 baseline 一致；接入后三文件 SHA 一致；`git diff --check` 通过；检查 diff/status，tracked 差异为指定 SQL 与 fake cursor 返回字段，新增 readiness 文件单列在 untracked 状态。未运行全仓、构建、前端或发布聚合。

继承性能证据仅为来源 SQLite 合成实验（119 任务、1,928 文件）以及 SELECT 次数，不能换算为生产 MySQL 净收益。历史两条生产查询合计 5.19 秒仍只是原查询预算，本轮未独立取得该原始 trace。

## 剩余边界

真实 MySQL 引擎与本轮认证列表/页面性能不在本子任务证据内，不能声明 AC-2 达标或两个页面已修复。未改异常列表；主会话继续其阶段测量和必要修复判断。若后续接入拆列候选或修改共享 SQL/夹具，应重新核对本记录的冻结身份并只补直接交叉影响验证。

注释与文档检查：接入候选新增的解释性注释、模块 docstring 和错误文字均为中文；保留原机器字段和测试合同字面量。本记录为本轮新增中文文档。

## 2026-11-07 后续实测

上述“真实 MySQL 未验证”是接入时状态。主会话随后提供本地独立 MySQL 8.4.13，本子代理执行既有真实引擎模块，10 项通过；并完成旧/ready 同库合成比较。默认页旧/ready 三次中位数为 6.856/6.444 秒，无匹配搜索为 6.589/6.001 秒，完整结果相等，仍高于 2 秒目标。生产版本为 8.4.9，本地合成数据不能替代线上验收。具体输入、分段、清理和证据见 [mysql-ready-validation.md](mysql-ready-validation.md)。
