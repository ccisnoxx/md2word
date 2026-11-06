# 整改总计划进度

更新：2026-11-06。仅整理已有证据，不运行测试、不提交/推送。两专项 completed 表示本地实现与批准定向验收完成，不等同代码已提交、部署或发布。

| 对象 | 当前状态 | 依据/下一边界 |
|---|---|---|
| B03 MinerU 下载边界 | completed（本地验收完成） | [AC01–AC10 对账](../11-06-mineru-download-boundary/acceptance-reconciliation.md)；复用新增边界10例、既有legacy1例及修复后回调4例 |
| 四个既有回调测试夹具专项 | completed（本地验收完成） | [运行证据](../11-06-callback-test-fixture-readiness/validation/targeted-tests.result.json)，4/4，1.021s，55条原断言保留；结果已回填B03 |
| 本整改总计划 | planning，进展部分完成 | 规划材料已交付；B03 已完成，其他批次等待选择/授权；不作为整套整改完成，也不直接启动其余实现 |

## 原总计划验收对应

U1/U2/U3/U5 由 B03 对账中的发送前拒绝、多入口、跳转和 checksum 证据覆盖。U4 的合法下载、错误摘要和取消已有运行证据；换代/CAS 相关代码未改只提供静态保留依据，没有新增换代或并发运行验证。B03 已批准子计划 AC01–AC10 全部满足，不能据此扩大为生产/全生命周期并发验证。

原 A05 描述保留为 main@79f20cef 审查基线；当前本地实现已在所有下载入口统一 URL 策略并完成获批定向验收。未宣称原基线曾被利用或存在已证实生产攻击。

## 其余批次（本轮不启动）

- B01：文档事实与产物清单，P2。
- B02：依赖及镜像来源基线，P1；仍需单独明确方案和授权。
- B04/B05：职责提取及 legacy 剩余消费者收敛，P2。
- B06：表格上下文，继续衔接既有 TR-404，不重复立项。
- B07–B11：按 design.md 的范围和触发条件分别推进，不改变本轮之外的既有任务/manifest 状态。

## 证据复用与操作边界

本轮只读取原日志、报告、源码摘要与 Git 差异；四例源码 SHA-256 与通过时一致，B03 实现及新增边界测试与保留基线一致。没有重跑测试、build、CI、lint/typecheck、发布检查或访问生产。

真实 CDN、生产依赖、代理/DNS 实际兼容及真实 Word 客户端仍未验证。当前代码未提交/推送，任务目录未归档；仅同步三个任务记录，原始失败/通过日志保持不变。

## 2026-11-06 Codex 派单批次（gpt-6-astra / high）

用户授权以 codex-dispatch write 模式实施；Claude 负责任务设计与验收。各写入批次在独立 worktree（基于 79f20cef）完成，均未 commit/push。

| 批次 | 分支 / worktree | Claude 验收 | 要点 |
|---|---|---|---|
| B01 | codex/b01-doc-facts | 通过 | Token 模块/差距/架构/Spec 文字更正；两个 test-results 已 `git rm --cached`（已暂存） |
| B04 | codex/b04-failure-policy | 通过 | 新增 `_failure_policy.py` 为失败分类/消息/证据唯一 owner；12 例定向通过；3 个既有失败在基线同样复现，属历史测试维护，未修 |
| B06 | codex/b06-table-context | 通过 | `translation_table_context_enabled` 默认关闭；61 例通过；语义质量未验证，开启前须排空在途翻译 |
| B07 | codex/b07-frontend-routes | 通过 | 路由动态导入；JobDetailPage 2995→264 行；入口 JS -38%；103 例 + vue-tsc 通过 |
| B05 | 只读调查 | 通过（调查） | 旧链路仍被启动重放与 StageWorker 消费，不可删；建议 0–4 分步，第 0/3 步需环境核查与在途任务决策 |

未派单：B02（独立任务进行中，需 hostdzire）、B08–B11（条件未触发）、CI（项目规则需用户明确要求）。B04 与主工作区 B03 均改动 execution.py 与 error-handling.md，合并时需处理。
