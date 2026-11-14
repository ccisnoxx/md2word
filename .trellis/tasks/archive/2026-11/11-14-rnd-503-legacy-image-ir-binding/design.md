# 旧图片报告 IR 绑定设计

## 兼容条件

把兼容限定在 `verify_image_report()` 已有的历史 IR 身份分支。优先沿用 `legacy_document_ir_payload()` 的现行哈希。失配时，依据 `DocumentIRMetadata.model_fields_set`，从同一历史投影中只省略四个未声明且值仍为各自默认值的字段，计算一个兼容哈希。显式字段及实质内容参与身份绑定；没有可省略字段时沿用原失配结果。只在同一报告的 `source_ir_sha256` 与这一投影精确匹配时继续执行后续认证。

共享历史投影、`document_ir_hash()` 及 v1 plan／trace 校验保持原语义，避免改变已有持久化计划身份。当前报告生成和 v2 内容认证沿用原路径。历史分支仍需通过冻结输入哈希、源计划、图像和题注、实际 DOCX 等后续检查。原 IR、报告和 DOCX 均保留原字节。

## 样本与对照

原件来自 [RND-503 归档清单](../../2026-10/10-23-rnd-503-image-group-caption-rendering/artifact-hashes.json)。

| 样本 | 仓库下原件路径前缀 | 报告中的生成策略与模式 |
| --- | --- | --- |
| `actual-B1` | `tests/tmp/rnd503/b1/b1-generated` | `single-only/v1`，`single_sequence` |
| `large-indent-table` | `tests/tmp/rnd503/post-review/large-indent-table` | `grouped/v1`，`group` |

每组读取 `.docx`、`.ir.json` 和 `.reports.json`，以归档文件哈希验证来源，再以真实原件执行完整图片认证。样本在本机忽略目录，原件验收应明确报告缺失或指纹不符，不能用重生成样本代替。篡改用例只操作内存或临时副本。正常分组样本的原始预览 PDF／页图可作参考，缺对应登记与成功 manifest 时不算历史恢复证据。

v1 plan／trace 用独立的已知有效夹具回归。若本地无已冻结的成对证据，使用现有 v1 plan／trace 构建组件做最小受控夹具，将基线预期从本次修复前的身份语义固定下来。复用现行持久化认证入口比较匹配和失配结果；两套 RND-503 图片原件只携带公式和图片报告，v1 夹具单列为兼容对照。
