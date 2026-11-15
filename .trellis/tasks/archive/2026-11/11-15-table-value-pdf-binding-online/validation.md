# 第四阶段本地验收

现有分支 `claude/parameter-column-binding-check-cb3979`。使用真实 Poppler 26.06.0、正式 HTTP 上传、Worker 转换和渲染、同代结果登记与实物重读。测试替代 MinerU 外部传输和预览 Provider，实际上传字节、原包、IR、Word、认证与审批发布均经过产品代码及本地仓储。发布测试使用完整的测试资源版本与经过本地预览流程确认的产物。

## 完整 gs-008

取完整缓存目录中的同源原件、v2、layout 及全部保留文件，打包给正式 Worker，原件和 v2 字节匹配基线清单。使用 `tests.test_online_table_value_pdf_binding` 的 `worker_case` 上传原件并登记归档，未传人工记录。根据实际报告中的表索引及源行映射读取 Word，重验独立报告、持久化 IR 和实际 DOCX。

| 源数据行 | MIN | TYP | MAX | UNIT |
| --- | --- | --- | --- | --- |
| 2 | 空 | ±5 | ±75 | μV |
| 3 | 空 | 空 | ±100 | μV |

两个目标及释放格均占单列，单位保持纵向合并。完整源报告的 23 个原 finding 全部保留。其中 9 个经 Word 实物认证解除，14 个 `row_ambiguous` 仍阻断，与公开质量接口中未决 ID 一致。

同一完整包改用同名、同文本、不同指纹的仓库 P7 PDF，自动修正为 0。原 Word 跨度保留，23 个 blocker 均以 `source_pair_unverified` 列为未决。两种输入都能获授权下载内部草稿，正式审批与发布分别返回 409 `review_quality_blocked`、`publication_quality_blocked`。[基线清单](../../../../../tests/fixtures/datasheet_quality/local_baseline_manifest.json)

## 独立 LOW/HIGH 划线表

真实 PDF 表格经同一 Worker 路径认证，`7.2e-4 s` 只归 HIGH，`43 ms` 只归 LOW。另一个 `48 ms` 的字框压列界时仍占两列，原 blocker 与源格定位均可读，审批发布均为 409。

人工核定正例用同一种划线版式。最后一个值明确位于 HIGH，但其独立条件有两行，自动证据仍报 `row_ambiguous`。从当前原 Grid 构造人工批次，分别在 file 和 SQLite 仓储执行。非管理员和过期源指纹先被拒绝，合法请求返回 202。同一 UUID 重放返回 200，改批次则返回 409。新代继续使用同一 raw ZIP，MinerU 上传与下载次数未增加，旧 Word 字节保持可读，执行期限得到初始化。SQLite 用例在接纳后关闭设置，新代仍按冻结的记录完成。

重读新 Word 时 `48 ms` 只在 HIGH，LOW 释放为空。实际报告仍有原始三项发现，三项修正均由实物认证，原阻断减至 0，基础质量完整。审批返回 200，发布返回 201。布局候选提示仍留在报告中，基础质量仅核销已经实物认证的表片段所对应的提示。[可复现实物回归](../../../../../tests/test_online_table_value_pdf_binding.py)

## 定向回归和证据边界

- 最终聚合 37 项通过。覆盖两种仓储的同包重生成与请求冲突、文件失效、实际摘要/跨归属拒绝、取证预算、降级引用、累计人工项、实际 Word 错列、审批前缺失或损坏报告、已认证未决的对账、默认路径和 OpenAPI 契约。另使用 fake MySQL 验证新代接纳 SQL 的依赖文件锁范围和顺序。
- 库存抽查有两项旧 FastAPI Worker 用例失败，干净基线 `73d2929f` 可同样复现。一个仍断言本地模板为 `default@1`，当前基线为 `default@2`。另一个错误路径替身只提供 `render_to_bytes`，缺少基线实际调用的 `render_to_result`。相关历史断言保留。
- 审批以当前 job、主件和 receipt 做既有 CAS，报告及 IR 描述在提交前重核，未持有审批事务的依赖文件锁。重核与审批提交之间仍有并发状态变化窗口。发布另行重验并在提交时核对和锁定依赖文件。
- 本地实际 Word 的落位和质量门禁已验。生产 Worker 镜像、真 MinerU 回包的原件配对、真实 MySQL 锁行为和生产发布留作启用前验收。
