# RND-503 实施前核对与实际边界

2026-10-23，用户已接受 v2 三件套及独立复核，并明确授权实施。执行前已输出十二项 preflight；此文件固定执行事实，覆盖规划文档开头的历史“仅规划”状态说明，不改变已批准验收合同。

1. **状态与依赖**：RND-503 原为 planning；IR-204=done，接受来源及集成硬门详 `dependency-integration.md`。无另一个冲突的 in_progress 任务。165 项原基线及 174 项集成门通过后，执行准确子任务的 `task.py start`，manifest 仅 RND-503 变为 in_progress。
2. **实际分支**：`md2word/RND-503`，基于原分支 RND-502 的 HEAD `1835263621a2a18627a5730e7fd62b6bc7cae8c2` 创建，未提交。已接受依赖通过有边界的工作树集成就绪，不声称依赖提交成为 HEAD 祖先。
3. **原有改动保护**：实施前索引含 302 项暂存删除；另有 journal、backlog、CON-104 prompt、manifest、未跟踪父任务等改动。原状态、索引 binary patch、相关 tracked hashes 保存于本轮系统临时快照，禁止 bulk stage、stash、覆盖或清理。原改动不纳入本任务提交计划。
4. **当前到目标**：旧制表位图片行及单注限制尚不满足目标；实现严格 bbox 决策、无边框固定布局表格、inline 等比图、逐图全部注释及独立 OOXML/evidence 对账。普通正文栏、原生数据表及公式 owner 保留。
5. **范围**：仅 RND-503 和使其真实可运行的已接受依赖集成。重绘、OCR、图片内文字翻译、新预览、页映射、视觉算法、全量 RenderPlan 和后续任务不实现。
6. **内部文件拆分**：实际实现允许增加 `app/services/renderer/image_evidence.py`，内聚冻结输入、报告与重验；分组仍归 layout_plan，避免 writer/evidence 复制规则。允许 `TemplateConfigPackage.load_content(bytes)` 最小入口：path loader 单次读取后共享原归一化/校验，确保被解析配置与记录 hash 同源，避免第二次路径读取的 TOCTOU。这两项由主会话核实现有接口后接受，不引入新 service、策略、配置产品或通用快照框架；验收与失败语义不变。
7. **公开合同**：不改 OpenAPI、DB schema、迁移、角色/权限、任务状态机或前端；新增报告/冻结格式输入是现有授权文件 metadata 内部字段，不扩展 API 响应。配置 schema 和 seed 保持。
8. **结果与并发**：沿现有 candidate descriptor、first-valid receipt、CAS/retry_count/generation；不在锁内做渲染/I/O，不新增跨仓储事务。三恢复入口必须绑定原文件 IR/模板和冻结输入，新件损坏拒绝，旧无报告件不补写。B1 保留 reader，只切生成侧为固定构建身份 single-only/v1，无运行时 feature flag。
9. **前端**：无路由、query key、URL 状态、generated types 或第二套业务状态机变化。发布与下载资格仍由后端决定。
10. **安全与外部边界**：现有 MinerU 唯一解析、路径和资产门禁保留；direct 零 Provider/翻译资源调用。冻结数据只存必需规范化规则、hash 和几何，不记录任意 YAML/Settings、路径、Prompt、翻译术语或凭据；普通事件只投影有界摘要。使用已授权去标识及中性合成样本，不主动部署/SSH/发送专有样本。
11. **验证**：定向 unit → component → direct matrix → check_release/Golden 精确命令 → task validate；OOXML/实际预览/Word 分别记账。候选稳定后运行，失败先诊断。完整 AC 映射、实际命令和结果在最终 validation 记录；未执行不写通过。
12. **风险与回滚**：主要风险是错误归组/注释串图、伪造布局表放宽内容表计数、当前配置污染历史恢复。实施和独立复核检查这些路径。停止条件沿 prd；B0 仅开发撤销点，已有新件后必须使用保留新 reader 的 B1，保留全部历史件/审计/receipt，不覆盖发布件。

收口目标为 manifest=review、Trellis=in_progress，等待人工验收与 commit plan 授权；不 done、不 archive、不提交、不 push。
