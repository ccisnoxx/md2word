---
doc_type: lib-api-ref
entry: config-workbench
category: endpoint
status: current
source_files:
  - app/api/v1/router.py
  - app/domains/config_workbench/router.py
  - app/domains/config_workbench/schemas.py
  - app/domains/config_workbench/summary.py
  - app/services/health_service.py
summary: Config Workbench API 为配置中心提供只读总览、发布门禁和按组深度检查。
tags: [config, governance, api, readiness]
last_reviewed: 2026-06-10
---

# Config Workbench API

## 概述

`config-workbench` 统一挂在 `/api/v1/config-workbench` 下，只读聚合系统状态、模板、术语规则集、翻译配置和翻译术语集治理信息。

当前约束：

- 需要 Bearer JWT，且必须是 `admin` 角色。
- 不执行发布、审核、重试、回滚或任何写操作。
- 响应不包含 secret 原文，只返回脱敏后的状态、数量、路径和治理入口。
- `mode=overview` 跳过术语规则集和翻译术语集的深度发布前检查，用于配置中心首屏快速加载。
- `mode=full` 返回完整检查；默认值为 `full`，兼容已有调用。

## API 参考

### `GET /api/v1/config-workbench/summary`

- 用途：返回配置中心总览。
- 认证：Bearer admin JWT。
- 查询参数：

| 参数 | 默认值 | 说明 |
|---|---|---|
| `mode` | `full` | `overview` 或 `full`；`overview` 会把深度检查组标记为 `detail_status=deferred` |

响应核心字段：

| 字段 | 说明 |
|---|---|
| `generated_at` | 生成时间 |
| `overall_status` | `ready`、`warning`、`blocked` 或 `unavailable` |
| `release_gate` | P0 文档任务发布门禁 |
| `groups[]` | 配置治理分组 |

`release_gate` 字段：

| 字段 | 说明 |
|---|---|
| `p0_document_jobs_required` | 当前部署是否要求 P0 文档任务链路就绪 |
| `p0_document_jobs_ready` | P0 文档任务链路是否就绪 |
| `blockers` / `warnings` | 机器可读就绪检查代码 |
| `blocker_findings` / `warning_findings` | 中文 finding，供前端直接展示 |

`groups[]` 字段：

| 字段 | 说明 |
|---|---|
| `id` | 分组 ID |
| `label` | 中文分组名 |
| `status` | `ready`、`warning`、`blocked` 或 `unavailable` |
| `detail_status` | `complete`、`deferred` 或 `failed` |
| `route` | 前端治理入口 |
| `default_label` | 当前默认版本标签 |
| `draft_count` | 草稿数量 |
| `pending_count` | 待处理建议数量 |
| `warning_count` / `blocker_count` | 告警和阻断数量 |
| `findings[]` | 中文诊断项 |

### `GET /api/v1/config-workbench/groups/{group_id}`

- 用途：返回单个配置治理分组明细。
- 认证：Bearer admin JWT。
- 路径参数：

| 参数 | 说明 |
|---|---|
| `group_id` | `runtime_readiness`、`templates`、`term_rule_sets`、`translation_profiles` 或 `translation_term_sets` |

- 查询参数：

| 参数 | 默认值 | 说明 |
|---|---|---|
| `mode` | `full` | `overview` 或 `full` |

前端配置中心建议流程：

1. 先请求 `GET /summary?mode=overview` 渲染首屏。
2. 对 `detail_status=deferred` 的分组再请求 `GET /groups/{group_id}?mode=full`。
3. 若分组明细失败，只标记该分组的深度检查失败，不阻断其他分组展示。

MinerU 密钥诊断路由约定：

- `mineru_api_token_missing` 和 `mineru_config_invalid` 指向 `/settings/mineru`。
- `mineru_callback_url_missing` 与 `mineru_uid_missing` 仍指向系统状态，因为 MinerU 配置页当前只维护 API 密钥。

## 状态语义

| 状态 | 说明 |
|---|---|
| `ready` | 当前分组没有阻断或告警 |
| `warning` | 当前分组存在发布前建议处理事项 |
| `blocked` | 当前分组存在必须先处理的阻断项 |
| `unavailable` | 当前部署未启用对应治理能力 |
| `complete` | 已完成该分组检查 |
| `deferred` | 概览模式暂缓深度检查 |
| `failed` | 读取或检查失败 |
