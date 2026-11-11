# 实施与验证

用户已授权写完文档直接实施，任务处于 in_progress；未初始化 Trellis developer，不为本任务修改工作区其他配置或指针。

1. 核对 11-01 PRD/design/implement、模板 Spec、现有校验与回归。
2. 实施子代理仅负责 read_service.py 校验和 tests/test_template_seed_history.py；主会话负责本任务文档和必要 Spec。
3. 修改前运行原 tests.test_template_seed_history；新增正向回归先证明原实现失败，再修复。
4. 运行完整 tests.test_template_seed_history（含新增及 build_runtime 用例），以及 FastAPIJobsBackendTests.test_bundled_v2_bootstrap_preserves_existing_v1_default、test_bundled_v2_bootstrap_sets_v2_default_in_empty_mysql_repository 两个定向方法。历史失败单独记录，不修。
5. Trellis check 静态复核最终 diff、范围、中文注释和原断言保留；成功输入不变不重复测试。

统一使用 ${PROJECT_ROOT}/.venv/bin/python，设置 PYTHONDONTWRITEBYTECODE=1 和 TMPDIR 指向本任务临时目录。禁止 unittest discover、全仓/前端/发布门禁；不访问生产或真实服务。测试完成清理本任务临时目录，不运行 archive/add_session，不提交。

## 实施结果

- 仅修改 bundled seed 已有记录的路径比较；同版受管目录内的同哈希路径可通过，目录本身、越界路径及其余身份/状态/快照冲突仍拒绝；没有新增 helper、回写或默认指针分支。
- 新增 4 个测试方法，原 14 个方法与断言经 AST 对比保持不变。新增中文边界注释并更新测试模块中文 docstring，原冲突异常文案保留。
- 基线完整模块 14/14 通过；新增生产路径与真实 build_runtime 用例在原代码上均以原冲突异常失败；修复后完整模块 18/18 通过。
- 两个 FastAPI 默认指针方法基线 2/2、修复后 2/2 通过；未发现基线失败。实际命令及边界见 verification.md。
