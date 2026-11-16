# 新建 direct 文种绑定验收

## 定向检查

7 项 `tests.test_document_job_modes` 用例通过，覆盖版本化与兼容快照的 `zh/en/ru/auto`、创建后配置变化、四个翻译方向、历史快照回退、继承克隆、术语重绑、direct 零翻译和只登记一份 DOCX。三个改动 Python 文件的语法编译、`git diff --check` 和 Trellis 上下文验证通过。独立复核确认覆盖范围限定在正式创建入口。

## 真实 MinerU v4

2026-11-16，通过本机隔离 FastAPI、SQLite、本地对象存储和正式 Worker 执行服务运行。输入为 TI OPA228 中文和英文数据手册各第 1 页。创建时配置为 `ru`，Worker 执行前改为 `latin`，仅作用于隔离运行时。使用兼容快照 `request_snapshot.mineru_language`。记录真实 HTTP 序列化请求，两个样本各提交一次，均返回 HTTP 200、业务码 0，使用 `vlm` 和 `is_ocr=true`。

| 样本 | 任务 ID | 快照值 | 请求值 | MinerU 与任务终态 |
| --- | --- | --- | --- | --- |
| 中文 OPA228 第 1 页 | `docjob_ab944caf1ae7` | `ch` | `ch` | `done`，`succeeded/completed` |
| 英文 OPA228 第 1 页 | `docjob_8b745555c663` | `en` | `en` | `done`，`succeeded/completed` |

两任务均有 MinerU 结果和渲染记录，翻译阶段、翻译批次、翻译启动和 Provider 调用均为零。通过任务下载接口获取两份 DOCX，每份包含原文正文与一张原生设备信息表。运行证据包含样本 SHA-256、批次 ID、阶段和文件指纹。 [实际请求与任务证据](../../../../../tests/tmp/direct-mineru-source-language-20261116/live-evidence.json)

## WPS 重新打开验收

在 WPS 桌面应用打开导出副本，在原文正文和原生单元格分别加标记，保存、关闭后按原路径重开。界面确认四处标记仍显示，磁盘 DOCX 复核确认它们分别位于原正文段落和原表格单元格内。

| 样本 | 原文正文标记 | 原表格单元格 | 文件 |
| --- | --- | --- | --- |
| 中文 | “精密直流性能的应用。”后有 `[BODY-ZH]` | 第 1 行第 1 列为 `器件型号 [T-ZH]` | [原始 DOCX](../../../../../tests/tmp/direct-mineru-source-language-20261116/OPA228-zh-direct.docx) · [WPS 副本](../../../../../tests/tmp/direct-mineru-source-language-20261116/OPA228-zh-WPS-edit.docx) |
| 英文 | “precision dc performance.” 后有 `[BODY-EN]` | 第 2 行第 2 列为 `Single [T-EN]` | [原始 DOCX](../../../../../tests/tmp/direct-mineru-source-language-20261116/OPA228-en-direct.docx) · [WPS 副本](../../../../../tests/tmp/direct-mineru-source-language-20261116/OPA228-en-WPS-edit.docx) |

WPS 提示本机缺少部分字体。保存后每份副本多一个空段落，原始 DOCX 指纹与初次下载一致。 [WPS 保存内容对照](../../../../../tests/tmp/direct-mineru-source-language-20261116/wps-edit-evidence.json)
