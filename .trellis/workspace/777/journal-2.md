# Journal - 777 (Part 2)

> Continuation from `journal-1.md` (archived at ~2000 lines)
> Started: 2026-11-16

---



## Session 61: 参数表数值列归属检查

**Date**: 2026-11-16
**Task**: 参数表数值列归属检查
**Branch**: `main`

### Summary

Datasheet Q3 / AC4 子项已归档。质量报告定位数值跨列歧义，保留原生可编辑 DOCX，正式发布要求当前主件和报告的有效人工确认。

### Main Changes

- 按源 Grid 识别数值列跨越，报告源位置和值，复用现有审核与发布合同。

### Git Commits

| Hash | Message |
|------|---------|
| `f1fd5398c34881a56b1594e3496717436fed28a5` | (see git log) |

### Testing

- [OK] 复用既有三包回放：SN74AC244 首轮 v4 报 6 项、重传 v4 无命中，OPA228 第 7 页准确定位 ±5 µV 和 ±100 µV；核对可编辑 Word 网格及值。
- [OK] 复用 24 项定向测试、OpenAPI 校验及发布拒绝证据。
- [OK] 历史 mock 失败保留：test_review_cas_rejects_retry_replacement_blocker_and_none_result_races 读取旧 expected_result_file_id 触发 KeyError。

### Status

[OK] **Completed**


## Session 62: 集中 API 启动初始化并复用 Celery Worker Runtime

**Date**: 2026-11-16
**Task**: 集中 API 启动初始化并复用 Celery Worker Runtime
**Branch**: `main`

### Summary

完成并归档 11-16-api-bootstrap-worker-runtime。API 负责 schema 和 seed，Worker 等 API 健康后启动并按进程复用 Runtime，保留现有 MinerU 启动恢复。

### Git Commits

| Hash | Message |
|------|---------|
| `dab58d26` | (see git log) |

### Testing

- [OK] 复用已通过的 63 项定向测试、真实 fork 检查及 dev/prod Compose 配置检查。

### Status

[OK] **Completed**

### Next Steps

- 本次为本地收尾，未推送或部署生产。
