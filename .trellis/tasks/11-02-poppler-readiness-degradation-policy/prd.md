# Poppler 就绪检查与降级策略配置化

## 目标

Poppler 已是图片回退和整页降级的必需依赖，生产环境缺失时要尽早暴露；单页文档、降级比例和渲染重试上限改为配置。来自 2026-11-02 重新审查的修复优先级第 4 项。

## 需求

1. 生产环境 Worker 缺 `pdfinfo` 或 `pdftoppm` 时启动失败；开发环境只告警。
2. `/health/ready` 在生产环境把 `pdf_crop_tools_missing` 列为阻断项，开发环境仍为告警。
3. 新增配置：`PAGE_DEGRADATION_MAX_RATIO`（默认 0.5）、`PAGE_DEGRADATION_ALLOW_SINGLE_PAGE`（默认 false）、`RENDER_DEGRADATION_MAX_ATTEMPTS`（默认 5）。

## 验收标准

- [x] 默认配置下降级行为与之前相同。
- [x] 比例上限同时作用于验证阶段和渲染阶段。
- [x] 开启单页开关后，单页文档在两个阶段都能降级；关闭时按原错误失败。
- [x] 重试上限来自配置，非法配置值启动时被拒绝。
- [x] 生产 Worker 缺工具时入口抛错且不启动 Celery；开发环境可启动。
- [x] 就绪检查在生产环境阻断、开发环境告警。

## 范围外

按绝对页数限制、翻译任务渲染降级、部署后的真实回退冒烟。`.env.example` 被权限规则禁止读取，示例行交由用户补充。
