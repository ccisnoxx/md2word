---
doc_type: architecture-decision-index
status: accepted
last_reviewed: 2026-10-03
---

# 架构决策记录

## ADR-001 保持模块化单体

**决策**：FastAPI API + 异步 Worker + MySQL/Redis/Artifact Storage，不拆微服务。

**原因**：内部单租户、强关联流水线、当前边界已经存在，主要问题是合同和模块职责。

**后果**：通过 package/service/port 收口；不得以本项目为由引入服务间 RPC。

---

## ADR-002 一任务一目标 DOCX

**决策**：一个任务固定一个模式和一个用户主 DOCX。

**原因**：配置、质量、审核和发布语义明确。

**后果**：需要其他语言时 clone/create 新任务；内部 Artifact 不计为多主输出。

---

## ADR-003 MinerU 是唯一 PDF 解析入口

**决策**：不做 OCR 预检、多解析器路由或解析器选择。

**原因**：产品聚焦 MinerU 结果到 Word 的质量。

**后果**：系统只验证 MinerU 产物；源 PDF 仅用于审核、裁图和视觉对照。

---

## ADR-004 DocumentIR 是内部文档真源

**决策**：MinerU、翻译和 Renderer 通过 DocumentIR 解耦。

**原因**：需要稳定 ID、来源追溯、可重渲染和结构不变量。

**后果**：Word 不是唯一主数据；翻译不得直接编辑 DOCX。

---

## ADR-005 HTML 表格默认原生化

**决策**：HTML 可解析时必须生成 Word Table。

**原因**：可编辑、可翻译、可检查数字/单位/术语。

**后果**：结构失真通过 QA 和 blocked 管理，不用截图掩盖。

---

## ADR-006 表格截图只作参照和异常占位

**决策**：Reference Image 是 QA Artifact；只有 HTML 完全缺失时可作为非编辑占位。

**后果**：占位任务 blocked，可内部下载，不可发布。

---

## ADR-007 Direct 模式不调用 AI

**决策**：中文/英文/俄文原文转 Word 都是 direct。

**原因**：直接转换是结构处理，不是语言编辑。

**后果**：不创建 zh2zh Prompt；历史 alias 只做兼容归一。

---

## ADR-008 翻译采用稳定 ID + Protected Token

**决策**：模型只接触文本单元，输出固定 ID/text；技术内容由代码占位和校验。

**原因**：Prompt 无法提供确定性技术安全。

**后果**：任何 ID/Token/数字/单位/公式不一致时禁止回填。

---

## ADR-009 CanonicalTableGrid 作为表格内部模型

**决策**：HTML parser 与 Word renderer 之间增加稳定二维网格。

**原因**：当前简单行模型无法完整表达冲突、翻译 run、跨页和质量证据。

**后果**：raw HTML 永久保留；Grid 可独立 Artifact 或兼容 metadata。

---

## ADR-010 执行、质量、复核、交付状态分离

**决策**：四个独立维度。

**原因**：成功生成 blocked 草稿、未复核可下载、已批准可发布是不同事实。

**后果**：前端不能从 `status=succeeded` 推断可交付。

---

## ADR-011 Direct 和 Translation 使用统一 Review 模型

**决策**：现有 translation QA 兼容演进为 document review。

**原因**：转换质量同样需要人工复核；避免双状态体系。

**后果**：旧 translation QA 字段过渡期保留。

---

## ADR-012 发布记录不可变

**决策**：PublicationRecord 绑定具体 result file/hash 和配置快照。

**原因**：最终交付可追溯，防止覆盖。

**后果**：发布任务不能原地覆盖结果；需要新任务或 generation。

---

## ADR-013 不做在线 Word/表格编辑

**决策**：审核页面只读；人工修改在 Word/WPS 中完成，不回传系统。

**原因**：避免把项目扩展为 Office 编辑器；保持文档交付聚焦。

**后果**：`needs_fix` 后由人工在系统外处理，系统只记录 QA。

---

## ADR-014 模板、符号规则、Prompt 和术语全部版本化

**决策**：任务绑定不可变资源快照。

**原因**：结果重现和历史追溯。

**后果**：默认版本变化不影响历史任务；发布资源需要验证和审计。

---

## ADR-015 Word Preview 是可替换基础设施端口

**决策**：DOCX→PDF/页面图由 Provider adapter 实现。

**原因**：预览工具可能因部署环境变化，不应进入核心语义。

**后果**：预览失败不删除 DOCX，但禁止发布；Provider 可替换。

---

## ADR-016 MySQL 是元数据真源，Artifact Storage 保存二进制

**决策**：数据库不保存 PDF/DOCX/图片全文。

**原因**：容量、保留和对象存储适配。

**后果**：文件记录和二进制删除必须一致、可审计。
