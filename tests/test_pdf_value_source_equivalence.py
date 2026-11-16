"""实际 PDF 的同序逐页版面比对回归。"""
from pathlib import Path
import shutil
import subprocess
from tempfile import TemporaryDirectory
from time import monotonic
import unittest
from unittest.mock import patch

from app.services.document_ir.pdf_value_column_observer import (
    PDF_OBSERVATION_BUDGET_EXHAUSTED,
    PdfObservationUnavailable,
)
from app.services.document_ir.pdf_value_source_equivalence import compare_pdf_pages
from tests.test_pdf_value_column_observer import make_pdf

_DRAWING = b"BT /F1 10 Tf 20 140 Td (75) Tj ET\n0.8 w 20 130 m 80 130 l S"
_POPPLER_AVAILABLE = all(shutil.which(tool) for tool in ("pdfinfo", "pdftotext", "pdftoppm"))


@unittest.skipUnless(_POPPLER_AVAILABLE, "逐页比对需要 Poppler")
class PdfValueSourceEquivalenceTests(unittest.TestCase):
    def setUp(self):
        self.directory = Path(self.enterContext(TemporaryDirectory()))

    def pdf(self, name, content=_DRAWING, **options):
        path = self.directory / name
        path.write_bytes(make_pdf(content, **options))
        return path

    def compare(self, source, returned):
        return compare_pdf_pages(source, returned, deadline=monotonic() + 30)

    @unittest.skipUnless(shutil.which("pdfunite"), "PDF 实际重写需要 pdfunite")
    def test_rewritten_pdf_keeps_the_complete_page_observation(self):
        source = self.pdf("source.pdf")
        returned = self.directory / "returned.pdf"
        subprocess.run(["pdfunite", str(source), str(returned)], check=True, timeout=5)
        self.assertNotEqual(source.read_bytes(), returned.read_bytes())
        comparison = self.compare(source, returned)
        self.assertIsNotNone(comparison)
        self.assertEqual(comparison.page_count, 1)
        self.assertEqual(comparison.page_sizes, ((200.0, 200.0),))
        self.assertRegex(comparison.poppler_version, r"^\d+(?:\.\d+)+$")
        self.assertRegex(comparison.observation_sha256, r"^[0-9a-f]{64}$")
        self.assertEqual(comparison, self.compare(source, source))

    def test_value_or_printed_line_change_is_a_mismatch(self):
        source = self.pdf("source.pdf")
        for name, content in (
            ("value.pdf", _DRAWING.replace(b"(75)", b"(79)")),
            ("rule.pdf", _DRAWING.replace(b"80 130 l", b"80 135 l")),
        ):
            with self.subTest(name=name):
                self.assertIsNone(self.compare(source, self.pdf(name, content)))

    @unittest.skipUnless(shutil.which("pdfunite"), "多页 PDF 夹具需要 pdfunite")
    def test_page_order_and_count_must_match(self):
        first = self.pdf("first.pdf")
        second = self.pdf("second.pdf", _DRAWING.replace(b"(75)", b"(79)"))
        source, swapped = self.directory / "source.pdf", self.directory / "swapped.pdf"
        subprocess.run(["pdfunite", str(first), str(second), str(source)], check=True, timeout=5)
        subprocess.run(["pdfunite", str(second), str(first), str(swapped)], check=True, timeout=5)
        self.assertIsNone(self.compare(source, swapped))
        self.assertIsNone(self.compare(source, first))

    def test_missing_text_and_unsupported_frame_are_unavailable(self):
        for name, source in (
            ("textless", self.pdf("textless.pdf", b"20 130 m 80 130 l S")),
            ("rotated", self.pdf("rotated.pdf", page_extra=b"/Rotate 90")),
            ("cropbox", self.pdf("cropbox.pdf", page_extra=b"/CropBox [1 1 199 199]")),
            ("excessive", self.pdf("excessive.pdf", width=10000, height=10000)),
        ):
            with self.subTest(name=name), self.assertRaises(PdfObservationUnavailable):
                self.compare(source, source)

    def test_mixed_poppler_versions_are_unavailable(self):
        source = self.pdf("source.pdf")
        with (
            patch("app.services.document_ir.pdf_value_column_observer._read_poppler", side_effect=[
                b"pdfinfo version 25.03.0\n",
                b"pdftotext version 25.03.0\n",
                b"pdftoppm version 26.06.0\n",
            ]),
            self.assertRaises(PdfObservationUnavailable),
        ):
            self.compare(source, source)


class PdfValueSourceEquivalenceBudgetTests(unittest.TestCase):
    def test_expired_deadline_is_preserved_without_running_tools(self):
        source = Path("source.pdf")
        with self.assertRaisesRegex(PdfObservationUnavailable, f"^{PDF_OBSERVATION_BUDGET_EXHAUSTED}$"):
            compare_pdf_pages(source, source, deadline=monotonic() - 1)
