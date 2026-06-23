from __future__ import annotations

# tests/test_page_flow_characterization.py: Characterize conservative page-budget planning for local MinerU runtime.

import unittest

from app.conversion.runtime import page_flow_runtime
from app.conversion.runtime_models import Block, ParagraphStyleConfig, RenderConfig, SectionLayout


EMU_PER_PT = 12700


def pt(value: float) -> int:
    return int(value * EMU_PER_PT)


class PageFlowCharacterizationTests(unittest.TestCase):
    def make_render_config(self, *, body_height_pt: float = 120.0) -> RenderConfig:
        return RenderConfig(
            section_layout=SectionLayout(
                top_margin=0,
                bottom_margin=0,
                left_margin=0,
                right_margin=0,
                header_distance=0,
                footer_distance=0,
                page_width=pt(500.0),
                page_height=pt(body_height_pt),
            ),
            use_mineru_header_footer=False,
            terminology=None,
            paragraph_styles={
                "Normal": ParagraphStyleConfig(font_size=10.0, line_spacing=1.0, space_before=0, space_after=0),
                "Caption": ParagraphStyleConfig(font_size=9.0, line_spacing=1.0, space_before=4, space_after=4),
                "TableContent": ParagraphStyleConfig(font_size=9.0, line_spacing=1.0, space_before=0, space_after=0),
            },
        )

    def test_plan_page_breaks_before_unit_when_anchor_would_be_orphaned(self):
        first = page_flow_runtime.FlowUnit(blocks=[object()], height_pt=80.0, anchor_height_pt=10.0)
        second = page_flow_runtime.FlowUnit(blocks=[object()], height_pt=30.0, anchor_height_pt=25.0)

        plan = page_flow_runtime.plan_page_breaks([first, second], page_body_height=100.0)

        self.assertTrue(plan.should_break_before_block(second.first_block))

    def test_table_anchor_includes_caption_and_visible_rows(self):
        render_config = self.make_render_config()
        table_model = page_flow_runtime.parse_html_table(
            "<table><tr><th>PARAMETER</th><th>VALUE</th></tr><tr><td>Input voltage</td><td>5 V</td></tr></table>"
        )
        self.assertIsNotNone(table_model)
        block_without_caption = Block(type="table", bbox=(0, 0, 100, 100), html="<table></table>", captions=[])
        block_with_caption = Block(type="table", bbox=(0, 0, 100, 100), html="<table></table>", captions=["Device Information"])

        without_caption = page_flow_runtime.estimate_table_anchor_height_pt(
            block_without_caption,
            table_model,
            render_config,
            usable_width=pt(450.0),
        )
        with_caption = page_flow_runtime.estimate_table_anchor_height_pt(
            block_with_caption,
            table_model,
            render_config,
            usable_width=pt(450.0),
        )

        self.assertGreater(with_caption, without_caption)


if __name__ == "__main__":
    unittest.main()
