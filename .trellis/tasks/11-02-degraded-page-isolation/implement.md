# 实施清单

1. `page_degradation.py`：写入 `notice_reserve_emu`。
2. `image_evidence.py`、`image_renderer.py`：共用可用高度。
3. `render_plan.py`、`layout_plan.py`：独占分节、keep-with-next、占位锚点。
4. `tests/test_render_page_degradation.py`：结构回归与校验回归。
5. Spec：`word-generation-rules.md`。
6. 实测：LibreOffice 转 PDF，核对页数与每页内容。
