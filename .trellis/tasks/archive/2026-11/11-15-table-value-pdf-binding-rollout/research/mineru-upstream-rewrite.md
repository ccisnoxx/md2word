# MinerU 3.4.4 的 PDF 重写与原件导出

- 调查问题为整份 PDF 为什么重写、`_origin.pdf` 写入哪些字节、是否有公开的原件保真选项。
- 范围为已归档的真实 ZIP、当前 Worker 和 MinerU 公开源码/API。调查日期为 2026-11-15。

## 保留的实物证据

两份新鲜回包的 `layout.json` 都声明 `_version_name=3.4.4`、`_backend=hybrid`、`_effort=medium`。在已保留 ZIP 中直接重读对应 PDF 的字节、Info 和 `startxref` 数值，得到下列结果。表中时间为 PDF 内部原始字段，字段未带时区。

| 样本 | PDF 长度 | SHA-256 前缀 | `CreationDate` | `startxref` 指向的偏移 |
| --- | ---: | --- | --- | ---: |
| P7 实际上传的历史同源原件 | 112080 | `24f724cf…` | `D:20260602160048` | 111118 |
| P7 新鲜包内原件 | 112172 | `69e9aaba…` | `D:20261115175423` | 111210 |
| LOW/HIGH 新鲜包内原件 | 1067 | `c5ee429f…` | `D:20261115175910` | 770 |

三份文件的 Info 都记录 `Creator=PDFium` 和 `Producer=PDFium`。P7 两件均有 39 个可见的间接对象编号，trailer 的 `/ID` 字节不同。LOW/HIGH 实际上传为 1503 字节、SHA-256 以 `bf90bdcb…` 开头。完整指纹与实际 Worker 证据见 [阶段五 Worker 验收](worker-acceptance.md)。

## 同版本开源路径

官方发布标签 `mineru-3.4.4-released` 指向 `0dfc9460cd9ab693b9af60ae3fbffd7bc111b062`。[MinerU 3.4.4 发布](https://github.com/opendatalab/MinerU/releases/tag/mineru-3.4.4-released)

1. 开源 FastAPI 保存上传文件的字节并以 `read_fn` 读取，原生 PDF 输入在读取阶段原样返回。同步和异步解析入口都在选择解析后端前调用 `_prepare_pdf_bytes`，该函数逐文件调用 `convert_pdf_bytes_to_bytes`。默认末页取最后一页。完整页范围同样进入重写路径。[上传读取与发送至解析入口](https://github.com/opendatalab/MinerU/blob/0dfc9460cd9ab693b9af60ae3fbffd7bc111b062/mineru/cli/fast_api.py#L808-L866) · [原生 PDF 读取](https://github.com/opendatalab/MinerU/blob/0dfc9460cd9ab693b9af60ae3fbffd7bc111b062/mineru/cli/common.py#L171-L183) · [同期预处理](https://github.com/opendatalab/MinerU/blob/0dfc9460cd9ab693b9af60ae3fbffd7bc111b062/mineru/cli/common.py#L668-L721) · [异步预处理](https://github.com/opendatalab/MinerU/blob/0dfc9460cd9ab693b9af60ae3fbffd7bc111b062/mineru/cli/common.py#L759-L811)
2. PDFium 打开源字节，创建新的 `PdfDocument`、按索引导入页并保存。这个流程按指定页范围构建解析输入。首次重写失败后，现有实现尝试逐页探测并重写可读页。仍失败时回退传入字节。历史 issue 记录了较早版本中导入异常的实物报告，3.4.4 的行为以发布源码为准。[重写和异常回退](https://github.com/opendatalab/MinerU/blob/0dfc9460cd9ab693b9af60ae3fbffd7bc111b062/mineru/cli/common.py#L194-L256) · [PDFium 导入和保存](https://github.com/opendatalab/MinerU/blob/0dfc9460cd9ab693b9af60ae3fbffd7bc111b062/mineru/utils/pdfium_guard.py#L108-L152) · [上游历史问题](https://github.com/opendatalab/MinerU/issues/3953)
3. `pypdfium2` 的 `PdfDocument.new` 进入原生 `FPDF_CreateNewDocument`。PDFium 在允许访问系统时间时写入新建时间，并为新文档写 `Creator=PDFium`。序列化按新输出的位置写交叉引用与 trailer，并初始化文件标识。3.4.4 声明 `pypdfium2>=4.30.0,<6.0.0`。所查 4.30.0 官方 macOS arm64 wheel 内的 PDFium 构建为 6462，只用来锚定原生机制说明，托管服务使用的库构建未确证。[依赖声明](https://github.com/opendatalab/MinerU/blob/0dfc9460cd9ab693b9af60ae3fbffd7bc111b062/pyproject.toml#L34-L45) · [pypdfium2 构造](https://github.com/pypdfium2-team/pypdfium2/blob/4.30.0/src/pypdfium2/_helpers/document.py#L127-L134) · [PDFium 6462 元数据](https://pdfium.googlesource.com/pdfium/+/refs/heads/chromium/6462/fpdfsdk/fpdf_editpage.cpp#153) · [PDFium 6462 序列化](https://pdfium.googlesource.com/pdfium/+/refs/heads/chromium/6462/core/fpdfapi/edit/cpdf_creator.cpp#318)
4. 同步和异步 Hybrid 都把预处理后的同一份 `pdf_bytes` 交给分析和输出。输出端把该参数作为 `_origin.pdf` 写出。开源 FastAPI 的 `return_original_file` 表单明确指包含经过处理的输入文件，只对 ZIP 生效。打包时从解析输出目录取 `_origin.*`，上传暂存文件保真导出在这条公开路径无选项。[Hybrid 传递方式](https://github.com/opendatalab/MinerU/blob/0dfc9460cd9ab693b9af60ae3fbffd7bc111b062/mineru/cli/common.py#L535-L615) · [原件成员写出](https://github.com/opendatalab/MinerU/blob/0dfc9460cd9ab693b9af60ae3fbffd7bc111b062/mineru/cli/common.py#L299-L305) · [表单字段定义](https://github.com/opendatalab/MinerU/blob/0dfc9460cd9ab693b9af60ae3fbffd7bc111b062/mineru/cli/api_request.py#L182-L203) · [ZIP 写入来源](https://github.com/opendatalab/MinerU/blob/0dfc9460cd9ab693b9af60ae3fbffd7bc111b062/mineru/cli/fast_api.py#L590-L605)

## 托管 API 的证据边界

- 本项目调用托管 v4 批量申请上传方式，逐文件以二进制 PUT 发送，没有设置页范围。公开 v4 批量接口文档列出 `data_id`、`page_ranges`、导出格式和回调设置。查询结果公开的是批次、`data_id`、状态、`full_zip_url` 等。保留上传原始字节的选项、可检索的原始上传件和已验原始 SHA-256 均未得到托管文档确认。回调 SHA-256 的输入是 UID、seed 和通知内容，可用于校验通知，接口文档没有声明通知包含原输入字节摘要。[本项目直传客户端](../../../../../../app/clients/mineru_client.py) · [MinerU 托管 v4 文档](https://mineru.net/doc/docs/)
- 当前 Word 生成规范要求实际上传件和所选 v2 同目录同文档名的 PDF 做逐字节摘要核对。官方同版的整页重写和新文档序列化足以解释实测现象。精确到托管后端使用的源代码或是否还做了其他处理，仍待服务方确认。公开机制和 PDF 内容对照适合诊断身份差异，线上启用仍需要实际可验证的原件字节或经单独评审、绑定同次解析结果的原始输入证明。[当前匹配入口](../../../../../../app/services/document_ir/pdf_value_column_review_flow.py) · [Word 生成规范](../../../../../spec/backend/word-generation-rules.md)
