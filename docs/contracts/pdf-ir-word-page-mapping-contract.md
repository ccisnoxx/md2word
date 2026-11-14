---
doc_type: data-contract
contract: pdf-ir-word-page-mapping
doc_status: active
last_verified_commit: e902143be735ac699eb13ee00bb77764fd5b877a
owner: null
verification_scope: >-
  核对当前页映射的生成、绑定、读取、审核与页面质量消费路径。
  B1 回退兼容性和生产运行待验证。
---

# PDF → DocumentIR → Word 预览页映射合同

页映射把 PDF 来源范围和 DocumentIR 块关联到选定 DOCX 的正文目标、可验证书签及 Word 预览页。源 PDF 页索引和预览 PDF 页索引分别属于各自文档，两者均从 `0` 开始。

## 载体与版本

`word-preview/v1` manifest 可带 `page_mapping`。成功预览由 [DocumentJob 预览服务](../../app/domains/document_jobs/preview.py) 写入，内层 schema 固定为 `pdf-ir-word-page-map/v1`。[映射实现](../../app/services/preview/page_mapping.py) 根据认证的渲染证据选用算法，当前读者接受两版。

| 算法 | 渲染证据 |
| --- | --- |
| `source-order-nearest/v1` | `render-plan/v1` 与 `block-render-evidence/v1` |
| `source-order-nearest/v2` | `render-plan/v2` 与 `block-render-evidence/v2`。正式预览读取这组证据时也要求同次 v2 锚点证明，并用共享表格各块的行范围区分正文位置。归并的目录项可按实际目录字段位置估算，保留缺锚状态。 |

内层对象包含 `status`、`reason_code`、`binding`、`entries`、`counts` 和 `mapping_sha256`。哈希为排除 `mapping_sha256` 后的 UTF-8 JSON SHA-256，键排序，紧凑分隔，保留 Unicode，拒绝非有限数。内层上限为 8 MiB 和 100,000 条记录，超限时映射整体不可用。

## 身份绑定

[预览证据读取](../../app/domains/document_jobs/preview_evidence.py) 从选定的主件凭据、当前预览 run 和已认证产物计算期望绑定。

| 字段 | 绑定对象 |
| --- | --- |
| `source_generation`、`result_file_id`、`docx_sha256` | 选定的主 DOCX |
| `source_pdf_file_id`、`document_ir_file_id`、`input_ir_sha256`、`plan_sha256` | 主件所引用的源 PDF、原始 IR 和已认证渲染计划。可用或降级的映射需要完整的来源与计划身份。 |
| `run_id`、`attempt`、`profile_sha256` | 当次预览及其冻结配置 |
| `preview_pdf_file_id`、`preview_pdf_sha256`、`page_count` | 预览 PDF 身份。三项一并存在或一并为空。 |

DOCX、profile 和预览 PDF 的哈希使用 `sha256:<64hex>`，IR、计划和映射哈希使用裸 64 位十六进制。块和锚点身份来自同一份渲染证据。可导航的 `bookmark_name` 来自同次 DOCX 的独立锚点证明，锚点缺失可与有效的页位置同时存在。

## 页位置与消费边界

`entries[*].source` 保留来源状态、源页范围、片段和布局信息。`verified_ir205` 来自已验证的逻辑表组 IR 片段，`legacy_layout` 表示只有旧布局定位。来源状态与目标页置信度分别记录。

- 只有一页预览且目标为已认证正文时，`single_page` 的 `preview_page_index=0`，`confidence=high`。
- 多页预览按源页相对次序、最近正文来源或物理正文顺序估算起始页，`estimated_start` 固定为 `low`，也可返回页 `0`。`page_range` 始终为 `null`，包括长表和有多个来源范围的块。
- 没有可定位的目标时，`location.kind=unavailable`，页索引为 `null`。非正文块如有 `fallback`，它只给出低置信的导航候选。若整份渲染证据没有正文目标，映射为 `unavailable/no_target`，可保留已证实的来源和输出状态。
- [审核内容](../../app/domains/document_jobs/review_content.py) 分别投影预览可用性、块来源和导航位置。[页面质量](../../app/services/preview/page_quality.py) 使用已认证映射为页面关联候选块，保留定位种类和置信度。映射提供导航和诊断关联，质量与交付状态仍由既有检查计算。

## 兼容读取与失败边界

先校验当前主件、manifest 和预览产物的归属、描述符、字节与运行身份，再解析可选映射。有效旧 manifest 缺字段时返回 `legacy_evidence_missing`。未知映射版本返回 `unsupported_version`，内层哈希或身份绑定失配返回 `invalid_mapping`。预览和审核读取仍保留已认证的预览，映射降级为不可用。页面质量报告单独认证，报告若与 manifest 中的映射哈希绑定失配，可处于未就绪状态。

外层 manifest 字节或身份错误、主件完整性错误和未知存储错误沿用原证据链的失败处理。读取兼容不会回填旧 DOCX、IR 或 manifest。

## B1 回退待验证

认定 B1 需要候选构建及源码指纹，并验证该版本停止写入新锚点与页映射，继续读取旧、新 manifest，保留带锚点 DOCX 的已有证据和内容认证。恢复实证须覆盖历史结果发现、显式结果指针和已准备结果凭据三条入口，确认可选导航故障局部降级，公开摘要不泄露私有证据。当前兼容回归覆盖当前读者的离线行为。历史 [PR #9](https://github.com/ccisnoxx/md2word/pull/9) 的 B1 结果对应其历史构建。
