# RND-504 实施交付摘要

本次复用历史931d2f6，逐hunk接入当前01e6c1a基线，保留CON-104/TR-406/RND-502/503与共享生成件file_id身份。独立工作树 `/Users/sc/.codex/worktrees/rnd504-current-integration/md2word`、分支 `codex/rnd504-current-integration`；原根保留业务与暂存内容。批准修订4三件套hash未改，当前授权见implementation-authorization.md。

## 行为与范围

- bytes/PreviewPolicy端口、tests-only fake、固定word-preview-exec/v1生产adapter；输入输出/宏/路径/资源/超时/进程组/清理校验。生产默认disabled、required=false，不安装/选择实际引擎。
- receipt物化及当前公式/图片原件认证后、completed CAS前接预览；PDF/pages/manifest独立不可变Artifact，metadata-first pending→对象→file锁确认，全部生成件继续共享file_id键。
- 同job锁下私有ledger、固定deadline/attempt/lease、登记前CAS与当前attempt确认；未知登记不能耗尽变完成，预登记耗尽只原预算内失败留证。单独预览retry受owner/Admin与tenant/company约束，不改DOCX/generation或调用MinerU/AI/renderer。
- 新key仅完整有效观测才alias，明确生命周期失效可有界新run；旧key仅历史、available独立。旧终态缺阶段可凭完整观测确认，旧在途缺阶段失败关闭。列表一次观测按完整Record过滤，单件/Token独立重验，S3按完整必需证据最短TTL。
- 质量只撤自身blocker，保守保留其他/未知/并发结论，公式fallback warning先合成；不复活批准/ready、不启用发布。可靠预览失败主DOCX可内部下载；存储未知安全固定错误但仍原oss_failed失败。

范围外保持：页映射、页级检查/QualityRun、前端/在线Word编辑、公开preview/retry/publish API、SaaS采购、第二套流水线、额外任务。direct零翻译资源、唯一主DOCX、MinerU唯一解析和原生表格规则保持。

## 实际路径与接口影响

当前候选38个业务/测试/Spec/docs路径的精确SHA见research/candidate-files.json（不含任务/manifest bookkeeping）：24个app、6个tests、8个Spec/docs。源37路径之外仅新增触及tests/test_document_job_delivery_state_api.py的必要legacy fixture隔离；旧断言完整保留，新默认/成功预览另有组合回归。

新增/更新内部接口为WordPreviewProvider.render、PreviewPolicy/Result/Failure、DocumentJobPreviewService、PreviewArtifactObservation、PreviewRetryResult.available、claim/begin-registration/finish窄仓储方法、verified_current_preview_files和preview_download_ttl。三种adapter同锁同规则；无DDL/SQL新列/迁移/回填、DocumentIR/前端或公开OpenAPI schema变化（release current）。新增私有可选JSON及文件/事件类型；旧结果与普通pending保持原合同。

## 验证与评审

详细命令/日志/AC及基线失败对照见implementation-validation.md；独立实际diff主审与delta复审见implementation-review.md。当前完整应用35项通过，未变Provider/持久化结果复用，总63项覆盖；post-review release203项全通过；113项既有合同回归仍6次明确HEAD基线失败，未隐藏或计通过。component1/1、direct5/5且P0=0，P1/P2提示与视觉签字仍待后续门禁。无配置lint/typecheck，N/A。

## 风险与回滚

真实引擎/validator/字体/批准隔离、真实MySQL/部署FS/S3、线上Golden和Microsoft Word人工视觉未验；adapter合同与production_ready区分，生产保持disabled。无跨job/files/object原子事务或S3即时撤销承诺，迟到对象物理回收沿既有retention限制。

若回滚，先停新预览/不兼容写者并关闭backend，保留能读写preview/checks/receipt的兼容代码、全部Artifact/metadata/审计；不清blocker、不恢复批准、不覆盖发布件、不回退丢字段/覆盖键writer。当前是未提交工作树，没有执行部署回滚或破坏性迁移。

本轮只进入review等待人工验收。未stage/commit/push/archive/add_session，不启动其他任务。新增和实质改动的注释/docstring/开发者消息按中文规则处理；协议/字段/错误码保持机器值。
