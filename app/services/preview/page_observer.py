"""批准隔离域内的参考 native PDF/PNG observer；主进程只调用窄端口。"""

from __future__ import annotations

import argparse
import io
import importlib.metadata
import math
from pathlib import Path
import time
from typing import Protocol

from app.services.preview.models import PreviewPage, PreviewPolicy, sha256
from app.services.preview.page_quality import (
    ANALYZER_VERSION, NativeObject, PageObservation, PageObservationBatch, PageQualityPolicy,
    RasterObservation, page_region, policy_sha256,
)


class PageObservationProvider(Protocol):
    def observe(self, pdf: bytes, *, pages: tuple[PreviewPage, ...] = (), page_count: int,
                policy: PageQualityPolicy, preview_policy: PreviewPolicy,
                budget_seconds: float | None = None) -> PageObservationBatch: ...


def unavailable_observation(pdf: bytes, *, page_count: int, policy: PageQualityPolicy,
                            reason_code: str = "observer_unavailable") -> PageObservationBatch:
    return PageObservationBatch(status="incomplete", reason_code=reason_code, input_sha256=sha256(pdf),
        profile_id=policy.profile_id, profile_sha256=policy.profile_sha256, analyzer_version=policy.analyzer_version,
        policy_sha256=policy_sha256(policy), page_count=page_count)


class _ResourceExceeded(Exception):
    pass


def observer_fingerprints() -> dict[str, str]:
    """指纹覆盖实际入口字节和已加载运行时发行版，交由批准 profile 固定。"""
    from app.services.preview.page_quality import canonical_bytes
    versions = {name: importlib.metadata.version(name) for name in
                ("pdfminer.six", "Pillow", "charset-normalizer", "cryptography", "cffi", "pycparser",
                 "pydantic", "pydantic-core", "annotated-types", "typing-extensions", "typing-inspection")}
    return {"analyzer_sha256": sha256(Path(__file__).read_bytes()), "dependencies_sha256": sha256(canonical_bytes(versions))}


def _raster(png: PreviewPage, page: PageObservation, policy: PageQualityPolicy, max_pixels: int) -> RasterObservation:
    from PIL import Image, ImageChops, ImageDraw

    with Image.open(io.BytesIO(png.content)) as original:
        if original.format != "PNG" or original.size != (png.width, png.height) or png.width * png.height > max_pixels:
            raise ValueError("页面 PNG 尺寸或编码不符合声明。")
        original.load()
        if abs(png.width / png.height - page.width_pt / page.height_pt) > max(1 / png.height, page.width_pt / page.height_pt / png.width) * 2:
            raise ValueError("页面 PNG 与有效页面的比例不一致。")
        rgba = original.convert("RGBA")
        white = Image.new("RGBA", rgba.size, (255, 255, 255, 255))
        gray = Image.alpha_composite(white, rgba).convert("L")
    ink = gray.point(lambda value: 255 if value <= policy.ink_luminance_threshold else 0)
    region = page_region(policy, page)

    def pixel_box(box):
        return (round(box[0] * png.width), round(box[1] * png.height), round(box[2] * png.width), round(box[3] * png.height))

    body_ink, body_pixels = None, None
    if region:
        body_mask = Image.new("L", ink.size)
        draw = ImageDraw.Draw(body_mask)
        left, top, right, bottom = pixel_box(region.body_bbox)
        if right > left and bottom > top:
            draw.rectangle((left, top, right - 1, bottom - 1), fill=255)
        for box in region.exclusion_bboxes:
            left, top, right, bottom = pixel_box(box)
            if right > left and bottom > top:
                draw.rectangle((left, top, right - 1, bottom - 1), fill=0)
        body_pixels = body_mask.histogram()[255]
        body_ink = ImageChops.multiply(ink, body_mask).histogram()[255]
    band = policy.rules["clipping"].thresholds.get("edge_band_pt")
    edge_pixels, edge_ink = 0, 0
    if band is not None:
        edge_mask = Image.new("L", ink.size, 255)
        x = min((png.width + 1) // 2, max(1, math.ceil(band * png.width / page.width_pt)))
        y = min((png.height + 1) // 2, max(1, math.ceil(band * png.height / page.height_pt)))
        if png.width - x > x and png.height - y > y:
            ImageDraw.Draw(edge_mask).rectangle((x, y, png.width - x - 1, png.height - y - 1), fill=0)
        edge_pixels = edge_mask.histogram()[255]
        edge_ink = ImageChops.multiply(ink, edge_mask).histogram()[255]
    bbox = ink.getbbox()
    return RasterObservation(png_sha256=sha256(png.content), width=png.width, height=png.height,
        dpi_x=png.width / page.width_pt * 72, dpi_y=png.height / page.height_pt * 72,
        ink_pixels=ink.histogram()[255], total_pixels=png.width * png.height, body_ink_pixels=body_ink,
        body_pixels=body_pixels, edge_ink_pixels=edge_ink, edge_pixels=edge_pixels,
        content_bbox=tuple(value * (page.width_pt / png.width if i % 2 == 0 else page.height_pt / png.height) for i, value in enumerate(bbox)) if bbox else None)


def observe_native_preview(pdf: bytes, *, pages: tuple[PreviewPage, ...], page_count: int,
                           policy: PageQualityPolicy, max_page_pixels: int, budget_seconds: float) -> PageObservationBatch:
    """只供隔离入口及公开合成测试使用；任何预算耗尽都丢弃不完整尾部。"""
    started = time.monotonic()
    base = unavailable_observation(pdf, page_count=page_count, policy=policy)
    try:
        from pdfminer.converter import PDFPageAggregator
        from pdfminer.layout import LAParams, LTChar, LTContainer, LTCurve, LTImage, LTLine, LTRect, LTTextLine
        from pdfminer.pdfinterp import PDFPageInterpreter, PDFResourceManager
        from pdfminer.pdfpage import PDFPage
        from pdfminer.utils import apply_matrix_pt
        fingerprints = observer_fingerprints()
    except ImportError:
        return base
    base = base.model_copy(update=fingerprints)

    count = [0]

    def check():
        count[0] += 1
        if count[0] > policy.max_objects:
            raise _ResourceExceeded()
        if time.monotonic() - started >= budget_seconds:
            raise TimeoutError()

    class Aggregator(PDFPageAggregator):
        def begin_page(self, native_page, ctm):
            self.page_ctm = ctm
            self.unsupported = False
            super().begin_page(native_page, ctm)

        def render_char(self, *args, **kwargs):
            check()
            return super().render_char(*args, **kwargs)

        def render_image(self, *args, **kwargs):
            check()
            stream = args[1]
            if "SMask" in stream or "Mask" in stream:
                self.unsupported = True
            return super().render_image(*args, **kwargs)

        def paint_path(self, *args, **kwargs):
            check()
            return super().paint_path(*args, **kwargs)

    class Interpreter(PDFPageInterpreter):
        def execute(self, streams):
            if time.monotonic() - started >= budget_seconds:
                raise TimeoutError()
            return super().execute(streams)

        def do_W(self):
            self.device.unsupported = True
            return super().do_W()

        def do_W_a(self):
            self.device.unsupported = True
            return super().do_W_a()

        def do_gs(self, name):
            # pdfminer 不解释 ExtGState 的透明/混合属性，不能宣称完整可见几何。
            self.device.unsupported = True
            return super().do_gs(name)

        def do_Tr(self, render):
            if render != 0:
                self.device.unsupported = True
            return super().do_Tr(render)

        def do_Do(self, name):
            from pdfminer.pdftypes import stream_value
            from pdfminer.psparser import literal_name
            stream = self.xobjmap.get(literal_name(name))
            if stream is not None and str(stream_value(stream).get("Subtype")) == "/'Form'":
                self.device.unsupported = True
            return super().do_Do(name)

    observations = []
    try:
        if pages and (len(pages) != page_count or any(page.page_index != i for i, page in enumerate(pages))):
            raise ValueError("观测页面图必须完整且连续。")
        manager = PDFResourceManager(caching=False)
        device = Aggregator(manager, laparams=LAParams(all_texts=True))
        for index, native_page in enumerate(PDFPage.get_pages(io.BytesIO(pdf), caching=False, check_extractable=True)):
            if index >= page_count:
                raise ValueError("原生 PDF 页数与声明不一致。")
            interpreter = Interpreter(manager, device)
            interpreter.process_page(native_page)
            layout = device.get_result()
            crop = native_page.cropbox
            media = native_page.mediabox
            effective = (max(crop[0], media[0]), max(crop[1], media[1]), min(crop[2], media[2]), min(crop[3], media[3]))
            points = [apply_matrix_pt(device.page_ctm, point) for point in ((effective[0], effective[1]), (effective[2], effective[1]), (effective[0], effective[3]), (effective[2], effective[3]))]
            x0, y0 = min(p[0] for p in points), min(p[1] for p in points)
            x1, y1 = max(p[0] for p in points), max(p[1] for p in points)
            objects, unsupported = [], device.unsupported or native_page.attrs.get("UserUnit", 1) != 1

            def walk(node, line=None):
                nonlocal unsupported
                if isinstance(node, LTTextLine):
                    line = "line:" + str(len(objects))
                if isinstance(node, (LTChar, LTImage, LTCurve)):
                    kind = "char" if isinstance(node, LTChar) else "image" if isinstance(node, LTImage) else "path"
                    role = "decoration" if isinstance(node, LTLine) or isinstance(node, LTRect) and not node.fill else "foreground"
                    if isinstance(node, LTCurve) and not isinstance(node, (LTRect, LTLine)):
                        unsupported = True
                    box = (node.x0 - x0, y1 - node.y1, node.x1 - x0, y1 - node.y0)
                    objects.append(NativeObject(object_id=f"leaf:{len(objects)}", kind=kind, bbox=box, text_line_id=line if kind == "char" else None, role=role))
                elif isinstance(node, LTContainer):
                    for child in node:
                        walk(child, line)

            walk(layout)
            observation = PageObservation(preview_page_index=index, width_pt=x1 - x0, height_pt=y1 - y0,
                crop_box=tuple(float(v) for v in effective), rotation=native_page.rotate, geometry_supported=not unsupported,
                reason_code="geometry_unsupported" if unsupported else None, objects=tuple(objects))
            if pages:
                observation = observation.model_copy(update={"raster": _raster(pages[index], observation, policy, max_page_pixels)})
            observations.append(observation)
        if len(observations) != page_count:
            raise ValueError("原生 PDF 页数与声明不一致。")
        if time.monotonic() - started >= budget_seconds:
            raise TimeoutError()
        return base.model_copy(update={"status": "ok", "reason_code": None, "pages": tuple(observations), **fingerprints})
    except _ResourceExceeded:
        return base.model_copy(update={"reason_code": "resource_exceeded"})
    except TimeoutError:
        return base.model_copy(update={"reason_code": "observer_timeout"})
    except Exception:
        # 解码器的任意错误不携带文本/对象 repr，隔离协议只允许固定原因。
        return base.model_copy(update={"reason_code": "invalid_observation"})


def execute_observe_request(request, root: Path):
    """正式 launcher 可调用的参考入口；路径固定且所有输入重算身份。"""
    from app.services.preview.executor_protocol import ObserveResult
    from app.services.preview.sandbox_adapter import SandboxWordPreviewProvider

    if (request.profile_id != request.policy.profile_id or request.profile_sha256 != request.policy.profile_sha256
            or request.analyzer_version != ANALYZER_VERSION or request.page_count > request.limits.max_pages
            or request.input.path != "preview.pdf" or request.input.mime_type != "application/pdf"):
        raise ValueError("观测请求的身份或预算无效。")

    def read(descriptor, expected, mime):
        if descriptor.path != expected or descriptor.mime_type != mime:
            raise ValueError("观测输入路径或类型无效。")
        content = SandboxWordPreviewProvider._read_regular(root / expected, request.limits.max_temp_bytes)
        if len(content) != descriptor.size_bytes or sha256(content) != descriptor.sha256:
            raise ValueError("观测输入身份不一致。")
        return content

    pdf = read(request.input, "preview.pdf", "application/pdf")
    pages = tuple(PreviewPage(page_index=i, content=read(page, f"page-{i:06d}.png", "image/png"), width=page.width, height=page.height)
                  for i, page in enumerate(request.pages) if page.page_index == i)
    if len(pages) != len(request.pages):
        raise ValueError("观测页面序号无效。")
    batch = observe_native_preview(pdf, pages=pages, page_count=request.page_count, policy=request.policy,
        max_page_pixels=request.limits.max_page_pixels, budget_seconds=request.budget_ms / 1000)
    return ObserveResult(observation=batch)


def main() -> int:
    from app.services.preview.executor_protocol import OBSERVE_PROTOCOL, ObserveRequest

    parser = argparse.ArgumentParser(description="派生 Word 预览的隔离观测参考入口。")
    parser.add_argument("--protocol", required=True, choices=[OBSERVE_PROTOCOL])
    parser.add_argument("--request", type=Path, required=True)
    parser.add_argument("--result", type=Path, required=True)
    args = parser.parse_args()
    request = ObserveRequest.model_validate_json(args.request.read_bytes())
    result = execute_observe_request(request, args.request.parent)
    args.result.write_text(result.model_dump_json(), encoding="utf-8")
    return 0 if result.observation.status == "ok" else 21


if __name__ == "__main__":
    raise SystemExit(main())
