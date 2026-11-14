# RND-504 Word 预览兼容回归与运行说明设计

## 定向回归

| 验收项 | 当前入口与拟用夹具 | 历史参考 |
| --- | --- | --- |
| AC1 | 通过 file 和 SQLite 的 `claim_document_job_preview` 真实仓储锁竞争。复用 `tests/test_document_job_result_persistence.py` 的适配器、结果凭据及进程同步做法，在同一个临时仓储上启动两个进程并重读持久结果。 | `27e9b1a:tests/test_document_job_preview_persistence.py:316` |
| AC2 | 复用 `tests/document_job_list_query_v2_publication_fixtures.py` 的临时本地运行夹具和页图输出。让 PDF 通过真实登记后注入页图登记失败。用文件记录确认部分写入，再从任务列表和下载授权核对其不可见性。初次预览从 `app/domains/document_jobs/render_result.py:97` 进入，登记顺序见 `preview.py:202`。 | `27e9b1a:tests/test_document_job_word_preview.py:409` |
| AC3 | 复用同一运行夹具，走 `app/domains/document_jobs/use_cases/downloads.py:74` 的授权入口，保留真实预览证据认证，仅替换 S3 对象读取和签名客户端。两种最短期限分别设在 manifest 和必需页图，核对签名 TTL 和返回的 `expires_at`。完整证据期限的截断点见 `preview_evidence.py:414`。 | `27e9b1a:tests/test_document_job_word_preview.py:784` |

三个场景共同落在 `tests/test_word_preview_compatibility.py`。现有历史重放用例继续承担其原覆盖。

## 运行说明

在 `docs/runbooks/backend.md` 增补 Word 预览小节。以 `app/core/config.py:76`、`app/services/preview/sandbox_adapter.py:38` 和任务快照构造为准，说明默认关闭且可选、页图默认关闭，启用时需核对 launcher、profile、哈希和沙箱能力。运行诊断以当前 run、attempt 与已选 DOCX 凭据为依据，区分明确的过期或缺失与未知存储错误。说明未确认的产物保持不可下载、历史请求与新请求的处理差别，以及已签发 S3 URL 的有效期边界。

通过现有[页映射合同](../../../docs/contracts/pdf-ir-word-page-mapping-contract.md#b1-回退待验证)引用 B1 待验证条件。file、SQLite 和 S3 替身仅用于验证本任务的离线行为，真实沙箱、对象存储、InnoDB 和 B1 恢复资格仍需相应环境证据。
