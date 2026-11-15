"""经 Poppler 同页对账的 PDF 词框、可见字形与轴向绘制。"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
from threading import Timer
from xml.etree import ElementTree

Box = tuple[float, float, float, float]
Point = tuple[float, float]
AxisSegment = tuple[float, float, float]

_SVG = "{http://www.w3.org/2000/svg}"
_HREF = "{http://www.w3.org/1999/xlink}href"
_MAX_OUTPUT_BYTES = 4 * 1024 * 1024
_MAX_ELEMENTS = 12_000
_MAX_WORDS = 4096
_TIMEOUT_SECONDS = 15
_COORDINATE_TOLERANCE = 0.02
_INK_TOLERANCE = 0.35


class PdfObservationUnavailable(ValueError):
    """无法完成首版 PDF 取证时，交由人工核定。"""

    def __init__(self, reason: str = "pdf_observation_unavailable") -> None:
        super().__init__(reason)
        self.reason = reason


@dataclass(frozen=True)
class PdfValueColumnWord:
    text: str
    bbox: Box
    glyphs: tuple[Point, ...]


@dataclass(frozen=True)
class PdfValueColumnPage:
    width: float
    height: float
    page_count: int
    words: tuple[PdfValueColumnWord, ...]
    rectangles: tuple[Box, ...]
    horizontal_lines: tuple[AxisSegment, ...]
    vertical_lines: tuple[AxisSegment, ...]
    extractor_version: str
    unsupported_regions: tuple[Box, ...] = ()
    unmapped_glyph_regions: tuple[Box, ...] = ()


_COLOR = re.compile(r"rgb\(([\d.]+)%,\s*([\d.]+)%,\s*([\d.]+)%\)")
_AXIS_TRANSFORM = re.compile(r"matrix\((-?1),\s*0,\s*0,\s*(-?1),\s*([+\-.\deE]+),\s*([+\-.\deE]+)\)")
_CLIP_REF = re.compile(r"url\(#([\w-]+)\)")


def _read_poppler(args: list[str], *, max_bytes: int = _MAX_OUTPUT_BYTES, version: bool = False) -> bytes:
    # 版本从 stderr 读取，XML 从 stdout 读取。读取在子进程退出前就受字节和时间上限约束。
    try:
        with subprocess.Popen(
            args, stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL if version else subprocess.PIPE,
            stderr=subprocess.PIPE if version else subprocess.DEVNULL,
            env={**os.environ, "LC_ALL": "C"},
        ) as process:
            stream = process.stderr if version else process.stdout
            assert stream is not None
            timer = Timer(_TIMEOUT_SECONDS, process.kill)
            timer.start()
            try:
                output = stream.read(max_bytes + 1)
                if len(output) > max_bytes:
                    process.kill()
                    raise PdfObservationUnavailable()
                if process.wait() != 0 or not output:
                    raise PdfObservationUnavailable()
            finally:
                timer.cancel()
    except OSError as exc:
        raise PdfObservationUnavailable() from exc
    return output


def _number(value: str) -> float:
    result = float(value)
    if not math.isfinite(result):
        raise ValueError("坐标或绘制参数不是有限数")
    return result


def _page_frame(info: str, page_index: int) -> tuple[float, float, int]:
    page = rf"Page[ \t]+{page_index + 1}[ \t]+"
    pages = re.findall(r"^Pages:[ \t]*(\d+)[ \t]*$", info, re.M)
    values = [
        re.findall(r"^" + page + name + r":[ \t]*([^\r\n]+)$", info, re.M)
        for name in ("rot", "MediaBox", "CropBox")
    ]
    if len(pages) != 1 or any(len(value) != 1 for value in values):
        raise PdfObservationUnavailable("pdf_geometry_unverified")
    count = int(pages[0])
    rotation, media, crop = (tuple(_number(n) for n in value[0].split()) for value in values)
    if (
        count <= page_index or rotation != (0,) or len(media) != 4 or media != crop
        or media[:2] != (0, 0) or min(media[2:]) <= 0
    ):
        raise PdfObservationUnavailable("pdf_geometry_unverified")
    return media[2], media[3], count


def _contains(outer: Box, inner: Box, tolerance: float = 0) -> bool:
    return (
        outer[0] - tolerance <= inner[0] and outer[1] - tolerance <= inner[1]
        and inner[2] <= outer[2] + tolerance and inner[3] <= outer[3] + tolerance
    )


def _intersection(a: Box, b: Box) -> Box | None:
    box = (max(a[0], b[0]), max(a[1], b[1]), min(a[2], b[2]), min(a[3], b[3]))
    return box if box[0] < box[2] and box[1] < box[3] else None


def _read_xml(data: bytes) -> ElementTree.Element:
    # pdftotext 输出外部 XHTML DOCTYPE。ElementTree 不取外部 DTD，内部实体另行拒绝。
    if re.search(rb"<!ENTITY\s", data, re.I):
        raise PdfObservationUnavailable()
    root = ElementTree.fromstring(data)
    if sum(1 for _ in root.iter()) > _MAX_ELEMENTS:
        raise PdfObservationUnavailable()
    return root


def _word_boxes(root: ElementTree.Element, frame: Box) -> list[tuple[str, Box]]:
    pages = root.findall(".//{*}page")
    if len(pages) != 1:
        raise PdfObservationUnavailable()
    if tuple(_number(pages[0].attrib[k]) for k in ("width", "height")) != frame[2:]:
        raise PdfObservationUnavailable("pdf_geometry_unverified")
    words = []
    for node in pages[0].findall(".//{*}word"):
        box = tuple(_number(node.attrib[k]) for k in ("xMin", "yMin", "xMax", "yMax"))
        if node.text and box[0] < box[2] and box[1] < box[3] and _contains(frame, box):
            words.append((node.text, box))
    if not words:
        raise PdfObservationUnavailable("pdf_text_unavailable")
    if len(words) > _MAX_WORDS:
        raise PdfObservationUnavailable()
    return words


def _rendered_word_indexes(
    root: ElementTree.Element, words: list[tuple[str, Box]], *, frame: Box, page_index: int, version: str,
) -> set[int]:
    pages = root.findall("page")
    if root.tag != "pdf2xml" or root.get("producer") != "poppler" or root.get("version") != version or len(pages) != 1:
        raise PdfObservationUnavailable()
    attrs = pages[0].attrib
    if (
        attrs.get("position") != "absolute" or int(attrs["number"]) != page_index + 1
        or (_number(attrs["left"]), _number(attrs["top"])) != (0, 0)
        or abs(_number(attrs["width"]) - frame[2]) >= 1 or abs(_number(attrs["height"]) - frame[3]) >= 1
    ):
        raise PdfObservationUnavailable("pdf_geometry_unverified")
    counts: Counter[int] = Counter()
    for run in pages[0].findall("text"):
        x, y, width, height = (_number(run.attrib[k]) for k in ("left", "top", "width", "height"))
        literal = "".join(run.itertext()).split()
        # ActualText 可能改变 pdftotext 的字面而不改变字形。经可见绘制设备独立核对同一整段文本。
        matched = sorted(
            (box[0], i, text) for i, (text, box) in enumerate(words)
            if abs(box[1] - y) <= _COORDINATE_TOLERANCE and abs(box[3] - y - height) <= _COORDINATE_TOLERANCE
            and x - _COORDINATE_TOLERANCE <= box[0] and box[2] <= x + width + _COORDINATE_TOLERANCE
        )
        if literal == [text for _, _, text in matched]:
            counts.update(i for _, i, _ in matched)
    return {i for i, count in counts.items() if count == 1}


@dataclass(frozen=True)
class _Stroke:
    start: Point
    end: Point


@dataclass(frozen=True)
class _Paint:
    bbox: Box
    kind: str
    glyph: Point | None = None
    stroke: _Stroke | None = None
    light: bool = False
    black: bool = False


@dataclass(frozen=True)
class _Clip:
    paths: tuple[tuple[Point, ...], ...]
    bounds: Box
    even_odd: bool = False


def _path_commands(value: str) -> list[tuple[str, tuple[Point, ...]]]:
    """读取 Cairo 实测的绝对坐标命令，含确定字形包围框所需的三次曲线。"""
    tokens = iter(value.split())
    commands = []
    for op in tokens:
        pairs = {"M": 1, "L": 1, "C": 3, "Z": 0}.get(op)
        if pairs is None:
            raise ValueError("未支持的 SVG 路径命令")
        points = tuple((_number(next(tokens, "")), _number(next(tokens, ""))) for _ in range(pairs))
        commands.append((op, points))
    if not commands or commands[0][0] != "M":
        raise ValueError("SVG 路径缺少起点")
    return commands


def _path_bounds(commands: list[tuple[str, tuple[Point, ...]]]) -> Box:
    points = [p for _, vertices in commands for p in vertices]
    return min(x for x, _ in points), min(y for _, y in points), max(x for x, _ in points), max(y for _, y in points)


def _linear_paths(commands: list[tuple[str, tuple[Point, ...]]]) -> tuple[tuple[Point, ...], ...]:
    # 只解释小型线性区域。Cairo 的裁剪可由两块紧邻矩形组成，Z 后可有一个独立 M。
    if len(commands) > 16:
        return ()
    paths: list[list[Point]] = []
    current: list[Point] = []
    for op, points in commands:
        if op == "C":
            return ()
        if op in {"Z", "M"} and len(current) > 1:
            paths.append(current)
            current = []
        if op == "M":
            current = [points[0]]
        elif op == "L":
            if not current:
                return ()
            current.append(points[0])
    if len(current) > 1:
        paths.append(current)
    return tuple(tuple(path) for path in paths) if all(len(path) >= 3 for path in paths) else ()


def _corners(box: Box) -> tuple[Point, ...]:
    left, top, right, bottom = box
    return (left, top), (right, top), (right, bottom), (left, bottom)


def _is_rectangle(paths: tuple[tuple[Point, ...], ...], bounds: Box) -> bool:
    return len(paths) == 1 and len(paths[0]) == 4 and set(paths[0]) == set(_corners(bounds)) and all(
        a[0] == b[0] or a[1] == b[1] for a, b in zip(paths[0], paths[0][1:] + paths[0][:1])
    )


def _inside_clips(box: Box, clips: tuple[_Clip, ...]) -> bool:
    # 只在能证明整个字形或色块留在裁剪区域时才接纳它。
    return all(_is_rectangle(clip.paths, clip.bounds) and _contains(clip.bounds, box) for clip in clips)


def _scanline(clip: _Clip, axis: int, offset: float) -> tuple[tuple[float, float], ...]:
    # 只计算黑色轴向线段实际与裁剪相交的中心线，不推定裁剪外的端点。
    across = 1 - axis
    crossings: Counter[float] = Counter()
    for path in clip.paths:
        for a, b in zip(path, path[1:] + path[:1]):
            if min(a[across], b[across]) <= offset < max(a[across], b[across]):
                fraction = (offset - a[across]) / (b[across] - a[across])
                crosses = a[axis] + fraction * (b[axis] - a[axis])
                crossings[crosses] += 1 if b[across] > a[across] else -1
    spans = []
    winding = 0
    start = 0.0
    for position, change in sorted(crossings.items()):
        before = bool(winding % 2 if clip.even_odd else winding)
        winding += change
        after = bool(winding % 2 if clip.even_odd else winding)
        if after and not before:
            start = position
        if before and not after:
            spans.append((start, position))
    return tuple(spans)


def _clipped_strokes(stroke: _Stroke, clips: tuple[_Clip, ...]) -> tuple[_Stroke, ...]:
    start, end = stroke.start, stroke.end
    axis = 0 if start[1] == end[1] else 1
    offset = start[1 - axis]
    spans = [(min(start[axis], end[axis]), max(start[axis], end[axis]))]
    for clip in clips:
        spans = [
            (max(lo, left), min(hi, right))
            for lo, hi in spans for left, right in _scanline(clip, axis, offset)
            if max(lo, left) < min(hi, right)
        ]
    if axis == 0:
        return tuple(_Stroke((a, offset), (b, offset)) for a, b in spans)
    return tuple(_Stroke((offset, a), (offset, b)) for a, b in spans)


def _straight_segments(commands: list[tuple[str, tuple[Point, ...]]]) -> tuple[_Stroke, ...]:
    segments = []
    first = last = (0.0, 0.0)
    for op, points in commands:
        if op == "C":
            return ()
        end = points[0] if points else first
        if op == "M":
            first = end
        elif end != last:
            if end[0] != last[0] and end[1] != last[1]:
                return ()
            segments.append(_Stroke(last, end))
        last = end
    return tuple(segments)


def _offset(box: Box, point: Point) -> Box:
    return box[0] + point[0], box[1] + point[1], box[2] + point[0], box[3] + point[1]


def _color(value: str) -> tuple[float, ...]:
    match = _COLOR.fullmatch(value)
    return tuple(_number(channel) for channel in match.groups()) if match else ()


def _stroke_bbox(segment: _Stroke, radius: float) -> Box:
    x0, y0 = segment.start
    x1, y1 = segment.end
    return min(x0, x1) - radius, min(y0, y1) - radius, max(x0, x1) + radius, max(y0, y1) + radius


def _paint_path(node: ElementTree.Element, region: Box, clips: tuple[_Clip, ...]) -> list[_Paint]:
    attrs = node.attrib
    transform = attrs.get("transform")
    match = _AXIS_TRANSFORM.fullmatch(transform) if transform is not None else None
    if (transform is not None and match is None) or len(node):
        return [_Paint(region, "unsupported")]
    commands = _path_commands(attrs["d"])
    if match:
        # 原生 PDF 的左下原点在 Cairo 轴线输出中可能保留为 y 轴反射。
        sx, sy, tx, ty = (_number(value) for value in match.groups())
        commands = [(op, tuple((sx * x + tx, sy * y + ty) for x, y in points)) for op, points in commands]
    bounds = _path_bounds(commands)
    stroke_color = _color(attrs.get("stroke", ""))
    stroke_keys = {
        "d", "fill", "stroke", "stroke-opacity", "stroke-width", "stroke-linecap",
        "stroke-linejoin", "stroke-miterlimit", "transform",
    }
    fill_keys = {"d", "fill", "fill-opacity", "fill-rule", "transform"}
    if "stroke-width" in attrs:
        width = _number(attrs["stroke-width"])
        clipped_paint = _intersection(region, (bounds[0] - width, bounds[1] - width, bounds[2] + width, bounds[3] + width))
        if clipped_paint is None:
            return []
        if (
            attrs.keys() <= stroke_keys and width > 0 and attrs.get("fill") == "none"
            and stroke_color == (0, 0, 0) and attrs.get("stroke-opacity", "1") == "1"
            and attrs.get("stroke-linecap", "butt") in {"butt", "round", "square"}
            and (segments := _straight_segments(commands))
        ):
            return [
                _Paint(paint_bbox, "stroke", stroke=clipped, black=True)
                for segment in segments for clipped in _clipped_strokes(segment, clips)
                if (paint_bbox := _intersection(_stroke_bbox(clipped, width / 2), region)) is not None
            ]
        return [_Paint(clipped_paint, "unsupported")]
    clipped_paint = _intersection(region, bounds)
    if clipped_paint is None:
        return []
    fill = _color(attrs.get("fill", ""))
    paths = _linear_paths(commands)
    if (
        attrs.keys() <= fill_keys and fill and attrs.get("fill-opacity", "1") == "1"
        and _is_rectangle(paths, bounds)
        and _inside_clips(bounds, clips) and _contains(region, bounds)
    ):
        # 灰底/白底的黑色字形仍有反差。深色不透明填充与黑字相交时保守放弃。
        return [_Paint(bounds, "rect", light=min(fill) >= 70)]
    return [_Paint(clipped_paint, "unsupported")]


def _glyph_definition(node: ElementTree.Element) -> tuple[bool, Box | None]:
    if node.tag == _SVG + "symbol":
        # 新版 Cairo 用 g 替代同义的 overflow=visible symbol。
        expected = {"id", "overflow"}
        if node.get("overflow") != "visible":
            return False, None
    elif node.tag == _SVG + "g":
        expected = {"id"}
    else:
        return False, None
    if node.attrib.keys() - expected or len(node) > 1:
        return False, None
    if not len(node):
        return True, None
    child = node[0]
    if child.tag != _SVG + "path" or set(child.attrib) != {"d"} or len(child):
        return False, None
    path = _path_commands(child.attrib["d"])
    box = _path_bounds(path)
    return (True, box) if any(op == "Z" for op, _ in path) and box[0] < box[2] and box[1] < box[3] else (False, None)


def _clip_definition(node: ElementTree.Element) -> _Clip | None:
    if node.tag == _SVG + "clipPath" and set(node.attrib) == {"id"} and len(node) == 1:
        child = node[0]
        if (
            child.tag == _SVG + "path" and "d" in child.attrib and child.attrib.keys() <= {"d", "clip-rule"}
            and child.get("clip-rule", "nonzero") in {"nonzero", "evenodd"}
        ):
            commands = _path_commands(child.attrib["d"])
            if paths := _linear_paths(commands):
                return _Clip(paths, _path_bounds(commands), even_odd=child.get("clip-rule") == "evenodd")
    return None


def _svg_paint(root: ElementTree.Element, frame: Box) -> list[_Paint]:
    if root.tag != _SVG + "svg" or tuple(_number(x) for x in root.attrib["viewBox"].split()) != frame:
        raise PdfObservationUnavailable("pdf_geometry_unverified")
    if root.attrib.keys() - {"viewBox", "width", "height", "version"}:
        raise PdfObservationUnavailable()
    # 把实际页的边框作为第一层裁剪，不为超出 MediaBox 的路径提供证据。
    definitions: dict[str, ElementTree.Element] = {}
    for defs in root.findall(_SVG + "defs"):
        for node in defs.iter():
            if "id" in node.attrib:
                identifier = node.attrib["id"]
                if identifier in definitions:
                    raise PdfObservationUnavailable()
                definitions[identifier] = node
    glyphs = {
        name: box for name, node in definitions.items()
        if name.startswith("glyph-") for supported, box in (_glyph_definition(node),) if supported
    }
    clips = {name: _clip_definition(node) for name, node in definitions.items() if node.tag == _SVG + "clipPath"}
    paint: list[_Paint] = []

    def visit(node: ElementTree.Element, region: Box, chain: tuple[_Clip, ...], *, depth: int) -> None:
        attrs = node.attrib
        if depth > 8:
            raise PdfObservationUnavailable()
        if node.tag == _SVG + "path":
            paint.extend(_paint_path(node, region, chain))
        elif node.tag == _SVG + "g" and attrs.keys() <= {"id"}:
            for child in node:
                visit(child, region, chain, depth=depth + 1)
        elif node.tag == _SVG + "g" and set(attrs) == {"clip-path"}:
            match = _CLIP_REF.fullmatch(attrs["clip-path"])
            clip = clips.get(match[1]) if match else None
            if clip is None:
                paint.append(_Paint(region, "unsupported"))
                return
            if (clip_region := _intersection(region, clip.bounds)) is not None:
                for child in node:
                    visit(child, clip_region, (*chain, clip), depth=depth + 1)
        elif node.tag == _SVG + "g" and attrs.keys() <= {"fill", "fill-opacity"} and "fill" in attrs:
            black = _color(attrs["fill"]) == (0, 0, 0) and attrs.get("fill-opacity", "1") == "1"
            for child in node:
                if child.tag != _SVG + "use" or set(child.attrib) != {"x", "y", _HREF} or len(child):
                    paint.append(_Paint(region, "unsupported"))
                    continue
                ref = child.attrib[_HREF].removeprefix("#")
                if child.attrib[_HREF] != "#" + ref or ref not in glyphs:
                    paint.append(_Paint(region, "unsupported"))
                    continue
                if (shape := glyphs[ref]) is None:
                    continue
                point = (_number(child.attrib["x"]), _number(child.attrib["y"]))
                glyph_box = _offset(shape, point)
                if (clipped := _intersection(glyph_box, region)) is not None:
                    fully_drawn = black and _contains(region, glyph_box) and _inside_clips(glyph_box, chain)
                    paint.append(_Paint(clipped, "glyph", glyph=point, black=fully_drawn))
        elif node.tag != _SVG + "defs":
            paint.append(_Paint(region, "unsupported"))

    for child in root:
        visit(child, frame, (_Clip((_corners(frame),), frame),), depth=0)
        if len(paint) > _MAX_ELEMENTS:
            raise PdfObservationUnavailable()
    return paint


def _observe_words(
    words: list[tuple[str, Box]], paint: list[_Paint], rendered_indexes: set[int],
) -> tuple[tuple[PdfValueColumnWord, ...], tuple[Box, ...]]:
    shapes = [(i, mark) for i, mark in enumerate(paint) if mark.glyph is None]
    glyphs = [(i, mark.glyph, mark) for i, mark in enumerate(paint) if mark.glyph is not None]
    by_word = []
    owners: Counter[int] = Counter()
    for _, (left, top, right, bottom) in words:
        # 最右边界附近的锚点可属于下一个词（如 T_A 的下标）。使用半开范围保留这一侧。
        hits = [
            (i, point, mark) for i, point, mark in glyphs
            if left - _COORDINATE_TOLERANCE <= point[0] < right - _COORDINATE_TOLERANCE
            and top - _COORDINATE_TOLERANCE <= point[1] <= bottom + _COORDINATE_TOLERANCE
        ]
        by_word.append(hits)
        owners.update(i for i, _, _ in hits)

    result = []
    mapped = set()
    for index, ((text, box), hits) in enumerate(zip(words, by_word)):
        glyph_anchors: tuple[Point, ...] = ()
        if index in rendered_indexes and len(hits) == len(text) and all(
            owners[i] == 1 and mark.black and _contains(box, mark.bbox, _INK_TOLERANCE)
            and not any(
                _intersection(shape.bbox, mark.bbox) is not None
                and (shape.kind == "unsupported" or not shape.light or order > i)
                for order, shape in shapes
            )
            for i, _, mark in hits
        ):
            anchors = tuple(sorted(point for _, point, _ in hits))
            if (
                abs(anchors[0][0] - box[0]) <= _COORDINATE_TOLERANCE
                and all(prev[0] < next_[0] for prev, next_ in zip(anchors, anchors[1:]))
            ):
                glyph_anchors = anchors
                mapped.update(i for i, _, _ in hits)
        result.append(PdfValueColumnWord(text, box, glyph_anchors))
    # 释放一个 Grid 格之前要确认该区域没有未能还原成词的实际字形。
    return tuple(result), tuple(mark.bbox for i, _, mark in glyphs if i not in mapped)


def _geometry(
    paint: list[_Paint],
) -> tuple[tuple[Box, ...], tuple[AxisSegment, ...], tuple[AxisSegment, ...], tuple[Box, ...]]:
    rectangles, horizontal, vertical, unsupported = [], [], [], []
    for i, mark in enumerate(paint):
        if mark.kind == "unsupported":
            unsupported.append(mark.bbox)
        if mark.kind not in {"rect", "stroke"}:
            continue
        if any(later.kind == "rect" and _intersection(mark.bbox, later.bbox) for later in paint[i + 1:]):
            continue
        if mark.kind == "rect" and mark.light:
            rectangles.append(mark.bbox)
        if mark.stroke is not None:
            x0, y0 = mark.stroke.start
            x1, y1 = mark.stroke.end
            if y0 == y1:
                horizontal.append((min(x0, x1), y0, max(x0, x1)))
            else:
                vertical.append((x0, min(y0, y1), max(y0, y1)))
    return tuple(rectangles), tuple(horizontal), tuple(vertical), tuple(unsupported)


def observe_pdf_value_column_page(pdf_path: Path, *, page_index: int) -> PdfValueColumnPage:
    """观察左上原点的轴向页面，未核实的图形保留其区域供上层拒绝。"""
    if type(page_index) is not int or page_index < 0:
        raise PdfObservationUnavailable("pdf_geometry_unverified")
    tool_paths = [shutil.which(name) for name in ("pdfinfo", "pdftotext", "pdftocairo", "pdftohtml")]
    if not all(tool_paths):
        raise PdfObservationUnavailable()
    source = str(pdf_path.resolve())
    options = ["-f", str(page_index + 1), "-l", str(page_index + 1)]
    try:
        info_tool, text_tool, cairo_tool, html_tool = tool_paths
        versions = []
        for utility in tool_paths:
            output = _read_poppler([utility, "-v"], max_bytes=4096, version=True)
            match = re.match(rb"[\w]+\s+version\s+([\d.]+)(?:\r?\n| )", output)
            if match is None:
                raise PdfObservationUnavailable()
            versions.append(match[1].decode("ascii"))
        if len(set(versions)) != 1:
            raise PdfObservationUnavailable()
        info = _read_poppler([info_tool, *options, "-box", source], max_bytes=64 * 1024)
        width, height, count = _page_frame(info.decode(errors="replace"), page_index)
        frame = (0.0, 0.0, width, height)
        xhtml = _read_xml(_read_poppler([text_tool, *options, "-bbox-layout", source, "-"]))
        words = _word_boxes(xhtml, frame)
        rendered_xml = _read_xml(_read_poppler([
            html_tool, *options, "-xml", "-i", "-stdout", "-zoom", "1", "-noroundcoord", "-nomerge", source,
        ]))
        rendered_indexes = _rendered_word_indexes(
            rendered_xml, words, frame=frame, page_index=page_index, version=versions[0],
        )
        svg = _read_xml(_read_poppler([cairo_tool, *options, "-svg", source, "-"]))
        paint = _svg_paint(svg, frame)
        rectangles, horizontal, vertical, unsupported = _geometry(paint)
        observed_words, unmapped = _observe_words(words, paint, rendered_indexes)
        return PdfValueColumnPage(
            width, height, count, observed_words, rectangles, horizontal, vertical,
            f"poppler-value-geometry/v1:{versions[0]}", unsupported, unmapped,
        )
    except PdfObservationUnavailable:
        raise
    except (ElementTree.ParseError, KeyError, ValueError) as exc:
        raise PdfObservationUnavailable() from exc
