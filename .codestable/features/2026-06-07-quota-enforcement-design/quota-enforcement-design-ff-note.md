---
doc_type: feature-ff-note
feature: quota-enforcement-design
date: 2026-06-07
requirement:
tags: [phase5, quota, files, enforcement]
---

## 做了什么
在 quota policy dry-run 基础上接入真实上传授权 preflight：policy ready 且 projected usage 达到 block 阈值时阻断 `/files/upload-url`，Admin 可用确认短语和 reason override。

## 改了哪些
- app/domains/files/quota_policy.py — 增加 enforcement decision、admin override、block/override compact audit reason。
- app/domains/files/router.py — 在 upload authorization 前执行 quota preflight，写 `file.quota_policy_block` / `file.quota_policy_override` 结构化审计。
- app/domains/files/schemas.py、frontend/src/api/types.ts、docs/api/files.md、docs/api/openapi.json — 同步可选 override 字段和 API 合同。
- tests/test_fastapi_jobs_backend.py — 覆盖 ready policy 阻断、Admin override 放行、dry-run 不改变上传授权和既有上传校验。

## 怎么验证的
运行 quota/upload/OpenAPI 目标 unittest：8 个用例通过。运行 `npm --prefix frontend run build` 通过；仅有既有 Vite chunk size / PURE 注释 warning。

## 顺手发现
- app/domains/files/router.py 和 tests/test_fastapi_jobs_backend.py 当前包含多批 Phase 5 未提交变更；本次只追加 quota enforcement 相关逻辑，未整理历史脏改。
