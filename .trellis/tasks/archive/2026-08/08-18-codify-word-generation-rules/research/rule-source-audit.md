# Word 生成规则来源审计

## 结论

权威规范只约束正式链路：

```text
MinerU package
  → MinerUToDocumentIRService
  → DocumentIR
  → build_layout_plan
  → DocumentIRWordRenderer
  → DOCX + docx_quality
```

本地正式调试入口 `scripts/dev/formal_mineru_conversion.py` 和线上 Document Jobs 都进入这条链路。旧 runtime 的编排、页面 renderer 和 Word writer 只作为历史规则、差异和待迁移证据，不是正式输出合同。正式 `table_renderer.py` 当前直接复用 `app/conversion/runtime/table_html_parser.py`；该 parser 是实际依赖，但 legacy writer/characterization tests 仍不能证明正式输出。

## 当前权威来源

| 来源 | 已确认内容 | 规范中的用途 |
|---|---|---|
| `.trellis/spec/backend/directory-structure.md` | 正式本地转换必须调用 `MinerUToDocumentIRService.convert_zip()` 与 `DocumentIRWordRenderer.render_to_bytes()` | 链路与代码归属 |
| `.trellis/spec/backend/quality-guidelines.md` | 原生 Word 结构、DOCX 视觉/OOXML 验收、公式边界、页脚和图片质量约束 | 待迁入/引用的现有合同 |
| `.trellis/spec/backend/template-layout-configuration.md` | 模板配置、版本治理和字体槽位的唯一 owner | 专项配置合同；主规则只引用，不复制 API/schema 细节 |
| `32edca58` 的 renderer parity PRD/audit | 正式链路是 P0 验收路径；共享纯规则与正式 OOXML writer 的边界 | 正式链路演进依据 |
| `08-18-fix-layout-formula-image-caption` | 原生分栏、OMML、图片尺寸、SEQ/REF/TOC、流式分页、页脚和推广封底规则 | 已实现行为与冲突来源 |
| `08-18-fix-mineru-first-page-layout` | v2 优先、页面坐标、列表、局部双栏、语义分页和高频 TeX 规则 | 最新已实现行为与 CM4112 回归证据 |
| 当前正式代码与测试 | 实际 owner、调用路径和自动断言 | “已实现/已测试”状态的最终证据 |

## 正式代码所有者

| 规则域 | 正式 owner |
|---|---|
| 本地正式入口 | `scripts/dev/formal_mineru_conversion.py` |
| MinerU 包选择 | `app/services/document_ir/mineru_package.py` |
| MinerU→DocumentIR 内容归一化 | `app/services/document_ir/mineru_converter.py`、`app/conversion/docx_rules/mineru_content.py` |
| 页面尺寸、bbox、占位续表 | `app/services/document_ir/layout_signals.py` |
| DocumentIR 合同 | `app/services/document_ir/models.py` |
| 页面与区域规划 | `app/services/renderer/layout_plan.py` |
| 分节、分页、分栏、页眉页脚编排 | `app/services/renderer/word_renderer.py` |
| 标题、正文、列表、公式、字段与引用 | `app/services/renderer/text_renderer.py`、`app/conversion/docx_rules/text_semantics.py` |
| 表格 | `app/services/renderer/table_renderer.py` |
| 图片 | `app/services/renderer/image_renderer.py` |
| 输出质量证据 | `app/services/renderer/docx_quality.py` |
| 模板配置与字体 | `app/domains/templates/layout_config_schema.py`、`app/conversion/docx_rules/run_fonts.py` |

## 历史规则与取代关系

| 历史规则/实现 | 当前状态 | 取代证据 |
|---|---|---|
| 1×2 无边框布局表格模拟双栏 | 已取代 | SC2167 任务改为原生 `w:cols`；严格纯图片对改用单栏制表位 |
| 每个同方向 PDF 物理页强制分页 | 已取代 | SC2167 为避免正文空白页改为 Word 流式分页；CM4112 再补页顶章节/独立表格组的语义分页 |
| 旧 runtime 的保守页高估算 | 历史/待评估 | 正式 renderer 未整体迁入；不能以函数仍存在证明正式链路执行 |
| 旧 runtime 的密集页后大标题分页 | 历史/部分迁移 | 正式链路只确认页顶 heading 与带 caption/context 表格组的 `pageBreakBefore` |
| 普通文字替代受支持公式 | 已取代 | 正式 renderer 对受支持 TeX 使用 OMML；未知/畸形输入保留并报告残留 |
| 固定最小图片显示宽度 | 已取代 | 当前按 bbox/page 比例计算且只允许缩小到可用宽度 |

历史会话 `019ef398-0ad3-70e3-ab3c-5722c63afcff` 还记录了早期“布局表格双栏、保守分页、P0 OPA228 优先”的阶段性决定。因这些决定已有后续替代实现，历史会话只能帮助定位来源，不能直接写成当前规范。

## 已确认的冲突域

1. **流式分页 vs 内容组分页**：禁止恢复每物理页硬分页，但非首页页顶 heading 和带 caption/context 的独立表格组需要内容锚定分页。
2. **长表跨页 vs 空白页**：表格允许自然跨页、重复表头和单行不拆；不能在长表后追加 break-only 段落。
3. **原生分栏 vs WPS 栏平衡**：普通文字使用一次原生双栏；严格成对纯图片使用单栏制表位，避免逐行 continuous section 拆页。
4. **源 PDF 视觉 vs Word 可编辑结构**：像素还原与可编辑结构冲突时，原生 Word 结构优先，但内容顺序、可读性和关键相对关系必须保留。
5. **公式归一化 vs 普通正文保真**：当前所有共享文本入口都会经过 `normalize_formula_text()`，但只能改写证据充分的 TeX 模式；OMML 限于明确数学边界/整段公式，不能破坏普通正文空格或 UNC 路径。
6. **模板配置 vs 源页装饰**：配置禁用时保留模板 decoration，自定义 footer 高于源 footer；源 header 在启用时会写入共享 section，并存在覆盖配置 header/同向页 header 的已确认缺口。

## 回归样本现状

| 样本 | 存放/证据 | 已覆盖焦点 | 状态风险 |
|---|---|---|---|
| OPA228 P1/P2/P6/P7 | `tests/fixtures/golden_samples/manifest.yaml` | 双栏、目录/修订、热阻表、宽电气表与符号 | 正式 P0 canonical suite，需要 admin 人工签字 |
| OPA228 P1 最小包 | `tests/fixtures/component_pdf_samples/manifest.yaml` | heading、paragraph、list、单位可读性 | 仓库内可运行，但覆盖面有限 |
| SC2167 | 归档任务与外部正式样本记录 | 原生分栏、图片网格、公式、SEQ/REF、空白页、页脚、推广封底 | 未作为完整仓库 fixture；依赖外部/历史证据 |
| CM4112/CM4114 | 归档任务与用户提供样本 | v2、纵向页面、列表、局部双栏、表格/章节分页、高频公式 | 最新输出仍暴露整文档页数/首页重排风险 |
| TPL51200、BL0942、RS2G04 | SC2167 任务负样本记录/本地样本 | 推广封底误删保护、声明/版本表 | 不保证仓库内长期可用 |

## 当前缺口

- 现有自动测试以模块级 OOXML/文本断言为主，不能单独证明整份文档布局没有退化。
- CM4112、SC2167 等关键真样本尚未全部成为可提交的最小长期 fixture；规范必须如实标注外部样本依赖。
- WPS/Microsoft Word 与 LibreOffice 对 continuous section、域更新和制表位的行为不同；需要按规则域标明最终人工验收工具。
- 早期规则和当前正式规则存在取代关系；如果规范没有状态和 `supersedes` 信息，会再次把废弃实现当成要求。
- `.trellis/spec/backend/quality-guidelines.md` 已包含多段 Word 输出行为，新增主规范后必须迁移或改成引用，避免两份规范并列。

## 实施阶段复核结论

- 正式链路完全不读取 `full.md`，`find_content_list()` 明确优先 v2，且只在无 v2 时回退 legacy content list。
- 已确认 `continuation_heights` 只写不读、v2 未归页 block 会被 layout plan 丢弃、源 header 会覆盖配置 header 且同向页源 header/footer 互相覆盖、纯页码 footer 缺少 `PAGE` field、无效表格可能重复题注、质量 flags 不阻断成功状态。
- OPA228 四个 Golden PDF 虽已提交，但当前测试只验证 manifest/治理协议，没有在当前版本转换 4/4；唯一离线正式端到端 MinerU fixture 是 P1 最小包，且只覆盖 heading/paragraph/list。
- SC2167、CM4112/CM4114、TPL51200、BL0942、RS2G04 均按 external/historical evidence 记录，不能写成当前可运行 fixture。
- 以上缺口只进入权威规范的 `implemented-gap`/`planned` 状态和产品缺口清单，本任务未修改产品代码或测试。

## 建议的规范形态

- 新建 `.trellis/spec/backend/word-generation-rules.md` 作为正式 Word 输出行为的唯一权威规范。
- 保留 `template-layout-configuration.md` 作为模板 API/schema/version 专项合同；主规范只描述输出优先级并链接专项合同。
- `quality-guidelines.md` 只保留通用验证要求，并链接主规范，不重复分页、分栏、公式或页脚行为。
- 每条规则包含稳定 ID、触发信号、owner、预期行为、优先级/例外、禁止做法、自动测试、人工样本、实现状态和取代关系。
- 不为 Markdown 新增验证程序；实施阶段用现有 `rg`、Python import/test discovery 和 `git diff --check` 校验引用即可。
