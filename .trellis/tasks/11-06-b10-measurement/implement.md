# 执行与验证

1. 已读取 AGENTS.md、RTK、Trellis 启动/开发/检查规则，及 backend 的目录、错误、数据库、列表 v2、质量指南。基线 `828e1d9d656bf266cba7bba0ed23a62c550db15c`，工作区干净。
2. 本目录承载规划、执行与结果状态。用户禁止目录外写入，因此不初始化 Trellis developer、不写 current-task 指针、不 archive、不 add_session。
3. Trellis implement 子代理仅负责本目录内 `measure.py` 及其直接生成的 JSON/CSV；主会话负责规划、静态分析、报告。所有子代理中文汇报，保留其他人的改动。
4. 实现后先以 120 档检验计数、只读与数据断言；再运行完整三档测量。根目录运行，解释器 `/Users/sc/PycharmProjects/md2word/.venv/bin/python`，始终 `PYTHONDONTWRITEBYTECODE=1`。
5. 主会话/检查代理检查采样与计数口径、输入输出一致性、数据比例、结果表及预算；只复跑修订直接影响的测量。不运行应用测试、前端测试、完整回归或发布门禁。
6. 将实际命令、结果、成本行号、MySQL 边界和未验证项写入报告，执行 `git diff --check` 与 `git status --short --untracked-files=all`，确认仅本任务目录新增。

## 完成条件

原始结果覆盖 4 路径 × 3 档；AC-1 至 AC-4 均有明确证据。观察到超预算不属于测量失败，不进行优化。任务结果不表示 Claude 已验收。

## 执行结果

2026-11-06：三档四路径正式测量和独立证据核对完成，报告见 report.md，完整命令/失败与纠正记录见 verification.md。未修改应用、Spec、依赖或任务清单；未提交、推送或归档。
