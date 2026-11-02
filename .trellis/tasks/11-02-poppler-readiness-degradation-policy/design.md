# 设计

## Poppler 检查

- `worker_ready` 信号不可用：Celery 的 `Signal.send` 会捕获接收方异常，Worker 照常运行。因此检查放在 `run_document_worker.main()`，在 `worker_main` 之前。
- `pdf_crop.poppler_tools_available()` 是工具判断的唯一实现，就绪检查和 Worker 入口共用。
- 生产判断收敛为 `Settings.production_like`，替换 `main.py`、`health_service.py` 的两份相同表达式，避免第三份副本。
- 就绪阻断项放入 `_build_p0_document_jobs_readiness`，同时使 `p0_document_jobs_ready` 为 false。

## 降级策略

`page_degradation.PageDegradationPolicy` 拥有数量判断。`build_runtime` 由配置构造并注入 converter；Worker 从 `document_ir_service.degradation_policy` 读取，与 `page_rasterizer` 同一来源，两阶段不会口径不一致。

- 单页文档只看开关：降级一页就是 100%，比例上限对它没有意义。
- 多页文档：降级页数不超过 `页数 × 比例`。默认 0.5 与原 `count * 2 > pages` 等价。
- `RENDER_DEGRADATION_MAX_ATTEMPTS` 取代代码常量；0 表示关闭渲染阶段降级，上限 20，避免耗尽 Worker 时限。
