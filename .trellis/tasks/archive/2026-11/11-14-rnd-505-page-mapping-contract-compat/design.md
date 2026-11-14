# RND-505 页映射合同与兼容回归设计

## 合同来源

- `app/domains/document_jobs/preview.py:221` 在成功预览的 manifest 写入页映射。`preview_evidence.py:139`、`:179` 和 `:200` 用选定主件、同次 run、预览 PDF 和可认证的渲染证据建立期望绑定。
- `app/services/preview/page_mapping.py:14` 区分载体 schema 与算法版本，`:219` 按渲染证据版本构建映射，`:353` 校验内层 schema、算法、hash 和绑定。旧 manifest 缺字段返回 `legacy_evidence_missing`，内层 hash 或绑定失配返回 `invalid_mapping`。外层权限、对象字节和 manifest 校验仍由预览证据链负责。
- `app/domains/document_jobs/review_content.py:209` 独立投影预览和映射的可用性。`app/services/preview/page_quality.py:481` 使用已认证映射关联页面与候选块。合同应说明这种关联的置信度和用途，保留既有交付判定边界。

合同拟落在 `docs/contracts/pdf-ir-word-page-mapping-contract.md`，沿用历史文件位置。以当前实现写清兼容边界，从 PR #9 的 `850c0090` 选取用例和背景。

## 兼容用例

- 通过当前 writer/reader 验证现行算法，使用可核对的 v1 夹具验证旧算法。针对坏 hash 和错绑定分别构造输入，错绑定用例保留正确的内层 hash，确保两个拒绝条件各自受到检验。
- 用带有效外层描述和 hash 的预览证据复现缺字段和坏内层数据，断言预览仍可用、映射降级且读取不写回。另以外层完整性失败核对原失败边界。
- 用最小正文场景断言单页零基页码和多页估算。保留 `tests/test_document_ir_word_renderer_layout.py:1748` 已有的合并目录书签所有权用例。

## B1 回退待验证

当前 `app/services/renderer/word_renderer.py:223` 仍实体化锚点，`app/domains/document_jobs/render_result.py:155` 的历史主件锚点读取只能说明当前 reader 的局部兼容边界。未来认定 B1 需有候选构建及源码指纹，证明它停止新锚点和映射写入，保留历史证据与内容认证，并具备旧／新 manifest 互读、含锚点 DOCX 的恢复入口实证和内部字段不泄露的证据。历史 #9 结果仅供溯源。
