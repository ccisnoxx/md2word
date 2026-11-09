# 运维材料与验收证据索引

整理日期：2026-11-09。本轮仅本地整理，事实截止于下列2026-11-07发布记录；没有重新检查当前生产状态。任务保持completed，原目录保留。

## 阅读顺序与提交范围

1. [生产执行记录](../production-execution.md)：获批窗口、备份恢复、O→C→R、生产迁移、统一切换与线上验收。
2. [主机验收摘要](production-acceptance-result.json)、[浏览器原始采样](production-browser-acceptance.json)、[已同步截图](production-acceptance.jpg)：相互佐证的最终证据。
3. [待批准本地提交计划](../ops-records-commit-plan.md)、[提交输入清单](ops-materials-inventory.json)：精确文件分组、SHA、验证复用条件和范围。
4. [本地材料审计](ops-materials-audit.md)：归属、历史时点、敏感信息及静态一致性核对。

当前代码HEAD为已集成的`b8b2779a9ee678f778ddb95890cebc3a0faff55e`。本批仅提交该版本之后的运维载体、Spec和任务记录，不重复提交已在`1a821110`及PR #34中的产品实现。

## 材料分层

| 材料 | 用途与证据时点 |
| --- | --- |
| [构建报告](production-build.md) / [构建manifest](production-build-manifest.json) | 构建时镜像、57 wheel、341/340运行文件、完整Compose差异及未激活维护候选；其中applied=false、syntax_only等是当时快照。 |
| [审批包manifest](approval-package-manifest.json) | UTC 2026-11-06T17:53:40的历史文件SHA及尚未执行标志；保留原值。 |
| [生产切换与回退方案](../production-switch-plan.md) / [执行准备研究](production-execution-plan.md) | 前者已追加实际完成状态，后者保留审批前命令形状与约束。它们不是新一轮生产授权。 |
| [六文件冻结清单](release-ops-manifest.json) / [载体README](release_ops/README.md) / [独立复核](release-ops-review.md) | 原6文件归档与12项离线/5文件AST/6次镜像CLI导入证据；README中的“尚未演练”属于冻结时事实。 |
| [窗口辅助复核](window-helpers-review.md) / [就绪合同](window-readiness.md) / [切换执行器复核](window-switch-review.md) | 补充辅助脚本的10项直接验证与最终执行器静态复核；不把静态复核当生产执行。 |
| [最终执行记录](../production-execution.md) / 两份验收JSON | 恢复/迁移真实执行和正常管理员浏览器验收；以这些材料说明最终通过。 |
| [本地验证摘要（历史）](verification-summary.md) | 原产品验证次数及局部基准保留；新增历史标记和最终结果链接。 |
| [提交与集成交接](../local-commit-handoff.md) | 既有提交、PR合并及生产完成的顺序记录。 |

### 历史审批SHA与当前方案的关系

`approval-package-manifest.json`固定的4份文档中，`production-build.md`、`production-execution-plan.md`及`release-ops-review.md`当前字节仍匹配；`production-switch-plan.md`已在审批后追加执行状态、实际server_name等，当前文件不等于历史SHA `7676626e955638aa6c45f78170caf3baa3b37e87dbe780b9dee99c902bced6b1`。本地未保存该审批版完整正文，不能宣称已逐字还原或再次核验其内容。保留历史SHA，并在本轮输入清单中单独记录当前SHA；不以重算历史manifest抹平差异。

`release-ops-manifest.json`的`production_execution=false`以及审批manifest的未执行标志都保持原样。最终`accepted=true`见独立的生产验收摘要，不能修改历史false为true。

## 冻结文件及窗口快照

- 原6文件：`release_ops/common.py`、`migrate.py`、`snapshot.py`、`query_diff.py`、`test_release_ops.py`、`README.md`；逐项SHA与原冻结清单一致。归档SHA `63b2d9ec86bbf15eaf4c1bf3483d0dca745c1d807db4203e68fc89415d1d245a`保留；本轮未读取或重新计算远端归档。
- 窗口补充：`release_ops/window_helpers.py`与`test_window_helpers.py`，身份以窗口辅助复核中的最终SHA为准；不把初版9项通过冒充修订后的10项。
- `window-lib.py`是远端`window_lib.py`的证据副本，保留原文件名映射，不为本地import重命名。
- `window-production-switch.py`是已审已执行窗口脚本的原字节快照，SHA `ddb9e4e3f5e845ad9a893c8d7fe5846437561790e20080257a1ca6b0e8754100`。它含固定release路径和有副作用的顶层流程，依赖当次受限状态/配置；不得为了提交检查而import、运行或重放，也不改造成通用发布入口。

## 可复用验证与本轮检查

| 既有结果 | 复用依据与边界 |
| --- | --- |
| 普通列表111个不同用例 | [整合记录](key-integration.md)，包括原8.4.13环境；源码、测试和依赖无新增改动，不当作本轮新跑或生产8.4.9的替代证据。 |
| 异常补充37项及8对正常/4对错误差分 | [实施记录](incident-session-implementation.md)，35离线+2真实RR；保留原事务/错误/观察证据，不与111简单相加。 |
| 载体12项离线、5文件AST、6次新旧镜像CLI导入 | 原6文件SHA相同，直接复用原记录，不重跑pytest/unittest、镜像或数据库。 |
| 窗口辅助10项 / 执行器静态复核 | 4个补充Python/测试文件的SHA与对应review一致，不修改已审代码。 |
| 恢复/生产迁移/O→C→R/线上验收 | 仅保留原11月7日真实执行记录和采样，未连接远端复测。 |
| Trellis上下文清单验证 | implement/check JSONL各6条的既有通过结果；两输入文件当前与HEAD一致，不因本地整理重复执行。 |

本轮只核对新整理输入：本地文件身份与归属、JSON/统计一致性、截图逐字节一致、相对链接和空白；不新增应用/容器/生产检查。具体结果与各文件SHA见输入清单及本地审计。

## 验收数据的解释

最终同步采样各3次、默认page1/page_size20：任务API中位1.5089秒，页面2.0604–2.447秒；异常API中位1.0227秒，页面1.235–1.5632秒。原始首次受控采样和自动化等待产生的上界试验也保留在浏览器JSON，不能只删掉较慢样本或称为p95。

浏览器证据UTC 01:32:44.560，比计划截止01:33:23.545早38.985秒；主机收尾accepted_at=01:38:49.566比截止晚326.021秒。入口已于01:18:34.980恢复；不能笼统称所有收尾在截止前完成。截图是11月7日已有裁剪图的原字节副本，仅展示页头/统计/同步状态，不作为11月9日的新截图。

## 留存边界

版本库只纳入脱敏摘要、静态脚本及裁剪图。原SQL/RDB/var/config归档、完整env/inspect、身份映射、cases及业务响应继续留在原受限证据位置；本轮不复制这些原始资产、不删除源证据、不变更保留期。运维记录包含实例/路径/容器标识，属于本次发布追溯信息，不是凭据；提交前的内容核对见审计报告。

本次不调用archive/add_session：它们会产生自动bookkeeping提交，archive还会移动任务路径。两个拟议工作提交不包含这些动作；任务完成状态与原目录保持。

图像格式核对：原外部文件虽使用.png扩展名，实际字节为JPEG/JFIF（1200×500）；本地留存副本因此命名为production-acceptance.jpg。只更正副本文件名与链接，没有转码或编辑，SHA-256仍为`19fbc282a12488c928895420948794d758a699a2c1d04079e166692e2f67ee3b`。
