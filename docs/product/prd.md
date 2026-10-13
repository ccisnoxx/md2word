---
doc_type: product-requirements
status: scope-frozen
product: md2word
version: 1.0
baseline_commit: e51e6ccd129f59d1b372dfc6907def1fd6bb5cd8
last_reviewed: 2026-10-03
---

# md2word 公司内部 Datasheet 文档交付平台 PRD

## 1. 产品定义

md2word 是面向公司内部文档交付、技术翻译、质量复核和配置治理人员的电子元器件 Datasheet 文档处理平台。

平台接收厂商 PDF，由 MinerU 生成 `content_list_v2.json` 与图片资源；系统把 MinerU 产物转换为 DocumentIR，根据任务创建时选择的单一模式生成一份 DOCX，并对文档结构、表格、图片、公式、翻译完整性和 Word 可编辑性进行质量检查。

产品只解决以下问题：

- PDF 转可编辑 Word；
- 跨语言翻译后生成目标语言 Word；
- 公司模板统一；
- 符号规则和翻译术语治理；
- 原 PDF、内容和 Word 预览审核；
- 逐页、逐元素质量检查；
- QA、批准和发布。

## 2. 核心产品原则

1. **一任务一目标文档**：一份 PDF、一种任务模式、一组配置快照、一份目标 DOCX。
2. **MinerU 是唯一 PDF 解析入口**：系统不做 OCR 路由或解析器选择。
3. **直接转换不调用大模型**：中文 PDF 转中文 Word属于原文转换，不是“中译中”。
4. **HTML 表格优先原生化**：HTML 可解析时必须生成 Word 原生表格。
5. **截图只作表格参照或异常占位**：不得在 HTML 正常存在时替代可编辑表格。
6. **执行成功不等于可交付**：执行、质量、复核、交付状态相互独立。
7. **严重表格问题可内部下载但不可交付**。
8. **未复核翻译可内部下载但不可发布**。
9. **人工修改后的 Word 不回传系统**。
10. **系统不提供在线 Word 编辑或在线修表**。

## 3. 用户和角色

### 3.1 Operator

可执行：

- 上传 PDF；
- 创建直接转换或翻译任务；
- 选择已发布模板和配置；
- 查看任务进度、事件、质量标记；
- 下载未复核或质量受阻的内部 Word；
- 提交 QA 结论和术语建议。

不可执行：

- 发布配置版本；
- 将质量阻塞文档标记为可交付；
- 发布最终交付件；
- 修改历史任务配置快照。

### 3.2 Admin

在 Operator 权限基础上可：

- 管理模板、页面样式、符号规则、翻译配置和术语；
- 复核 QA；
- 批准并发布最终交付件；
- 查看审计、系统状态和验收证据；
- 进行配置回滚和草稿模板验证。

## 4. 任务模式

| 用户界面名称 | 内部模式 | AI 翻译 | 结果语言 |
|---|---|---:|---|
| 原文 PDF 转可编辑 Word | `direct_pdf_to_word` | 否 | 保持原文 |
| 英译中 | `en2zh_pdf_to_word` | 是 | 简体中文 |
| 俄译中 | `ru2zh_pdf_to_word` | 是 | 简体中文 |
| 中译英 | `zh2en_pdf_to_word` | 是 | 英文 |
| 中译俄 | `zh2ru_pdf_to_word` | 是 | 俄文 |

历史兼容参数 `zh2zh`、`zh_to_zh` 只允许在服务端归一化为 `direct`，不得出现在新 UI、文档或新 API 示例中。

## 5. 用户主流程

### 5.1 直接转换

```text
上传 PDF
→ 创建 direct 任务
→ MinerU 解析
→ MinerU 产物验证
→ DocumentIR 规范化
→ DOCX 原生渲染
→ 自动质量检查
→ 内部下载
→ 人工 QA
→ Admin 批准和发布
```

### 5.2 翻译转换

```text
上传 PDF
→ 选择语言方向
→ MinerU 解析
→ 源 DocumentIR
→ 抽取翻译单元
→ 技术 Token 保护
→ 术语注入与模型翻译
→ ID/Token/数字/单位/公式校验
→ 目标 DocumentIR
→ DOCX 原生渲染
→ 自动质量检查
→ 未复核状态下允许内部下载
→ 人工 QA
→ Admin 批准和发布
```

## 6. 功能需求

### FR-001 PDF 上传

- 支持单文件 PDF；
- 保存文件名、大小、MIME、SHA-256、上传者和上传时间；
- 上传完成后创建任务；
- 一个任务只关联一个源 PDF；
- 上传失败可重新上传，但不得产生不完整任务。

### FR-002 任务创建

创建任务时绑定：

- 任务模式；
- 模板版本；
- 符号与排版规则版本；
- 翻译模式下的翻译配置、Prompt 哈希、模型标识和翻译术语版本。

任务创建后配置形成不可变快照；默认配置后续变化不得影响历史任务。

### FR-003 MinerU 结果包接收与验证

输入包至少包括：

```text
source.pdf
content_list_v2.json
images/
```

必须验证：

- JSON 可解析；
- 页面和块顺序有效；
- `bbox` 合法；
- 图片路径存在；
- 表格 HTML、参考图、caption、footnote 可读取；
- 源块数量和类型可与 DocumentIR 对账；
- 空 HTML、空图片、缺失资源被记录为质量问题。

### FR-004 DocumentIR 构建

- 保持 MinerU 数组顺序为主要阅读顺序；
- 保留页码、坐标、源索引和源类型；
- 识别重复运行页眉页脚；
- 识别列表和跨页段落；
- 归并跨页表格；
- 规范 caption 和 footnote；
- 为每个块分配稳定 ID；
- 保存原始和规范化质量标记。

### FR-005 原文 PDF 转 Word

- 不调用翻译 Provider；
- 不加载翻译 Prompt 或翻译术语；
- 不进入翻译 QA；
- 标题、正文、列表、表格、公式为 Word 原生对象；
- MinerU 图片和 chart 为 Word 图片对象；
- 不进行语义改写、润色或技术修正。

### FR-006 翻译

仅四种跨语言模式进入翻译流程。

可翻译内容：

- 标题；
- 段落；
- 列表项；
- 图片/图表 caption 与 footnote；
- 表格 caption、HTML 文本节点和 footnote。

必须保护：

- 数字、正负号、范围；
- 单位；
- 料号、型号、引脚和信号名；
- 寄存器地址和位字段；
- 协议、标准和缩写；
- 公式、LaTeX；
- URL、邮箱和版本号。

翻译结果必须保持输入 ID 集合和顺序，不允许合并、拆分、漏项、额外项或静默回退原文。

### FR-007 符号规则与翻译术语

区分两类配置：

1. **符号与排版规则**：所有任务可用，用于上下标、变量、单位、字体和非语义格式化。
2. **翻译术语集**：仅跨语言任务使用，用于源术语到目标术语映射、推荐译法、禁用译法、同义词和优先级。

两类配置都必须版本化、可发布、可回滚，并被任务固化为执行快照。

### FR-008 图片和图表

- 直接插入 MinerU 图片资源；
- 保持宽高比；
- 默认使用行内图片；
- 多图并排可使用无边框布局表格；
- caption 和 footnote 独立渲染；
- 图片内部文字不翻译；
- 不重新绘图或矢量化。

### FR-009 表格

- HTML 可解析时必须生成 Word 原生表格；
- 支持 `rowspan`、`colspan`、多层表头、跨页、横向节、公式和脚注；
- 结构可疑时仍生成可编辑表格并标记质量阻塞；
- HTML 完全缺失时允许使用参考图或 PDF 裁图作为明显的非编辑占位；
- 非编辑占位不得通过最终发布；
- 表格参考图保留为 QA 证据，不是正常交付内容。

### FR-010 DOCX 原生渲染

| 内容 | Word 表达 |
|---|---|
| 标题 | Heading 或模板命名样式 |
| 正文 | Paragraph/Run |
| 列表 | 原生编号/项目符号 |
| 表格 | Word Table |
| 公式 | OMML 或明确受控降级 |
| 图片 | InlineShape/Picture |
| caption | Caption 段落 |
| 页码/目录 | Word Field |
| 分栏/横向页 | Section |

禁止整页截图替代正文。

### FR-011 公司模板

模板管理内容：页面、边距、字体、标题、正文、列表、表格、caption、页眉页脚、Logo、目录、横向节和表格边距。

模板版本状态：

```text
draft → validated → published → disabled/archived
```

Operator 只能使用已发布版本；Admin 可以使用草稿版本做验证任务。

### FR-012 自动质量检查

质量检查覆盖：

- 源块到 DocumentIR 完整性；
- 图片与表格资源完整性；
- 表格网格、粘连、列数、跨页和越界；
- 翻译 ID、术语、数字、单位、公式和源语言残留；
- DOCX 可打开、可编辑、标题、编号、表格、图片、LaTeX 残留和页面布局；
- Word 页面预览中的裁切、溢出、空白页和重叠。

### FR-013 三栏审核

审核页包含：

```text
原始 PDF | 原文/译文与 QA 证据 | Word 只读预览
```

点击任意块时同步定位 PDF 页和 `bbox`、DocumentIR 块、Word 页面或锚点。

审核页不提供内容编辑、修表或上传人工 Word。

### FR-014 QA

统一状态：

```text
unreviewed | approved | needs_fix | blocked
```

统一问题类型：

```text
conversion | translation | terminology | table_structure |
layout | source_quality | artifact_missing | other
```

保存审核人、时间、备注、DOCX 哈希和当时质量标记。

### FR-015 批准和发布

发布前必须满足：

```text
execution_status = succeeded
quality_status != blocked
review_status = approved
result_file 存在
Word 预览存在
```

发布后保存源 PDF、DOCX、模板、规则、Prompt、模型、术语和渲染器快照；已发布文件不可覆盖。

### FR-016 下载规则

| 状态 | 内部下载 | 最终交付 |
|---|---:|---:|
| 已生成、未复核 | 允许 | 禁止 |
| 翻译未复核 | 允许，显示“未复核” | 禁止 |
| 质量 warning | 允许 | QA 通过后允许 |
| 质量 blocked | 允许，显示“质量阻塞，不可交付” | 禁止 |
| needs_fix | 允许 | 禁止 |
| approved | 允许 | Admin 可发布 |
| published | 允许 | 是 |

### FR-017 任务管理

支持列表、搜索、状态筛选、模式筛选、事件、重试、取消、克隆、归档、下载和配置快照查看。

重试默认使用原任务快照；克隆可选择保留原快照或使用当前已发布配置。

## 7. 状态模型

### 7.1 执行状态

```text
pending | queued | running | succeeded | failed | canceled
```

### 7.2 处理阶段

直接模式：

```text
uploaded → parsing → parsed → ir_converting → rendering
→ quality_checking → uploading → completed
```

翻译模式：

```text
uploaded → parsing → parsed → ir_converting → translating
→ translation_validating → rendering → quality_checking
→ uploading → completed
```

### 7.3 质量状态

```text
pending | passed | warning | blocked
```

### 7.4 复核状态

```text
unreviewed | approved | needs_fix | blocked
```

### 7.5 交付状态

```text
internal_draft | ready_to_publish | published
```

## 8. 验收标准

1. 直接转换全过程无 LLM 调用和翻译批次。
2. 一个任务只产生一份用户主 DOCX。
3. 有效 HTML 表格全部生成为 Word Table。
4. 严重表格问题生成内部可下载草稿，状态必须是不可交付。
5. 空 HTML 表格必须产生阻断证据，不得静默消失。
6. 翻译前后所有受保护 Token 完整一致。
7. 翻译 ID 数量、集合和顺序保持一致。
8. 未复核翻译允许内部下载但不可发布。
9. 质量阻塞文档不得批准和发布。
10. 发布记录包含源、模板、规则、Prompt、术语和结果哈希。
11. 系统不要求上传人工修改后的 Word。
12. 正式验收以公司实际使用的 Microsoft Word 为主。

## 9. 非目标

- 在线 Word 编辑；
- 在线改译文并重新生成；
- 在线表格结构修复；
- 人工 Word 回传和版本管理；
- 图片内部文字翻译；
- 双语 Word；
- 一任务多语言；
- 批量上传；
- 泛 PDF；
- 元器件参数数据库、BOM、选型、供应链或知识问答；
- 外部 SaaS 和计费。
