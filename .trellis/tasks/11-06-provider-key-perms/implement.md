# 执行与检查

1. 读取三件套、backend 的 directory-structure/error-handling/quality-guidelines/runtime-configuration 及 guides/index。
2. 运行既有基线：FastAPIJobsBackendTests.test_ai_provider_config_api_updates_runtime_config_and_masks_secret 和 test_health_ready_reports_invalid_ai_provider_config_file。
3. 最小修改写入及权限 owner；加入创建权限、chmod/创建/确认失败、清理、旧记录保全、残留/符号链接回归。复用既有 API 错误语义，必要时新增定向 API 错误测试。
4. 运行新增 unittest 模块和受影响既有方法，禁止 discover / 全仓检查。Python 固定 ${PROJECT_ROOT}/.venv/bin/python，PYTHONDONTWRITEBYTECODE=1；测试使用自动清理的临时文件，不留下工作区临时目录。
5. 独立只读检查权限窗口、错误传播、原子替换、清理和范围；复用输入未变的成功结果。
6. 主会话核对 diff/status、记录实际结果，不 commit/push/archive/add_session。Trellis 未初始化 developer，本任务以显式路径传入代理，不初始化仓库外或范围外元数据。

## AC-3 返工

用户已授权按唯一随机临时名方案直接修改。保留 AC-1/AC-2 的创建瞬间权限与失败保全断言；调整 AC-3 为历史普通文件/符号链接残留不阻塞保存且原样保留，清理断言须检查实际随机临时文件。重新运行 tests.test_provider_config 与上述两个现有 FastAPI 方法，替换验证记录中的旧结论。
