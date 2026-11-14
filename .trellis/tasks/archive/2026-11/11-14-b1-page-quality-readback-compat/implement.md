# 实施与验证计划

1. 用户确认后启动任务。按后端规范索引定向阅读 [Word 生成规则](../../../../spec/backend/word-generation-rules.md)中的证据条款，核对 `read_page_quality()`、`mapping_source()` 的调用点与归档候选声明，保持普通调用默认严格。
2. 在预览证据模块加入页级质量专用的停写兼容条件。沿用原身份与完整性检查，复用同次 plan／trace 认证和报告绑定比较。无需变更 API schema、数据库、写入配置或候选配方。
3. 在 `tests/test_b1_preview_rollback.py` 复用归档候选、bundle 和 file／SQLite 夹具，新增 `B1PreviewRollbackTests.test_main_authenticates_b1_page_quality_readback` 定向入口。独立读取进程核验实际加载的待验模块。覆盖 B1 报告原样读回、正常报告对照、普通缺证、坏锚点证明、同次证据或报告绑定失配以及外层损坏。断言映射和持久对象未被改变。
4. 获准实施后，只运行本次定向兼容用例 `.venv/bin/python -m unittest tests.test_b1_preview_rollback.B1PreviewRollbackTests.test_main_authenticates_b1_page_quality_readback`。静态核对受影响调用路径与差异，记录读者、生产者、适配器、结果和验收边界。定向用例不运行此前的三入口历史恢复矩阵。

实现预计涉及 `app/domains/document_jobs/preview_evidence.py` 和 `tests/test_b1_preview_rollback.py`。归档验证数据保留原生产者、读者和当时结果。本次计划结束时保持 `planning`。
