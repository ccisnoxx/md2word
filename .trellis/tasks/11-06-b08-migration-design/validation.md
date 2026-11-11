# B08 设计交付验证

## 交付与授权边界

日期：2026-11-06。源码基线：`828e1d9d656bf266cba7bba0ed23a62c550db15c`，分支 `codex/b08-migration-design`。仅新增本任务目录；未修改产品代码/测试/Spec/依赖/部署或总清单，未访问生产、数据库服务、Provider/MinerU，未 commit/push/发布/归档/写开发日志。

三件套已完成；task.json 保持 planning，未来实施决定 D-1 至 D-5 尚待批准。这是设计交付状态，不代表迁移完成或 Claude 已验收。

初始化读取 get_context 的普通模式提示开发者未初始化；未运行 init_developer（避免扩大写入范围）。通过 task.py create 的显式 assignee 和 no-start 参数只创建本任务目录，phase/packages 上下文可正常读取，文档校验不受影响。

## 本轮已执行检查

| 检查/实际命令 | 结果 | 证据边界 |
|---|---|---|
| `PYTHONDONTWRITEBYTECODE=1 ${PROJECT_ROOT}/.venv/bin/python .trellis/scripts/task.py validate .trellis/tasks/11-06-b08-migration-design` | 通过 | implement.jsonl、check.jsonl 各 5 个有效条目；这是上下文格式/路径检查，不是设计语义或迁移执行验收。 |
| `PYTHONDONTWRITEBYTECODE=1 ${PROJECT_ROOT}/.venv/bin/python -`（内联只读检查） | 通过 | 扫描三件套中反引号包裹的代码文件:行号，共 29 处唯一引用；路径存在且行号有效，已输出并人工核对目标行含义。另检查行尾空白、task.json 可解析、Git 未跟踪范围及暂存/已跟踪差异为空。 |
| `git diff --check` | 通过 | 无已跟踪差异或空白错误；新增文件的空白检查由上条补足。 |
| `git status --short --untracked-files=all`、`git diff --stat`、`git diff --cached --stat` | 通过 | 只有本任务目录内新增文件，已跟踪及暂存差异为空。 |

内联检查采用 pathlib 读取文件、正则提取现有代码锚点，并以 git porcelain 返回值断言全部路径位于本任务目录；没有 import 应用模块、启动服务或写入临时文件。

## AC 对账

| 编号 | 状态 | 证据 |
|---|---|---|
| AC-1 | met | prd.md 包含目标/范围/非目标、B05 顺序和 D-1 至 D-5 审批点；生产 DROP 独立授权。 |
| AC-2 | met | design.md 包含单表账本逻辑结构、两种基线轮廓、单连接执行者、只读兼容检查、P/Q 恢复、逐项可逆性、保护表和三表前置条件，并比较显式 SQL 与 Alembic。 |
| AC-3 | met | implement.md 的 S0–S10、F1–F16 与六组真实引擎检查定义最小验证和停止条件；明确隔离 MySQL/生产的不同授权边界。 |
| AC-4 | met | 29 处唯一代码锚点核实通过；未来测试模块明确标记拟新增，不冒充已有实现。 |

## 未运行与风险

- 应用测试、真实 MySQL 重跑/中断/恢复、生产结构/行数/消费者和备份核查均未运行，属于未来实施与授权验证范围。未执行 unittest discover、完整前端测试、check_release 或在线门禁。
- B05 第 3/4 步尚未合入是用户给定状态；本分支三表 CREATE 仍存在。不能部署本分支后直接 DROP，否则旧启动维护可能重建表。
- 现有初始化包含 DDL 与数据维护，外层 rollback 不保证整体恢复；本轮未发现足以确认正在发生立即数据损坏的证据，也未修改维护逻辑。
- 推荐显式 SQL 方案，但工具、旧版本/数据库（含 SQLite）、停写/RTO/RPO、生产操作与 DROP 仍待批准。Alembic 1.20.1 仅完成官方文档和发布说明层面的比较，未安装或验证依赖组合。
- 生产 0/2511/119 行快照不能替代未来窗口中的再次检查；fake 或离线夹具不能证明真实 MySQL DDL、锁与恢复正确。

## 独立只读复核

独立 reviewer 已检查三件套和 29 处唯一代码锚点，最终未发现阻断本轮设计交付的具体合同漏洞。复核中明确收缩恢复必须持续对照首次停写保护快照，并修正其适用范围：该守恒要求仅针对 B08_002；fresh 用冻结清单 P/Q 与业务数据仍为零判定恢复，避免将正常建表误判为漂移。对应隔离验证要求已同步。

复核仅为静态设计审查，未运行应用测试或访问服务。最终范围检查确认 7 个新增任务文件；JSON/JSONL 可解析，代码引用有效，无行尾空白，已跟踪及暂存差异为空。Trellis 上下文条目未变化，复用已通过的 task.py validate 结果。
