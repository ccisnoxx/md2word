"""用实际 Poppler 核对源 PDF 裁图的坐标和页面约束。"""

import io
import unittest

from PIL import Image

from app.infrastructure.pdf_crop import PopplerPdfTableCropProvider, poppler_tools_available
from app.services.document_ir.table_placeholder import PdfCropRequest, PdfCropSource, TablePlaceholderError, checksum


def _source(*, media="0 0 841.89 595.28", crop=None, rotation=0) -> PdfCropSource:
    """生成可直接设定页面框及旋转的一页矢量 PDF。"""
    stream = b"0.1 0.2 0.8 rg\n210 149 421 297 re f\n"
    objects = (
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        (f"<< /Type /Page /Parent 2 0 R /MediaBox [{media}] /CropBox [{crop or media}]"
         f" /Rotate {rotation} /Resources << >> /Contents 4 0 R >>").encode("ascii"),
        f"<< /Length {len(stream)} >>\nstream\n".encode("ascii") + stream + b"endstream",
    )
    pdf = bytearray(b"%PDF-1.4\n")
    offsets = []
    for index, payload in enumerate(objects, start=1):
        offsets.append(len(pdf))
        pdf.extend(f"{index} 0 obj\n".encode("ascii") + payload + b"\nendobj\n")
    xref = len(pdf)
    pdf.extend(b"xref\n0 5\n0000000000 65535 f \n")
    for offset in offsets:
        pdf.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    pdf.extend(f"trailer\n<< /Size 5 /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode("ascii"))
    content = bytes(pdf)
    return PdfCropSource("source", checksum(content), content)


@unittest.skipUnless(poppler_tools_available(), "实际裁图验证需要 pdfinfo 和 pdftoppm")
class PopplerPdfTableCropTests(unittest.TestCase):
    def test_truncated_frame_matches_actual_fractional_frame_crop(self):
        source = _source()
        provider = PopplerPdfTableCropProvider()
        actual = provider.crop(PdfCropRequest(source, 0, (210.4725, 148.82, 631.4175, 446.46), (841.89, 595.28)))
        truncated = provider.crop(PdfCropRequest(
            source, 0, (210.25, 148.75, 630.75, 446.25), (841, 595), from_normalized_bbox=True,
        ))

        self.assertEqual(truncated.content, actual.content)
        self.assertEqual(truncated.frame, (841, 595))
        with Image.open(io.BytesIO(truncated.content)) as image:
            self.assertEqual(image.size, (843, 596))

    def test_rejects_unverified_frame_bbox_box_origin_rotation_and_budget(self):
        source = _source()
        provider = PopplerPdfTableCropProvider()
        bbox = (10, 20, 30, 40)
        cases = {
            "absolute_points": PdfCropRequest(source, 0, bbox, (841, 595)),
            "rounded_up": PdfCropRequest(source, 0, bbox, (842, 595), from_normalized_bbox=True),
            "nearby_fractional": PdfCropRequest(source, 0, bbox, (841, 595.28), from_normalized_bbox=True),
            "declared_bbox_overflow": PdfCropRequest(
                source, 0, (10, 20, 841.5, 40), (841, 595), from_normalized_bbox=True,
            ),
            "different_boxes": PdfCropRequest(
                _source(crop="0 0 800 550"), 0, bbox, (841, 595), from_normalized_bbox=True,
            ),
            "nonzero_origin": PdfCropRequest(
                _source(media="1 0 842.89 595.28"), 0, bbox, (841, 595), from_normalized_bbox=True,
            ),
            "rotation": PdfCropRequest(_source(rotation=90), 0, bbox, (841, 595), from_normalized_bbox=True),
            "actual_frame_over_budget": PdfCropRequest(
                _source(media="0 0 2000.99 1999.99"), 0, bbox, (2000, 1999), from_normalized_bbox=True,
            ),
        }
        for case, request in cases.items():
            with self.subTest(case=case):
                with self.assertRaises(TablePlaceholderError) as caught:
                    provider.crop(request)
                self.assertEqual(caught.exception.code, "table_placeholder_geometry_invalid")
