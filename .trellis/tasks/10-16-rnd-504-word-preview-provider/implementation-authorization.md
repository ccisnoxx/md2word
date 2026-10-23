# RND-504 修订4实施授权与范围

2026-10-23，用户明确接受修订4三件套及独立复核结论，授权按规划开始实施，复用历史实现并保留当前合同。保护现有dirty与暂存区，生产预览保持disabled；完成验证后停review，不提交、不push、不归档、不启动其他任务。

本轮授权取代三件套中的“仅规划/未授权”阶段性说明；冻结的需求/设计/验收正文保持原字节。实际实施使用独立工作树 `/Users/sc/.codex/worktrees/rnd504-current-integration/md2word`，分支 `codex/rnd504-current-integration`，基线 `01e6c1add86f1ba7f24abc120629fa2fe6bd5ed9`。不覆盖历史 md2word/RND-504 分支，不复制根目录其他dirty或.env。

最小差距是将历史931d2f6预览port/adapter/Artifact/幂等链增量接入当前owner，补修订4的登记中断确认与失效预览有界恢复。业务所有权为app及必要tests；主会话拥有本任务文档、manifest和相关Spec/runbook。保留CON-104、TR-406、RND-502/503和共享独立file_id键；不实施页映射、页级检查、Review/Publication API、前端或新依赖/部署。没有授权任何提交、push、归档或生产启用。

依赖CON-103在根权威manifest仍done，Git归档completed与人工接受证据保持；当前功能合同已存在，非宣称原bd828da提交成为祖先。三个批准文档SHA-256如下：

- prd.md: `b8e6756a61aacb863c96af9694ada504c9cc4f596cbdcda6bcff223a6187b62e`
- design.md: `7b5c184a725f0861594450c4ab3682e4ab275be18bb68eea353929b524cf9d40`
- implement.md: `a718d7b828e3904c936e9c17da91ff235cdad6c04455742105135009278b41c0`
