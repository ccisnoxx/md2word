# Parent Design：Datasheet DOCX 交付质量完善

## 1. 架构

保持模块化单体：FastAPI API、Celery Worker、MySQL、Redis、Artifact Storage、Vue 内部门户。

目标模块边界参见：

- `docs/architecture/system-architecture.md`
- `docs/architecture/domain-model.md`
- `docs/architecture/workflows-and-state-machines.md`

## 2. 关键设计

### DocumentIR

继续使用 v2 兼容扩展；只有破坏性合同才升级 v3。

### 表格

```text
MinerU HTML + reference image
→ HTML Normalize
→ CanonicalTableGrid
→ Validator
→ Translation Units
→ Word Native Table
→ Table/Page QA
```

### 翻译

```text
Stable Units
→ Context
→ ProtectedTokenCodec
→ Terms
→ Provider
→ Shape/Token/Term Validation
→ Target DocumentIR
```

### 质量和发布

```text
execution_status
quality_status
review_status
delivery_status
```

PublicationRecord 不可变，绑定 result hash 和资源快照。

## 3. 兼容

- 旧 translation QA 字段保留过渡；
- 新 DB 字段 additive；
- 旧 v2 Artifact 可读；
- 现有 direct/translation API 不做破坏性改名；
- 新 stage 需要旧前端 unknown fallback；
- feature flags 支持逐步启用。

## 4. 回滚

- 关闭新 feature flags；
- 保留新表/列和审计记录；
- 新任务可回到旧 parser/renderer profile；
- 发布件不重新生成；
- 不以截图默认策略作为回滚。

## 5. 风险

- 大表 Word OOXML 性能；
- MinerU 结构错误误报；
- Token 保护过度；
- Preview Provider 环境差异；
- 状态迁移和旧前端兼容；
- 专有样本不能入库。

## 本轮建立记录

2026-10-12：依据 DOC-001 实现授权补建父任务，保留 bootstrap 目标；父任务不启动、不执行其他阶段。当前仅关联 DOC-001。机器状态以 `docs/implementation/codex-task-manifest.yaml` 为准；模板 task-map 是建议，实际任务拆分以 backlog 为准。
