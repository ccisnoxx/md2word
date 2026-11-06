"""直接验证正式 MinerU 转换复用的内容清洗规则。"""

from __future__ import annotations

import unittest

from app.conversion.docx_rules import mineru_content


class InputAdapterCharacterizationTests(unittest.TestCase):
    def test_clean_markdown_document_removes_details_blocks(self):
        raw = "# Title\n\nkeep\n<details>\n<summary>flowchart</summary>\nhidden\n</details>\n\n## Next\n"
        cleaned = mineru_content.clean_markdown_document(raw)

        self.assertEqual(cleaned, "# Title\n\nkeep\n\n## Next\n")

    def test_clean_text_removes_details_blocks_but_keeps_inline_markup(self):
        cleaned = mineru_content.clean_text("before <details><summary>x</summary>hidden</details> R<sub>L</sub> after")
        self.assertEqual(cleaned, "before R<sub>L</sub> after")

    def test_extract_first_html_ignores_details_wrapped_html_from_content_list(self):
        html = mineru_content.extract_first_html(
            {
                "html": "<details><summary>text_image</summary><table><tr><td>A</td></tr></table></details>"
            }
        )

        self.assertIsNone(html)

    def test_merge_footnote_fragments_keeps_unmarked_notes_separate(self):
        self.assertEqual(
            mineru_content.merge_footnote_fragments(["Source: data sheet.", "All values are typical."]),
            ["Source: data sheet.", "All values are typical."],
        )


if __name__ == "__main__":
    unittest.main()
