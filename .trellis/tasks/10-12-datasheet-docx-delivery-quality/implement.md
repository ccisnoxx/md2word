# Parent Implement：Datasheet DOCX 交付质量完善

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

## 本轮建立记录

2026-10-12：依据 DOC-001 实现授权补建父任务，保留 bootstrap 目标；父任务不启动、不执行其他阶段。当前仅关联 DOC-001。机器状态以 `docs/implementation/codex-task-manifest.yaml` 为准；模板 task-map 是建议，实际任务拆分以 backlog 为准。
