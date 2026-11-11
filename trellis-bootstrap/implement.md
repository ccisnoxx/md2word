---
doc_status: active
last_verified_commit: null
owner: null
verification_scope: >-
  全文辅助/模板用途、原指令结构与Manifest定义的静态对照；仅追加治理字段和导语，未执行提示词、创建任务、修改状态或验收产品。原文字节、TR-406旧依赖差异及合并关系见 ../.trellis/tasks/11-10-documentation-evidence-governance/research/b4-preparation.md；45项实现证据沿用同目录manifest-reconciliation.md原范围。
---

# Parent Implement：Datasheet DOCX 交付质量完善

本页是父任务计划/集成验收空白模板；原目标、复选框、建议映射与验收条件供实际任务引用和确认，不证明当前已实施或验收，也不授权创建、启动、提交或归档任务。定义及 AC 见 [原任务清单](../docs/implementation/codex-task-backlog.md)，执行状态与依赖门以 [Manifest](../docs/implementation/codex-task-manifest.yaml) 为准；原模板字节保留。

## 1. 说明

父任务负责阶段、子任务、依赖和最终集成，不建议直接承载全部代码修改。

## 2. 计划

### Phase 0 文档与基线

- [ ] 合入文档包
- [ ] 更新 README 索引
- [ ] 执行 current baseline verification
- [ ] 创建子任务树

### Phase 1 合同与状态

- [ ] CON-101 产品模式文案
- [ ] CON-102 阶段扩展
- [ ] CON-103 状态模型与迁移
- [ ] CON-104 下载/发布可用性

### Phase 2 MinerU/IR

- [ ] IR-201 Artifact Validator
- [ ] IR-202 Margin Normalizer
- [ ] IR-203 Cross-page Paragraph
- [ ] IR-204 Caption Reconciler
- [ ] IR-205 Logical Tables
- [ ] IR-206 Reference Assets
- [ ] IR-207 ZK7044 fixtures

### Phase 3 Tables

- [ ] TAB-301..TAB-308

### Phase 4 Translation

- [ ] TR-401..TR-407

### Phase 5 Rendering/Preview

- [ ] RND-501..RND-506

### Phase 6 QA/Publication

- [ ] QA-601..QA-607

### Phase 7 Release

- [ ] REL-701..REL-704

## 3. 每阶段集成验证

- [ ] targeted unit tests
- [ ] `git diff --check`
- [ ] `scripts/ops/check_release.py`
- [ ] component PDF regression（相关阶段）
- [ ] P0 Golden Sample（转换/渲染相关）
- [ ] translation regression（翻译相关）
- [ ] frontend build/unit/smoke（UI 相关）
- [ ] OpenAPI snapshot（API 相关）
- [ ] migration/rollback（DB 相关）

## 4. 最终验收

- [ ] Direct AI calls = 0
- [ ] One task = one DOCX
- [ ] HTML tables native
- [ ] Severe table issue → downloadable blocked draft
- [ ] Unreviewed translation → downloadable, not publishable
- [ ] Protected Token integrity = 100%
- [ ] Unified review works for direct and translation
- [ ] Publication immutable
- [ ] P0 and enabled language gates pass
- [ ] Admin signoff

## 5. Context

为父任务和子任务添加：

- 产品 PRD；
- 相关设计文档；
- 相关 `.trellis/spec`；
- 当前实现和 tests；
- 样本 manifest；
- migration/rollout 文档。
