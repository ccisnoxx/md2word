# CON-101 规划校验记录

日期：2026-10-12（America/Los_Angeles）；分支 `md2word/CON-101`；业务基线 HEAD `e03232e`。

## 实际完成

- `pwd` 与初始 `git status --short`：目录正确，唯一已有 dirty 为 `.gitignore`。
- 已核对 CON-101=`todo`、BAS-001=`done` 与归档人工验收；依赖通过，无需 blocked。
- 复用现有父任务，未发现同 slug 子任务；通过 `task.py create --parent` 创建 `.trellis/tasks/10-12-con-101-product-mode-ui-copy`，随后记录实际分支。
- 三份规划及 research 已完成，PRD 按最终需求结构重写并通读，AC1–AC8 与有序计划/风险对应；无未决产品冲突，等待人工评审。
- manifest 只将 CON-101 改为 planning、记录实际路径和说明；resolution 仍为 null。

## 实际验证

| 检查 | 结果 |
|---|---|
| `python3 .trellis/scripts/task.py validate .trellis/tasks/10-12-con-101-product-mode-ui-copy` | 退出 0，All validations passed；implement.jsonl 4 条、check.jsonl 5 条。此命令校验 context，不代替人工需求审核。 |
| schema 只读探针 | 退出 0，direct 被接受；两种历史 alias 的 normalizer=direct、create_schema=literal_error，确认待修缺口。 |
| direct resolver spy 探针 | 退出 0，当前 direct 空值及显式旧 term ID 都调用术语 resolver，确认待修缺口；没有加载真实数据。 |
| `git diff --check` | 退出 0。另以 Python 检查未跟踪规划文件行尾空白、换行、Markdown 相对链接、JSON/JSONL 路径及现有测试方法名称。 |
| manifest/父任务对比 HEAD | 其余 44 个任务对象完全不变；父 task.json 仅新增本子任务 children 项，父状态未变。 |
| 业务路径 diff | `app/frontend/tests/scripts/resources/docs/api/.trellis/spec` 无变化。 |
| `.gitignore` 校验 | SHA-256 仍为 `b0719d64dea7293460521fa0fb9b575bb3440abcdc4d567ec465adc95a39dc89`。 |
| `task.py current --source` | 指向当前子任务的会话规划指针；task.json status=planning。指针由 create 自动设置，没有执行 start。 |

## 未执行与证据边界

没有修改业务代码、测试、API 文档/OpenAPI 快照、业务配置或 Spec；没有执行实现、业务测试套件、构建、Playwright、真实数据库、MinerU/LLM、部署、提交或 push。implement.md 中这些是计划，不是已通过结果。BAS-001 的历史测试证据未冒充本轮执行。

本轮主代理完成调查和规划，没有派发实现或独立复核，因没有候选业务 diff 不宣称独立代码审查。后续实际 API 变更的独立审查已纳入计划。

两个探针通过 stdin 执行，没有一次性脚本/日志、DOCX、截图或报告临时文件；没有启动后台服务和端口监听。保留的 research、三份规划、context、task.json 和本记录均为正式规划交付物；保留 Trellis 会话规划指针用于评审续接。

## 当前评审重点

1. HTTP alias 的兼容接受与规范枚举分离，未知/空串仍失败。
2. direct 新请求显式翻译资源统一拒绝会收紧旧行为；历史任务惰性快照不迁移、不清理、不重新加载。
3. 仅隐藏翻译/AI 项，不能吞 P0 blocker、未知 warning、符号规则或改变权限。
4. 无 DB/状态机/发布扩展，全部冻结不变量保留；CON-101 尚未实现，不建议 skipped_existing。

规划停在评审门，等待用户审核三份文档。
