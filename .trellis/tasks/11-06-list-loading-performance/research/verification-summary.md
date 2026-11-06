# 本地交付与验证摘要

普通列表候选已在隔离 worktree 整合，未 commit/push/生产部署。root 产品树未变，其他候选来源逐文件身份未变。

- 本轮组合候选：99 个离线不同用例最终通过；MySQL 模块 12 项通过，其中 4 项入口/离线 guard、8 项真实 8.4.13 引擎用例，总计111个不同用例。首轮旧布局断言失败已修复并定向重跑，未隐去失败。
- 完整结果对照12次一致；组合默认合成页三次中位数0.103204s、无匹配0.087858s。继承旧/ready同输入构造三次中位6.856/6.444s，分轮测量不能描述为随机交替实验，也不代表线上API/浏览器。
- 独立只读 trellis-check 实际diff复核未发现确认产品缺陷；唯一迁移设计坏链接由主会话修复并复核。覆盖V域/五列缺失、权限和binary、writer旁路、事务和回退。复核未额外跑测试/lint/typecheck。
- 实际线上只读测量与补测均未改变产品或业务数据；异常分类92次连接中建连约1.78s，补充方案已批准并完成本地实现，37项直接验证和冻结差分通过。
- 临时测试库、容器、专属卷、VM/profile/context和两份凭据已清理。原三个profile仍Stopped、默认Dockercontext仍default；安全证据保留，见mysql-environment.md。
- 未运行全仓/前端构建/发布门禁；无前端改动；异常读取会话已完成定向验证。生产8.4.9、迁移、真实界面3秒验收均未完成，任务保持in_progress。

Python新增/修改的必要注释、docstring、CLI帮助和开发者文案使用中文，迁移和错误合同Spec已同步。

最终 `task.py validate` 的 implement/check 两清单各5条全部通过；`git diff --check` 通过，最终路径仅为明确候选/直接测试/Spec/任务。未 stage、commit、push、archive 或 add_session。

原始忽略证据保存在本任务独立工作树 `/Users/sc/PycharmProjects/md2word-wt/list-loading-performance` 的 research/data，root仅同步脱敏文档和轻量测量记录，不复制凭据或大体积冻结副本。

## 异常补充方案最终结果

35项直接离线回归+2项真实MySQL用例通过；真实RR两连接验证新观察及错误事务边界。8对完整正常响应、4对错误响应与冻结旧路径一致。完整合成调用中位0.542135→0.116432秒；分类92次get/保护查询和逐次commit不变，连接92→1；完整请求保留页内动作读取，连接107→16、commit107次。无人工延迟，不含HTTP/认证/浏览器。

独立只读review未发现产品缺陷；主会话核对当前七模块SHA与实际基准记录完全一致。普通列表共享SQL身份未变。run2资产和新凭据已清理，原三个profile仍Stopped、默认context仍default。基准最初遗漏页内clone读取的计数错误已据实记录，只修研究脚本；未重复成功tests。Task上下文两清单各6条验证通过。
