---
doc_type: feature-acceptance
feature: 2026-06-03-delivery-acceptance-report
status: accepted
summary: 发布前验收 PDF -> Word P0 direct 主链路，给出 merge 建议和 deploy 前人工 gate。
tags: [release, acceptance, merge, pdf-to-word, p0]
accepted_at: 2026-06-03
roadmap: pdf-to-word-delivery-hardening
roadmap_item: delivery-acceptance-report
requirement: fastapi-backend-productization
---

# delivery-acceptance-report 验收报告

> 阶段：发布前验收 / merge gate  
> 验收日期：2026-06-03  
> 关联路线：`.codestable/roadmap/pdf-to-word-delivery-hardening/pdf-to-word-delivery-hardening-roadmap.md`

## 1. 验收范围

本轮只判断 PDF -> Word P0 内部发布候选是否可以进入 merge，不执行 deploy，不声称 Golden Sample 正式规模验收已通过。

- [x] P0 默认路径：`direct_pdf_to_word` 上传、建任务、Worker、下载 Word。
- [x] 失败状态：`failed_stage`、`error_code`、`error_message` 和失败事件。
- [x] DocumentIR v2 与 renderer metadata 可追踪。
- [x] 前端工作台上传、详情、下载、重试路径收口。
- [x] readiness、metrics、release check 支持排障。
- [x] Golden Sample 报告已回填真实样本结果。
- [x] `en2zh_pdf_to_word` 明确作为实验能力，不阻塞 P0 direct 发布。

## 2. 当前未提交范围

当前分支是 `main`，工作区存在未提交改动。本轮未 revert 任何已有改动。

与本次发布候选相关：

- `app/domains/document_jobs/execution.py`：DocumentIR artifact 文件名对齐 v2。
- `app/conversion/runtime/*`、`runtime_helpers.py`、`runtime_models.py`、`runtime_rendering_api.py`：Golden Sample 质量基线后形成的 renderer/layout/text/table runtime 改动。
- `tests/test_fastapi_jobs_backend.py`、runtime characterization tests：覆盖 direct、en2zh、失败分类、DocumentIR v2 和 renderer metadata。
- `frontend/src/**`：前端工作台收口，保留 P0 上传、详情、下载、重试和失败解释。
- `scripts/ops/run_golden_sample_regression.py`、`tests/fixtures/golden_samples/**`、`docs/testing/pdf-to-word-golden-sample-acceptance-report.md`：Golden Sample inventory、正式样本映射和真实 smoke 结果。
- `README.md`：发布与联调入口补齐。
- `.codestable/roadmap/pdf-to-word-delivery-hardening/**`、`.codestable/features/**`：路线、阶段验收和发布验收记录。

已确认纳入本次发布：

- `resources/term_rules/term_rules.v2.yaml`：大体量术语规则扩展，已确认属于本次发布候选范围；发布验证未发现直接失败。
- `tests/fixtures/golden_samples/pdfs/OPA228_P2.pdf`、`OPA228_P6.pdf`、`OPA228_P7.pdf`：已映射进 manifest，分别作为 `gs-004`、`gs-006` 和 `gs-008`，不再是 manifest 外 PDF。

## 3. 验证结果

发布前最小验证已通过：

```text
/Users/sc/miniconda3/envs/md2word/bin/python scripts/ops/check_release.py
Release check report ok: True
OpenAPI snapshot is current
Targeted unittest passed: 28 tests OK
```

```text
cd frontend && npm run build
vue-tsc --noEmit && vite build passed
```

补充 smoke：

- [x] direct PDF -> Word：`test_document_job_download_url_returns_temporary_generated_word_link` 通过，创建任务、完成、下载可打开 DOCX。
- [x] en2zh：`test_document_job_en2zh_worker_translates_ir_and_saves_ai_audit_artifacts` 通过，翻译 IR 并保存 AI audit artifact。
- [x] 失败分类：`test_document_job_worker_classifies_timeout_mineru_render_and_oss_failures` 通过，覆盖 timeout、MinerU、renderer、uploading failure。
- [x] DocumentIR v2 metadata：`test_document_job_worker_saves_mineru_raw_ir_and_image_assets` 通过，`document-ir/v2`、`renderer_mode=layout_v2` 可追踪。
- [x] Golden Sample manifest：`tests.test_golden_sample_manifest` 6 tests OK，当前 12 个 manifest 样本、4 个正式匹配 PDF、8 个缺失、0 个 manifest 外 PDF。

未执行项：

- [ ] 本轮未重新跑真实 HTTP Golden Sample 脚本；本机 8000/3000/4173 未监听，且 `.env` 未设置 `GOLDEN_SAMPLE_PASSWORD`。
- [ ] 本轮未重新做浏览器连接真实后端的人工上传/下载；前端已有前一轮 preview + Playwright smoke，当前构建通过。

## 4. 文档与交付性核对

- [x] `docs/runbooks/backend.md` 覆盖本地启动、readiness、metrics、worker、metadata backend、artifact storage、release check 和真实样例联调口径。
- [x] `docs/testing/pdf-to-word-p0-integration-guide.md` 覆盖登录、上传授权、上传 PDF、创建 `document-jobs`、查询、事件和下载。
- [x] `docs/testing/pdf-to-word-golden-sample-acceptance-report.md` 已回填 hostdzire 真实链路 smoke：`gs-003 / OPA228_P1.pdf`，`job_id=docjob_d4c4101592ad`，Word 可打开。
- [x] `docs/testing/pdf-to-word-gs-003-quality-triage.md` 已记录人工质量 triage：主链路条件通过，版面与语义质量未通过。
- [x] `docs/api/openapi.json` 已由 release check 确认可复现，包含 `/api/v1/files/*` 和 `/api/v1/document-jobs/*`。
- [x] `README.md` 已补发布与联调入口。

文档 warning：

- `docs/api/jobs.md` 主要覆盖旧 `/api/v1/jobs`，P0 `/api/v1/document-jobs` 目前主要靠 OpenAPI、integration guide 和代码 schema 支撑。内部交付够用；外部 API 参考应后补。

## 5. Blockers / Warnings / 残余风险

Release blockers：

- 无已发现 release blocker。

Warnings：

- Golden Sample 正式规模仍 blocked：当前只有 4 个 manifest-matched PDF，不满足 10-20 份样本目标，且其中 3 个新映射样本尚未跑真实链路。
- `gs-003` 人工质量 triage 未通过 P0 版面与语义质量，只能证明主链路可交付，不证明 datasheet 结构还原质量达标。
- `en2zh_pdf_to_word` smoke 通过，但仍按实验能力发布，不阻塞 P0 direct。
- 前端真实后端联调未在本轮重跑，deploy 前需要人工确认。
- 当前在 `main` 分支直接积累改动；merge 前应选择提交策略。`resources/term_rules/term_rules.v2.yaml` 和 `OPA228_P2/P6/P7.pdf` 已确认纳入本次发布范围。

可接受残余风险：

- 内部 P0 direct 发布可以接受 Golden Sample 样本规模不足，只要发布说明明确“主链路候选可交付，正式质量验收未完成”。
- 前端 chunk size warning 可接受，不影响当前构建产物。
- 外部 API 文档滞后可接受于内部交付，但不适合对外发布前长期保留。

## 6. 发布建议

建议进入 merge：

- 后端 release check 通过。
- 前端生产构建通过。
- direct PDF -> Word 主链路 smoke 通过。
- 失败状态、DocumentIR v2 artifact、renderer metadata、下载、retry 和前端失败解释路径均有测试或收口记录。
- Golden Sample 报告已诚实标记 blocked，没有把 1/1 smoke 包装成正式样本规模通过。

不建议直接 deploy：

- deploy 前必须完成人工 gate，并在发布记录里写明确认结果。

## 7. Deploy 前人工 gate

deploy 前必须人工确认：

- [ ] 用真实账号/token 复跑一次 Golden Sample，或确认 2026-06-02 hostdzire `docjob_d4c4101592ad` 结果仍可作为本次部署基线。
- [ ] 人工打开最新生成 DOCX，确认 Word 可打开、可编辑。
- [ ] 前端连接真实后端，手工走上传、详情、下载、失败重试。
- [x] 确认 `OPA228_P2/P6/P7.pdf` 映射进 manifest，作为 `gs-004`、`gs-006`、`gs-008`。
- [x] 确认 `resources/term_rules/term_rules.v2.yaml` 属于本次发布范围。
- [ ] 发布说明中把 `en2zh_pdf_to_word` 标为实验能力。

## 8. Roadmap 回写

- [x] `delivery-acceptance-report` 从 `planned` 回写为 `done`。
- [x] 主 roadmap 子 feature 清单同步为 `done`。
- [x] 保留 `document-ir-layout-risk-pass` 和 `word-renderer-editable-output-pass` 为后续质量硬化输入，不阻塞本次 P0 direct 内部发布候选。

## 9. 下一步

- 进入 merge 准备：确认范围、提交策略和是否拆分 commit。
- merge 后、deploy 前执行第 7 节人工 gate。
- deploy 后若出现质量问题，优先从 `document-ir-layout-risk-pass` 或 `word-renderer-editable-output-pass` 开新 feature，而不是在发布分支继续扩大范围。
