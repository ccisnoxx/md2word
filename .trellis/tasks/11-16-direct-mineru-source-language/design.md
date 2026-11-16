# 设计

`DocumentJobSubmission.create_job` 负责新建任务的原文语言选择。只在 direct 且文种明确时，复用 `normalize_mineru_language()` 得到请求语言，并通过现有 `mineru_language` 参数传给请求快照构建器。`auto` 和翻译模式沿用当前模式解析器及配置。

`DocumentJobRequestSnapshots.build_request_snapshot` 将显式传入的语言写到 `resources.mineru.language`。兼容快照沿用现有的顶层 `mineru_language` 写入逻辑。继承快照的克隆通过同一个写入点保存原解析语言，术语重绑和 Worker 继续依据历史绑定执行。保留现有字段位置、公开 schema、配置和解析阶段。

回归在 FastAPI 创建入口覆盖两种快照及 Worker 的请求序列化。真实样本使用隔离任务存储，复用正式 MinerU 客户端和 DOCX 生成链路。保留未编辑产物和 WPS 修改副本。
