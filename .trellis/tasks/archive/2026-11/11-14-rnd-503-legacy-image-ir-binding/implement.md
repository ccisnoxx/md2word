# 实施与验证计划

1. 规划获确认后启动任务。按后端规范索引定向阅读 [Word 生成规则的 RND-503 章节](../../../../spec/backend/word-generation-rules.md#rnd-503图片布局与原文件输入的可执行合同)。核对两组原件及归档哈希，沿历史持久化内容认证追到 `verify_image_report()`。
2. 在 `app/services/renderer/image_evidence.py` 的历史源 IR 绑定内增加四个字段的受限兼容。继续用现有规范化哈希计算。保持正常写入和共享 v1 plan／trace 计算原样。
3. 在 `tests/test_image_group_rendering.py` 复用已有原件与篡改辅助代码，增加聚焦的兼容测试类。覆盖两套原件、IR／报告绑定／DOCX 篡改、显式默认值保留、现行历史身份及当前内容路径对照，并用现有 v1 组件核对匹配与失配的 plan／trace。通过原件正例或更窄的持久化读回用例，确认历史分支确实启用兼容。
4. 获准实施后只运行本任务定向用例，计划命令为 `.venv/bin/python -m unittest tests.test_image_group_rendering.LegacyImageIRBindingTests`。记录原件可用性、实际执行用例和边界。完整 B1、历史恢复矩阵和生产演练另行验收。

本轮停在 `planning`。计划内只改图片认证和定向回归，归档原件及历史证据保持原样。
