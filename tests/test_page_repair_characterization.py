from pathlib import Path
from unittest import mock

try:
    from .runtime_direct_loaders import load_page_repair_module
except ImportError:  # pragma: no cover - compatibility for direct execution
    from runtime_direct_loaders import load_page_repair_module


class PageRepairCharacterizationTests(__import__("unittest").TestCase):
    @classmethod
    def setUpClass(cls):
        cls.module = load_page_repair_module()

    def make_block(self, block_type, bbox, **kwargs):
        return self.module.Block(type=block_type, bbox=bbox, **kwargs)

    def test_bbox_distance_sums_coordinate_deltas(self):
        distance = self.module.bbox_distance((0.0, 1.0, 2.0, 3.0), (1.0, 3.0, 5.0, 7.0))
        self.assertEqual(distance, 10.0)

    def test_find_best_visual_match_picks_closest_same_type_under_threshold(self):
        target = self.make_block("image", (0.0, 0.0, 10.0, 10.0))
        close = self.make_block("image", (1.0, 1.0, 11.0, 11.0), image_path=Path("/tmp/a.png"))
        far = self.make_block("image", (100.0, 100.0, 120.0, 120.0), image_path=Path("/tmp/b.png"))
        wrong_type = self.make_block("table", (0.0, 0.0, 10.0, 10.0), image_path=Path("/tmp/c.png"))

        matched = self.module.find_best_visual_match(target, [far, close, wrong_type])

        self.assertIs(matched, close)

    def test_find_best_visual_match_returns_none_when_distance_too_large(self):
        target = self.make_block("image", (0.0, 0.0, 10.0, 10.0))
        far = self.make_block("image", (100.0, 100.0, 120.0, 120.0), image_path=Path("/tmp/b.png"))

        matched = self.module.find_best_visual_match(target, [far])

        self.assertIsNone(matched)

    def test_merge_page_with_middle_backfills_header_and_visual_metadata(self):
        page = self.module.PageData(
            page_idx=0,
            blocks=[
                self.make_block("image", (10.0, 10.0, 30.0, 30.0), text="", image_path=None, captions=[], footnotes=[]),
            ],
            page_size=None,
        )
        matched_visual = self.make_block(
            "image",
            (12.0, 12.0, 32.0, 32.0),
            text="patched-text",
            image_path=Path("/tmp/image.png"),
            captions=["Cap"],
            footnotes=["Note"],
        )
        middle_page = self.module.MiddlePage(
            page_idx=0,
            page_size=(800.0, 1000.0),
            discarded_blocks=[self.make_block("page_header", (0.0, 0.0, 10.0, 10.0), text="Header")],
            visual_blocks=[matched_visual],
        )

        self.module.merge_page_with_middle(page, middle_page)

        self.assertEqual(page.page_size, (800.0, 1000.0))
        self.assertEqual(page.blocks[0].image_path, Path("/tmp/image.png"))
        self.assertEqual(page.blocks[0].captions, ["Cap"])
        self.assertEqual(page.blocks[0].footnotes, ["Note"])
        self.assertEqual(page.blocks[0].text, "patched-text")
        self.assertEqual(page.blocks[1].type, "page_header")
        self.assertEqual(page.blocks[1].text, "Header")

    def test_attach_table_continuations_moves_placeholder_heights_to_last_real_table(self):
        leading_table = self.make_block(
            "table",
            (0.0, 0.0, 100.0, 100.0),
            html="<table><tr><td>A</td></tr></table>",
            continuation_heights=[],
        )
        placeholder_one = self.make_block("table_placeholder", (0.0, 0.0, 100.0, 220.0))
        placeholder_two = self.make_block("table_placeholder", (0.0, 0.0, 100.0, 180.0))
        pages = [
            self.module.PageData(page_idx=0, blocks=[leading_table]),
            self.module.PageData(page_idx=1, blocks=[placeholder_one]),
            self.module.PageData(page_idx=2, blocks=[placeholder_two]),
        ]

        self.module.attach_table_continuations(pages)

        self.assertEqual(leading_table.continuation_heights, [220.0, 180.0])
        self.assertEqual(pages[1].blocks, [])
        self.assertEqual(pages[2].blocks, [])

    def test_load_pages_merges_middle_sorts_blocks_and_attaches_continuations(self):
        paragraph = self.make_block("paragraph", (30.0, 30.0, 60.0, 60.0), text="Body")
        title = self.make_block("title", (10.0, 10.0, 50.0, 20.0), text="Title")
        table = self.make_block(
            "table",
            (20.0, 20.0, 80.0, 90.0),
            html="<table><tr><td>A</td></tr></table>",
            continuation_heights=[],
        )
        placeholder = self.make_block("table_placeholder", (0.0, 0.0, 100.0, 150.0))
        pages = [
            self.module.PageData(page_idx=0, blocks=[paragraph, title, table]),
            self.module.PageData(page_idx=1, blocks=[placeholder]),
        ]
        middle_pages = {
            0: self.module.MiddlePage(
                page_idx=0,
                page_size=(700.0, 900.0),
                discarded_blocks=[],
                visual_blocks=[],
            )
        }

        with (
            mock.patch.object(self.module, "load_content_pages", return_value=(pages, Path("/tmp/content.json"))),
            mock.patch.object(self.module, "load_middle_pages", return_value=middle_pages),
        ):
            merged_pages, source_path = self.module.load_pages(Path("/tmp/package"))

        self.assertEqual(source_path, Path("/tmp/content.json"))
        self.assertEqual(merged_pages[0].page_size, (700.0, 900.0))
        self.assertEqual([block.type for block in merged_pages[0].blocks], ["title", "table", "paragraph"])
        self.assertEqual(table.continuation_heights, [150.0])
        self.assertEqual(merged_pages[1].blocks, [])


if __name__ == "__main__":
    __import__("unittest").main()
