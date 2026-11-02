# 设计

## 不新增操作类型

审查报告建议新增 `degraded_page` RenderOperation。现有 `section`（`new_page`）加普通 `block` 操作已能表达独占一页，新类型还要同步改写入器、证据校验和白名单，没有额外收益。

## 独占标记

`replace_degraded_pages` 在提示和图像块写入 `metadata.exclusive_page`，在图像块写入 `metadata.notice_reserve_emu`。存档校验会按规则重新计算图片尺寸，不能让规则追溯作用于旧 DOCX，因此：

- 带 `exclusive_page` 的页才独占；预留高度随 IR 持久化，常量以后调整也不影响已生成结果。
- 旧 IR 没有这两个字段，计划与尺寸保持不变。

## 计划

`_build_render_plan_v1`：独占页及其下一页都开新页分节，并跳过语义分页，避免重复分页；提示 `keep_with_next`。未知页占位不再以独占页为锚点，避免混入降级页。

## 尺寸

`image_evidence.image_available_height` 是写入和校验共用的唯一计算点：有效高度减去预留。预留 3 cm，容纳两到三行提示和 `add_section` 产生的分节段落。

## 已知限制

- 模板页眉页脚仍显示，可能与图像里的原页眉页脚重复。取消它要处理节间继承和证据里的归属，留待有需求时再做。
- 页面尺寸沿用模板纸张，图像按正文区等比缩放，不铺满整页。
- 没有 `layout.json` 时页面方向可能未知，按纵向处理。
