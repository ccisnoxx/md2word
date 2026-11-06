# 设计

在 build_job_read_view → _build_job_read_observation → _build_publish_action 显式传递是否核验发布证据的布尔参数，默认 True。仅 list_jobs 页内调用显式设 False；不从 observed_result 推断。原有状态检查与 reasons 顺序保持，仅包住 prepare_publication_evidence 和后续元数据回查的现有分支。保留 not_checked 对象和消息，不增加响应字段。

前端没有列表 publish/publication_evidence 消费，不修改。异常中心在筛选分页前遍历所有可见任务并调用默认完整读视图，另行处理。源码调查未发现列表其余动作读取正文：clone/new_generation 为元数据检查，完整源 PDF 读取在新代命令中。

同步列表查询 Spec 的发布部分，其他深度动作文字保持；用户已授权替换原冲突条款。回退仅撤销本任务局部差异，不改持久化数据。

沿用现有 publish.enabled 驱动 delivery_status=ready_to_publish 的返回投影；坏证据时列表可能与详情不同，不改持久化状态。测试断言该伴随行为及无写入。

## 第二轮设计：先分类分页，再构建完整动作

原异常列表对全部可见任务先 build_job_read_view 再筛选；分类、建议、搜索和统计依赖 retry action、有效复核、降级页、时间及任务元数据，不依赖 publish/clone/new_generation 等完整动作。筛选前保留 canonical 有效复核与原 retry owner，避免复制业务条件；需要时使用最小共享方法承接这些真实复用。注意 _effective_job 与 _build_result_read_view 的主件门控并非可随意互换，需保持原观察语义。

内部分类投影与完整响应动作分开，筛选、排序及全过滤集合汇总照旧；仅分页后当前页调用 build_job_read_view(check_publication_evidence=False)。保留原 job 记录与分类观察，不能用公开 schema 反向恢复丢失内部字段的记录。详情/前检查/发布 POST 默认完整核验；diagnostics、bulk 等其他异常调用默认保持，除非原分类 helper 重用需要最小拆分。

共享 owner、参数和分类结构采用最小实现，不新增缓存、持久状态、SQL下推或通用框架。前端 IncidentTriagePage 使用 retryable 等现有字段，没有 publish/publication_evidence 依赖，不计划修改。

第二轮最终观察边界：`build_incident_classification_view` 复用原 `_build_result_read_view(job)`（按实际分类时刻判断到期）与共享 `_build_retry_action`，返回完整内部任务记录、retry 和 download。页内通过可选 `observed_result_view=(job, download)` 复用本请求已校验观察，避免换件/到期后条目与统计不一致，也避免为未完成但保留 result 指针的任务新增文件读取。该内部参数默认 None，不改变其他调用方原校验；发布仍仅使用第一轮的 `check_publication_evidence` 开关。

异常中心原请求 now 仅拥有停滞时间及分类文字投影；不得将主件到期观察冻结到更早的请求起始时刻。分类前已经到期应按旧规则失效，分类后的页内构建则复用已得到的观察，不再次判断到期。
