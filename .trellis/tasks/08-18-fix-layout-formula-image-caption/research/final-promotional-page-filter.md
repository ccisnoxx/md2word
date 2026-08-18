# Research: MinerU 最后一页微信/小程序推广封底过滤

- Query: 调查 MinerU 页面/块表示、现有页面级清洗、二维码或广告检测，并确定只删除最后一页微信/小程序推广页的最小权威边界与保守验收条件。
- Scope: internal
- Date: 2026-08-18

## Findings

### Files found

- `app/services/document_ir/mineru_package.py`：正式 DocumentIR 链读取并扁平化 MinerU `content_list`。
- `app/services/document_ir/mineru_converter.py`：线上 `document_jobs` 与正式本地转换共用的 MinerU 原始块到 DocumentIR/图片资产边界。
- `app/services/document_ir/layout_signals.py`：从原始块及 `middle/layout.json` 构造物理页、bbox、页角色并合并空续表。
- `app/services/renderer/layout_plan.py`：按 `DocumentIR.pages` 与 block page index 生成 Word 布局页。
- `app/conversion/docx_rules/mineru_content.py`：两条转换路径可复用的 MinerU 文本、资产路径和空续表纯规则；当前不含推广页规则。
- `app/conversion/runtime/input_adapter_runtime.py`：仍存在的兼容转换路径；保留独立的 `PageData` 页面结构。
- `app/conversion/runtime/page_repair_runtime.py`：兼容路径当前唯一明显的页面级修复，处理空续表页，不处理推广封底。
- `tests/test_document_ir_mineru_converter_layout.py`：正式转换器现有的合成 MinerU zip 测试入口，已覆盖嵌套 v2 页、资产、页尺寸、题注重配和续表。
- `/Users/sc/Downloads/TPL51200_mineru_result/*_content_list_v2.json`：现有负样本；最后一页是商标/免责声明文字，无图片 block。
- `/Users/sc/Downloads/BL0942_mineru_result/*_content_list_v2.json`：现有负样本；最后一页是“Version update”真实表格，不能按“短末页”删除。
- `mineru_result/RS2G04_(RevA.4).pdf-*/**_content_list_v2.json`：现有负样本；最后一页是重要声明，不能按“末页声明/联系信息”删除。

### MinerU 页面与块信号

1. `load_content_blocks()` 接受扁平 block 数组或 page-list 数组；page-list 被扁平化时为每个 block 补 `page_idx`，因此正式转换边界可按页分组而不需要改持久化模型（`app/services/document_ir/mineru_package.py:37-63`）。
2. 页号兼容 `page_idx` 和 `page_index`，可通过现有 `parse_page_index()` 统一读取（`app/services/document_ir/layout_signals.py:150-157`）。
3. v2 文本可位于 `title_content`、`paragraph_content`、`list_items[].item_content`；正式转换器已有递归 `collect_text_from_fields()`/`coerce_text_list()`，能够从嵌套字段提取文字（`app/conversion/docx_rules/mineru_content.py:58-105`）。
4. 图片路径可出现在 `img_path`、`image_path`、`path` 或嵌套 `image_source.path`；现有 `extract_first_asset_path()` 已递归处理这些形状（`app/conversion/docx_rules/mineru_content.py:222-245`）。
5. block 提供 `type`、`bbox`、页号、题注/脚注及可选图片路径。v2 二维码在结构上最可能表现为 `image`/`figure` 及近方形 bbox，但现有数据没有 `is_qr`、条码类型或识别置信度字段。
6. 物理页尺寸来自 `middle.json`/`layout.json` 的 `pdf_info[].page_idx/page_size`，且 `build_pages()` 会把所有 `pdf_info` 页加入 DocumentIR，即使该页的 raw blocks 已为空（`app/services/document_ir/layout_signals.py:32-64,169-182`）。

### 当前清洗行为

- 正式转换在生成 pages、DocumentIR blocks 和图片资产之前，只执行“图片题注重配”和“空续表合并”（`app/services/document_ir/mineru_converter.py:91-110`）。不存在广告、微信、小程序、二维码、封底或 CTA 关键词检测；在 `app/`、`tests/`、`scripts/`、`resources/` 中搜索相关中英文词和 QR 命名未找到实现。
- `clean_markdown_document()` 只删除 HTML `<details>` 并规整空行，`clean_text()` 只折叠空白，不是内容策略过滤（`app/conversion/docx_rules/mineru_content.py:25-35`）。
- 正式转换器在 raw block 循环中才读取图片字节并创建 `image_assets`/`DocumentIRAsset`（`app/services/document_ir/mineru_converter.py:110-159`）。因此若在该循环之前剔除确定的推广末页，二维码不会被注册或上传。
- 线上任务直接调用 `MinerUToDocumentIRService.convert_zip()`（`app/domains/document_jobs/execution.py:789-818`）；正式本地验收脚本也调用同一服务（`scripts/dev/formal_mineru_conversion.py:164-182`）。这是当前用户所关心生成质量的权威入口。
- 兼容转换仍通过 `app/conversion/service.py:22-35` → `runtime/input_adapter_runtime.py:136-150` 使用 `PageData`。其页面修复只会合并/清空续表 placeholder（`app/conversion/runtime/page_repair_runtime.py:49-103`），无推广页过滤。若产品仍承诺这条路径输出同一语义，需要复用同一个纯判定合同，但不能让两个入口各自维护关键词。

### 最小权威边界

最小且能一次阻断正文、翻译和图片资产的边界是 `MinerUToDocumentIRService._convert_blocks()` 的 raw-block 归一化入口：在题注重配、续表合并、`build_pages()` 和资产登记之前，对“最后一个物理源页”的原始 blocks 做一次保守判定。

边界必须同时处理两件事：

1. 删除命中页的所有 raw blocks，避免正文、页眉页脚、二维码资产和翻译条目继续进入管线。
2. 删除相同 page index 的 `DocumentIRPage`，或让 `build_pages()` 显式排除该页。仅删除 blocks 不够：`build_layout_plan()` 将 `document_ir.pages` 的全部 index 放入布局页集合（`app/services/renderer/layout_plan.py:39-69`），残留的 `pdf_info` 页仍会形成空 LayoutPage。

不建议在 renderer 删除：到 renderer 时二维码资产已经登记、翻译可能已经处理，且 renderer 不应承担 PDF 内容策略。也不建议直接改 `load_content_blocks()`：该 helper 只负责输入形状归一化，没有 package_root/page-size/质量标记上下文，加入业务规则会混淆职责。

### 可用的保守组合信号

目前没有正样本证明单一阈值，故应采用“全部满足才删除”的组合守卫，不以任一关键词或方形图片单独删除：

- 位置守卫：只检查最后一个物理源页；优先以 `pdf_info` 最大 page index 为准，缺少 layout/middle 时才退到 raw blocks 最大 page index。非末页即使出现推广文案也保留。
- 文案守卫：正文文本命中明确行动号召组合，如“微信 + 扫码/扫描”“扫码 + 进入/打开/关注”“小程序 + 进入/打开/扫码”“长按 + 识别二维码”“扫一扫 + 进入/打开”。不要把单独的“微信”“二维码”“官网”“联系我们”视为充分条件。
- 视觉守卫：页内至少有一个真实 `image`/`figure` 资产；近方形、无编号图注的 bbox 可作为 QR 候选的附加证据，但仅凭方形外观不能证明是二维码。
- 实质内容否决：出现真实 HTML 表格、公式、编号章节标题、编号图/表题注或明显长篇技术/法律正文时保留整页。不能尝试只删除二维码和一句话，因为用户要求的是明确推广封底整页，局部删除更容易破坏合法内容。
- 可观测性：命中后写入单个 document quality flag（包含原 page index），便于验收和误删追踪；未命中时不静默修改页面。

以上守卫只根据当前可观测字段提出。若后续拿到多份真实正样本，才应据实收紧/扩展词组和视觉条件；不应先增加模糊打分器或黑盒分类器。

### 推荐的可观察验收用例

1. **应删除**：三页输入；末页只有“微信扫码进入小程序”短文、一个有真实 path 的无题注方形 `image`、页眉/页脚/页码。结果 pages、blocks、assets 均不含末页；quality flag 记录被过滤 page index。
2. **应删除（v2 嵌套形状）**：文案分散在 title/paragraph rich-content nodes，二维码路径位于 `content.image_source.path`；仍能从共享递归抽取规则命中。
3. **应保留**：末页正文提到“可通过微信公众号获取技术支持”，但没有图片/二维码候选。
4. **应保留**：末页有无题注方形产品封装图或 Logo，但没有扫码/小程序行动号召。
5. **应保留**：末页是版本历史 HTML 表格，即使页脚或联系方式出现“微信”。
6. **应保留**：末页是 IMPORTANT NOTICE/免责声明、联系地址、域名或商标说明。
7. **应保留**：倒数第二页是明确推广页，最后一页仍有技术正文；本需求只授权删除最终封底页。
8. **应保留并可诊断**：命中文案但 image path 缺失，或只有方形 bbox 无资产；证据不足时不删。
9. **空页回归**：命中删除后，`DocumentIR.pages` 不含末页 index，正式 renderer 不产生空 LayoutPage，输出无空白尾页。
10. **资产回归**：命中页二维码字节不出现在 `result.image_assets`/`document.assets`，其余图片内容和 id 顺序保持一致。

### Related specs

- `.trellis/spec/backend/quality-guidelines.md` 规定空续表应在 MinerU 输入边界归一化、renderer 不猜测输入语义，并要求分页/空白页变更做 OOXML 与 WPS/LibreOffice 验收。推广封底过滤属于同一输入边界原则，但当前 spec 尚无相关合同。
- 当前任务 `prd.md`、`design.md`、`implement.md` 已定义“附件仅为复现/验收样本”和正式 MinerU→DocumentIR→Word 质量链；新增需求尚未写入这些任务文档。

## Caveats / Not Found

- 仓库及当前可见 MinerU 样本中没有包含“微信扫码进入/小程序二维码”的正样本，因此无法从真实数据确认 MinerU 会把二维码标为 `image`、`figure`、`chart`，也无法校准 bbox 比例或文案变体。
- `requirements.txt` 未声明 OpenCV、pyzbar、zxing 或其他二维码识别依赖；Python 标准库也不提供 QR 解码。当前证据不支持为了这一页过滤新增图像识别依赖。
- 现有负样本证明“最后一页短、含品牌/域名/免责声明或表格”并不足以删除，但它们没有覆盖合法正文中同时出现“微信 + 方形图片”的边界情况。
- 兼容 `app/conversion/runtime/*` 仍有调用者，但用户当前主流程和线上 `document_jobs` 的权威边界是 `MinerUToDocumentIRService`。是否同步兼容路径是产品兼容范围决定，不应由本研究擅自扩展。
- 按研究角色隔离要求，未读取 `implement.jsonl`/`check.jsonl`；已完整读取 `prd.md`、`design.md`、`implement.md` 和相关 backend spec。
