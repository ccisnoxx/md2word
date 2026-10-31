# 本地正式转换样本验证

日期：2026-10-22。本轮直接运行已有正式 converter/renderer 样本入口，无后端服务、真实 Provider、VPS 或线上连接。它们证明未变更转换 owner 的基线输出，不代替 TR-406 Worker 的 fake Provider 成功/失败和并发验收。

## 已运行

```bash
.venv/bin/python scripts/dev/manage_component_pdf_samples.py validate
.venv/bin/python scripts/dev/run_component_pdf_regression.py --sample-id ti-opamp-opa228-p1-smoke --json
.venv/bin/python scripts/dev/run_local_mineru_quality_matrix.py --sample-set phase2-core --mode direct
```

- 清单校验：1 enabled/runnable，ok=true，退出0。
- 公开 OPA228 P1：1/1 succeeded，DOCX 可打开，退出0。报告：`tests/tmp/component_pdf_regression/20261022T060045Z/report.json`。
- direct phase2-core：5/5 succeeded，failed=0、blocked=0、p0_issues=0、automated_matrix_ok=true，退出0。报告：`tests/tmp/local_mineru_quality/20261022T060037Z/report.json`。
- 矩阵仍有3个文档的既有标题样式flags：`docx_unstyled_heading_candidates:1/:10/:3`；`phase3_entry_ready=false`，原因 `p1_p2_backlog_required`。本任务未修改正式renderer/模板，不以此扩大样式修复范围。
- 未运行真实 Provider/四方向正式实译、真实 MySQL/S3、LibreOffice/Word 或人工视觉签字。

## 可复用边界

转换 owner 和脚本未变时可复用本结果；若后续实现修改其输入解释/renderer或样本配置，须重新评估。完整草稿下载/批准发布门和任务执行状态另由API/Worker测试验证。
