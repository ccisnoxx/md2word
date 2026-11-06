# 定向验证记录

执行位置为本 worktree 根目录。所有 Python 调用设置 `PYTHONDONTWRITEBYTECODE=1`；临时夹具在任务目录内创建并于验证结束清理，不访问真实服务。

## seed 模块基线与最终结果

```bash
PYTHONDONTWRITEBYTECODE=1 TMPDIR=/Users/sc/PycharmProjects/md2word-wt/template-seed-path-check/.trellis/tasks/11-06-template-seed-path-check/implement-tmp /Users/sc/PycharmProjects/md2word/.venv/bin/python -m unittest tests.test_template_seed_history -v
```

基线 14/14 通过（0.398 秒）；修复后 18/18 通过（1.279 秒），退出码均为 0。新增拒绝矩阵覆盖 hash、template_id、version、draft、snapshot_hash、其他模板/版本、相似目录前缀、父目录逃逸、符号链接逃逸及无效路径字段；正向覆盖相对/绝对/规范化路径和关闭状态保留。

## 原代码复现

```bash
PYTHONDONTWRITEBYTECODE=1 TMPDIR=/Users/sc/PycharmProjects/md2word-wt/template-seed-path-check/.trellis/tasks/11-06-template-seed-path-check/implement-tmp /Users/sc/PycharmProjects/md2word/.venv/bin/python -m unittest tests.test_template_seed_history.TemplateSeedHistoryTests.test_published_seed_accepts_managed_relative_path_without_writes tests.test_template_seed_history.TemplateSeedHistoryTests.test_build_runtime_accepts_published_managed_seed -v
```

原实现运行 2 项均为预期错误（0.908 秒，退出码 1），均抛 `ValueError: 模板 seed 版本与已登记资源冲突: default@2`；启动用例从真实 `app/main.py:325` 进入 bootstrap。修复后两项已包含在 18/18 成功结果中。

## 已有默认指针回归

```bash
TMPDIR="$PWD/.trellis/tasks/11-06-template-seed-path-check/check-tmp" PYTHONDONTWRITEBYTECODE=1 /Users/sc/PycharmProjects/md2word/.venv/bin/python -m unittest tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_bundled_v2_bootstrap_preserves_existing_v1_default tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_bundled_v2_bootstrap_sets_v2_default_in_empty_mysql_repository -v
```

基线 2/2 通过（0.274 秒）；修复后 2/2 通过（0.302 秒），退出码均为 0。使用既有 fake MySQL，未连接数据库服务。仅有既有 Starlette/httpx 与 HTTP 状态常量弃用警告。

## 静态与证据边界

`git diff --check` 通过；原 14 个测试方法及断言 AST 保持不变。AC-1 至 AC-4 均有本地定向测试证据；真实生产部署、MySQL、Provider、MinerU、全仓测试与发布门禁按授权不执行，不据本地结果推断线上验收。

独立 `trellis-check` 只读复核未发现可行动缺陷，确认路径边界、原校验及默认逻辑保留、启动测试隔离，以及与 11-01 PRD/Spec 不存在明确矛盾。复核未重复应用测试。任务实施与验证完成，按用户要求保持未提交、不归档；两个任务临时目录已清理。
