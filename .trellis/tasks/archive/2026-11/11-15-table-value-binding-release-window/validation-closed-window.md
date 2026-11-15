# 第六阶段关闸生产窗口验收

## 已完成的切换和运行核对

2026-11-15 12:33 UTC，按授权在 `hostdzire` 的 `md2word-p0` 项目只替换 API 与 Worker。使用已隔离验收的 Linux/amd64 候选 `sha256:3ef58149ac459277d74dbc7552de7b3863b8bc78ca6dd02677c827dbec1f7b81`，对照现有分支的 425 个应用、脚本及资源文件，摘要全部相符。部署标识为 `hostdzire-8034ead5-table-values-closed-20261115`。API 和 Worker 的镜像及发布标识相同。

在原有十一层 Compose 之后追加本次应用服务 override。展开编排后逐项对比，只有两项应用服务的镜像、发布标识和关闸配置改变。MySQL 与 Redis 的容器 ID 及启动时间均保持。保留上一制品 `sha256:1c50d72534cefaf27dc35801706bdb44d5bff457a9857dbf348ea6c1890be8c6` 与原 Compose 文件顺序，本次没有执行回退。

- 回源及公开入口 `/api/v1/health/ready` 均为 200，均报告 `8034ead5`。Worker 由正式入口启动，日志报告 ready 和 `document-jobs` 队列。启动日志未匹配到 ERROR 或 Traceback。
- 在两个实际容器使用服务用户核对有效配置，总开关均为 false，白名单均为空。Worker 使用 Celery，文档队列为 `document-jobs`，翻译队列为 `document-translation-batches`。五项 Poppler 工具均在 `/usr/bin`，均为 25.03.0。
- 两个实例均从生产运行时配置读取目标 MinerU 账号，脱敏 UID 匹配。VLM 与正式回调路径有效配置已核对。生产 Word 预览和发布写开关保持关闭。

## P7 真实回调及实物验收

2026-11-15 12:44 UTC，使用已授权的工作台账号，从正式入口提交一份关闸 P7 对照件。任务脱敏标识 `fa6c6a44f35b20f4`，原文转可编辑 Word，第 0 解析代。正式文件登记实读为 112080 字节，SHA-256 为 `24f724cf0e795f6afeb6fec5c72ff8f144085c59d57fbf0a5c9efbf1808b1eb3`。

| 证据 | 结果 |
| --- | --- |
| 真实回调验签 | 12:44:41.724 UTC 记录 `mineru_callback_received`，该事件在正式入口验签通过后写入。相邻的生产回调请求返回 HTTP 200。签名 `content` 的 SHA-256 为 `ea161910de0b81695902c5273d76df626d93bc8b106e72e8ddec5f5b727e0d79`。签名内容中的批次和结果身份与当代上传登记匹配。 |
| 当前代 Worker 消费 | 同一专用消息于 12:44:41.755 UTC 入队，12:44:44.031 UTC 完成消费。第 0 代只有 1 条完成态消息及 1 次成功尝试，消费事件的原包指针与任务登记一致。 |
| 原包归档 | 实读 231554 字节，SHA-256 为 `d89add63817aec1a66001c7d3dbb68ee30882e4d80b9dbd43dc7358834ead073`。原包身份认证标记、实际上传指纹、源文件、批次、`data_id` 和解析代对账一致。重读 v2、layout 和包内 PDF 的摘要。包内 PDF 指纹与上传 PDF 不同，关闸路径未生成逐页等同证据。 |
| 实际 Word | 任务转换成功。用正式证据读取契约重读第 0 代报告、IR 和 Word。实际 DOCX SHA-256 为 `043682d696c1af00f363d28d8aa90deab8e5d7aad6791c9325c65afec6ffdaec`。关闸后 `±5 µV` 仍跨 MIN–TYP，`±100 µV` 仍跨 MIN–TYP–MAX。本次回包的 23 个原跨列 blocker 全部保留，自动修正及解阻均为 0。 |
| 审批与发布状态 | 质量为 `blocked`，复核为 `unreviewed`，交付为 `internal_draft`。工作台标示仅供内部使用，发布资格显示质量阻塞，复核及发布记录均为 0。生产发布写开关保持关闭。本轮通过只读状态核实门禁，审批、发布或同包重生成写请求均未发出。 |

## 关闸验收收口

P7 关闸验收通过。MinerU 真实回调已通过验签，第 0 代 Worker 已消费同一回调消息并归档原包，实际 Word 的 23 个原始跨列阻断全部保留，自动解除为 0。总开关保持 `false`，白名单为空。第六阶段任务保持 `in_progress`，单公司灰度尚未开始。

[第五阶段收口](../11-15-table-value-pdf-binding-rollout/validation.md#第五阶段收口) 单独保留既有生成件的结论。留存 P7 的 13 处和真实新回包 P7 的 14 处均继续阻断各自审批和发布，严格逐页比对未通过的 LOW/HIGH 结论照旧。本次生产关闸样本的 23 处全部保留结果独立记录。
