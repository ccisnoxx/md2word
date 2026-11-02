# 设计

## 口径

- `source_page_count = len(document.pages) + 过滤页数`。`document.pages` 已排除宣传页过滤，过滤页由 `final_promotional_page_filtered:` 质量标记识别。
- `converted_page_count = len(document.pages) - 降级页数`，包含无内容的空白页。
- `page_count_basis`：任一页带 `page_size_source` 为 `mineru_layout`；否则 `content_blocks`，此时无内容的页可能未计入，只能当下限。
- 不引入 `pdfinfo` 取页数：Poppler 不是所有部署的必需项，失败时还会多一个外部依赖；现有依据已能如实标明可信度。

## 归属

- `integrity.build_page_counts` 是唯一计算点，`build_source_integrity` 写入 `page_counts`。
- `base_quality.SourcePageCounts` 受控校验后写入贡献，与 `degraded_pages` 同样缺失时不序列化。
- 渲染失败：`word_renderer` 把总页数和依据挂进 `failure_context`，经白名单进入事件。
- 验证失败：取报告 `inventory.raw_page_count`，依据固定为 `content_blocks`；为 0 视为未知。

## 被否决的方案

审查报告建议的 `failed_source_page_count` 和 `not_reached_source_page_count` 不做：当前只要一页不能降级就整份失败，交付结果中这两项恒为 0，失败任务里又无法可靠得知。
