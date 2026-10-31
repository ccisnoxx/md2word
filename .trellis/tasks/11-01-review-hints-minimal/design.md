# 技术设计

## 数据流与 owner

既有 CaptionReconciler -> 已持久化 IR 主源块 caption_reconciliation -> review_content._block 的授权只读投影 -> 现有 DocumentReviewBlocksResponse -> documentJobsApi.listReviewBlocks -> format 纯展示 -> JobDetailPage。

不修改 producer、renderer metadata、router、schema 或仓储。投影只读已选来源，不新增兼容选件或降级；沿用 _load/read.finish、source、content_snapshot 与 cursor 的现有权威边界。

## 受控提示

主源块 caption_reconciliation 的 uncertain 映射 caption_binding_uncertain/warning；rebound 映射 caption_reassociated/info。后者表示既有规则已整理，不冒充仍有歧义或修改正式审核。忽略 source_block_id 派生块，不复制 originals、自由 reasons、source_locator 或任意 message。普通、未知状态不制造新风险码。既有 table/块 flags 保留并按 (code, severity, table_id) 完整身份去重。

## 页面接线

前端只新增 GET listReviewBlocks 和所需 DTO，使用 problem=flagged 及有界 limit/cursor。复用页现有请求轮次/销毁保护；新读取再绑定任务、retry_count、source_document_ir_file_id、document_ir_file_id、result_file_id；分页 source 与 snapshot 必须一致，冲突清理旧结果并给刷新入口，不静默拼接不同快照。

format 负责固定码中文建议和 source_spans 的0-based到1-based展示；未知源页显示未知，多span去重，不能从 preview_page_index 猜源页。数量明确是提示位置/已加载数量，未读全时不宣称全量复核完成；未知码仅安全保留机器码，不显示私有 metadata。

成功任务存在 warning 时显示完成但需复核；仅 info 不升级警告。任何提示都不推导 quality/review/delivery/publish。文案避免无条件声称可下载；按钮、发布资格、签发分类和警告沿用原 server action helper。

## 兼容与失败

无新增 public 字段、仅复用现有块 flags。旧 IR 无题注事实时照旧读取。availability/error 与源变化保留语义，缺失证据不表示通过；不从 files.metadata/review_issues 补造列表。冻结历史渲染和 source selector 完全不改。

## 独立回归

后端用真实题注 producer/IR和只读块投影，隔离外部依赖；断言三态、源页、派生块与不变性，不启动 app/runtime/DB/renderer。前端用真实 API wrapper、formatter、Vue computed 与既有 executePageRequests/deferred 支持，验证实行为和并发反例，不导入旧测试文件或整套 smoke。可在新增模块内导入 SFC 触发正常编译，但不运行独立 build/typecheck。

## 静态复核收敛：源 IR 安装交错

独立只读复核确认 AC3 的具体遗漏：后端详情已公开 source_document_ir_file_id，且同代最终 IR 尚空时可正常安装源 IR；首版前端类型与绑定未消费该字段。旧读取在服务器 finish 后延迟，新详情先安装源 IR 时，旧 not_ready 响应与 finally 仍可能写回。仅在原前端类型、页面绑定/快照检查与新模块补齐，不改后端字段或 producer。前端检查 source_ir/final_ir 时遵守现有 direct 与翻译快照语义；不新增来源fallback。

源IR遗漏已在原授权类型/页面/新回归内修复；首次前端执行即39/39通过，独立增量复核无剩余确定缺陷。前端按_load原有direct/翻译语义核对source_ir/final_ir/basis，并区分缺字段与显式null。此修正不改变产品范围或后端协议。

## 本次本地提交边界

本轮只将已经实现并复核的14个授权路径保存为一笔本地提交。源码、两个回归和Spec保留已审阅字节，仅任务记录补充当前授权说明。不运行应用检查、不推送/合并/删分支，不自动归档或追加记账提交。
