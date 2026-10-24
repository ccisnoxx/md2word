# PDF / IR / Word导航映射

## 触发与唯一owner

修改block通用书签、独立创建证明、预览页映射或其恢复/摘要时必须阅读本Spec及`docs/contracts/pdf-ir-word-page-mapping-contract.md`。正文合同以该文档为唯一详细定义，不复制预览状态机。

- `renderer/block_anchors.py`：同次真实marker创建/最终对象绑定及可选block-anchor-evidence/v1。
- `renderer/block_evidence.py`、`evidence.py`：原RND-501 v1与原runtime ownership/内容认证；新证明不得重定义targets或bookmark首名。
- `preview/page_mapping.py`：纯派生模型、确定性低置信算法、固定预算和内层reader。
- `document_jobs/execution.py`、`preview.py`：原主件登记及预览manifest接线；原CAS/权限/质量规则不变。

## 必须保持

稳定ID贯穿固定IR，按真实正文target顺序推断；P=1才能证明正文page0，P>1全部low；稀疏来源用rank，S≤1用输出序，平局低页，range始终null。source provenance不因目标推断提升。 持久化record的代表字段须与已认证text policy及TOC target owner一致；混合列表允许最后归并项的代表，无归并策略则应为空。非空native_text的disposition须与实际自有target一致（有则rendered，无则coalesced），空策略沿原规则。禁止把未经对账的record字段作为导航归属，错误可选trace只降级映射。suppressed/header/footer无实际location，完整trace无正文仍保留entries。

通用锚只信同次成功创建证明，不能凭命名空间、模板同名、旧record.bookmark_name或JSON metadata猜成功。证明在receipt前随主件metadata固定，不回填选定文件。marker必须在最终save/freeze/报告之前写入，并从真实对象引用重算所有locator；图片必须保留各cell/run归属。

映射和证明最多8MiB/100000entry，超限整体降级，不静默截断为完整。可选导航缺/坏不改变原业务状态；原内容/hash/公式图片认证、manifest完整性与存储/权限错误继续原失败规则。完整新私有字段从事件/公开摘要/错误出口显式剔除，只允许固定计数/版本/受控原因。

## 验证与回退

定向入口：tests.test_renderer_block_anchors、tests.test_preview_page_mapping、tests.test_document_job_word_preview、tests.test_document_job_result_persistence、tests.test_document_job_preview_persistence及原renderer公式/图片/布局。实际OOXML和可见内容守恒、模板冲突、错owner/run、坏hash/来源、三恢复入口、重放/迟到/权限/TTL负例不可缺。

回退只能使用保留新marker/证明、不会泄露私有键的B1读者；新写入前需源码指纹及旧/新manifest、带marker主件三恢复入口实证。不能将旧G0/B0天然视为兼容，不得删除历史Artifact或绕过内容门。

生产预览保持disabled，离线fake/OOXML不能代签Word视觉、Golden、真实引擎沙箱、InnoDB/部署FS-S3。当前任务验证记录须明确这些未验边界。
