# 第六阶段隔离名单对照与关闸回滚

沿用现有分支的 `0d62a292` 与正式候选 `8034ead5`。生产环境保持关闸，本次只在隔离环境改变名单和开关。当前生产真实回调及关闸结果见[生产关闸窗口验收](validation-closed-window.md)。

各组使用同一份 P7 上传原件（SHA-256 `24f724cf0e795f6afeb6fec5c72ff8f144085c59d57fbf0a5c9efbf1808b1eb3`）及第五阶段留存真实原包（SHA-256 `5de05d59fdacea166361bde14625ff8045350b0aefc894a923ff181a030fe033`）。留存原包在隔离环境按各自任务登记来源，复用正式转换及证据读取；本轮无真实托管新提交。

## 运行与范围

复用 Linux/amd64 镜像 `sha256:3ef58149ac459277d74dbc7552de7b3863b8bc78ca6dd02677c827dbec1f7b81`，与关闸生产验收为同一镜像。隔离环境使用 MySQL、独立 Redis 队列、临时对象目录和无外网的 Docker 内部网络。运行正式 Uvicorn API 与 Celery Worker，并从镜像内核对 Poppler 25.03.0 及五个取证应用文件的摘要。

同一测试租户 `canary6_test_tenant` 有 `canary6_company_in` 和 `canary6_company_out` 两个公司。各组通过正式认证和上传入口，核对了持久化的账号、任务和文件归属。开启阶段的 API 与 Worker 使用同一份单公司白名单 `[["canary6_test_tenant","canary6_company_in"]]`。

## 名单对照

| 场景 | 实物与质量证据 | 正式审批及发布 |
| --- | --- | --- |
| 名单内 | 18 个原始阻断中，只有实际 Word 认证通过的 5 处解除。原 finding 与有效 blocker 按 ID 对账，剩余 13 处为 `row_ambiguous`。`±5 µV` 只在 TYP，`±100 µV` 保持只在 MAX，均占一列。正式 IR 有逐页等同证据。 | 审批 409 `review_quality_blocked`，发布 409 `publication_quality_blocked`。 |
| 名单外 | 零修正、零认证，18 个原始阻断全部保留。`±5 µV` 仍跨 MIN–TYP 两列，`±100 µV` 保持只在 MAX。正式 IR 无逐页等同凭证。 | 审批 409 `review_quality_blocked`，发布 409 `publication_quality_blocked`。 |

两组复核与发布历史均为空。名单外文档的 `pdf_value_column_unresolved` 为空，因为该任务未进入自动核定，交付仍由原始质量阻断拦截。

## 关闸回滚

在同一候选镜像上，将总开关改回 `false`、白名单清空为 `[]`。重启隔离 API 和 Worker，核对两个进程的配置，并沿用同一隔离 MySQL、Redis 队列和对象目录。

| 对照 | 关闸结果 |
| --- | --- |
| 原名单内公司的关闸后新任务 | 零修正、零认证，18 处原始阻断全部保留。Word 的 `±5 µV` 仍跨 MIN–TYP，`±100 µV` 仍只在 MAX。审批和发布继续因质量阻断返回 409。 |
| 开启期间的名单内旧任务 | 关闸后可通过正式证据契约重读。原包、IR、报告与 Word 的 SHA-256、报告 finding ID、认证项和 blocker 集合均与关闸前相同。已认证 5 处及剩余 13 处继续有效，审批及发布仍因质量阻断返回 409。 |

两类关闸对照的复核与发布历史均为空。三份新生成的结果逐一核对了同一组 18 个原始 finding ID。有且只有实物认证集合会从有效阻断集合中扣除。

本次验证功能停用与兼容旧件读取，沿用同一候选镜像。已接纳同包 UUID 及在途代的停用证据见[第五阶段单公司停用演练](../11-15-table-value-pdf-binding-rollout/validation.md#单公司灰度与回滚)。本轮没有新增人工修正或回退镜像。

本轮隔离名单内外及关闸回滚通过。生产未操作，保持关闭和空名单。第五阶段 P7 13/14 项与 LOW/HIGH 严格比对结论、生产关闸 P7 的 23 项阻断分别保留。第六阶段任务保持 `in_progress`。
