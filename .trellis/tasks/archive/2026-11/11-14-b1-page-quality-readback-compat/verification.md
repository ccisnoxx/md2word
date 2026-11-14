# 交付与验证记录

[PR #65](https://github.com/ccisnoxx/md2word/pull/65) 已合入 `main`。交付提交为 `68046e87`，合并提交为 `48699a10`。

复用实施阶段定向结果。`.venv/bin/python -m unittest tests.test_b1_preview_rollback.B1PreviewRollbackTests.test_main_authenticates_b1_page_quality_readback` 通过，耗时 10.562 秒。file 和 SQLite 各覆盖 15 个场景，共 30 个。归档前核对交付提交与当前 `main` 上的两个相关文件一致。

- **AC1。** 正常读者认证 B1 原报告，页级质量读取返回 `available`，保留报告的 `incomplete/pending` 和映射的 `legacy_evidence_missing`。读回前后的登记及对象哈希一致。
- **AC2。** 正常基线报告与导航继续可读。普通缺证、坏停写声明、坏锚点证明、plan／trace 或报告上下文失配按原规则降级。B1 页级报告可读时，发布路径仍取不到要求有效锚点的计划。
- **AC3。** 外层 manifest 或原始 IR 损坏、必需内容证据缺失仍被拒绝。报告上下文负例重算报告及外层哈希后仍因绑定失配而不可用。

RND-503 旧 IR 绑定暂缓，完整历史恢复仍缺样本。B1 回退仍待验证，生产回退演练另行验收。收尾未重跑测试、未部署。
