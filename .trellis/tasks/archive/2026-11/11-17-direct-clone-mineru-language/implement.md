# 实施与验证

1. 在快照构建器统一解析和冻结语言，移除新建提交入口的重复决策与克隆分支的单独解析。
2. 在克隆提交入口加入保留快照时的文种冲突检查，保留已有权限、文种、资源和调试字段校验。
3. 在 `tests/test_document_job_modes.py` 复用现有 TestClient、快照和 MinerU HTTP 线协议夹具覆盖 PRD 矩阵。同一请求先断言持久化快照，再改变设置并执行 Worker。
4. 执行 `.venv/bin/python -m unittest tests.test_document_job_modes`，检查 `git diff --check`，复核相关改动与任务合同。必要时对直接受影响的 clone 既有 API 用例做定向复核。记录真实执行命令和结果。
5. 更新 DocumentJob 模式合同与验证记录。提交和推送不在任务授权内。

本地测试覆盖正式应用入口和真实请求序列化，外部 HTTP 使用替身。若需要撤回候选，只撤回本任务的变更，已有任务和快照可继续读取。
