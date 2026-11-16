# PDF 文本观测、页坐标与来源配对

- 查询范围为现有 PDF 观测能力、MinerU 表区域到源 PDF 点坐标的转换，以及本地自动核定的输入门槛。
- 依据为当前分支、安装环境和完整 `gs-008` 缓存的只读页级实测。
- 日期为 2026-11-15。

## 现有能力和限制

| 位置 | 已有事实及复用范围 |
| --- | --- |
| `app/services/preview/page_observer.py:95–171,177–211` | 原生观测用 pdfminer 的 `PDFPageAggregator` 读取 `LTChar`、`LTLine`、`LTRect` 等，按实际 MediaBox 与 CropBox 交集及页 CTM 转换为有效页左上点框。逐页限定对象数和执行预算。透明、复杂路径、裁剪、非普通文字绘制、Form XObject 或非默认 UserUnit 等情形会将页标为几何不支持。 |
| `app/services/preview/page_observer.py:193–203`、`page_quality.py:148–158,187–237` | `NativeObject` 仅有类型、点框、行 ID 和角色，文字字面值及路径端点、描边、填充等细节已被丢弃。预览报告能证实形状和同文本行，不能凭它复原某个数值或把任意 path bbox 当作列边。若用相同解析器做源表取证，应在归约前取得 `LTChar.get_text()` 和所需直线或矩形边界，维持现有预览报告合同。 |
| `app/services/preview/sandbox_adapter.py:151–213`、`page_observer.py:37–43,229–254` | 正式页观测依赖批准的隔离 launcher、profile 与代码和依赖指纹，绑定实际输入 PDF 字节、页数、预算和输出完整性。首版本地源 PDF 不应复用 Word 预览的启用、页类型或可用性结论。若抽取共用解析逻辑并改变预览实现，需一并核对现有 analyzer 指纹合同。 |
| `scripts/dev/run_datasheet_quality_baseline.py:168–190` | 已有 `pdftotext -bbox-layout` 到词框与文字串的离线读法。它生成的是用于验收的归一化框及一基页号。用作本地取证时，应保留实际页宽高和点框，明确换成零基页索引，加入调用、输出和对象预算。当前词框输出本身不能提供已绘制表格线、字形级遮挡或可见性证明。 |

运行实测中，仓库 Python 3.11.15 环境和当前 `python3` 都找不到 `pdfminer`。该模块原本就是有意可选，见 `.trellis/tasks/archive/2026-11/11-01-p0b-runtime-deps-poppler/design.md:39–49`。`page_observer.py:100–108` 在依赖缺失时返回观测不可用。当前 `pdfinfo` 和 Poppler `pdftotext` 26.06.0 可运行。这次页框核验来自 Poppler 和已有 IR 换算。要确认原生字形及线段 provider 可用于本地自动核定，仍需在有现成合规运行环境时验证其真实输入和失败行为。

## 同源和坐标的接纳顺序

1. `mineru_package.py:189–215` 唯一选择结果根与优先 v2 内容列表，保留原始字节 SHA-256。转换器在实际选中的包上从原始 JSON 建立表账本，`logical_table_group.py:125–144` 从经过校验的 Pointer、页号和原 bbox 构造 `SourceSpan`。取证用此来源表区域和真实源页索引，Word 的页和表坐标属于输出证据。
2. 当前 `PdfCropSource` 只带 file ID、checksum 和 bytes（`table_placeholder.py:66–79`）。第二阶段通过已给的记录核对实际 PDF 和内容列表摘要（`table_value_column_review.py:129–172`）。自动生成记录前仍需独立确认 PDF 与所选解析结果的配对。首版可要求可信包中与选中 v2 同目录同文档名且唯一的 `*_origin.pdf`，以其实际字节哈希比对显式源 PDF。已登记样本也可用可信清单的 PDF 与 v2 成对指纹核对，现有例子见 `run_datasheet_quality_baseline.py:224–236`。仅对传入的 PDF 重新计算 SHA-256 再写入新记录无法验证 PDF 与解析内容之间的关系。缺少独立配对证据时保留 blocker。
3. `layout_signals.py:52–96,248–265,395–401` 先从包内候选 layout/middle 读取物理页尺寸和版本，再把满足版本与范围条件的 IR 页标为 `mineru_normalized_1000`。由于页尺寸入口可选择包内其它布局候选，自动核定还应核对 `read_same_document_layout` 实际选出的唯一同文档布局（`layout_signals.py:293–313`），把已用布局摘要与页号、宽高、版本绑定。这个布局读取器的摘要在转换入口已经可得（`mineru_converter.py:135–165`）。
4. 使用 `layout_signals.pdf_point_bbox` 这一个 owner 处理原 bbox（`layout_signals.py:100–117`）。已确认千分位坐标按宽高分别缩放。首版建议要求明确的千分位标记、实际源 PDF 与同文档 layout 的页数对应、相同完整的 MediaBox/CropBox、零原点、旋转为 0、UserUnit 为 1、点框和方向一致。避免用 1000×1000 的 bbox 空间猜方向。参考 `infrastructure/pdf_crop.py:45–90` 的字节、边界、框和方向检查，抽取页框验证比为核验额外渲染图片更直接。裁图现有的逐轴整数截断例外只适用于标记过的归一化框并会映射回实测尺寸，不能扩成自动取证的无界容差。

## 完整 gs-008 页级实测

| 检查项 | 观测 |
| --- | --- |
| 文件配对 | 完整缓存的唯一 v2 和同文档名 `_origin.pdf`，实际 v2 SHA-256 为 `fdc0ea4050914df39ce7d3e9e42798164d32d1f04b82bd9dff4d2ffc1e9e98c3`，源 PDF SHA-256 为 `24f724cf0e795f6afeb6fec5c72ff8f144085c59d57fbf0a5c9efbf1808b1eb3`，与 `tests/fixtures/datasheet_quality/local_baseline_manifest.json:99–103` 一致。 |
| 页框 | `pdfinfo -f 1 -l 1 -box` 报告 1 页，612×792 pt，旋转为 0，MediaBox 与 CropBox 均为 [0, 0, 612, 792]，方向为竖向。同文档 `layout.json` 的版本为 3.1.8，零基页 0 的 `page_size` 为 [612, 792]。使用的布局 SHA-256 为 `cb69b35f9fbefc2740d95a1d70c5c858690a854923354a12d11140ee211ad3b8`。 |
| 表区域 | `/0/2` 原 table bbox 为 [89, 130, 908, 657]。经现有 `build_pages` 命中 `mineru_normalized_1000`，用 `pdf_point_bbox` 得到左上点框约 [54.468, 102.960, 555.696, 520.344]。同文档 layout 里 `table_body` 的点框为 [55, 103, 556, 521]。这是表体区域的交叉印证，逐值行列仍需在实际 PDF 内独立定位。 |
| 现成配对负例 | 仓库 `tests/fixtures/golden_samples/pdfs/OPA228_P7.pdf` 的 PDF SHA-256 为 `0afe536bc8ff50b8a30c5da25fbd54ea4226179c7cceb16fb331671c71da077f`。它与完整缓存的源 PDF 导出的 `pdftotext -layout` 全页文本完全相同，均为 5780 字节。按源字节合同，仍需拒绝将这个同名、同文字的 PDF 与完整缓存自动配对。 |

## 首版保守范围

- 有效范围限于原生可见文字和可独立认证的单表行列。存疑的包括扫描件、有不可见 OCR 层或重复叠字的页面、旋转或不同裁切页框、乱码或文本提取失败、缺少版本或同文档布局、越界和不一致的实际几何。对这些场景，留原跨列 blocker 和原因，交人工核定。
- 标题位置、原格文本和原横跨范围可以产生候选。自动核定还要用经过认证的行区间与列边界，让完整值框归入唯一列，且证据处于同一源表区域。仅词框时可做只读归属探查。列边界或文本可见性缺少确证时，保持人工核定。多命中、跨边界、不能证明文字可见、超时和对象预算耗尽都应停止对应自动核定。
- 相关规范为 `.trellis/spec/backend/word-generation-rules.md:158–168` 的 IR-002、`:385–392` 的 TABLE-001 核定合同和 `:421–429` 的 TABLE-004 页框示例。暂无 PDF 文本核定的产品集成或校正输出证据，本次验证只覆盖输入配对和页框。
