# Parent PRD：Datasheet DOCX 交付质量完善

## 1. 背景

md2word 已具有 PDF 上传、MinerU 解析、DocumentIR v2、DOCX Renderer、模板治理、四种翻译模式、术语和翻译 QA。当前需要在不扩大产品范围的前提下，完善复杂表格、翻译技术完整性、统一质量复核和最终交付发布。

产品范围真源：

- `docs/product/prd.md`
- `docs/product/scope-and-decisions.md`

## 2. 目标

1. HTML 表格默认生成可编辑 Word 表格；
2. 严重表格问题可内部下载，但不可交付；
3. Direct 模式不调用大模型；
4. 四种翻译方向使用稳定 ID、术语、Protected Token 和确定性校验；
5. Direct/Translation 使用统一质量和复核状态；
6. 未复核文档可内部下载但不可发布；
7. 形成不可变最终交付发布记录；
8. 保持现有 P0 Golden Sample 和生产主链路不回归。

## 3. 非目标

- 双语文档；
- 在线 Word/译文/表格编辑；
- 人工 Word 回传；
- 图片内部文字翻译；
- 批量任务；
- 泛 PDF；
- 参数数据库、BOM、选型、知识库；
- 微服务或框架替换。

## 4. 父任务交付物

- 完整产品与架构文档合入；
- 子任务树；
- 所有阶段的集成验收证据；
- 数据/API 兼容和迁移记录；
- P0 direct、各启用翻译方向和审核发布 E2E 通过；
- Admin 最终签字。

## 5. 子任务阶段

1. 合同与状态；
2. MinerU/DocumentIR 规范化；
3. 表格核心；
4. 翻译完整性；
5. DOCX 与预览；
6. QA、批准与发布；
7. 回归和上线。

详细任务：`docs/implementation/codex-task-backlog.md`。

## 6. 跨任务验收标准

- 一个任务只有一份用户主 DOCX；
- direct Provider 调用数为 0；
- HTML 存在的表格为 Word Table；
- 大表不因阈值丢失合并语义；
- 技术 Token 完整率 100%；
- blocked 下载允许、发布禁止；
- unreviewed 翻译下载允许、发布禁止；
- 已发布文件不可覆盖；
- 所有配置和结果可追溯；
- 现有 Golden Sample 不回归。

## 本轮建立记录

2026-10-12：依据 DOC-001 实现授权补建父任务，保留 bootstrap 目标；父任务不启动、不执行其他阶段。当前仅关联 DOC-001。机器状态以 `docs/implementation/codex-task-manifest.yaml` 为准；模板 task-map 是建议，实际任务拆分以 backlog 为准。
