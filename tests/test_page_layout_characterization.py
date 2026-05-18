from types import SimpleNamespace
from unittest import mock

try:
    from .test_render_table_from_html_characterization import _load_module
except ImportError:  # pragma: no cover - compatibility for direct execution
    from test_render_table_from_html_characterization import _load_module


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
        cls.module = _load_module()

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

    def test_should_start_new_section_true_for_orientation_change(self):
        render_config = self.make_render_config()
        previous_page = self.module.PageData(page_idx=0, blocks=[], page_size=(800, 1000))
        current_page = self.module.PageData(page_idx=1, blocks=[], page_size=(1000, 800))

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
