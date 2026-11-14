# 交付与验证记录

交付提交为 `c588c46a`。本地 `main` 已包含 GitHub 上的合并提交 `c2e93202`，其文件树与交付提交一致。[PR #67](https://github.com/ccisnoxx/md2word/pull/67)

复用 PR 记录的实施阶段结果。`.venv/bin/python -m unittest tests.test_image_group_rendering.LegacyImageIRBindingTests` 共 5 个用例通过，0 跳过，耗时 0.217 秒。

- **AC1 旧报告认证。** `actual-B1` 单图和 `large-indent-table` 正常分组均通过历史图片报告认证。两组共 6 个原始 DOCX、IR 和报告文件的 SHA-256 与归档一致，原件字节在用例前后保持一致。
- **AC2 篡改拒绝。** IR 实质变更、报告源 IR 绑定失配和 DOCX 图片对象篡改均被拒绝。四个显式默认字段以及变为非默认值的隐式字段继续参与绑定。既有历史哈希及当前持久化内容对照通过。
- **AC3 v1 渲染证据。** 受控夹具中的 `render-plan/v1` 与 `block-render-evidence/v1` 匹配组合通过。IR 身份或 trace 的计划绑定失配时，证据认证拒绝。

完整历史恢复仍缺原始登记及成功预览样本，B1 回退仍待验证，生产回退演练另行验收。本次收尾未重跑测试。
