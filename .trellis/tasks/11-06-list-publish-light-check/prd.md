# 任务列表发布资格轻量判断

用户已批准任务创建、实施及覆盖列表查询 Spec 的发布实时认证条款。
仅 GET /api/v1/document-jobs 的 publish 动作改为状态准入；publication_evidence 保持 not_checked。接受列表可点而提交被拒。详情、发布前检查、POST 和其他调用方完整核验，schema、其他动作及非管理员行为保持。

## 验收

- AC-1：管理员待发布任务列表 prepare_publication_evidence 与 read_file_content 零调用。
- AC-2：列表 publish enabled/disabled_reason 只取现有状态条件；证据检查 not_checked。
- AC-3：详情、发布前检查证据异常仍禁用 publish，保留 reason_code。
- AC-4：列表可点而发布 POST 因证据异常拒绝，错误码保持。
- AC-5：其他动作及非管理员结果保持。
- AC-6：仅调查异常中心逐行深度核验，禁止修改。

## 边界

仅 service.py 读视图/发布动作、定向测试、直接相关 Spec/API 文档及本任务文档。前端、incidents.py、manifest 不改；不提交、推送、发布、访问生产/真实 Provider/MinerU，不运行完整测试或发布门禁。不得修改 worktree 外文件，不运行 archive/add_session。

## 第二轮：异常中心（用户已授权直接实施）

扩展范围为 incidents.py、必要的 service.py 最小调整、异常中心相关 Spec/API 文档及定向测试。原先“异常中心不改”仅为第一轮边界；本轮明确授权优化 GET /api/v1/document-job-incidents。复用既有显式参数，不改变详情、发布前检查、POST；不改 schema、分类、筛选、排序、分页、total、统计、其他动作或非管理员语义。前端只有确有字段依赖才修改。

- AC-7：管理员异常列表 prepare_publication_evidence/read_file_content 零调用。
- AC-8：完整动作读视图仅当前页构建；筛选所需纯状态/元数据计算保持，给出多任务前后计数。
- AC-9：冻结改前逻辑作对照，分类/筛选/排序/分页/total/全部统计一致。
- AC-10：异常列表 publish 状态准入、not_checked，其他动作保持。
- AC-11：重跑第一轮定向测试保护 AC-1～AC-5。

本轮仍禁止提交、推送、发布、仓库外写入、生产/真实 Provider/MinerU、完整回归和发布门禁。原历史失败需在基线复现并保留，不扩展维护。
