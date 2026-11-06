# 设计

复用 app/services/tables/grid_builder.py 的现有 CanonicalTableGrid 视图，按源行/单元格序号关联原 BeautifulSoup DOM；不修改表格 owner，不用网格 ID 替代 .html.NNNN。原 extraction/apply 与 eq 索引规则保留，context 不成为翻译目标。上下文只含目标表头与同行参数，不复制全文；eq 后代不作为上下文文本发送。缺失表头使用空路径，不猜测语义标题。

使用冻结只读 context DTO，与 TranslationTextItem(id,text) 及输出 DTO 分离；TranslationProviderRequest 追加可选关联，Provider 仅在有 context 时为相应输入 item 序列化 context。开启时追加只读说明，关闭时 system/user prompt 原字符串不变。

技术字段经现有 encode 处理；上下文编码用包含正文 namespace 的保留输入占用 namespace，确保 context Token 与正文 ledger 不重合。不得修改 Codec 规则或 Validator 输出语义；上下文 Token 回写会作为未知 Token 被拒绝。上下文不计入原文/输出完整性 evidence，现有 source/encoded/restored hash 继续绑定原 item 集合。

字符预算定义为原编码 text 字符数加独立 context JSON 值字符数（ensure_ascii=False、indent=2，含字段/坐标），复用 max_chars/item/page 分批；不是整个 Prompt 的 tokenizer 或网络字节上限。上下文每项最多 1024 字符，另受单项正文编码后的剩余空间约束；优先表头再同行参数，整段省略并标记 truncated，不截断 Token；短项更有剩余预算。最小结构也超限则在调用前用现有 translation_request_budget_exceeded 失败；计划和实际请求使用同一构建/计数逻辑。原 batch char_count 仍表示原文。

现有网格构建器不接受 caption 等格外文字；只在临时网格输入投影中移除 td/th 以外的文字，保留所有结构标签。原 DOM/抽取/回填不变，这类非单元格 item 不附 context。显式行标题不能充作后续行的列标题；表头路径使用共享网格的表头行或明确列标题语义，不从任意上方 th 猜测。

上下文纯文字投影保留 br/hr 和明确块级标签的换行，普通内联文本连续，避免把 `5 V<br>Typical` 拼成 `5 VTypical` 或拆开 `OPA<b>228</b>`。scope 枚举按 HTML 大小写不敏感语义读取。eq 子树整体排除，原 DOM 不改写。

Settings 增加 translation_table_context_enabled=False，显式注入 DocumentIRTranslationService，direct 流程不变。开关是进程配置，切换须保持执行端一致并排空在途翻译，不新增持久化快照机制。回退关闭开关；语义改善未验证，禁止默认开启。

不实现额外 section/group 推断、跨页网格迁移或术语 QA；不改 manifest。若现有网格不能对应某类 HTML，须明确失败而非猜测关联或静默丢弃上下文。
