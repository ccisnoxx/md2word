# 技术设计

## 设计结论

本任务只修改 Trellis 规范、规范索引和任务研究材料，不修改产品代码、测试行为或样本资产。交付一个正式 Word 输出行为的唯一权威规范，并把现有分散规则迁移为引用关系，避免新文档与 `quality-guidelines.md`、模板专项合同形成并列真相源。

任务保持单一任务：规则盘点、冲突矩阵和规范索引共同构成一个不可分割的文档交付；拆成子任务会让分类和优先级在合并前失去统一审核。

## 权威层级

```text
.trellis/spec/backend/word-generation-rules.md
  ├─ 权威：正式 MinerU→DocumentIR→DocumentIRWordRenderer 输出行为
  ├─ 引用：template-layout-configuration.md 的 API/schema/version 合同
  ├─ 引用：quality-guidelines.md 的通用验证要求
  └─ 证据：正式代码、测试、样本清单、归档任务和历史差异

app/conversion/runtime/*
  └─ 非权威：只进入“历史差异/待迁移”附录
```

`word-generation-rules.md` 决定“正式输出应该怎样”；专项规范继续决定其已有所有权范围，例如 `template-layout-configuration.md` 决定模板配置字段和版本治理。主规范引用专项合同，不复制全部 API 和 schema 字段。

## 规范结构

### 1. 范围与术语

- 明确正式链路、非权威 legacy runtime、支持的输入版本和验收工具。
- 定义规则状态：
  - `enforced-tested`：正式代码存在且有自动测试；
  - `enforced-sample`：正式代码存在且有真样本/人工证据；
  - `implemented-gap`：正式代码存在但测试或长期样本不足；
  - `planned`：有明确意图但尚未实现；
  - `historical`：旧 runtime/历史决定，仅供差异参考；
  - `superseded`：已被新规则明确取代。

状态不是质量等级；同一规则可同时列出自动测试和人工样本，最终状态取最低已证明层级。

### 2. 规则目录

使用稳定前缀，避免按 PDF 型号建立规则：

| 前缀 | 规则域 |
|---|---|
| `PIPE` | 正式入口和链路 |
| `INPUT` | MinerU 包选择、内容清理和源页过滤 |
| `IR` | DocumentIR 语义与坐标 |
| `PAGE` | 页面尺寸、方向、页边距和分节 |
| `FLOW` | 流式分页、语义分页和空白页 |
| `COL` | 单栏、双栏、wide 块和纯图片行 |
| `TEXT` | 标题、正文、目录和列表 |
| `TABLE` | 表格、长表、宽表、表题和表注 |
| `IMAGE` | 图片绑定、显示尺寸、清晰度和图注 |
| `FIELD` | TOC、SEQ、bookmark、REF、PAGE |
| `MATH` | 公式输入、预处理、OMML 和失败合同 |
| `STYLE` | 模板样式、字体、页眉页脚优先级 |
| `QUALITY` | OOXML、自动测试、样本和人工视觉门禁 |

### 3. 单条规则合同

每条规则采用相同字段：

```markdown
### FLOW-003 页顶内容组语义分页

- 状态：enforced-tested / implemented-gap / ...
- 输入信号：非首页 LayoutPage 的第一个可见 body block ...
- 正式 owner：`app/services/renderer/word_renderer.py::_semantic_page_break_block_id`
- 预期输出：...
- 优先级/冲突：高于 FLOW-001 的自然流式分页，但不得生成 break-only 段落
- 例外：...
- 禁止：按页码/型号硬编码；恢复每物理页分页
- 自动验证：`tests.test_document_ir_word_renderer_layout...`
- 样本证据：CM4112/SC2167 ...
- 来源/取代：归档任务/commit/旧规则 ID
```

规则 owner 必须指向当前存在的文件和符号；如果只有文件级 owner 或尚无实现，要明确写 `implemented-gap`/`planned`，不得伪造符号。

### 4. 冲突优先级

单独维护冲突矩阵，不在多个规则段落重复解释：

| 冲突 | 基础规则 | 优先规则 | 必须共同保护的回归 |
|---|---|---|---|
| 自然流式分页 vs 页顶内容组分页 | 同方向页面不硬分页 | heading/独立表格组的真实内容段落 `pageBreakBefore` | SC2167 无空白页 + CM4112 内容组起页 |
| 普通双栏 vs 成对图片 | 一次 `w:cols` | 严格图片对使用单栏制表位 | 文本阅读顺序 + SC2167 图片网格 |
| 源视觉 vs Word 结构 | 保持内容关系 | 可编辑原生结构优先 | OPA228 canonical + OOXML |
| 公式清理 vs 正文保真 | 数学边界归一化 | 普通正文不做数学压缩 | CM4112 公式 + UNC 路径测试 |

冲突矩阵只描述已确认合同；无法确定产品意图的项进入“待决/缺口”，不由文档作者自行裁决。

### 5. 回归矩阵

按规则 ID 映射：正式 owner、自动测试模块/测试方法、仓库样本、外部样本、人工工具和当前缺口。样本路径不可用时记录为 `external evidence`，不能写成可运行 fixture。

P0 canonical suite、component PDF fixture 和外部真样本分层列出，避免把一次性本地文件当成长期门禁。

### 6. 历史差异与待迁移

旧 runtime 规则只记录：历史 owner、行为、正式链路当前状态、是否已取代、迁移需要的证据。此附录不使用 `必须/应当` 描述正式输出，也不把 legacy characterization test 计入正式规则已覆盖证明。

### 7. 规则变更流程

后续 Word 行为变更按以下顺序：

1. 找到或新增规则 ID，写清冲突和影响样本；
2. 更新唯一正式 owner，不在调用者/样本特例中复制逻辑；
3. 运行本规则自动测试和冲突矩阵列出的共同回归；
4. 使用正式转换入口生成真样本证据；
5. 按规则指定工具做 OOXML、LibreOffice 和必要的 WPS/Word 检查；
6. 更新规则状态和证据，不以单个新 PDF 的通过覆盖旧样本失败。

## 现有规范迁移

- 新建 `.trellis/spec/backend/word-generation-rules.md`。
- 更新 `.trellis/spec/backend/index.md`：在 pre-development checklist 和指南索引中加入强制读取触发条件。
- 将 `.trellis/spec/backend/quality-guidelines.md` 中 Word 输出行为迁入主规范或替换为链接；保留通用测试原则，消除重复合同。
- `template-layout-configuration.md` 保持模板配置专项权威；必要时只增加回链，不复制字段合同。
- 任务 `research/rule-source-audit.md` 保存来源审计，但不是长期规范的一部分。

## 验证设计

本任务不新增永久验证脚本。使用现有工具完成一次性检查：

1. `rg`/Python 检查规范引用的仓库文件、测试模块和明确符号是否存在；外部/历史来源必须显式标注，不能混入存在性检查。
2. 检查每个规则段落都包含状态、输入、owner、输出、冲突/例外、禁止、验证和来源字段。
3. 检查规则 ID 唯一，回归矩阵引用的 ID 均已定义。
4. 检查 backend index 链接可解析，quality/template 规范不再复制相同输出合同。
5. `git diff --check`，并人工通读主规范，检查矛盾、重复、失效路径和把历史行为误写成正式要求的问题。

无需运行产品单元测试或重新生成 DOCX，因为本任务不改变代码和输出；如果实施阶段意外触及产品文件，必须停止并回到规划扩展范围。

## 风险与控制

- **把当前 bug 固化为规范**：只有代码、测试和产品意图一致时标记 `enforced`；否则记录缺口。
- **复制导致再次漂移**：主规范描述输出行为，专项规范描述其所有权合同，其他规范只链接。
- **历史规则污染当前合同**：legacy runtime 独立附录且全部标为非权威。
- **文档过长失去可执行性**：规则使用稳定模板和矩阵，解释只保留冲突原因与禁止模式。
- **真样本不可复现**：明确区分 committed fixture 与 external evidence，并列出需要后续最小化的样本缺口。

## 回滚

全部为 Markdown 修改；按文件回退即可，不涉及产品代码、数据迁移或生成产物。
