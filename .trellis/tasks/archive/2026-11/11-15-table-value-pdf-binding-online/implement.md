# 实施与验收计划

基线为 `claude/parameter-column-binding-check-cb3979` 的 `73d2929f`。本文件是规划，最新方案获确认后进入实现。

实施和复核前按需读取 Word 生成规则的 PIPE-001、INPUT-001/002、IR-002、TABLE-001 和质量认证章节。完整规范超出自动注入单文件上限，应从源码工作树按规则定位。[Word 生成规则](../../../../spec/backend/word-generation-rules.md)

## 实施顺序

1. 在正式 Worker 构建 IR 的入口接入默认关闭的配置，测量可选原件读取成本。核对显式 raw 指针、归属与实物摘要。通过现有来源 loader 和第三阶段服务出具候选、自动修正或逐格未决。区分普通证据不足、既有必需裁图错误和正式输入损坏。复用页缓存，落实文档级预算。
2. 基于现有最终 IR、Word、独立表报告和当前选中凭据构建有效结果。在 `quality/tables` 投影有界逐格定位，保持现有访问和快照范围。对本阶段实际应用修正的结果，在批准入口使用原表报告认证守卫；验证发布的原拒绝和正向路径。补齐移除降级表组时的 IR 引用处理。
3. 接入 Admin 新代的显式同包核定类型。复用原子接纳、幂等、审计与投递，冻结同源结果包和累计人工记录。在其新代从 `parsed` 初始化执行时限并调用同一 converter 和 renderer。在私有账本关联同包重放意图、失败续跑与代次防护，并验证不可变与其他阻断。
4. 按验收矩阵做本地定向验证与独立复核。确认设置、生成 OpenAPI（如所提 API 字段实施）、可读性和交付规范更新。实施完成后记录实际证据及待生产启用验证。

## 验证矩阵

| 需求 | 后续实际验证 |
| --- | --- |
| A1 完整 MIN/TYP/MAX | 通过正式上传、MinerU 归档登记、执行器、质量检查、登记及重新下载。使用清单核对同源完整 `gs-008`，只替换 MinerU 网络调用等环境边界。实际 Poppler 和 Word 核对目标、源格、相邻值、释放列和单位，比较全部 finding ID。 |
| A2 普通划线 LOW/HIGH | 复用 `tests.test_table_value_pdf_binding_poppler` 的独立实际 PDF 与跨列 HTML。断言两个自动落位与一处贴边未决。对全部证实的输入给真实质量贡献走批准、确认预览、发布正例；保留 fresh base，逐值确认 Word 和报告绑定。 |
| A3 失败隔离 | 同名同字异源、缺原件/布局、读结果校验错误、异任务、图形或文字歧义、工具缺失、预算耗尽、Word 故意错位、独立表报告删除或篡改。分别区分内部草稿的业务 blocker、正式输入失败和 Word 未认证不可登记。 |
| A4 人工及代次 | 现有权限及 CAS 的本地真实仓储定向测试。验证合法累积核定、幂等、旧期望源、换包或任一格失效、并发接纳/审批/发布、同包新代超时及重投、迟到结果。审核新 Word 后仅解除对应 finding。覆盖 file/SQLite 原子提交，MySQL 隔离验收单独记账。 |
| A5 兼容与边界 | 关闭功能、历史任务/已发布产物、同代恢复、明确旧解析包、必需与可选 PDF 失败、降级新 IR 的关联及内部下载。依赖失败不签发可交付文件，其他类型 blocker 仍有效。 |

现有定向回归入口包括 `tests.test_table_value_column_span_delivery`、`tests.test_table_value_pdf_binding_poppler`、`tests.test_table_value_pdf_binding_integration`、`tests.test_table_value_pdf_binding_delivery`、`tests.test_document_job_execution_stages`、`tests.test_document_job_result_persistence`。为实际新增的线上分支增加必要用例。使用现有本地测试运行器及临时存储，区分 Poppler 实跑、fake 上游传输及真实线上未验范围。

## 启用前交接

在默认关闭的候选上确认兼容读取和回滚方式。生产开启前独立验证实际 Worker 镜像四工具、同次实际上传 PDF 和 MinerU 回包配对、观察预算以及相关仓储并发合同。部署或生产开启属于单独授权。
