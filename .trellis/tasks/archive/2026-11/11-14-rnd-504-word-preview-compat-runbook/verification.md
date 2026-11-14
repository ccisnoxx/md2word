# 交付与验证记录

- [PR #61](https://github.com/ccisnoxx/md2word/pull/61) 已合入 `main`。交付提交 `a7beacb0`，合并提交 `c763d224`。交付包含[运行说明](../../../../../docs/runbooks/backend.md#23-word-预览配置与恢复)和[兼容回归](../../../../../tests/test_word_preview_compatibility.py)。
- AC1–AC3 复用实施阶段结果。`.venv/bin/python -m unittest tests.test_word_preview_compatibility` 共 3 个用例通过，耗时 3.213 秒。file 和 SQLite 各只产生一个预览领取者。页图登记失败保留主 DOCX 和原凭据，未确认 PDF 不出现在文件列表，下载返回 409。manifest 或必需页图最早到期时，签名参数及响应期限均受约束。S3 使用测试替身。
- AC4 已核对运行说明与当前实现的配置、任务快照、沙箱前提、存储故障处置及下载期限。B1 回退仍待验证。收尾未重跑测试、未执行 B1 演练或部署。
