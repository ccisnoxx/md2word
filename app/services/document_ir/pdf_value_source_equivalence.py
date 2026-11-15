"""用有界的逐页 Poppler 观测核对参数值列取证的 PDF 版面。"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from math import ceil
from pathlib import Path
import re
import shutil
from xml.etree import ElementTree

from app.services.document_ir.pdf_value_column_observer import (
    PdfObservationUnavailable,
    _matching_poppler_version,
    _observation_timeout,
    _page_frame,
    _read_poppler,
    _read_xml,
    _word_boxes,
)
from app.services.document_ir.table_placeholder import MAX_PIXELS, canonical_hash

_MAX_PAGES = 200
_RASTER_DPIS = (96, 144)
_PPM_HEADER = re.compile(rb"P6\n([1-9][0-9]{0,8}) ([1-9][0-9]{0,8})\n255\n")


@dataclass(frozen=True, slots=True)
class PdfPageComparison:
    """只保存一一对应的整份页面观测，不持久化词或像素。"""

    page_count: int
    poppler_version: str
    observation_sha256: str
    page_sizes: tuple[tuple[float, float], ...]


def _complete_word_digest(xml: bytes, width: float, height: float) -> str:
    root = _read_xml(xml)
    words = _word_boxes(root, (0.0, 0.0, width, height))
    # 原取证可以忽略出框的词。全页比对须保留全部词框，无法核实时拒绝。
    if len(words) != len(root.findall(".//{*}word")):
        raise PdfObservationUnavailable()
    return canonical_hash(words)


def _raster_digest(
    tool: str, path: Path, options: list[str], width: float, height: float, dpi: int, *, deadline: float,
) -> str:
    # pdfinfo 的页框有显示精度限制，给实际栅格尺寸预留一像素并在跑前限制资源。
    max_width = ceil(width * (dpi / 72)) + 1
    max_height = ceil(height * (dpi / 72)) + 1
    pixels = max_width * max_height
    if pixels > MAX_PIXELS:
        raise PdfObservationUnavailable()
    data = _read_poppler(
        [tool, *options, "-r", str(dpi), "-singlefile", str(path)],
        max_bytes=3 * pixels + 64, deadline=deadline,
    )
    header = _PPM_HEADER.match(data)
    if header is None:
        raise PdfObservationUnavailable()
    actual_width, actual_height = (int(value) for value in header.groups())
    if (not max_width - 2 <= actual_width <= max_width or not max_height - 2 <= actual_height <= max_height
            or len(data) - header.end() != 3 * actual_width * actual_height):
        raise PdfObservationUnavailable()
    return sha256(data).hexdigest()


def compare_pdf_pages(source: Path, returned: Path, *, deadline: float) -> PdfPageComparison | None:
    """同序逐页核对帧、完整词框和两档像素。工具异常及耗尽时限保留既有取证原因。"""
    _observation_timeout(deadline)
    tool_paths = [shutil.which(name) or "" for name in ("pdfinfo", "pdftotext", "pdftoppm")]
    if not all(tool_paths):
        raise PdfObservationUnavailable()
    info_tool, text_tool, raster_tool = tool_paths
    version = _matching_poppler_version(tool_paths, deadline=deadline)
    try:
        paths = (source.resolve(), returned.resolve())
        info = tuple(
            _read_poppler(
                [info_tool, "-f", "1", "-l", str(_MAX_PAGES), "-box", str(path)],
                max_bytes=256 * 1024, deadline=deadline,
            ).decode(errors="replace")
            for path in paths
        )
        source_count, returned_count = (_page_frame(item, 0)[2] for item in info)
        if source_count != returned_count:
            return None
        if source_count > _MAX_PAGES:
            raise PdfObservationUnavailable()

        observations = []
        for index in range(source_count):
            frame, returned_frame = (_page_frame(item, index) for item in info)
            if frame != returned_frame:
                return None
            width, height, _ = frame
            page_number = str(index + 1)
            options = ["-f", page_number, "-l", page_number]
            words, returned_words = (
                _complete_word_digest(
                    _read_poppler([text_tool, *options, "-bbox-layout", str(path), "-"], deadline=deadline),
                    width, height,
                )
                for path in paths
            )
            if words != returned_words:
                return None
            rasters = []
            for dpi in _RASTER_DPIS:
                image, returned_image = (
                    _raster_digest(raster_tool, path, options, width, height, dpi, deadline=deadline) for path in paths
                )
                if image != returned_image:
                    return None
                rasters.append(image)
            observations.append((width, height, words, rasters))
    except PdfObservationUnavailable:
        raise
    except (OSError, ElementTree.ParseError, KeyError, ValueError, OverflowError) as exc:
        raise PdfObservationUnavailable() from exc
    digest = canonical_hash(("poppler-pdf-page-comparison/v1", version, _RASTER_DPIS, observations))
    page_sizes = tuple((width, height) for width, height, _, _ in observations)
    _observation_timeout(deadline)
    return PdfPageComparison(source_count, version, digest.removeprefix("sha256:"), page_sizes)
