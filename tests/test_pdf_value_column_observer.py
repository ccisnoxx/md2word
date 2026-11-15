"""针对正式自动核定的 Poppler 观测合同读取实物 PDF。"""
from __future__ import annotations

from pathlib import Path
import shutil
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from app.services.document_ir.pdf_value_column_observer import (
    PdfObservationUnavailable,
    _read_poppler,
    observe_pdf_value_column_page,
)


def make_pdf(content: bytes, *, width: int = 200, height: int = 200, page_extra: bytes = b"") -> bytes:
    """构造可供端到端用例验证的原生 Helvetica 页面。"""
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Count 1 /Kids [3 0 R] >>",
        (
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {width} {height}] ".encode()
            + b"/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R " + page_extra + b" >>"
        ),
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>",
        f"<< /Length {len(content)} >>\nstream\n".encode() + content + b"\nendstream",
    ]
    result = bytearray(b"%PDF-1.6\n")
    offsets = []
    for number, body in enumerate(objects, start=1):
        offsets.append(len(result))
        result.extend(f"{number} 0 obj\n".encode() + body + b"\nendobj\n")
    start_xref = len(result)
    result.extend(f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode())
    result.extend(b"".join(f"{offset:010d} 00000 n \n".encode() for offset in offsets))
    result.extend(f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{start_xref}\n%%EOF\n".encode())
    return bytes(result)


_POPPLER_AVAILABLE = all(shutil.which(tool) for tool in ("pdfinfo", "pdftotext", "pdftocairo", "pdftohtml"))
_TEXT = b"BT /F1 10 Tf 20 140 Td (75) Tj ET"


@unittest.skipUnless(_POPPLER_AVAILABLE, "实物观测验证需要 Poppler")
class PdfValueColumnObserverTests(unittest.TestCase):
    def observe(self, content: bytes, *, page_extra: bytes = b""):
        with TemporaryDirectory() as temporary:
            path = Path(temporary) / "source.pdf"
            path.write_bytes(make_pdf(content, page_extra=page_extra))
            return observe_pdf_value_column_page(path, page_index=0)

    def test_observes_word_ink_rectangle_and_clipped_axis_strokes(self):
        page = self.observe(
            b"0.85 g 20 130 60 20 re f\n"
            + b"0 g 0 G BT /F1 10 Tf 31 140 Td (\\2615) Tj ET\n"
            + b"0.35 w 1 J 20 130 m 80 130 l S\n"
            + b"80 130 m 80 150 l S\n"
            + b"q 24 124 52 6 re W n 20 126 m 80 126 l S Q"
        )
        self.assertEqual((page.width, page.height, page.page_count), (200, 200, 1))
        self.assertEqual(page.rectangles, ((20, 50, 80, 70),))
        self.assertIn((20, 70, 80), page.horizontal_lines)
        self.assertIn((24, 74, 76), page.horizontal_lines)
        self.assertIn((80, 50, 70), page.vertical_lines)
        self.assertEqual(page.unsupported_regions, ())
        self.assertEqual(page.unmapped_glyph_regions, ())
        (word,) = page.words
        self.assertEqual(word.text, "±5")
        self.assertEqual(word.glyphs[0], (word.bbox[0], 60))
        self.assertEqual(len(word.glyphs), 2)

    def test_hidden_white_covered_and_duplicate_words_cannot_provide_ink(self):
        for name, painting in (
            ("不可见绘制模式", b"BT /F1 10 Tf 20 140 Td 3 Tr (75) Tj ET"),
            ("白底白字", b"1 g " + _TEXT),
            ("绘制后覆盖", _TEXT + b"\n1 g 19 139 18 13 re f"),
            ("绘制重复", _TEXT + b"\n" + _TEXT),
            ("隐字重叠", _TEXT + b"\nBT /F1 10 Tf 20 140 Td 3 Tr (45) Tj ET"),
        ):
            with self.subTest(name=name):
                page = self.observe(painting)
                self.assertIn("75", {word.text for word in page.words})
                self.assertTrue(all(not word.glyphs for word in page.words))
                if name in {"绘制重复", "隐字重叠"}:
                    self.assertGreaterEqual(len(page.unmapped_glyph_regions), 2)

    def test_unsupported_fill_is_local_to_its_actual_profile(self):
        page = self.observe(_TEXT + b"\n0 g 110 20 m 110 30 130 40 140 40 c 120 45 l h f")
        self.assertEqual(len(page.words[0].glyphs), 2)
        self.assertEqual(page.unsupported_regions, ((110, 155, 140, 180),))

    def test_actualtext_cannot_substitute_the_literal_painted_in_the_page(self):
        page = self.observe(b"/Span << /ActualText (45) >> BDC " + _TEXT + b" EMC")
        (word,) = page.words
        self.assertEqual(word.text, "45")
        self.assertEqual(word.glyphs, ())
        self.assertEqual(len(page.unmapped_glyph_regions), 2)

    def test_unsupported_page_frame_is_rejected_before_reading_words(self):
        for extra in (b"/Rotate 90", b"/CropBox [1 1 199 199]"):
            with self.subTest(extra=extra):
                with self.assertRaisesRegex(PdfObservationUnavailable, "^pdf_geometry_unverified$"):
                    self.observe(_TEXT, page_extra=extra)

    def test_textless_page_does_not_supply_column_evidence(self):
        with self.assertRaisesRegex(PdfObservationUnavailable, "^pdf_text_unavailable$"):
            self.observe(b"20 130 60 20 re f")


class PdfObserverBudgetTests(unittest.TestCase):
    def test_poppler_overflow_is_unavailable(self):
        with self.assertRaises(PdfObservationUnavailable):
            _read_poppler([sys.executable, "-c", "print('0' * 200000)"], max_bytes=100)

    def test_poppler_timeout_is_unavailable_even_after_partial_output(self):
        with patch("app.services.document_ir.pdf_value_column_observer._TIMEOUT_SECONDS", 0.15):
            with self.assertRaises(PdfObservationUnavailable):
                _read_poppler([sys.executable, "-c", "import time; print('partial', flush=True); time.sleep(10)"])


if __name__ == "__main__":
    unittest.main()
