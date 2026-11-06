# 设计：保留真实表格片段定位，贯通既有失败诊断

## 数据流与职责

来源片段 → prepare_placeholders 捕获 TablePlaceholderError 并附定位 → converter 保留原验证报告 → worker_failure_evidence 按白名单生成 stage_failed.payload.failure_context → project_failure_diagnostic → 详情/异常 API → 共享前端摘要。

继续使用现有异常、stage_failed 和 failure_context，不建立第二套存储或错误分类。表格转换层不导入 Word renderer 来获取辅助函数。

## 异常上下文

1. 将 `word_renderer.py` 已有的 `FAILURE_CONTEXT_ATTRIBUTE` 与 `attach_failure_context` 原样移至依赖中立的 `app/services/failure_context.py`；现有导入使用方切到共同 owner，renderer 保留导入名称以兼容既有测试/调用。该函数仍仅在异常没有内层上下文时附加，不覆盖更精确位置，不增加包装异常。
2. `prepare_placeholders` 在实际片段处理边界捕获且只捕获 `TablePlaceholderError`，附 `operation_kind=table_placeholder`、`block_ids` 和 `source_page_index=fragment.source_span.page_index` 后原样抛出。依赖现有可信账本，不从错误字符串、列表顺序或 owner 首页猜页。
3. 全局数量/累计资源预算和源文件整体身份校验失败附文档范围上下文（page=None）。必须在逐片段补定位之前标记此范围，防止外层把全局错误绑定到当前片段。没有已确认的源页时也保持 None。
4. 页数复用 `integrity.build_page_counts`，只携带 `source_page_count` 和 `page_count_basis`；不复制计数公式，不报告已成功转换页数。为避免无关依赖，不搬动该函数。缺页数证据允许为空。
5. `TablePlaceholderError` 的 code、固定安全消息和异常类型不变。底层 crop provider 的坐标检查、失败关闭和图片完整性规则不变。图片回退/整页降级捕获 TablePlaceholderError 后转为原验证失败的路径保持现状。

## 事件边界与安全

`_failure_policy.worker_failure_evidence` 继续同时保留原 mineru_validation 和真实 failure_context；已经存在的 reason_code 注入和事件脱敏路径继续拥有公开证据。

仅向 `evidence.FAILURE_OPERATION_KINDS` 增加固定 `table_placeholder`，四个原因码原本已在白名单中。不放宽任意字符串、ID、整数、页数依据等规则，不加入 HTML、bbox、文件路径、异常正文或新的日志输出。

## 诊断选择与公开合同

- 保持仅消费当前 retry_count 的既有 stage_failed 选择规则。
- 存在有效 MinerU 致命报告时，仍保留现有 MinerU 诊断结果。
- 报告不存在或不足以产生诊断（包括 can_convert=true、缺少有效 first_fatal）时，尝试同一事件的已脱敏操作失败上下文；两者均不可用才返回 null。
- 将现有 `_project_render_failure` 调整为操作失败投影：`operation_kind=table_placeholder` 时 source=`table_placeholder`，既有渲染操作仍为 `render_operation`。该来源标识避免把转换阶段错误标成渲染错误。
- 本次唯一新的公开枚举值为 `DocumentJobFailureDiagnosticResponse.source=table_placeholder`；不新增字段或端点。页索引只在投影中 +1。实际已知失败片段为 affected_page_numbers 的单页，fatal_count=1；未知页为 scope=document、page_number=null、affected_page_numbers=[]。
- `block_ids`、`operation_kind` 的说明从仅渲染扩展为失败操作；同步前端联合类型及 `docs/api/openapi.json`。`json_pointer` 无证据时保持 null，不另建未经约束的路径字段。

## 展示

复用已有四个原因码的中文映射：表格占位区域无效、裁切失败、来源不可用、完整性校验失败。概览显示原因和源页；诊断/异常抽屉对 `table_placeholder` 和 `render_operation` 都显示块与操作。旧 null 诊断回退保持原样，不解析 error_message 推断结构化位置。

## 兼容与发布边界

- JSON 事件 payload 增加既有键中的新受控操作值，无 DDL、迁移或回填；老事件仍可读取。
- 新前端可读取旧 API；旧前端对新来源仍能显示原因与页码，但可能不显示块/操作技术细节，因此正式发布应同步 API/Worker 和前端合同。
- 回退到本次修改前的版本会失去新上下文的展示，但任务状态、文件与原错误消息仍按旧合同读取。不改持久化状态机，不对历史记录做不可逆修补。
- 当前线上 3 条缺页记录没有实际失败位置证据；非致命 empty_table_html 告警页不等同于几何失败页，不用于补写。

## 关键风险及控制

- 跨页逻辑表格 owner 位于首页：用源片段 span 定位，独立回归后续片段失败。
- 验证报告掩盖操作失败：定向复现通过报告与失败上下文并存。
- 新增定位影响降级：转换占位只补元数据，保持渲染 operation_kind 和降级策略不变，并运行直接相关回归。
- shared helper 搬移引入循环依赖：新模块只依赖标准类型，不引用 IR/renderer；复用既有函数，不抽取通用框架。
