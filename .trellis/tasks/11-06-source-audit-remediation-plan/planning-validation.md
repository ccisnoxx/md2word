# 规划校验记录

日期：2026-11-06（Asia/Shanghai）。代码基线：`main@79f20cef9ca0bb1a59af635e2408e130c4935e2d`。

## 已执行与结果

| 检查 | 结果与证据边界 |
|---|---|
| 初始 Git 状态与提交 | main，干净；与用户报告基线一致；未 fetch。 |
| 源码/Spec/测试定义/任务调查 | A01–A29 已建立；没有运行测试或把历史测试记录计作本轮通过。 |
| PRD 收敛 | 按目标、事实、需求、范围和 AC 重写并复核，当前规划无阻塞问题；未来专项决定明确延期。 |
| Trellis context 校验 | `python3 .trellis/scripts/task.py validate .trellis/tasks/11-06-source-audit-remediation-plan` 退出 0；implement/check 各 9 项真实条目，最终无警告。 |
| 引用检查 | 只读 Python 检查 112 个不同的文件:行号组合，文件存在且行号有效；这不是逐项运行验收。 |
| 编号覆盖 | A01–A29 共 29 项、B01–B11 共 11 批完整。 |
| JSON/JSONL 与状态 | 可解析，context 路径存在，无 seed 示例行；任务保持 planning。 |
| 未来测试入口定位 | 3 个具体 class.method 选择器经 AST 定位存在；仅解析源码，没有导入应用或执行用例。 |
| 新文件空白 | Python 检查未发现尾空白；新文件尚未跟踪，不能单凭 git diff --check 声称覆盖。 |
| Git 范围 | 已跟踪文件无 diff，index 无 diff；未跟踪文件均在本任务目录。未改业务、配置、依赖、测试、Spec、其他任务或产品 manifest。 |

## 校验过程中的工具问题

- task.py set-meta 首次使用了不支持的多参数写法，退出 2，未写入 metadata。阅读 --help 后按 dir/key/value 调用成功，只记录 planning_only 与基线。
- 首次 context 校验发现 Word 规范文件超出 32 KiB 注入上限。改用 backend index 定位权威文件，明确后续按相关段落读取；没有更改 Spec 或提高限制。
- 自编引用检查首次遇到 task 工具生成的 _example 行而停止；按模板说明删除示例行后重跑通过。以上均为文档工具问题，不是产品测试失败。
- 最终格式检查曾要求工具生成的 task.json 必须有末尾换行；JSON 本身没有此要求，改为仅对 Markdown/JSONL 检查末尾换行，保留 task 工具输出后复查。

## 本轮交付与授权边界

新增文件：prd.md、design.md、implement.md、task.json、implement.jsonl、check.jsonl、research/audit-matrix.md、research/existing-work.md、planning-validation.md，共 9 个。Trellis 创建命令同时设置了本会话任务指针，未调用 start，未进入业务实施。

未执行：应用单测、全量测试、前端构建/浏览器、依赖安装、Docker pull/build、CI、release/online 聚合检查、真实 Provider 调用、MySQL/S3/Worker/Word 运行验收、生产访问、提交、推送、归档、add_session。

初始规划校验时的结果是“规划材料已交付、等待审阅”，不是 B01–B11 已实施，也不是产品验收完成。优先候选为 B03 下载边界一致性和 B02 依赖基线；B01 可独立开展。实际下一批工作仍需用户选定与授权。

## 后续状态说明（2026-11-06）

上文保留首次规划的检查结果。当前 B03 及其回调夹具专项已完成获批本地定向验收，证据已回填；本总计划继续 planning，其他批次待选择/授权。当前进度以 [progress.md](progress.md) 为准。本轮只整理记录，没有重新运行应用测试。
