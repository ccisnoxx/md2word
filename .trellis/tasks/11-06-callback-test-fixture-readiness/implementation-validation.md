# 实施与验收记录

日期：2026-11-06。用户明确批准最新最小方案后实施，任务现为 completed（仅本地实现与定向验收完成）；本地实现与定向验收完成，未提交或归档。

## 实际变更

仅 tests/test_fastapi_jobs_backend.py 四个既有回调测试：public_deployment_mode 改为 internal；将已有创建 HTTP 201 断言移至首次读取 job_id 前，原位置删除。合计 8 additions / 8 deletions。

四个方法原有 55 条断言全部保留；共享 build_test_runtime、fake MinerU、真实 renderer、业务代码、安全/就绪检查及其他测试均未修改。新说明仅写入本任务文档；触及范围注释/docstring/开发者文本已审阅，无需新增或翻译，故有意保持不变。

## 验收结果

按 implement.md 的四个 unittest selector 一次运行：4 tests，1.021s，OK，exit 0。错误 checksum 403 且零消息；正常回调先入队、Worker 后完成；重复回调仅一条消息和一次下载；取消后 ignored 且不下载。独立 checker 未发现范围内缺陷，也未二次修正或重跑。

完整命令、stdout/stderr、退出码、时间及源码 SHA-256 见 validation/targeted-tests.*。55 条断言比对和 29 个既有路径保护证据见 validation/static-review.json；评审结论见 checker-report.md。源码未经后续修改，无需重复测试。

## 收尾与边界

- 精确 diff 和静态断言比对通过；git diff --check 无问题。既有 29 个 B03/路线图及业务改动路径的字节/删除状态保持不变。
- 共享 Spec 无行为合同变化，无需修改；已知夹具原因和最小修复选择保留在本任务 research/root-cause.md 和 design.md。
- 输出存在既有 Starlette 弃用警告，未在本任务处理。
- 未运行其他测试、全量测试、lint/typecheck、build、CI 或发布聚合脚本；未启动线上依赖。四例通过不代表公开部署、真实外部服务或 B03 整体验收。
- 未 stage、commit、push、archive 或 add_session；实施验收时 B03 独立任务记录与状态保持原样；随后用户授权本轮记录同步，证据回填及当前状态见 [B03 证据对账](../11-06-mineru-download-boundary/acceptance-reconciliation.md)。本轮没有重跑测试。
