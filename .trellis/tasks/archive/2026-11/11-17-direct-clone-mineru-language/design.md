# 设计

在 `DocumentJobSubmission.clone_job` 完成既有授权、源文件和策略检查后，取请求文种或源任务文种。保留快照时先比较有效文种并抛应用层 `conflict`，沿用标准错误壳和嵌套原因码。校验在模板和资源快照解析、任务和事件写入、投递之前。

在 `DocumentJobRequestSnapshots.build_request_snapshot` 统一解析新建和克隆的 MinerU 语言。保留源快照时传入源任务，继承有效的已绑定值并归一历史别名；缺字段时沿用原有模式和配置回退。其他策略及新建任务使用模式解析器：翻译模式的方向优先，direct 显式文种覆盖默认配置，`auto` 读当前配置。通用资源服务继续构建其它 MinerU 字段，DocumentJob 快照构建器写入最终的语言。

版本化快照以 `resources.mineru.language` 为准，旧版快照写顶层 `mineru_language`。沿用已有快照字段和 Worker 读取逻辑，源任务、历史重试、资源版本准入和部署配置无需迁移。
