---
doc_type: rollout-plan
status: target
last_reviewed: 2026-10-03
---

# 迁移、兼容与上线方案

## 1. 原则

- API 优先 additive；
- DB 新字段先可空/有默认值；
- API 与 Worker 必须支持滚动部署窗口；
- 历史任务不自动重跑；
- 历史发布/结果文件不覆盖；
- 新门禁先观测、后阻断，但技术 Token 和确定性内容丢失例外，直接 fail-closed。

## 2. 数据库迁移顺序

### Migration A：任务状态

新增：

```text
quality_status
review_status
delivery_status
quality_summary_json
```

默认：

```text
quality_status = pending
review_status = unreviewed
delivery_status = internal_draft
```

### Migration B：质量和复核表

```text
document_job_quality_runs
document_job_review_records
```

### Migration C：发布表

```text
document_job_publications
```

Publication 表对 `result_file_id/checksum` 建唯一或业务约束，防止重复发布。

### Migration D：可选 preview/evidence metadata

优先复用 document_files；只在确需查询字段时新增关联列。

## 3. 历史任务 backfill

### 已成功 direct/translation

- `quality_status=pending` 或 `warning`，不能假定 passed；
- `review_status` 从旧 translation QA 映射；
- `delivery_status=internal_draft`；
- 不自动创建 publication。

### 旧 translation QA

```text
approved → approved
needs_fix → needs_fix
blocked → blocked
unreviewed → unreviewed
```

只有与当前 `result_file_id/hash` 一致时映射有效。

### 历史人工 Golden signoff

不自动转为任务 publication，除非有可验证 result file/hash 和 Admin 明确迁移动作。

## 4. API 兼容

第一阶段同时返回：

```json
{
  "translation_qa_status": "approved",
  "review": {"status":"approved"}
}
```

新前端切到 `review` 后，再在后续 PRD 版本废弃旧字段。

Stage 新值需要前端 unknown fallback，旧前端不能因新 stage 崩溃。

## 5. Feature Flags

建议：

```text
DOCUMENT_QUALITY_STATUS_ENABLED
CANONICAL_TABLE_GRID_ENABLED
TRANSLATION_PROTECTED_TOKENS_ENABLED
WORD_PREVIEW_ENABLED
DOCUMENT_PUBLICATION_ENABLED
UNIFIED_REVIEW_ENABLED
```

使用原则：

- 不是永久双实现；
- 每个 flag 有移除条件；
- 新任务按创建时 flag snapshot 行为；
- 不在任务中途切换算法。

## 6. 上线阶段

### A. 影子质量

- 新 validator 只写 flags；
- 不改变用户状态（确定性 blocker 除外）；
- 比较误报。

### B. 内部 blocked

- 新任务聚合 quality status；
- blocked 下载提示；
- publish 功能尚未开放。

### C. 审核统一

- 新 review API/UI；
- 旧 translation QA 兼容；
- direct QA 启用。

### D. 发布启用

- Admin-only；
- preview required；
- 先在观察样本启用；
- 正式 gate 通过后成为默认。

## 7. API/Worker 部署顺序

1. 备份；
2. 执行 additive migration；
3. 部署兼容新旧字段的 API；
4. 部署 Worker；
5. 运行 readiness；
6. 开启 shadow flags；
7. 执行回归；
8. 逐项启用功能；
9. 最后删除兼容代码。

## 8. 回滚

### 代码回滚

- 新字段继续保留；
- 旧 API 能忽略；
- feature flag 关闭新行为；
- 不回删已生成质量和发布记录。

### 数据回滚

不建议删除新表/列。回滚以停用新读写为主，避免丢失审计。

### Provider/Renderer 回滚

- 任务快照记录算法版本；
- 新任务可切回旧版本；
- 已开始任务使用原 snapshot 完成或明确失败；
- 发布件不重新生成。

## 9. 上线验证

- DB schema current；
- API/Worker 版本一致；
- direct 不调用 LLM；
- blocked 下载/发布 negative test；
- unreviewed 下载/发布 negative test；
- preview；
- Publication immutable；
- Golden Samples；
- 启用语言方向的 translation samples；
- metrics/alerts。

## 10. 兼容代码移除条件

只有满足全部条件：

- 新前端已部署；
- API 客户端无旧字段依赖；
- 历史任务查询通过；
- 线上至少一个完整发布周期；
- rollback 不再需要旧实现；
- 文档和 OpenAPI 已标记 deprecation。
