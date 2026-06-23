from __future__ import annotations

# tests/test_page_layout_characterization.py: 固化 MinerU 页面 block 到 DOCX 页面区域的布局行为。

from types import SimpleNamespace
from unittest import mock

try:
    from .runtime_direct_loaders import load_page_layout_module
except ImportError:  # pragma: no cover - compatibility for direct execution
    from runtime_direct_loaders import load_page_layout_module


class FakeHeaderFooter:
    def __init__(self):
        self.is_linked_to_previous = False
        self.paragraphs = [SimpleNamespace(text="")]


class FakeSection:
    def __init__(self):
        self.page_width = 1000
        self.page_height = 1400
        self.left_margin = 0
        self.right_margin = 0
        self.top_margin = 0
        self.bottom_margin = 0
        self.header_distance = 0
        self.footer_distance = 0
        self.header = FakeHeaderFooter()
        self.footer = FakeHeaderFooter()


class FakeDocument:
    def __init__(self):
        self.sections = [FakeSection()]

    def add_section(self, _start):
        section = FakeSection()
        self.sections.append(section)
        return section

    def add_paragraph(self):
        return SimpleNamespace(text="")


class PageLayoutCharacterizationTests(__import__("unittest").TestCase):
    @classmethod
    def setUpClass(cls):
        cls.module = load_page_layout_module()

    def make_block(self, block_type, bbox, **kwargs):
        return self.module.Block(type=block_type, bbox=bbox, **kwargs)

    def make_render_config(self):
        section_layout = SimpleNamespace(
            top_margin=0,
            bottom_margin=0,
            left_margin=0,
            right_margin=0,
            header_distance=0,
            footer_distance=0,
        )
        return self.module.RenderConfig(
            section_layout=section_layout,
            use_mineru_header_footer=False,
            terminology=None,
            paragraph_styles={},
        )

    def test_split_page_blocks_separates_header_footer_page_number_and_body(self):
        blocks = [
            self.make_block("page_header", (0, 0, 10, 10), text="H"),
            self.make_block("page_footer", (0, 10, 10, 20), text="F"),
            self.make_block("page_number", (0, 20, 10, 30), text="1"),
            self.make_block("paragraph", (0, 30, 10, 40), text="Body"),
        ]

        header_blocks, footer_blocks, page_number_blocks, body_blocks = self.module.split_page_blocks(blocks)

        self.assertEqual([block.type for block in header_blocks], ["page_header"])
        self.assertEqual([block.type for block in footer_blocks], ["page_footer"])
        self.assertEqual([block.type for block in page_number_blocks], ["page_number"])
        self.assertEqual([block.type for block in body_blocks], ["paragraph"])

    def test_configure_section_uses_default_word_page_size_not_source_pdf_page_size(self):
        section = FakeSection()
        render_config = self.make_render_config()

        self.module.configure_section(section, (612.0, 792.0), render_config.section_layout)

        self.assertEqual(section.page_width, self.module.A4_WIDTH)
        self.assertEqual(section.page_height, self.module.A4_HEIGHT)
        self.assertEqual(section.orientation, self.module.WD_ORIENTATION.PORTRAIT)

    def test_configure_section_prefers_yaml_page_size_over_source_pdf_page_size(self):
        section = FakeSection()
        layout = SimpleNamespace(
            top_margin=1,
            bottom_margin=2,
            left_margin=3,
            right_margin=4,
            header_distance=5,
            footer_distance=6,
            page_width=self.module.Pt(612.0),
            page_height=self.module.Pt(792.0),
        )

        self.module.configure_section(section, (1000.0, 500.0), layout)

        self.assertEqual(section.page_width, self.module.Pt(612.0))
        self.assertEqual(section.page_height, self.module.Pt(792.0))
        self.assertEqual(section.orientation, self.module.WD_ORIENTATION.PORTRAIT)

    def test_is_toc_page_true_for_explicit_directory_title(self):
        body_blocks = [
            self.make_block("title", (0, 0, 50, 10), text="目录"),
            self.make_block("paragraph", (0, 20, 100, 30), text="1.1 产品概述 1"),
        ]

        self.assertTrue(self.module.is_toc_page(body_blocks))

    def test_is_toc_page_true_for_english_contents_title(self):
        body_blocks = [
            self.make_block("title", (0, 0, 80, 10), text="Contents"),
            self.make_block("paragraph", (0, 20, 100, 30), text="Appendix A Device Pinout 120"),
        ]

        self.assertTrue(self.module.is_toc_page(body_blocks))

    def test_is_toc_continuation_page_true_for_toc_like_list_page(self):
        body_blocks = [
            self.make_block(
                "list",
                (0, 0, 100, 50),
                items=["1.1 产品概述 1", "1.2 产品特点 2", "1.3 产品用途 3", "1.4 对应国外产品情况 4"],
            )
        ]

        self.assertTrue(self.module.is_toc_continuation_page(body_blocks))

    def test_build_regions_detects_two_col_band_then_one_col_region(self):
        left = self.make_block("paragraph", (0, 0, 150, 40), text="L")
        right = self.make_block("paragraph", (200, 0, 350, 40), text="R")
        wide = self.make_block("paragraph", (0, 60, 400, 100), text="W")

        regions = self.module.build_regions([wide, right, left], page_width=400)

        self.assertEqual([region.kind for region in regions], ["two_col", "one_col"])
        self.assertEqual([len(region.blocks) for region in regions], [2, 1])

    def test_build_regions_keeps_separated_source_columns_in_one_two_col_region(self):
        blocks = [
            self.make_block("title", (88, 133, 191, 150), text="1 Features"),
            self.make_block("list", (88, 157, 401, 327), items=["• Low noise"]),
            self.make_block("chart", (94, 463, 478, 661), captions=["Chart Caption"]),
            self.make_block("title", (509, 133, 638, 152), text="3 Description"),
            self.make_block("paragraph", (508, 157, 906, 234), text="First paragraph"),
            self.make_block("paragraph", (508, 407, 906, 500), text="Later paragraph"),
            self.make_block("table", (511, 604, 906, 731), captions=["Device Information"]),
        ]

        regions = self.module.build_regions(blocks, page_width=906)

        self.assertEqual(len(regions), 1)
        self.assertEqual(regions[0].kind, "two_col")
        self.assertEqual(len(regions[0].blocks), len(blocks))

    def test_split_toc_page_blocks_separates_later_body_title(self):
        blocks = [
            self.make_block("title", (413, 103, 581, 119), text="Table of Contents"),
            self.make_block("list", (89, 128, 485, 375), items=["1 Features... 1"]),
            self.make_block("title", (86, 410, 264, 428), text="4 Revision History"),
            self.make_block("list", (88, 467, 906, 741), items=["• Updated numbering"]),
        ]

        toc_blocks, body_blocks = self.module.split_toc_page_blocks(blocks)

        self.assertEqual([block.text for block in toc_blocks if block.type == "title"], ["Table of Contents"])
        self.assertEqual(body_blocks[0].text, "4 Revision History")

    def test_split_toc_column_blocks_uses_source_left_and_right_toc_columns(self):
        blocks = [
            self.make_block("title", (413, 103, 581, 119), text="Table of Contents"),
            self.make_block(
                "list",
                (89, 128, 485, 375),
                items=["1 Features... 1", "2 Applications... 1", "3 Description... 1"],
            ),
            self.make_block(
                "list",
                (526, 128, 906, 332),
                items=[
                    "7.3 Feature Description.. .17",
                    "8 Application and Implementation.. 25",
                    "9 Device and Documentation Support.. 31",
                ],
            ),
            self.make_block("paragraph", (511, 334, 906, 359), text="10 Mechanical, Packaging, and Orderable Information.. 32"),
        ]

        columns = self.module.split_toc_column_blocks(blocks, page_width=906)

        self.assertIsNotNone(columns)
        title_blocks, left_blocks, right_blocks = columns
        self.assertEqual([block.text for block in title_blocks], ["Table of Contents"])
        self.assertEqual(left_blocks[0].items[0], "1 Features... 1")
        self.assertEqual(right_blocks[-1].text, "10 Mechanical, Packaging, and Orderable Information.. 32")

    def test_split_toc_column_blocks_rejects_single_column_toc(self):
        blocks = [
            self.make_block("title", (0, 0, 100, 20), text="Table of Contents"),
            self.make_block(
                "list",
                (0, 30, 500, 200),
                items=["1 Features... 1", "2 Applications... 1", "3 Description... 1"],
            ),
        ]

        self.assertIsNone(self.module.split_toc_column_blocks(blocks, page_width=500))

    def test_render_document_page_body_renders_mixed_toc_remainder_as_body(self):
        document = FakeDocument()
        render_config = self.make_render_config()
        blocks = [
            self.make_block("title", (413, 103, 581, 119), text="Table of Contents"),
            self.make_block("list", (89, 128, 485, 375), items=["1 Features... 1"]),
            self.make_block("title", (86, 410, 264, 428), text="4 Revision History"),
        ]

        with (
            mock.patch.object(self.module, "render_toc_page") as render_toc_page,
            mock.patch.object(self.module, "render_page_body") as render_page_body,
            mock.patch.object(self.module, "insert_page_break") as insert_page_break,
        ):
            self.module.render_document_page_body(
                document,
                blocks,
                render_config,
                current_is_toc=True,
                skip_product_title=False,
            )

        render_toc_page.assert_called_once()
        insert_page_break.assert_called_once_with(document)
        render_page_body.assert_called_once()
        self.assertEqual(render_page_body.call_args.args[1][0].text, "4 Revision History")

    def test_render_page_body_skips_primary_product_title_when_requested(self):
        document = FakeDocument()
        title = self.make_block("title", (0, 100, 300, 160), text="CWQ2P690T 型")
        paragraph = self.make_block("paragraph", (0, 300, 300, 360), text="正文")
        render_config = self.make_render_config()

        with (
            mock.patch.object(self.module, "render_toc_page") as render_toc_page,
            mock.patch.object(self.module, "render_one_col_region") as render_one_col_region,
            mock.patch.object(self.module, "render_two_col_region") as render_two_col_region,
        ):
            self.module.render_page_body(document, [title, paragraph], render_config, skip_product_title=True)

        render_toc_page.assert_not_called()
        render_two_col_region.assert_not_called()
        render_one_col_region.assert_called_once()
        passed_blocks = render_one_col_region.call_args.args[1]
        self.assertEqual([block.text for block in passed_blocks], ["正文"])

    def test_render_page_body_applies_flow_plan_break_before_region(self):
        document = FakeDocument()
        left = self.make_block("paragraph", (0, 0, 150, 40), text="L")
        right = self.make_block("paragraph", (200, 0, 350, 40), text="R")
        render_config = self.make_render_config()

        class BreakBeforeFirstRegionPlan:
            def __init__(self):
                self.first_region = None

            def should_break_before_region(self, region):
                if self.first_region is None:
                    self.first_region = region
                    return True
                return False

        flow_plan = BreakBeforeFirstRegionPlan()
        with (
            mock.patch.object(self.module, "build_page_flow_plan", return_value=flow_plan),
            mock.patch.object(self.module, "insert_page_break") as insert_page_break,
            mock.patch.object(self.module, "render_one_col_region") as render_one_col_region,
            mock.patch.object(self.module, "render_two_col_region") as render_two_col_region,
        ):
            self.module.render_page_body(document, [left, right], render_config, skip_product_title=False)

        insert_page_break.assert_called_once_with(document)
        self.assertEqual(render_two_col_region.call_count + render_one_col_region.call_count, 1)

    def test_render_block_into_container_disables_keep_with_next_before_visual_block(self):
        title = self.make_block("title", (0, 0, 100, 20), text="1.2 电气特性")
        image = self.make_block("image", (0, 30, 200, 160), text="")
        render_config = self.make_render_config()
        container = SimpleNamespace(add_paragraph=lambda: SimpleNamespace(text=""))

        with (
            mock.patch.object(self.module, "fill_title_paragraph") as fill_title_paragraph,
            mock.patch.object(self.module, "render_visual_block"),
        ):
            self.module.render_block_into_container(
                container,
                title,
                page_width=400,
                usable_width=800,
                render_config=render_config,
                next_block=image,
            )

        self.assertEqual(fill_title_paragraph.call_args.kwargs["keep_with_next"], False)

    def test_render_block_into_container_promotes_bullet_like_paragraph_to_list(self):
        paragraph = SimpleNamespace(text="")
        container = SimpleNamespace(add_paragraph=lambda: paragraph)
        block = self.make_block("paragraph", (0, 0, 100, 20), text="• Low noise")
        render_config = self.make_render_config()

        with (
            mock.patch.object(self.module, "fill_list_paragraph") as fill_list_paragraph,
            mock.patch.object(self.module, "fill_body_paragraph") as fill_body_paragraph,
            mock.patch.object(self.module, "fill_title_paragraph") as fill_title_paragraph,
        ):
            self.module.render_block_into_container(
                container,
                block,
                page_width=400,
                usable_width=800,
                render_config=render_config,
            )

        fill_list_paragraph.assert_called_once_with(paragraph, "Low noise", render_config, level=0)
        fill_body_paragraph.assert_not_called()
        fill_title_paragraph.assert_not_called()

    def test_should_start_new_section_false_for_consecutive_normal_pages(self):
        render_config = self.make_render_config()
        previous_page = self.module.PageData(
            page_idx=0,
            blocks=[self.make_block("paragraph", (0, 0, 100, 20), text="A")],
            page_size=(800, 1000),
        )
        current_page = self.module.PageData(
            page_idx=1,
            blocks=[self.make_block("paragraph", (0, 0, 100, 20), text="B")],
            page_size=(800, 1000),
        )

        self.assertFalse(
            self.module.should_start_new_section(
                current_page,
                previous_page,
                render_config,
                header_blocks=[],
                footer_blocks=[],
                page_number_blocks=[],
            )
        )

    def test_should_start_new_section_ignores_source_orientation_when_word_page_size_is_configured(self):
        render_config = self.make_render_config()
        render_config.section_layout.page_width = self.module.A4_WIDTH
        render_config.section_layout.page_height = self.module.A4_HEIGHT
        previous_page = self.module.PageData(page_idx=0, blocks=[], page_size=(800, 1000))
        current_page = self.module.PageData(page_idx=1, blocks=[], page_size=(1000, 800))

        self.assertFalse(
            self.module.should_start_new_section(
                current_page,
                previous_page,
                render_config,
                header_blocks=[],
                footer_blocks=[],
                page_number_blocks=[],
            )
        )

    def test_should_start_new_section_true_when_leaving_toc(self):
        render_config = self.make_render_config()
        previous_page = self.module.PageData(
            page_idx=0,
            blocks=[self.make_block("title", (0, 0, 100, 20), text="目录")],
            page_size=(800, 1000),
        )
        current_page = self.module.PageData(
            page_idx=1,
            blocks=[self.make_block("paragraph", (0, 0, 100, 20), text="正文")],
            page_size=(800, 1000),
        )

        self.assertTrue(
            self.module.should_start_new_section(
                current_page,
                previous_page,
                render_config,
                header_blocks=[],
                footer_blocks=[],
                page_number_blocks=[],
            )
        )

    def test_should_start_new_section_false_for_appendix_entry_inside_toc_continuation(self):
        render_config = self.make_render_config()
        previous_page = self.module.PageData(
            page_idx=0,
            blocks=[self.make_block("title", (0, 0, 100, 20), text="目录")],
            page_size=(800, 1000),
        )
        current_page = self.module.PageData(
            page_idx=1,
            blocks=[
                self.make_block("title", (0, 0, 100, 20), text="附录 A.1"),
                self.make_block("paragraph", (0, 20, 100, 40), text="附录 A.2"),
                self.make_block("paragraph", (0, 40, 100, 60), text="表 A.1"),
                self.make_block("paragraph", (0, 60, 100, 80), text="图 1"),
            ],
            page_size=(800, 1000),
        )

        self.assertFalse(
            self.module.should_start_new_section(
                current_page,
                previous_page,
                render_config,
                header_blocks=[],
                footer_blocks=[],
                page_number_blocks=[],
            )
        )

    def test_should_start_new_section_true_for_appendix_title_page(self):
        render_config = self.make_render_config()
        previous_page = self.module.PageData(
            page_idx=0,
            blocks=[self.make_block("paragraph", (0, 0, 100, 20), text="上一页正文")],
            page_size=(800, 1000),
        )
        current_page = self.module.PageData(
            page_idx=1,
            blocks=[self.make_block("title", (0, 0, 100, 20), text="附录A.1")],
            page_size=(800, 1000),
        )

        self.assertTrue(
            self.module.should_start_new_section(
                current_page,
                previous_page,
                render_config,
                header_blocks=[],
                footer_blocks=[],
                page_number_blocks=[],
            )
        )

    def test_should_start_new_section_true_for_english_appendix_title_page(self):
        render_config = self.make_render_config()
        previous_page = self.module.PageData(
            page_idx=0,
            blocks=[self.make_block("paragraph", (0, 0, 100, 20), text="Previous body page")],
            page_size=(800, 1000),
        )
        current_page = self.module.PageData(
            page_idx=1,
            blocks=[self.make_block("title", (0, 0, 100, 20), text="Appendix A")],
            page_size=(800, 1000),
        )

        self.assertTrue(
            self.module.should_start_new_section(
                current_page,
                previous_page,
                render_config,
                header_blocks=[],
                footer_blocks=[],
                page_number_blocks=[],
            )
        )

    def test_should_start_new_section_true_for_top_level_title_after_dense_visual_page(self):
        render_config = self.make_render_config()
        previous_page = self.module.PageData(
            page_idx=0,
            blocks=[
                self.make_block("table", (0, 80, 700, 760), html="<table></table>"),
                self.make_block("image", (0, 770, 700, 970), image_path=None),
            ],
            page_size=(800, 1000),
        )
        current_page = self.module.PageData(
            page_idx=1,
            blocks=[self.make_block("title", (0, 80, 400, 120), text="10 Parameter Measurement Information")],
            page_size=(800, 1000),
        )

        self.assertTrue(
            self.module.should_start_new_section(
                current_page,
                previous_page,
                render_config,
                header_blocks=[],
                footer_blocks=[],
                page_number_blocks=[],
            )
        )

    def test_should_start_new_section_false_for_top_level_title_after_short_visual_page(self):
        render_config = self.make_render_config()
        previous_page = self.module.PageData(
            page_idx=0,
            blocks=[self.make_block("table", (0, 80, 700, 500), html="<table></table>")],
            page_size=(800, 1000),
        )
        current_page = self.module.PageData(
            page_idx=1,
            blocks=[self.make_block("title", (0, 80, 400, 120), text="10 Parameter Measurement Information")],
            page_size=(800, 1000),
        )

        self.assertFalse(
            self.module.should_start_new_section(
                current_page,
                previous_page,
                render_config,
                header_blocks=[],
                footer_blocks=[],
                page_number_blocks=[],
            )
        )

    def test_should_start_new_section_false_when_previous_visual_page_already_overflows(self):
        render_config = self.make_render_config()
        previous_page = self.module.PageData(
            page_idx=0,
            blocks=[
                self.make_block("image", (0, 80, 700, 700), image_path=None),
                self.make_block("paragraph", (0, 930, 700, 1100), text="overflowing notes"),
            ],
            page_size=(800, 1000),
        )
        current_page = self.module.PageData(
            page_idx=1,
            blocks=[self.make_block("title", (0, 80, 400, 120), text="11 Package Outline Dimensions")],
            page_size=(800, 1000),
        )

        self.assertFalse(
            self.module.should_start_new_section(
                current_page,
                previous_page,
                render_config,
                header_blocks=[],
                footer_blocks=[],
                page_number_blocks=[],
            )
        )

    def test_build_document_reuses_single_section_for_same_orientation_flow_pages(self):
        render_config = self.make_render_config()
        document = FakeDocument()
        pages = [
            self.module.PageData(
                page_idx=0,
                blocks=[self.make_block("paragraph", (0, 0, 100, 20), text="A")],
                page_size=(800, 1000),
            ),
            self.module.PageData(
                page_idx=1,
                blocks=[self.make_block("paragraph", (0, 0, 100, 20), text="B")],
                page_size=(800, 1000),
            ),
        ]

        with (
            mock.patch.object(self.module, "create_document", return_value=document),
            mock.patch.object(self.module, "clear_document_body"),
            mock.patch.object(self.module, "fill_template_intro"),
            mock.patch.object(self.module, "clone_first_section_layout"),
            mock.patch.object(self.module, "render_toc_page"),
            mock.patch.object(self.module, "render_page_body"),
        ):
            self.module.build_document(pages, render_config, template_document=None)

        self.assertEqual(len(document.sections), 1)

    def test_build_document_skips_empty_page_and_keeps_toc_continuation_mode(self):
        render_config = self.make_render_config()
        document = FakeDocument()
        pages = [
            self.module.PageData(
                page_idx=0,
                blocks=[self.make_block("page_header", (0, 0, 10, 10), text="only-header")],
            ),
            self.module.PageData(
                page_idx=1,
                blocks=[self.make_block("title", (0, 0, 100, 20), text="目录")],
            ),
            self.module.PageData(
                page_idx=2,
                blocks=[
                    self.make_block(
                        "list",
                        (0, 0, 100, 50),
                        items=["1.1 产品概述 1", "1.2 产品特点 2", "1.3 产品用途 3", "1.4 对应国外产品情况 4"],
                    )
                ],
            ),
            self.module.PageData(
                page_idx=3,
                blocks=[self.make_block("paragraph", (0, 0, 100, 20), text="普通正文")],
            ),
        ]

        with (
            mock.patch.object(self.module, "create_document", return_value=document),
            mock.patch.object(self.module, "clear_document_body"),
            mock.patch.object(self.module, "configure_section"),
            mock.patch.object(self.module, "fill_template_intro"),
            mock.patch.object(self.module, "clone_first_section_layout"),
            mock.patch.object(self.module, "render_toc_page") as render_toc_page,
            mock.patch.object(self.module, "render_page_body") as render_page_body,
        ):
            result = self.module.build_document(pages, render_config, template_document=None)

        self.assertIs(result, document)
        self.assertEqual(render_toc_page.call_count, 2)
        self.assertEqual(render_page_body.call_count, 1)
        self.assertEqual(render_page_body.call_args.args[1][0].text, "普通正文")


if __name__ == "__main__":
    __import__("unittest").main()
