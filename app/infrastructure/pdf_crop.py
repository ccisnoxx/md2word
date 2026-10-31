"""Poppler 单页受控裁图；只接收已授权 PDF 字节和明确原始坐标 frame。"""
from __future__ import annotations

import io
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

from PIL import Image

from app.services.document_ir.table_placeholder import (
    MAX_IMAGE_BYTES, MAX_PIXELS, PdfCropRequest, PdfCropResult, TablePlaceholderError,
    checksum, validate_geometry, validate_image,
)


class PopplerPdfTableCropProvider:
    """首版仅接受与实际 PDF 点空间一致、原点为零且未旋转的 frame。"""
    def __init__(self, *, pdfinfo: str | None = None, pdftoppm: str | None = None, timeout: float = 20):
        self.pdfinfo = pdfinfo or shutil.which("pdfinfo")
        self.pdftoppm = pdftoppm or shutil.which("pdftoppm")
        self.timeout = timeout

    def crop(self, request: PdfCropRequest) -> PdfCropResult:
        validate_geometry(request.page_index, request.bbox, request.frame)
        if (not self.pdfinfo or not self.pdftoppm or len(request.source.content) > 128 * 1024 * 1024
                or not request.source.content.startswith(b"%PDF-")
                or checksum(request.source.content) != request.source.checksum_sha256):
            raise TablePlaceholderError("table_placeholder_crop_failed")
        if request.frame[0] * request.frame[1] * 4 > MAX_PIXELS:
            raise TablePlaceholderError("table_placeholder_geometry_invalid")
        with tempfile.TemporaryDirectory(prefix="table_crop_") as directory:
            root = Path(directory)
            pdf = root / "source.pdf"
            pdf.write_bytes(request.source.content)
            info = root / "info.txt"
            page = str(request.page_index + 1)
            self._run([self.pdfinfo, "-f", page, "-l", page, "-box", str(pdf)], info)
            if info.stat().st_size > 64 * 1024:
                raise TablePlaceholderError("table_placeholder_crop_failed")
            text = info.read_text(errors="replace")
            def values(name, count):
                match = re.search(r"^(?:Page\s+\d+\s+)?" + name + r":\s*(.*)$", text, re.M)
                if match is None:
                    raise TablePlaceholderError("table_placeholder_geometry_invalid")
                try:
                    result = tuple(float(n) for n in match.group(1).split()[:count])
                except ValueError:
                    raise TablePlaceholderError("table_placeholder_geometry_invalid") from None
                if len(result) != count or not all(math.isfinite(n) for n in result):
                    raise TablePlaceholderError("table_placeholder_geometry_invalid")
                return result
            media, crop = values("MediaBox", 4), values("CropBox", 4)
            rotation = re.search(r"^(?:Page\s+\d+\s+rot|Page rot):\s*(-?\d+)", text, re.M)
            if rotation is None or int(rotation.group(1)) != 0 or media != crop or media != (0, 0, *request.frame):
                raise TablePlaceholderError("table_placeholder_geometry_invalid")
            x0, y0, x1, y1 = request.bbox
            left, top, right, bottom = math.floor(x0 * 2), math.floor(y0 * 2), math.ceil(x1 * 2), math.ceil(y1 * 2)
            prefix = root / "crop"
            self._run([self.pdftoppm, "-f", page, "-l", page, "-singlefile", "-r", "144",
                       "-x", str(left), "-y", str(top), "-W", str(right-left), "-H", str(bottom-top),
                       "-png", str(pdf), str(prefix)], root / "raster.log")
            output = root / "crop.png"
            if not output.exists() or output.stat().st_size > MAX_IMAGE_BYTES:
                raise TablePlaceholderError("table_placeholder_crop_failed")
            content = output.read_bytes()
            validate_image(content)
            with Image.open(io.BytesIO(content)) as image:
                if image.size != (right-left, bottom-top) or image.format != "PNG":
                    raise TablePlaceholderError("table_placeholder_crop_failed")
            return PdfCropResult(content, request.frame)

    def _run(self, args, output):
        try:
            with output.open("wb") as stream:
                result = subprocess.run(args, stdin=subprocess.DEVNULL, stdout=stream, stderr=subprocess.DEVNULL,
                                        timeout=self.timeout, check=False, env={**os.environ, "LC_ALL": "C"})
            if result.returncode:
                raise ValueError()
        except (OSError, ValueError, subprocess.TimeoutExpired):
            raise TablePlaceholderError("table_placeholder_crop_failed") from None
