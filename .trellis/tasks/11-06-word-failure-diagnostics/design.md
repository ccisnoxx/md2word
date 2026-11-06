# 设计：复用失败诊断投影，补齐可读摘要

## 数据流与所有权

沿用 renderer/validator → _failure_policy → stage_failed → project_failure_diagnostic → detail/incident API → UI。后端负责证据及脱敏，前端负责中文展示。先修复已确认的展示缺口，不建立第二套错误存储。

## 展示设计

- 在既有 `frontend/src/utils/failureDiagnostic.ts` 维护共享格式化逻辑，结合任务 failed_stage/error_code/error_message 和可选 failure_diagnostic 构造摘要。必要时在同文件导出函数，保持既有调用兼容。
- 为受控原因码和操作类型提供准确中文映射，优先复用 format.ts 现有质量标记文案，不解析任意异常正文推断根因。
- 原因优先级：明确受控原因及安全细分信息 → 已知阶段与任务安全消息 → 具体原因尚未识别及现有技术码。未知机器码保留供诊断，不虚构解释。
- 位置区分：有页码 → 源 PDF 第 N 页；文档范围诊断 → 文档范围错误、无法定位单页；无诊断 → 未记录失败页码。scope=document 不能证明所有页面都错。
- JobOverviewPanel 仅在 failed 时显示摘要，通过既有 props/composable 数据传递，避免额外请求；JobDiagnosticsPanel 和 IncidentTriagePage 复用相同解释。
- 技术细节保留在诊断区域；概览突出原因、阶段和源页。任务 ID/trace_id 使用已有加载结果。

## 后端边界

现有 schema 足够支持已确认的展示改动，默认不改 API、持久化和 worker 状态机。实施时按需要使用定向测试确认页上下文、白名单、事件与投影；仅有复现证据时修复直接相关的信息丢失。如果需要改变公共合同或持久化模型，先更新方案并重新确认。

不得放开 _safe_failure_context 白名单或公开任意 str(exc) 来增加信息。未知异常不能还原精确根因时如实说明信息不足。保持错误分类、retry_count 隔离、权限、降级和发布行为。

## 兼容与风险

旧任务和旧响应允许 failure_diagnostic=null；不补造历史证据。列表仍不逐行请求事件。仅映射语义确认的代码，未知码保留诚实说明。已有可见文案测试随新合同更新。

没有真实失败任务证据，线上旧版本或未覆盖路径仍需进一步核查；UI 改善不能被表述为修复所有转换根因。

## 回退

可按本任务变更路径回退展示修改，无数据库迁移；生产部署另行授权。
