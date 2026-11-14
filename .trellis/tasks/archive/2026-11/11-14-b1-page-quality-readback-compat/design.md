# 页级质量读回设计

## 读回路径

在 `app/domains/document_jobs/preview_evidence.py` 内沿用 `artifact_evidence()` 和 `read_page_quality()` 的既有顺序。前者核对实际主件与已选 receipt 描述符、manifest、预览 PDF 和页图，后者重算冻结策略与当次绑定。复用 `mapping_source()` 已有的原始 IR、必需内容和持久化 plan／trace 认证，在页级质量读取时允许明确停写的 v2 计划通过锚点缺失分支。

以已归档候选写出的停写事实为兼容输入。使用已核对的主件凭据 metadata，要求 `render-plan/v2`、同次 plan／trace 认证通过、`block_anchor_evidence` 字段缺失、`block_anchor_summary` 严格符合候选声明 `{"schema_version":"block-anchor-evidence/v2","created":0,"generation_disabled":1}`。两个计数按整数核对。字段存在但无效、缺失或不符合形状的停写声明、单独缺失 `page_mapping` 都不足以识别 B1。

兼容入口只供页级质量读回。页映射、审核渲染证据读取、正常新件生成和发布继续走原锚点门。页级报告仍使用 `page_quality_context_sha256(..., require_authenticated=True)` 重算实际上下文，再与源代次、主件、当次 PDF、run、profile、policy、映射哈希等原绑定一起比较。保留 manifest 和报告字节，不改写报告或校准状态，不信任报告自报的上下文来替代计算。

## 兼容证据

保留归档候选、原测试记录和证据哈希。验证时可在临时目录用归档配方生成原始 B1 与正常基线样本，让待验读者进程实际加载修改后的工作树源码。沿用既有 bundle、适配器和产物读回辅助函数。保留“旧正常读者无法认证”的归档断言，新增针对待验正常读者的定向入口。用同一束有效产物的受控变体证明普通缺证、坏锚点证明、失配上下文及外层损坏继续按原合同处理。
