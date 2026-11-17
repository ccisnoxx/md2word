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


## Session 63: 生产冷启动单一初始化

**Date**: 2026-11-16
**Task**: 生产冷启动单一初始化
**Branch**: `codex/production-cold-start-bootstrap`

### Summary

API 统一负责 SQL schema、内部账号导入和资源 seed。生产与开发 Compose 等待 API 健康后启动 Worker。16 项定向检查及空库一次启动、API 初始化失败拦截、保留数据分别重启三项隔离验收通过。验收报告已随任务归档，隔离资源已清理。

### Git Commits

| Hash | Message |
|------|---------|
| `374403859b74242daa327491c7d085fb619eeed2` | (see git log) |

### Status

[OK] **Completed**


## Session 64: 参数表未决数值列以警告交付

**Date**: 2026-11-17
**Task**: 参数表未决数值列以警告交付
**Branch**: `main`

### Summary

未决数值列以警告生成可下载的 DOCX。确认当前报告后可批准发布，无效人工核定保留上一代 DOCX。

### Main Changes

- 归档 [任务验收记录](../../tasks/archive/2026-11/11-17-table-value-column-warning-delivery/implement.md)。

### Git Commits

| Hash | Message |
|------|---------|
| `6fa8664` | (see git log) |

### Testing

- [OK] 复用已执行的主回归结果，75 项通过、2 项因缺少样本路径跳过。补充回归 16 项通过，其中 1 项为历史 v3 下载复验。OpenAPI、Trellis 上下文和差异检查已通过。

### Status

[OK] **Completed**


## Session 65: 坏表结构的可复核回退交付

**Date**: 2026-11-17
**Task**: 坏表结构的可复核回退交付
**Branch**: `main`

### Summary

普通 PDF 转 DOCX 可保留坏表 HTML、非法合并格和空表占位失败场景中的可靠来源，生成可下载的 DOCX 并记录警告与人工复核定位。

### Main Changes

- 依次采用可核验的原生表、参考图或原 PDF 裁图、原 PDF 整页图像；图像回退带不可编辑提示。
- 无可靠回退时明确失败；资产摘要与 Word 实物完整性门禁保留。归档已由 26262657 完成。

### Git Commits

| Hash | Message |
|------|---------|
| `e03815a3` | (see git log) |

### Testing

- [OK] 复用六项定向结果。原生表、参考图、单页原图三个场景复验通过，核对 warning、人工复核定位、HTTP 200 下载和主件字节。
- [OK] 复用首轮三个负例的通过结果，包括无可靠回退、参考图摘要不一致和 Word 漏表。未重跑测试。
- 局部裁图、跨页回退、v2 图表分支、非字符串坏 HTML 的占位证据和历史凭据兼容仅静态复核。生产部署、生产预览、Word/WPS 视觉及发布后最终件下载未验证。

### Status

[OK] **Completed**
