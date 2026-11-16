# PDF 坐标取证与 Grid 修正接入

- 调研问题为自动列归属如何沿用第二阶段修正和交付认证。
- 范围为本地正式转换的源表、修正记录及结果证据。日期为 2026-11-15。

## 现有合同

| 位置 | 已确认的行为 |
| --- | --- |
| `scripts/dev/run_local_mineru_conversion.py:141–157`、`:177–188`，`scripts/dev/formal_mineru_conversion.py:74–82`、`:228–271` | 本地入口解析人工 JSON 和显式提供的 PDF。原排版转换使用同一转换器与正式渲染后写 IR、DOCX。CLI 重算 PDF 散列，但本地文件 ID 与散列均来自本次所给文件，形成不了 PDF 与 MinerU 包的独立配对证明。 |
| `app/services/document_ir/mineru_converter.py:135–165`、`:408–428` | 先解包并选择实际 content list，记录包和内容列表散列。逻辑表归组、表头核定与上游续表覆盖证据就绪后才挂载数值列核定，随后验证完整 IR。这个位置已有来源账本和当次 PDF loader。 |
| `app/services/tables/validator.py:159–199`、`:392–394` | `iter_parameter_value_column_spans` 产出源格 finding 和原跨度里的已识别数值列。原始报告继续使用这些 findings。 |
| `app/services/document_ir/table_value_column_review.py:31–73`、`:76–126`、`:129–175` | `TableValueColumnReview` 的核定指纹包含记录整体。resolver 重建源 Grid，仅接纳单片原生表中 `rowspan=1`、完整位于并列数值列且已是 blocker 的格，核对原格内容、原跨度、目标列号及标题，逐条返回真实 finding ID。attach 校验 PDF 字节与版本、实际 content list、单片与可见正文。一个源 Pointer 只接一份记录，整批校验后才挂载。 |
| `app/services/renderer/logical_table_plan.py:185–209`、`:221–262` | 渲染复算原始 Grid 与当前布局的几何一致性。只把已有格移到原跨度内的单列，在计划中保留其余格及核定指纹。当前支持原排版视图中的原生表。 |
| `app/services/renderer/content_contract.py:388–425`、`:475–486`，`app/services/renderer/table_content_evidence.py:183–221`、`:263–270` | 实际 Word 几何、单元格文字和释放位置先通过核验，才生成 `value_column_corrections`。报告 `validation` 留存原始 findings，交付 flags 只解除已认证列表中的 finding ID。 |
| `app/services/tables/evidence.py:237–286`、`:444–457`、`:505–515`，`app/services/renderer/render_evidence.py:409–434` | 重读按源格、原区间、输出表行、单列跨度和核定指纹交叉检查修正记录，重新计算状态、计数及报告散列。实际 IR 和 DOCX 的双文件重读会重建新版内容认证并比对证据，输入接口没有 PDF。 |

## 建议接入方式

1. 只在本地原排版入口经显式开关启用。用 formal converter 的受控解包结果，在选中的 v2 content list 所在结果根找唯一同文档的源 PDF 副本，比较其实际字节散列和显式 `--source-pdf`。带前缀时按同文档命名匹配。没有唯一副本的情形仅在已有可信清单事先同时绑定这次 PDF 和实际内容列表时具备自动取证前提。参考 `app/services/document_ir/mineru_package.py:189–202` 的实际版本选择、`app/services/document_ir/layout_signals.py:293–313` 的同根同文档选择，以及 `scripts/dev/run_datasheet_quality_baseline.py:230–236` 的双散列验收。自动器为两份新输入各算一个散列无法建立配对，包内副本的证明范围也限于已信任且留存的 MinerU 结果包。
2. 在 converter 已归组与覆盖校验后、现有 attach 前完成取证。复用原 spans iterator 取待决 blocker、原格与数值列，先按片内源行/格识别显式人工核定，再观察尚未核定的位置。人工选项保留既有严格来源校验与整批拒绝。一个源格仅接受唯一表、行、完整值词和独立列证据，自动目标还须在源原跨度和对应列标题内。合格结果生成普通 `TableValueColumnCorrection` 交给第二阶段 resolver，按片组装成一份 `TableValueColumnReview`，与已接纳人工核定合批一次挂载。避免同一 Pointer 两份记录或同一字形被多个原格占用。有竞争行列/字形、边界不足、文本层缺失等情形仅记录未决原因，保留原 blocker 供后续人工处理。
3. 将自动取证出处随逐格核定绑定。最小改法是在 correction 上增可选的内部 typed `pdf_binding`，沿用现有 PDF、内容列表、原 HTML、页/Pointer 源锚点，保存取证算法与坐标版本、可复核的表/行锚、标题和数值包围框、列边界及同源配对摘要。由观察器创建后纳入 `review_sha256`，交付证据可投影该摘要与出处，避免把逐页完整文本放进质量报告。不带几何出处时省略新字段，保留既有人工记录序列化、hash 和测试语义。原人工 JSON 入口仅接受人工核定，提交的几何字段不能充当观察器事实。再次本地转换应从实际同源 PDF 重新取证。已有结果重读只校验冻结的 IR 中出处、指纹、认证计划及实际 Word，界面或文档应如实说明它没有再读取 PDF。
4. 描述每个未决 candidate 的原因时可用源 finding ID、源表和单元格锚点，和现有 blocker 一起供人工定位。自动阶段只产生已证实的拟修正及未决结果，后续继续由原始 validator 和认证回放计算问题状态。缺少唯一证据属于正常未决。通过取证后仍不满足原 Grid、记录或 Word 完整性合同属于校验失败，沿正式入口拒绝，不能把拟修正算成解除。线上路径后续另行对齐。

## 验收关注点

- 完整 `gs-008` 的第二阶段人工结果提供列位置对照，自动验收不传入该人工样表做判断。核对实际 Word 的两格位置、值、单位及相邻格，比较原始 23 条 finding ID 与解除集合。其余条目各自按独立证据决定，剩余数量由实测给出。参见 `.trellis/tasks/archive/2026-11/11-15-table-value-column-review/validation.md:16–31`。
- 用同一源格位置与数值制造重复归属、跨列边界或推断到原跨度外的对照，确认修正为空且原 blocker 保留。交换同布局的另一版 PDF、原包缺源文件、多候选源文件、新记录自带 PDF hash 等情形均不能开启自动绑定。并测正常人工核定占位、错误人工记录仍整批拒绝与未启用自动开关的回归。
- 改动或移除自动出处、替换 IR/实际 DOCX、无修改记录的历史产物重读，覆盖报告与计划指纹。核对认证前拟修正未触发解除。

## 边界与未验证

- 本笔记按本地代码和阶段二归档核对，未重复执行字形与列带测量，也未调用外部资料。现有 `app/services/preview/page_observer.py:193–211` 的预览模型仅投影 char/path 的 bbox、行标识及角色，未保留字形文本和完整画线端点。取词及可用线依据应在现有底层 PDF 观察处与坐标研究对齐。
- 适用规范见 `.trellis/spec/backend/word-generation-rules.md` 的 TABLE-001 及参数值列的同源人工修正，质量聚合仍由 `app/domains/document_jobs/base_quality.py:198–214` 消费经过认证的 table evidence。
