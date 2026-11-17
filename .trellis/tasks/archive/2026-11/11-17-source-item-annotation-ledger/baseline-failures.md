# 既有降级回归失败

实施阶段在独立临时工作树的干净 `57772613` 上，用同一本地 Python 环境复现以下两项。临时工作树已移除。本记录复用当时结果。

| 用例 | 干净基线结果 |
| --- | --- |
| `tests.test_page_degradation.PageDegradationPipelineTests.test_degraded_job_succeeds_as_blocked_internal_draft` | 查找 `pdf_page_raster` 文件时触发 `StopIteration`。 |
| `tests.test_render_page_degradation.RenderPageDegradationPipelineTests.test_table_plan_failure_is_degraded_by_located_page` | 测试替身 `failing_build` 接收两个位置参数，当前表格构建入口传入三个，抛出 `TypeError`。 |

原验证命令在干净基线的工作树中执行。下文用变量表示实施仓库中使用的同一 Python 解释器。

```bash
# 从实施仓库根目录取得解释器路径，再切换到干净基线的工作树。
ledger_repo_python="$(pwd)/.venv/bin/python"
env -u PYTHONPATH "$ledger_repo_python" -m unittest \
  tests.test_page_degradation.PageDegradationPipelineTests.test_degraded_job_succeeds_as_blocked_internal_draft \
  tests.test_render_page_degradation.RenderPageDegradationPipelineTests.test_table_plan_failure_is_degraded_by_located_page
```

两项仍无通过证据，留待独立排查。来源账本的实际通过结果与验证范围见[验收记录](validation.md)。
