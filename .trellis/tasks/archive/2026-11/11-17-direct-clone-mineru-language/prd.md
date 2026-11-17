# 修正 direct 克隆的 MinerU 语言绑定

## 目标

克隆后，任务文种和 MinerU 请求语言应符合所选配置策略。新任务在创建时冻结请求语言，使排队后的配置变化不影响解析。

## 现状

通过本地 FastAPI 入口在版本化和旧版快照上复现：源任务绑定 `latin`，以 `keep_source_snapshot` 或 `use_current_defaults` 克隆并指定 `zh`，均返回 201，新任务文种为 `zh`，MinerU 语言仍为 `latin`。

## 要求

- R1. `keep_source_snapshot` 保留源任务文种及 MinerU 绑定。省略文种即沿用源任务。指定不同文种时拒绝克隆，返回 HTTP 409、`error_code=conflict`、`error.reason_code=clone_document_language_conflicts_with_snapshot`。
- R2. `use_current_defaults` 和 `select_published_versions` 可修改文种。direct 的 `zh/en/ru` 分别绑定 `ch/en/east_slavic`，`auto` 绑定克隆创建时的 `MINERU_LANGUAGE`。显式版本选择及其权限沿用现有合同。
- R3. 翻译模式绑定模式源语言：`en2zh → en`、`ru2zh → east_slavic`、`zh2en/zh2ru → ch`。已有文种准入规则及继承优先级继续有效。
- R4. 沿用两种快照字段与历史别名兼容。缺少绑定的历史任务按既有模式和配置回退；若克隆其快照，在新任务中冻结回退结果。

## 验收

- AC1（R1）：两种快照均验证显式同文种成功并继承、不同文种返回约定 409。拒绝时无任务创建、审计或投递副作用。
- AC2（R2、R4）：两种快照均验证重选配置后的文种及冻结语言，涵盖 `zh/en/ru/auto`。版本化路径验证显式 published 版本。修改运行配置后，捕获 Worker 实际序列化的 MinerU 请求，确认语言与新任务冻结值一致。
- AC3（R3）：四种翻译分别验证新建和克隆的快照绑定及 Worker 请求，覆盖翻译文种的 `auto` 与源语言选择。
- AC4（R4）：相关的历史别名、缺字段回退与术语重绑回归通过。

## 范围

产品代码限 DocumentJob 请求快照构建和克隆请求校验。定向验证使用本地现有测试夹具；保持 Worker、前端、存储 schema 和运行配置装配。交付本地改动与验证记录，不提交、不推送。
