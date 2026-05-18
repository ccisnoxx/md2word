import tempfile
import unittest
from pathlib import Path

try:
    from .test_render_table_from_html_characterization import _load_module
except ImportError:  # pragma: no cover - compatibility for direct execution
    from test_render_table_from_html_characterization import _load_module


class TranslationRuntimeCharacterizationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.module = _load_module()
        cls.translation = cls.module.translation_runtime

    def make_page(self, page_idx, blocks):
        return self.module.PageData(page_idx=page_idx, blocks=blocks)

    def make_block(self, block_type, text="", block_idx=0, **kwargs):
        return self.module.Block(
            type=block_type,
            bbox=(0.0, 0.0, 10.0, 10.0),
            text=text,
            block_idx=block_idx,
            **kwargs,
        )

    def test_extract_translation_items_uses_stable_minimal_ids(self):
        pages = [
            self.make_page(
                0,
                [
                    self.make_block("title", "1 Features", block_idx=0),
                    self.make_block(
                        "paragraph",
                        "The OPA228 input offset voltage is typically 10 kΩ.",
                        block_idx=1,
                    ),
                    self.make_block("list", block_idx=2, items=["Low noise", "High slew rate"]),
                    self.make_block(
                        "table",
                        block_idx=3,
                        captions=["Electrical Characteristics"],
                        html="<table><tr><th>Parameter</th><td>Input voltage 5 mV</td></tr></table>",
                    ),
                ],
            )
        ]

        items = self.translation.extract_translation_items(pages)
        ids = [item.id for item in items]

        self.assertEqual(
            ids,
            [
                "p0001.b0000.text",
                "p0001.b0001.text",
                "p0001.b0002.items.i000",
                "p0001.b0002.items.i001",
                "p0001.b0003.captions.i000",
                "p0001.b0003.html.c0000",
                "p0001.b0003.html.c0001",
            ],
        )
        paragraph_item = items[1]
        self.assertIn("{{PH_001}}", paragraph_item.text)
        self.assertIn("{{PH_002}}", paragraph_item.text)
        self.assertEqual(paragraph_item.placeholders["{{PH_001}}"], "OPA228")
        self.assertEqual(paragraph_item.placeholders["{{PH_002}}"], "10 kΩ")

    def test_extract_translation_items_skips_page_decorations(self):
        pages = [
            self.make_page(
                0,
                [
                    self.make_block("page_header", "Technical documentation", block_idx=14),
                    self.make_block("title", "1 Features", block_idx=0),
                    self.make_block("paragraph", "Body text", block_idx=1),
                    self.make_block("page_footer", "Page 1", block_idx=20),
                ],
            )
        ]

        items = self.translation.extract_translation_items(pages)

        self.assertEqual([item.id for item in items], ["p0001.b0000.text", "p0001.b0001.text"])

    def test_batching_extends_to_complete_section_when_page_boundary_splits_it(self):
        pages = []
        section_starts = {0: "1 Overview", 3: "2 Pins", 9: "3 Operation", 17: "4 Electrical Characteristics"}
        for page_idx in range(23):
            blocks = []
            if page_idx in section_starts:
                blocks.append(self.make_block("title", section_starts[page_idx], block_idx=0))
            blocks.append(self.make_block("paragraph", f"Body text page {page_idx + 1}", block_idx=1))
            pages.append(self.make_page(page_idx, blocks))

        config = self.translation.TranslationConfig(max_pages_per_batch=20, max_chars_per_batch=100000)
        items = self.translation.extract_translation_items(pages)
        batches = self.translation.build_translation_batches(items, total_pages=len(pages), config=config)

        self.assertEqual(len(batches), 1)
        self.assertEqual(batches[0].start_page, 1)
        self.assertEqual(batches[0].end_page, 23)
        self.assertIn("4 Electrical Characteristics", batches[0].section_title)

    def test_batching_splits_oversized_section_by_page_and_marks_continuation(self):
        pages = []
        for page_idx in range(5):
            blocks = []
            if page_idx == 0:
                blocks.append(self.make_block("title", "4 Electrical Characteristics", block_idx=0))
            blocks.append(self.make_block("paragraph", "Long text " + ("x" * 40), block_idx=1))
            pages.append(self.make_page(page_idx, blocks))

        config = self.translation.TranslationConfig(max_pages_per_batch=2, max_chars_per_batch=120)
        items = self.translation.extract_translation_items(pages)
        batches = self.translation.build_translation_batches(items, total_pages=len(pages), config=config)

        self.assertGreater(len(batches), 1)
        self.assertFalse(batches[0].section_continuation)
        self.assertTrue(any(batch.section_continuation for batch in batches[1:]))

    def test_request_payload_keeps_llm_items_minimal(self):
        pages = [
            self.make_page(
                0,
                [
                    self.make_block("title", "1 Features", block_idx=0),
                    self.make_block("paragraph", "The device supports 5 V operation.", block_idx=1),
                ],
            )
        ]
        payload = self.translation.build_translation_request_payload(
            pages,
            self.translation.TranslationConfig(max_pages_per_batch=20, max_chars_per_batch=10000),
        )

        item = payload["batches"][0]["items"][0]
        self.assertEqual(set(item), {"id", "text"})
        self.assertEqual(payload["batches"][0]["page_range"], [1, 1])

    def test_apply_translation_responses_restores_placeholders_and_rewrites_html_cells(self):
        pages = [
            self.make_page(
                0,
                [
                    self.make_block("title", "1 Features", block_idx=0),
                    self.make_block(
                        "paragraph",
                        "The OPA228 input offset voltage is typically 10 kΩ.",
                        block_idx=1,
                    ),
                    self.make_block(
                        "table",
                        block_idx=2,
                        html="<table><tr><th>Parameter</th><td>Input voltage 5 mV</td></tr></table>",
                    ),
                ],
            )
        ]
        items = self.translation.extract_translation_items(pages)
        translations = {item.id: item.text for item in items}
        translations["p0001.b0000.text"] = "1 特性"
        translations["p0001.b0001.text"] = "{{PH_001}} 输入失调电压的典型值为 {{PH_002}}。"
        translations["p0001.b0002.html.c0000"] = "参数"
        translations["p0001.b0002.html.c0001"] = "输入电压 {{PH_001}}"

        self.translation.apply_translation_responses(pages, translations)

        self.assertEqual(pages[0].blocks[0].text, "1 特性")
        self.assertEqual(pages[0].blocks[1].text, "OPA228 输入失调电压的典型值为 10 kΩ。")
        self.assertIn("<th>参数</th>", pages[0].blocks[2].html)
        self.assertIn("<td>输入电压 5 mV</td>", pages[0].blocks[2].html)

    def test_validate_translation_responses_rejects_placeholder_mismatch(self):
        pages = [
            self.make_page(
                0,
                [self.make_block("paragraph", "The device supports 5 V operation.", block_idx=0)],
            )
        ]
        items = self.translation.extract_translation_items(pages)
        translations = {items[0].id: "器件支持 5V 工作。"}

        with self.assertRaises(ValueError):
            self.translation.validate_translation_responses(items, translations)

    def test_load_translation_response_file_accepts_batch_payload(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "response.json"
            path.write_text(
                '{"batches":[{"items":[{"id":"p0001.b0000.text","text":"特性"}]}]}',
                encoding="utf-8",
            )

            translations = self.translation.load_translation_response_file(path)

        self.assertEqual(translations, {"p0001.b0000.text": "特性"})


if __name__ == "__main__":
    unittest.main()
