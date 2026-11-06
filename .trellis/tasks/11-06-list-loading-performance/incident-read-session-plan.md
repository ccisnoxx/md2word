# 补充方案：异常列表请求内连接复用

状态：2026-11-07 用户明确批准后，本地实施、定向验证与独立复核已完成。普通列表本地候选与验证已完成，本文件记录异常列表已实施的批准方案；提交、推送及生产变更继续另行确认。

## 实证与目标

线上默认异常接口三个成功样本中位数2.351秒。补充分段测得单次分类68次文件get、24次保护关系查询，共92次连接；建连1.775504秒，SELECT execute约0.073秒，探针额外只读设置约0.104秒，分类总2.488秒。见research/incident-findings.md。这支持针对重复建连，而非删除文件检查或缓存分类。目标继续沿用原AC-2；不能预先把1.78秒全部算作上线净收益。

## 推荐设计与所有权

1. 文件仓储新增请求级 `read_session()`，只向调用方暴露 `get_document_file`、`is_document_file_protected` 两方法的窄reader协议。MySQL后端的会话拥有一个惰性创建、只属于当前请求的物理连接；不使用全局池、ContextVar或进程缓存。
2. MySQL仓储会话创建局部仓储实例，使用专用的 read_connect；仅上述两种读取走它。原SQL、JSON/model/id校验继续只有一个实现；普通仓储和写方法仍走原backend.connect。file/SQLite提供无状态会话，沿用原读取行为。不得通过修改共享仓储或DocumentJobService的字段来临时切换依赖，也不克隆整个service。
3. IncidentService.list_incidents在原参数校验、utc_now和搜索归一化之后打开会话，只覆盖首次有效复核及分类；分类后立即关闭，页内动作沿用observed_result_view。把reader沿list_visible_jobs/_effective_job和classification/_build_result_read_view/_get_completed_result_file/_ensure_file_not_expired传递。使用明确的可选关键词参数，其他调用继续使用原self.file_repository；不加getattr兼容探测，不把诊断、下载或POST迁移到新会话。
4. 普通connect与会话共用同一份事务收尾规则；每次原仓储connect块仍独立成功commit、失败rollback；下一次读取开启新的RR事务，不能把整页固定在同一长快照。物理连接仅在会话结束时close；没有读取时不建连，异常退出必定close，不隐藏失败或自动重连/重试。
5. 保留两阶段有效复核、每次现有时钟观察、缺件/身份/完整模型/到期/保护关系错误、首次降级不再提升，以及页内observed_result_view复用。get的模型/ID校验原在事务退出后，保护JSON解析原在事务内，二者位置不变。

这是连接生命周期合同的变化。它保留业务读取及错误顺序，但不承诺每次新连接/关闭的网络故障机会完全相同：本来就要消除多余建连，不能用“严格逐连接等价”阻止目标本身。已有连接一旦失效则本请求显式失败；不引入成功型兜底。其他产品路径、写锁顺序和持久化布局不变。

## 明确涉及的范围

- files仓储协议及file/SQLite/MySQL实现：新只读会话和窄reader合同。
- MySQL backend：会话持有物理连接、每次读取仍保持原事务边界。
- document_jobs service/incidents：显式传递仅本请求的reader，保留默认调用者。
- 直接回归、相关Spec和本任务记录。无新依赖、数据库列、索引、前端改造、连接池配置或异常SQL下推。

## 最小验证

- 次数与生命周期：68+24类读取保留，物理连接合并；零读取不连接；每个仓储操作独立commit，异常rollback及最终close，不自动重试。
- 错误与时钟：文件JSON/model/id错误、保护JSON错误、naive到期异常、缺件/ApiError、分类前到期、分类后到期、首次复核降级及页内结果一致。冻结改前路径对照，不让新旧期望共用已改的观察逻辑。
- 隔离：同一singleton并发两请求各自持有reader，普通详情/下载/POST保留旧路径；不用共享可变会话状态。
- 真实MySQL两连接验证（明确配置并检查RR，不依赖默认值假设）：第一次读取后外部提交更新，第二次仍看见更新；事务及异常边界符合原合同。使用本任务新建的隔离实例/UUID库，结束清理，不能用生产做实验。
- 相同数据分布的异常完整列表结果/summary/动作对照与本地阶段计时；线上接口/页面目标仅在后续部署另行授权后验证。只跑直接受影响测试，不扩大全仓或发布门禁。

## 已批准的授权边界

用户已批准以上补充范围的本地实施与定向验证；保留现有错误覆盖和逐次观察，不接受以过滤正常任务来绕过元数据错误。无需重新创建任务。该批准不包含commit、push、迁移、发布或生产配置变更。

之所以再次提交审核，是因为原已批准design明确要求：优化若“增加仓储批量合同”或改变观察语义，应先补充设计并重新审核；请求级reader及连接生命周期同属新共享读取合同，超出了原先仅局部调整异常分类的范围。

## 独立架构复核补充

只读架构复核确认可局限于七个产品模块：`app/domains/files/repository.py`、`app/infrastructure/persistence/mysql/backend.py`、`app/infrastructure/persistence/mysql/files.py`、`app/infrastructure/persistence/file/files.py`、`app/infrastructure/persistence/sqlite/files.py`、`app/domains/document_jobs/service.py`、`app/domains/document_jobs/incidents.py`。无需新增数据库迁移；候选不满足快照/错误/隔离合同则撤回session接入，不扩展成连接池兜底。

事务机制参考[MySQL 8.4 一致性读取说明](https://dev.mysql.com/doc/refman/8.4/en/innodb-consistent-read.html)，该文档支持设计依据，实际引擎行为仍以新定向用例验证。架构复核本身只读；后续实施与测试结果见research/incident-session-implementation.md。
