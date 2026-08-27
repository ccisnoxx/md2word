# 研究：题注主体完整性

- 问题：`source_ir_integrity:caption_subject_unresolved` 的精确触发条件、caption 主体解析 owner、相关调用路径与测试，以及 `docjob_475553eaf015` 的最小正确修复位置
- 范围：混合视觉块
- 日期：2026-08-27

## 研究结论

### 相关文件

- `app/services/document_ir/mineru_converter.py`：MinerU 源块预处理、caption 抽取/主体裁决、DocumentIR 构造和首次完整性门禁。
- `app/services/document_ir/integrity.py`：`source_ir_integrity:*` 证据与失败关闭的唯一 owner。
- `app/domains/document_jobs/execution.py`：线上 Worker 的 MinerU→DocumentIR 调用、失败分类和任务状态落盘。
- `app/main.py`：线上 runtime 创建唯一 `MinerUToDocumentIRService` 实例。
- `scripts/dev/formal_mineru_conversion.py`：正式本地转换入口，复用同一 converter 和 renderer integrity。
- `app/services/renderer/evidence.py`：渲染阶段再次消费 source integrity；本次错误在 converter 内已抛出，因此没有到达此路径。
- `app/conversion/runtime/table_html_parser.py`：已有 HTML table 结构 parser，可复用来判定稀疏 table，不需要新增 parser 或依赖。
- `tests/test_document_ir_mineru_converter_layout.py`：编号图题、跨类型主体、表图复合、富文本 caption 分组和失败关闭的现有回归。
- `tests/test_fastapi_jobs_backend.py`：完整性错误在线上任务边界映射为 `document_ir_failed` 且不发布 IR/DOCX 的回归。
- `.trellis/spec/backend/word-generation-rules.md`：IR-004、TEXT-004、IMAGE-002、IMAGE-003 的现行合同。

### 精确触发条件

1. `_convert_blocks()` 的预处理顺序固定为：尾页过滤 → `_reassociate_numbered_image_captions()` → 空表续页合并 → 表图包含关系归一化 → `_reassociate_visual_group_captions()`，之后才建立 source inventory（`app/services/document_ir/mineru_converter.py:129-140`）。
2. `_reassociate_visual_group_captions()` 只扫描 `source_type == "table"` 且至少有一条匹配 `Figure|Fig.|图` 的 Figure caption 的块（`app/services/document_ir/mineru_converter.py:412-425`；正则定义在 `app/services/document_ir/mineru_converter.py:56-60`）。
3. 唯一表图复合已由 IMAGE-004 确定，且总 caption 恰好一条、Figure caption 恰好一条、group 恰好是一个 image 加一个 table 时，题注绑定复合主体并清空原 table annotation（`app/services/document_ir/mineru_converter.py:426-446`）。
4. 否则只尝试“同页、源顺序在 table 之前”的普通图片主体。table 必须有 page/bbox；向前扫描遇到换页或 `title/heading/table` 立即停止；候选只接受 `chart/image/figure`，且必须有 bbox、完全位于 table 上方并与 table 水平相交。任一候选图片不满足几何条件也会整体返回空（`app/services/document_ir/mineru_converter.py:597-621`）。
5. 只要总 caption 不是一条、Figure caption 不是一条，或上述主体列表为空，原 table 就写入 `_md2word_caption_owner_unresolved=True`（`app/services/document_ir/mineru_converter.py:447-450`）。`_bind_group_caption()` 在主体或 owner bbox 缺失时也会写同一标记（`app/services/document_ir/mineru_converter.py:648-687`），但当前普通图片路径已先检查这些条件。
6. 构造主 IR block 时，该私有标记映射为 `metadata.caption_owner_unresolved=True`（`app/services/document_ir/mineru_converter.py:204-210`）。`build_source_integrity()` 对每个主 block 看到该 metadata 即生成 `source_ir_integrity:caption_subject_unresolved:<block.id>`（`app/services/document_ir/integrity.py:52-85`）；`ensure_integrity()` 看到任一 blocking flag 就抛 `DocumentIntegrityError`（`app/services/document_ir/integrity.py:160-164`），converter 在返回结果前立即调用它（`app/services/document_ir/mineru_converter.py:349-364`）。

### 权威 owner 与调用路径

- caption 文本边界 owner：`MinerUToDocumentIRService._captions()` / `_caption_texts()`（`app/services/document_ir/mineru_converter.py:887-916`）。flat rich-node list 当前被合成一条逻辑 caption。
- 编号图片组 owner：`_reassociate_numbered_image_captions()` / `_reassociate_image_group()`（`app/services/document_ir/mineru_converter.py:385-410,758-787`）。当前只把 `chart/image/figure` 当作图片源（`app/services/document_ir/mineru_converter.py:789-793`）。
- 跨类型主体 owner：`_reassociate_visual_group_captions()`、`_prior_image_subject_indices()`、`_bind_group_caption()`（`app/services/document_ir/mineru_converter.py:412-490,597-687`）。
- blocking evidence/exception owner：`build_source_integrity()` / `ensure_integrity()`（`app/services/document_ir/integrity.py:52-164`）。这里应保持失败关闭，不应作为修复点。
- 线上路径：runtime 在 `app/main.py:183-195` 创建 converter；Worker 在 `execute_job()` 的 `ir_converting` 分支进入 `_convert_and_save_document_ir()`（`app/domains/document_jobs/execution.py:150-176`），读取 MinerU ZIP 后调用 `convert_zip()`（`app/domains/document_jobs/execution.py:789-798`）；异常按当前 stage 映射为 `document_ir_failed`（`app/domains/document_jobs/execution.py:2511-2527`）。
- 本地正式路径：`convert_formal_mineru_package()` 同样调用 `MinerUToDocumentIRService().convert_zip()`，成功后才渲染并执行 renderer gate（`scripts/dev/formal_mineru_conversion.py:173-194`）。
- 二次门禁路径：若 IR 来自其他路径且进入渲染，`build_renderer_metadata()` 会再次调用 `build_source_integrity()`，并把其 flags 合入最终 blocker（`app/services/renderer/evidence.py:100-105,109-145`）。本次 converter 已先失败，未到达渲染。

### `docjob_475553eaf015` 线上证据

- 2026-08-27 对 `hostdzire` 当前线上任务和原始 MinerU ZIP 做了只读核对；任务确为 `failed_stage=ir_converting`、`error_code=document_ir_failed`，没有线上写操作。
- MinerU flat blocks 为 177；两个空表续页占位合并后 source inventory 为 175。归一化后的 `block_0099/0100/0101` 对应原始第 101/102/103 块，均在 source page 11。
- `block_0099`：`table`，bbox `[117,84,457,274]`，有 JPEG `image_source`，HTML 是 1 行 3 cell（`20mV/DIV`, `4μs/DIV`），无 caption。
- `block_0100`：`table`，bbox `[556,84,895,273]`，与 `block_0099` 严格并排对齐，有 JPEG `image_source`，HTML 是 1 行 3 cell（`20mV/DIV`, `10μs/DIV`），唯一 caption 为“图 20 小信号响应…”。
- `block_0101`：`chart`，bbox `[72,344,484,565]`，有 JPEG `image_source`；其单个 flat rich caption 节点数组实际依次包含“图 19 …”和一个新的 text node“图 21 …”，当前 `_caption_texts()` 将两者拼成一条 caption。
- PDF 页面事实已核对为三张图：图 19/20 在上方并排，图 21 在下方。因此这是 MinerU 将前两张图误分类为 sparse table，并把图 19/21 annotation 放入第三个 chart flat list 的组合异常。
- 当前代码必然失败：IMAGE-002 不把前两个 table 纳入图片组；IMAGE-003 处理 `block_0100` 时，向前第一块就是 `block_0099 table`，按 barrier 规则立即停止，得不到 image subject，于 `app/services/document_ir/mineru_converter.py:447-450` 写 unresolved。

### block 数量相等能证明和不能证明的内容

- `expected_source_block_count=175` 来自预处理后的 `len(raw_blocks)`（`app/services/document_ir/mineru_converter.py:349-357`）；`ir_main_block_count=175` 排除了带 `metadata.source_block_id` 的 table context、standalone caption、TOC anchor 等合成块（`app/services/document_ir/integrity.py:55-58`）。相等只证明每个归一化 source block 都有一个主 IR block，不证明语义类型、caption 主体或视觉资产正确。
- 本样本两个 table 的 HTML 可解析，因此会通过 table payload gate；但 converter 只对最终 `block_type == "image"` 的块解析并登记 image asset（`app/services/document_ir/mineru_converter.py:234-264`）。如果仅让 `block_0100` 保留 Figure caption 并继续当 table，任务虽可绕过当前 blocker，图 19/20 的 JPEG 仍不会进入 IR/DOCX，且图 19/21 仍是一条错误 caption；这不是正确修复。

### 根因排序

1. **已验证直接根因**：混合视觉序列中的前两张图被 MinerU 标成 `table`；当前 IMAGE-002 只处理 `chart/image/figure`，IMAGE-003 又把前置 table 当 barrier，因此 `block_0100` 无可接受主体。
2. **已验证共同根因**：第三张 chart 的 flat rich caption 包含两个有明确 text-node 起点的编号图题；TEXT-004 的通用 owner将整个 flat list 合为一条，导致即使扩展视觉候选类型，现有严格编号算法仍只看到两个 caption 对三个主体。
3. **完整性覆盖缺口**：table source 有 `image_source` 但只要 HTML 可解析就能通过 IR-004；source/main 数量与 type count 相等也发现不了“图像型 sparse table 的 JPEG 被丢弃”。

### 最小正确修复位置

最小正确修复应在 **converter 的现有编号视觉组预处理 owner**，即 `app/services/document_ir/mineru_converter.py::_reassociate_numbered_image_captions` / `::_reassociate_image_group` 附近，并保持发生在 source inventory 与 `_map_block_type()` 之前；不要修改 `integrity.py`、错误分类或 renderer。

建议的保守边界是：

1. 只在同页、源顺序连续的视觉 run 中，把 `chart/image/figure` 与“有有效 `image_source`、可解析为稀疏单行 HTML、且至少有一个带编号 Figure caption 的同类严格对齐 table pair”作为候选组；`table_type=simple_table` 或单行 HTML 单独都不足以改类型。
2. 只在该候选组内部检查 raw flat rich nodes；若后续 **text node 本身**以新的编号 Figure 开头，可形成候选逻辑边界。不要全局修改 `_caption_texts()`，也不要在普通 caption 字符串内部按图号切割。
3. 只有分组后 caption 总数与视觉块数严格相等、label 相同、编号唯一且连续时，才把这组已证明误分类的 sparse table 归一为 chart/image 语义，并复用现有 `_reassociate_image_group()` 按编号分配题注。任一证据不足继续保持当前 fail-closed。
4. 这样线上三块会归一为三个 image/assets，题注按 19/20/21 分配；不会新增 renderer 路径、第二套 caption owner 或新依赖。已有 `parse_html_table()` 可直接提供 row/cell 结构（`app/conversion/runtime/table_html_parser.py:18-25,79-86`）。

更小但不安全的方案均应拒绝：在 `integrity.py` 忽略 flag、让任意 table 自持 Figure caption、把所有 `simple_table + image_source` 全局转 image、或全局按图号拆 flat rich caption。它们分别会放行内容丢失、误改真表或违反现有 caption 边界。

### 现有测试与必要回归

- 编号图组严格重关联及数量不足/编号不连续负例：`tests/test_document_ir_mineru_converter_layout.py:1020-1078`。
- table 上 Figure caption 迁到唯一前置 image group：`tests/test_document_ir_mineru_converter_layout.py:1080-1128`。
- 无唯一 image subject 时必须 `caption_subject_unresolved`：`tests/test_document_ir_mineru_converter_layout.py:1192-1215`。
- 唯一表图复合主体正例：`tests/test_document_ir_mineru_converter_layout.py:1293-1342`。
- 富文本 flat caption 保持单条、nested groups/string list 保持多条：`tests/test_document_ir_mineru_converter_layout.py:359-460`。
- API 完整性 blocker 映射为 `ir_converting/document_ir_failed` 且不发布 IR/DOCX：`tests/test_fastapi_jobs_backend.py:10908-10947`。
- 最小新增正例应复刻三个脱敏块：两个并排 sparse table image + 一个 chart，flat rich nodes 在第二个编号 Figure text node处分界；断言 3 个 image/assets、caption 19/20/21、`caption_owner_unresolved` 不存在、source/main count 相等且 blocker 为空。保留现有无唯一主体负例，并补一个“没有完整连续编号/对齐证据时 flat rich list 仍保持一条且不改真表”的负例即可。

### 相关 Spec 与合同影响

- IR-004 指定 `_convert_blocks` 与 `integrity.py` 是 source→IR owner，数量/类型相等只是基础证据（`.trellis/spec/backend/word-generation-rules.md:165-175`）。
- TEXT-004 当前规定 flat rich-node list 是一条 caption，并明确“无可靠结构时不按图号猜测”（`.trellis/spec/backend/word-generation-rules.md:323-333`）。全局拆分会直接违约；上述方案只有在 IMAGE-002 的完整组级证据成立后，才把后续编号 Figure text-node 起点作为窄例外，实施后应同步该例外。
- IMAGE-002 当前输入限于连续 image group（`.trellis/spec/backend/word-generation-rules.md:407-417`）。修复会把它窄化扩展为“严格证明的混合视觉组”，并仍要求数量、label、连续编号全部成立。
- IMAGE-003 当前正确要求主体不唯一时失败关闭（`.trellis/spec/backend/word-generation-rules.md:419-428`）；不应放松。修复是在 IMAGE-003 之前把可证明的 MinerU 类型/题注错配归一化，IMAGE-003 的负例合同不变。

### 外部证据

- `hostdzire` 线上只读证据，日期 2026-08-27；API/Worker 镜像为 `partsignal-backend:mvp-20260825-172239-2a6fd940b848`。原始 ZIP、图片和客户 PDF 未写入仓库或研究文件。

## 限制与未发现项

- 未发现现有测试覆盖“table/table/chart 混合视觉 run + 一个 flat rich list 内多个编号 Figure 起点”；这正是当前缺口。
- 没有把生产原始文件或 proprietary 页面内容复制进仓库，只记录了支持裁决所需的脱敏结构、bbox、caption 和 payload 形状。
- 稀疏 table 的精确阈值仍需实现代理以最小回归固定；不应仅凭 `table_type=simple_table`、单行或 `image_source` 任一单条件改类型。组级严格编号与对齐证据必须是授权归一化的共同门槛。
