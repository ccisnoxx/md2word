# TR-406 实施授权与工作区保护

日期：2026-10-22。用户已接受 revision 2 规划并明确授权开始实施：先整合已验收 CON-102，再按执行计划推进和验证，保留现有未提交改动，完成后停验收，不提交或 push。

- revision 2 独立架构复审见 planning-rereview.md，原两项 P2 在规划层闭合；旧稿“待复审/未授权”描述属于历史发稿状态，本记录取代该状态说明，不改变技术设计或 AC1–13。
- 初始 HEAD：596a2de7ed29edb7fdb378d91c17bda09b7f1066；原分支 md2word/TR-403，新实施分支 codex/tr-406-partial-batch-failure-semantics，切换保留未提交改动，不产生提交。
- 初始 1428 个 tracked/untracked 路径哈希、原工作树/暂存差异和未提交文件副本保存在系统临时目录 /var/folders/m5/j06tv2sn1hn93d6f33j559jm0000gn/T/md2word-tr406-fv84psqk。父任务六个既存删除保持。
- 为遵守 Trellis“in_progress 后才改业务代码”的执行门，先激活这个已接受子任务，再将依赖基线整合作为第一项执行工作；不另建任务或推进其他任务状态。
- 变更边界：复用 CON-102 阶段、原子 retry、receipt 与 TR-403 编码/验证/evidence/唯一文件身份；在既有 workflow/仓储/执行 owner 收口完整根计划、attempt/lease、终态失败与重放；API/UI additive 投影并保护旧代响应；新增对应定向回归和更新相关文档/Spec。
- 不实施 TR-404/405/407，不新增数据库字段/依赖/队列系统，不扩大下载发布或 debug 权限，不进行真实 Provider/生产部署/VPS 操作。
- 最终状态为实现待人工验收；不运行 commit、push、archive 或 add_session。

## CON-103/104 依赖基线追加授权

2026-10-22，用户在明确得知当前 checkout 缺少 CON-103/104，且整合将带入 CON-103 原有 schema bootstrap 后，答复：“同意整合 CON-103/104 已验收基线，再完成全部验收”。因此追加范围仅为复用这两项已验收实现及原有 bootstrap/兼容/测试，不授权 TR-406 新设计 DDL、连接生产或部署。共享文件实现已暂停，在完成该基线整合后恢复。

- CON-103：已验收提交 bd828da4e3a3025856afd758e0b0a686ff6ccb72、80b82dbc0bf388c97b4f5b8d8e6654625cad9186，原实施基线 75d0a07c481aa3f79feb8dc5f18c17065c922f1b。
- CON-104：已验收业务提交 48c9402f6ed7ece4871c3ec3ca28a6a6f20920a6。
- 追加整合前候选快照：/var/folders/m5/j06tv2sn1hn93d6f33j559jm0000gn/T/md2word-tr406-before-con103104-ip_armw9。
