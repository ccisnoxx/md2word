"""图片写前输入、几何和最终包认证；不负责图片归组或任务状态。"""

from __future__ import annotations

import hashlib
import io
import math
import re
import zipfile
from pathlib import PurePosixPath
from typing import Any
from xml.etree import ElementTree as ET

from docx import Document
from docx.oxml.ns import qn
from docx.shared import Twips
from docx.image.exceptions import InvalidImageStreamError, UnexpectedEndOfFileError, UnrecognizedImageError

from app.conversion.docx_rules.formula import canonical_sha256, output_sha256, sha256_text
from app.conversion.docx_rules.terminology import TerminologyReplacer
from app.services.document_ir.models import DocumentIR
from app.services.renderer.layout_plan import IMAGE_GROUP_VERSION, IMAGE_GROUP_THRESHOLDS, build_image_plan, build_layout_plan, image_annotations
from app.services.renderer.template_config import TemplateConfigPackage, TemplateParagraphStyleConfig
from app.services.renderer.text_renderer import WordTextRendererMixin

IMAGE_REPORT_VERSION = "image-layout/v1"
IMAGE_INPUTS_VERSION = "image-render-inputs/v1"
IMAGE_PROJECTION_VERSION = "image-annotation-output/v1"
IMAGE_WRITER_VERSION = "image-writer/v1"
# B1 构建仅替换此生成常量；reader 始终解释两种原文件策略。
IMAGE_GENERATION_POLICY = "grouped/v1"
IMAGE_TABLE_PREFIX = "md2w_image_layout:"
IMAGE_EVIDENCE_KEYS = frozenset({"image_layout_report", "image_layout_summary", "expected_layout_table_count",
    "layout_table_count", "layout_table_count_delta", "expected_content_table_count", "content_table_count",
    "content_table_count_delta", "expected_total_table_count", "total_table_count", "total_table_count_delta"})
_NS = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
       "wp": "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing",
       "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
       "pic": "http://schemas.openxmlformats.org/drawingml/2006/picture"}


def image_anchor(block_id: str, field: str = "image") -> str:
    return "md2w_img_" + hashlib.sha256(f"{block_id}/{field}".encode()).hexdigest()[:28]


def source_image_position(block: Any) -> dict:
    """无效坐标仅禁用并排；私有报告以 null 确定保存非有限坐标，不改写 IR。"""
    box = block.layout.bbox if block.layout else None
    return {"page_index": block.page_index, "order": block.order,
            "bbox": [value if math.isfinite(value) else None for value in box] if box is not None else None}


def caption_bookmark_inventory(document_ir: DocumentIR) -> dict:
    """图片投影与正式正文使用相同的唯一题注编号规则。"""
    from collections import Counter
    text_renderer = WordTextRendererMixin()
    keys = []
    for block in document_ir.blocks:
        values = image_annotations(block) if block.type == "image" else tuple(("", t) for t in dict.fromkeys(t.strip() for t in block.captions) if t) if block.type == "table" else ()
        for _, text in values:
            parsed = text_renderer._parse_caption_text(text)
            if parsed:
                _, label, _, number, _ = parsed
                keys.append(("figure" if label.lower() == "figure" or label == "图" else "table", number))
    counts = Counter(keys)
    result = {}
    for key in keys:
        if counts[key] == 1 and key not in result:
            result[key] = (f"_md2word_{key[0]}_{key[1]}", len(result) + 1)
    return result


def section_geometry(sect_pr: Any) -> dict[str, Any]:
    """读取实际 section；原始尺寸/边距/栏距为 twip，有效宽高为 EMU。"""
    size = sect_pr.find(qn("w:pgSz"))
    margins = sect_pr.find(qn("w:pgMar"))
    columns = sect_pr.find(qn("w:cols"))
    if size is None or margins is None:
        raise ValueError("图片布局缺少有效页面几何")
    geometry = {key: int(size.get(qn("w:" + key))) for key in ("w", "h")}
    geometry["orientation"] = size.get(qn("w:orient"), "portrait")
    geometry["margins"] = {key: int(margins.get(qn("w:" + key), "0")) for key in ("top", "bottom", "left", "right", "header", "footer", "gutter")}
    geometry["columns"] = int(columns.get(qn("w:num"), "1")) if columns is not None else 1
    geometry["column_space"] = int(columns.get(qn("w:space"), "720")) if columns is not None else 720
    usable = geometry["w"] - geometry["margins"]["left"] - geometry["margins"]["right"] - geometry["margins"]["gutter"]
    geometry["effective_width"] = int(Twips((usable - geometry["column_space"] * (geometry["columns"] - 1)) / geometry["columns"]))
    geometry["effective_height"] = int(Twips(geometry["h"] - geometry["margins"]["top"] - geometry["margins"]["bottom"]))
    if geometry["effective_width"] <= 0 or geometry["effective_height"] <= 0:
        raise ValueError("图片布局的有效区域为空")
    return geometry


def image_slots(blocks: list, page_width: float, geometry: dict) -> tuple[int, list[dict]]:
    """以相邻间隔中点划 slot，半间隔已经包含在列宽内。"""
    boxes = [block.layout.bbox for block in blocks]
    scale = geometry["effective_width"] / page_width
    boundaries = [boxes[0][0]] + [(left[2] + right[0]) / 2 for left, right in zip(boxes, boxes[1:])] + [boxes[-1][2]]
    positions = [round((value - boundaries[0]) * scale / 635) for value in boundaries]
    slots = []
    for i, box in enumerate(boxes):
        width = positions[i + 1] - positions[i]
        left = round((box[0] - boundaries[i]) * scale / 635)
        right = round((boundaries[i + 1] - box[2]) * scale / 635)
        slots.append({"width": width, "left": left, "right": right, "inner_width": int(Twips(width - left - right))})
    return positions[-1], slots


def image_dimensions(pixel_width: int, pixel_height: int, width: int, height: int) -> tuple[int, int]:
    scale = min(width / pixel_width, height / pixel_height)
    return round(pixel_width * scale), round(pixel_height * scale)


def single_image_width(block: Any, page_width: float | None, geometry: dict) -> int:
    available = geometry["effective_width"]
    box = block.layout.bbox if block.layout else None
    if (box is None or page_width is None or not math.isfinite(page_width) or page_width <= 0
            or not all(math.isfinite(value) for value in box) or box[2] <= box[0]):
        return available
    return max(1, min(available, int(available * (box[2] - box[0]) / (page_width / geometry["columns"]))))


def annotation_projection(paragraph: Any) -> str:
    """绑定可见 run、字段、富文本和数学，忽略位置锚点及段落排版。"""
    nodes = []
    for node in paragraph:
        if node.tag in {qn("w:pPr"), qn("w:bookmarkStart"), qn("w:bookmarkEnd")}:
            continue
        nodes.append(node)
    return output_sha256(nodes)


def expected_annotation(text: str, inputs: dict, bookmarks: dict) -> str:
    """仅由源字符串和冻结语义生成预期，不读取最终 DOCX。"""
    renderer = WordTextRendererMixin()
    paragraph = Document().add_paragraph()
    style = TemplateParagraphStyleConfig.model_validate(inputs["caption_style"])
    rules = TerminologyReplacer.from_frozen_rules(inputs["format_rules"]["rules"])
    if not renderer._fill_caption_paragraph(paragraph, text, style, terminology=rules, caption_bookmarks=bookmarks):
        renderer._fill_paragraph(paragraph, text, style, terminology=rules, reference_bookmarks=bookmarks)
    return annotation_projection(paragraph._p)


def new_image_report(document_ir: DocumentIR, *, template_config: TemplateConfigPackage, template_content: bytes | None,
                     config_content: bytes | None, template_version_id: str | None, language: str) -> dict:
    terminology = template_config.terminology
    inputs = {"schema_version": IMAGE_INPUTS_VERSION, "projection_version": IMAGE_PROJECTION_VERSION,
              "writer_version": IMAGE_WRITER_VERSION, "rule_version": IMAGE_GROUP_VERSION,
              "generation_policy": IMAGE_GENERATION_POLICY, "document_language": language,
              "template": {"version_id": template_version_id,
                  "docx": {"kind": "file" if template_content is not None else "builtin/python-docx/v1", "sha256": hashlib.sha256(template_content).hexdigest() if template_content is not None else None},
                  "config": {"kind": "file" if config_content is not None else "builtin/template-config/v1", "sha256": hashlib.sha256(config_content).hexdigest() if config_content is not None else None}},
              "caption_style": template_config.caption.model_dump(mode="json"),
              "format_rules": {"kind": "file" if terminology is not None and terminology.content_sha256 else "builtin/format-rules/v1",
                  "content_sha256": terminology.content_sha256 if terminology is not None else None,
                  "rules": terminology.freeze_rules() if terminology is not None else []}, "spans": []}
    return {"schema_version": IMAGE_REPORT_VERSION, "rule_version": IMAGE_GROUP_VERSION,
            "thresholds": dict(IMAGE_GROUP_THRESHOLDS), "source_ir_sha256": canonical_sha256(document_ir.model_dump(mode="json")),
            "render_inputs": inputs, "render_inputs_sha256": None, "spans": []}


def finish_image_report(report: dict) -> dict:
    report["render_inputs_sha256"] = canonical_sha256(report["render_inputs"])
    return report


class _ImageEvidenceError(ValueError):
    """只允许固定、安全的检查原因进入执行事件。"""


def _check(condition: bool, message: str) -> None:
    if not condition:
        raise _ImageEvidenceError("图片布局证据无效：" + message)


def _actual_section(body: Any, child: Any) -> Any:
    children = list(body)
    for following in children[children.index(child):]:
        section = following if following.tag == qn("w:sectPr") else following.find("./w:pPr/w:sectPr", _NS)
        if section is not None:
            return section
    raise ValueError("图片位置没有所属 section")


def verify_image_report(document_ir: DocumentIR, content: bytes, report: dict, *, expected_template_version_id: str | None = None,
                        expected_generation_policy: str | None = None) -> dict:
    """源计划、冻结输入、实际包三方核验；失败不得降级为历史报告。"""
    try:
        return _verify_image_report(document_ir, content, report, expected_template_version_id=expected_template_version_id,
                                    expected_generation_policy=expected_generation_policy)
    except _ImageEvidenceError:
        raise
    except (ValueError, KeyError, TypeError, IndexError, AttributeError, OverflowError, re.error, zipfile.BadZipFile,
            ET.ParseError, InvalidImageStreamError, UnexpectedEndOfFileError, UnrecognizedImageError):
        # 配置校验、正则编译及整数解码错误可能含私有快照值，不复制第三方消息。
        raise ValueError("图片布局报告缺少必要字段或结构损坏") from None


def _verify_image_report(document_ir: DocumentIR, content: bytes, report: dict, *, expected_template_version_id: str | None,
                         expected_generation_policy: str | None) -> dict:
    _check(isinstance(report, dict) and report["schema_version"] == IMAGE_REPORT_VERSION, "报告版本")
    _check(report["rule_version"] == IMAGE_GROUP_VERSION and report["thresholds"] == IMAGE_GROUP_THRESHOLDS, "归组规则")
    _check(report["source_ir_sha256"] == canonical_sha256(document_ir.model_dump(mode="json")), "原始 IR 绑定")
    inputs = report["render_inputs"]
    _check(set(inputs) == {"schema_version", "projection_version", "writer_version", "rule_version", "generation_policy",
                          "document_language", "template", "caption_style", "format_rules", "spans"}, "输入字段白名单")
    _check(inputs["schema_version"] == IMAGE_INPUTS_VERSION and inputs["projection_version"] == IMAGE_PROJECTION_VERSION
           and inputs["writer_version"] == IMAGE_WRITER_VERSION and inputs["rule_version"] == IMAGE_GROUP_VERSION, "输入或投影版本")
    _check(report["render_inputs_sha256"] == canonical_sha256(inputs), "冻结输入 hash")
    _check(inputs["generation_policy"] in {"grouped/v1", "single-only/v1"}, "构建策略")
    if expected_generation_policy is not None:
        _check(inputs["generation_policy"] == expected_generation_policy, "当前构建策略")
    _check(isinstance(inputs["document_language"], str) and bool(inputs["document_language"]), "文档语言")
    if expected_template_version_id is not None:
        _check(inputs["template"]["version_id"] == expected_template_version_id, "模板版本身份")
    for kind, builtin in (("docx", "builtin/python-docx/v1"), ("config", "builtin/template-config/v1")):
        descriptor = inputs["template"][kind]
        _check(descriptor["kind"] in {"file", builtin}, "模板来源")
        _check((descriptor["kind"] == "file" and isinstance(descriptor["sha256"], str) and len(descriptor["sha256"]) == 64)
               or (descriptor["kind"] == builtin and descriptor["sha256"] is None), "模板内容 hash")
    format_rules = inputs["format_rules"]
    _check(set(format_rules) == {"kind", "content_sha256", "rules"}, "格式规则白名单")
    _check((format_rules["kind"] == "file" and isinstance(format_rules["content_sha256"], str) and len(format_rules["content_sha256"]) == 64)
           or (format_rules["kind"] == "builtin/format-rules/v1" and format_rules["content_sha256"] is None), "格式来源 hash")
    TerminologyReplacer.from_frozen_rules(format_rules["rules"])
    TemplateParagraphStyleConfig.model_validate(inputs["caption_style"])
    plan = build_image_plan(document_ir)
    _check(len(report["spans"]) == len(plan) == len(inputs["spans"]), "span 覆盖")
    blocks = {block.id: block for block in document_ir.blocks}
    assets = {asset.id: asset for asset in document_ir.assets}
    pages = {page.index: page for page in document_ir.pages}
    legacy_layout = build_layout_plan(document_ir).mode == "legacy_v1_fallback"
    bookmarks = caption_bookmark_inventory(document_ir)
    with zipfile.ZipFile(io.BytesIO(content)) as package:
        root = ET.fromstring(package.read("word/document.xml"))
        styles = ET.fromstring(package.read("word/styles.xml"))
        body = root.find("./w:body", _NS)
        relations = {node.attrib["Id"]: node.attrib["Target"] for node in ET.fromstring(package.read("word/_rels/document.xml.rels"))}
        tables = root.findall(".//w:tbl", _NS)
        marked = [table for table in tables if table.find("./w:tblPr/w:tblCaption", _NS) is not None and table.find("./w:tblPr/w:tblCaption", _NS).get(qn("w:val"), "").startswith(IMAGE_TABLE_PREFIX)]
        found_markers = set()
        image_paragraphs = []
        group_count = single_count = uncertain_count = 0
        reasons: dict[str, int] = {}
        expected_anchors = set()
        last_body_position = -1
        for decision, entry, frozen in zip(plan, report["spans"], inputs["spans"], strict=True):
            _check(entry["span_id"] == frozen["span_id"] == decision.id and entry["block_ids"] == list(decision.block_ids), "源序或成员")
            _check(entry["planned_mode"] == decision.mode and entry["page_index"] == decision.page_index and entry["metrics"] == dict(decision.metrics), "源计划")
            mode = entry["mode"]
            allowed = "group" if decision.mode == "group" and inputs["generation_policy"] == "grouped/v1" else "single_sequence"
            _check(mode == allowed or (allowed == "group" and mode == "single_sequence" and entry["reasons"] in [["asset_unavailable"], ["image_size_unfit"]]), "实际写入策略")
            _check(entry["reasons"] == list(decision.reasons) or (allowed == "group" and mode == "single_sequence" and entry["reasons"] in [["asset_unavailable"], ["image_size_unfit"]]), "拒绝原因")
            geometry = frozen["geometry"]
            members = [blocks[block_id] for block_id in decision.block_ids]
            image_geometries = frozen.get("image_geometries", {})
            _check(isinstance(image_geometries, dict) and set(image_geometries).issubset(decision.block_ids)
                   and (not image_geometries or allowed == "single_sequence"), "逐图几何覆盖")
            downgraded = allowed == "group" and mode == "single_sequence"
            group_slots = None
            size_unfit = False
            if downgraded:
                # 缺资产的真实回退最终必须失败；完整图片不能借报告原因伪造缺图回退。
                _check(entry["reasons"] != ["asset_unavailable"], "缺失资产不能作为完整产物登记")
                group_width, group_slots = image_slots(members, pages[decision.page_index].width, geometry)
                size_unfit = group_width <= 0 or any(slot["inner_width"] <= 0 for slot in group_slots)
            slots = None
            table = None
            if mode == "group":
                group_count += 1
                marker = IMAGE_TABLE_PREFIX + decision.id
                _check(entry["marker"] == marker and marker not in found_markers, "布局表 marker")
                candidates = [table for table in marked if table.find("./w:tblPr/w:tblCaption", _NS).get(qn("w:val")) == marker]
                _check(len(candidates) == 1, "布局表缺失或重复")
                table = candidates[0]
                _check(table in list(body), "布局表位置")
                table_position = list(body).index(table)
                _check(table_position > last_body_position, "图片 span 源顺序")
                last_body_position = table_position
                _check(section_geometry(_actual_section(body, table)) == geometry, "所属 section 几何")
                found_markers.add(marker)
                width, slots = image_slots(members, pages[decision.page_index].width, geometry)
                _verify_table(table, width, slots, styles)
                cells = table.findall("./w:tr/w:tc", _NS)
            else:
                _check(entry["marker"] is None, "单图含布局表 marker")
                single_count += len(members)
            if entry["reasons"]:
                uncertain_count += 1
                for reason in entry["reasons"]:
                    reasons[reason] = reasons.get(reason, 0) + 1
            _check(len(entry["images"]) == len(members), "逐图覆盖")
            previous_position = -1
            for index, (block, image) in enumerate(zip(members, entry["images"], strict=True)):
                image_geometry = image_geometries.get(block.id, geometry)
                _check(image["block_id"] == block.id and image["asset_ref"] == block.asset_ref and image["anchor"] == image_anchor(block.id), "图片来源")
                _check(image["source"] == source_image_position(block), "源图片位置")
                anchor = image["anchor"]
                expected_anchors.add(anchor)
                starts = root.findall(f'.//w:bookmarkStart[@w:name="{anchor}"]', _NS)
                _check(len(starts) == 1, "图片锚点缺失或重复")
                paragraph = next((p for p in root.findall(".//w:p", _NS) if starts[0] in list(p)), None)
                _check(paragraph is not None, "图片锚点容器")
                _verify_anchor(root, paragraph, starts[0])
                indentation = paragraph.find("./w:pPr/w:ind", _NS)
                _check(indentation is not None and all(indentation.get(qn("w:" + key)) == "0" for key in ("left", "right", "firstLine"))
                       and indentation.get(qn("w:hanging"), "0") == "0", "图片段缩进")
                image_paragraphs.append(paragraph)
                container = cells[index] if table is not None else body
                _check(paragraph in list(container), "图与 cell 绑定")
                if table is None:
                    _check(section_geometry(_actual_section(body, paragraph)) == image_geometry, "单图 section 几何")
                    position = list(body).index(paragraph)
                    _check(position > previous_position and position > last_body_position, "单图源顺序")
                    previous_position = position
                    last_body_position = position
                inlines = paragraph.findall(".//wp:inline", _NS)
                _check(not paragraph.findall(".//wp:anchor", _NS), "浮动图片")
                _check(len(inlines) == 1, "图片缺失或重复")
                image_nodes = [node for node in paragraph if node.tag != qn("w:pPr")]
                _check(len(image_nodes) == 3 and image_nodes[1].tag == qn("w:r")
                       and len(image_nodes[1]) == 1 and image_nodes[1][0].tag == qn("w:drawing")
                       and len(image_nodes[1][0]) == 1, "图片段含未登记内容")
                inline = inlines[0]
                _check(all(inline.get(key) == "0" for key in ("distT", "distB", "distL", "distR")), "图片对象外距")
                _check(inline.find("./wp:docPr", _NS).get("name") == anchor, "图片对象身份")
                extent = inline.find("./wp:extent", _NS)
                actual_size = (int(extent.get("cx")), int(extent.get("cy")))
                picture = inline.find("./a:graphic/a:graphicData/pic:pic", _NS)
                transform = picture.find("./pic:spPr/a:xfrm", _NS)
                # 原始字节和外框尺寸不变时，裁切与变换仍可破坏可见内容和比例。
                _check(int(transform.get("rot", "0")) == 0
                       and all(transform.get(key, "0") in {"0", "false"} for key in ("flipH", "flipV")), "图片旋转或翻转")
                offset = transform.find("./a:off", _NS)
                _check(offset is not None and all(int(offset.get(key)) == 0 for key in ("x", "y")), "图片内部偏移")
                source_rect = picture.find("./pic:blipFill/a:srcRect", _NS)
                fill_rect = picture.find("./pic:blipFill/a:stretch/a:fillRect", _NS)
                _check(source_rect is None or all(int(source_rect.get(side, "0")) == 0 for side in ("l", "t", "r", "b")), "图片源裁切")
                _check(fill_rect is not None and all(int(fill_rect.get(side, "0")) == 0 for side in ("l", "t", "r", "b")), "图片填充偏移")
                picture_extent = transform.find("./a:ext", _NS)
                _check(picture_extent is not None and (int(picture_extent.get("cx")), int(picture_extent.get("cy"))) == actual_size,
                       "图片内部显示尺寸")
                blip = inline.find(".//a:blip", _NS)
                target = relations[blip.get(qn("r:embed"))]
                path = str(PurePosixPath("word") / target)
                _check(".." not in PurePosixPath(path).parts and not target.startswith("/"), "图片关系路径")
                data = package.read(path)
                digest = hashlib.sha256(data).hexdigest()
                asset = assets.get(block.asset_ref)
                _check(asset is not None and digest == image["asset_sha256"], "图片字节绑定")
                if asset.checksum_sha256:
                    _check(asset.checksum_sha256.removeprefix("sha256:") == digest, "源资产 checksum")
                from docx.image.image import Image
                decoded = Image.from_blob(data)
                if downgraded and group_slots[index]["inner_width"] > 0:
                    size_unfit |= min(image_dimensions(decoded.px_width, decoded.px_height,
                        group_slots[index]["inner_width"], geometry["effective_height"])) <= 0
                available = slots[index]["inner_width"] if slots else single_image_width(block, pages[decision.page_index].width if not legacy_layout and decision.page_index in pages else None, image_geometry)
                expected_size = image_dimensions(decoded.px_width, decoded.px_height, available, image_geometry["effective_height"])
                _check(actual_size == expected_size == (image["width"], image["height"]), "图片显示尺寸或比例")
                annotations = image_annotations(block)
                _check(len(image["annotations"]) == len(annotations), "注释覆盖")
                paragraphs = list(container)
                start_index = paragraphs.index(paragraph)
                for annotation_index, ((field, text), annotation) in enumerate(zip(annotations, image["annotations"], strict=True)):
                    expected_anchor = image_anchor(block.id, field)
                    _check(annotation["field"] == field and annotation["anchor"] == expected_anchor and annotation["source_sha256"] == sha256_text(text), "注释来源")
                    expected_anchors.add(expected_anchor)
                    matches = root.findall(f'.//w:bookmarkStart[@w:name="{expected_anchor}"]', _NS)
                    _check(len(matches) == 1, "注释锚点缺失或重复")
                    actual = paragraphs[start_index + annotation_index + 1]
                    _check(actual.tag == qn("w:p") and matches[0] in list(actual), "注释次序或 cell 绑定")
                    _verify_anchor(root, actual, matches[0])
                    expected_hash = expected_annotation(text, inputs, bookmarks)
                    _check(annotation["expected_output_sha256"] == expected_hash == annotation_projection(actual), "注释内容或字段投影")
                    _check(_keep_next(actual) == (annotation_index < len(annotations) - 1), "注释 keep 链")
                    if table is None:
                        last_body_position = list(body).index(actual)
                _check(_keep_next(paragraph) == bool(annotations), "图片 keep 链")
                if table is not None:
                    _check(len(paragraphs) == 1 + len(annotations) + 1, "cell 含额外内容")  # tcPr 也计入直接子节点。
            if downgraded:
                _check(size_unfit, "尺寸降级缺少实际依据")
        _check(len(marked) == group_count, "未登记或伪造布局表")
        _check(len(root.findall(".//wp:inline", _NS)) == len(image_paragraphs) and not root.findall(".//wp:anchor", _NS), "未登记图片")
        actual_anchors = [node.get(qn("w:name")) for node in root.findall(".//w:bookmarkStart", _NS) if node.get(qn("w:name"), "").startswith("md2w_img_")]
        _check(len(actual_anchors) == len(expected_anchors) and set(actual_anchors) == expected_anchors, "未登记或重复锚点")
    return {"schema_version": IMAGE_REPORT_VERSION, "accepted_group_count": group_count,
            "single_image_count": single_count, "uncertain_span_count": uncertain_count,
            "reason_counts": dict(sorted(reasons.items())), "examples": [{"span_id": e["span_id"], "block_ids": e["block_ids"][:40],
                "omitted_member_count": max(len(e["block_ids"]) - 40, 0)} for e in report["spans"][:40]],
            "omitted_example_count": max(len(plan) - 40, 0), "report_sha256": canonical_sha256(report)}


def _keep_next(paragraph: Any) -> bool:
    node = paragraph.find("./w:pPr/w:keepNext", _NS)
    return node is not None and node.get(qn("w:val"), "true") not in {"0", "false", "off"}


def _verify_anchor(root: Any, paragraph: Any, start: Any) -> None:
    bookmark_id = start.get(qn("w:id"))
    starts = [node for node in root.findall(".//w:bookmarkStart", _NS) if node.get(qn("w:id")) == bookmark_id]
    ends = [node for node in root.findall(".//w:bookmarkEnd", _NS) if node.get(qn("w:id")) == bookmark_id]
    content = [node for node in paragraph if node.tag != qn("w:pPr")]
    _check(len(starts) == len(ends) == 1 and content[0] is start and content[-1] is ends[0], "图片或注释锚点范围")


def has_image_markers(content: bytes) -> bool:
    """无新报告的历史件不能携带新 writer 的位置或布局表标记。"""
    with zipfile.ZipFile(io.BytesIO(content)) as package:
        root = ET.fromstring(package.read("word/document.xml"))
    return (any(node.get(qn("w:name"), "").startswith("md2w_img_") for node in root.findall(".//w:bookmarkStart", _NS))
            or any(node.get("name", "").startswith("md2w_img_") for node in root.findall(".//wp:docPr", _NS))
            or any(node.get(qn("w:val"), "").startswith(IMAGE_TABLE_PREFIX) for node in root.findall(".//w:tblCaption", _NS)))


def _effective_table_position(table: Any, styles: Any) -> tuple[int, str]:
    """仅解析布局表定位所需的 direct、basedOn 和默认表格样式。"""
    props = table.find("./w:tblPr", _NS)
    resolved: dict[str, Any] = {}

    def consume(properties: Any) -> None:
        if properties is None:
            return
        for tag in ("tblInd", "jc"):
            nodes = properties.findall("./w:" + tag, _NS)
            _check(len(nodes) <= 1, "表格定位属性重复")
            if nodes and tag not in resolved:
                resolved[tag] = nodes[0]

    consume(props)
    if len(resolved) < 2:
        table_styles = {style.get(qn("w:styleId")): style for style in styles.findall("./w:style", _NS)
                        if style.get(qn("w:type")) == "table"}
        explicit = props.find("./w:tblStyle", _NS)
        if explicit is not None:
            style_id = explicit.get(qn("w:val"))
            _check(style_id in table_styles, "布局表样式缺失")
            current = table_styles[style_id]
        else:
            defaults = [style for style in table_styles.values() if style.get(qn("w:default")) in {"1", "true", "on"}]
            _check(len(defaults) <= 1, "默认表格样式不唯一")
            current = defaults[0] if defaults else None
        seen: set[str] = set()
        while current is not None and len(resolved) < 2:
            style_id = current.get(qn("w:styleId"))
            _check(style_id not in seen, "表格样式继承循环")
            seen.add(style_id)
            consume(current.find("./w:tblPr", _NS))
            parent = current.find("./w:basedOn", _NS)
            if parent is None:
                break
            parent_id = parent.get(qn("w:val"))
            _check(parent_id in table_styles, "表格父样式缺失")
            current = table_styles[parent_id]
    indent = resolved.get("tblInd")
    effective_indent = 0
    if indent is not None:
        unit = indent.get(qn("w:type"), "dxa")
        _check(unit in {"dxa", "pct", "auto", "nil"}, "表格缩进单位")
        # pct/auto 的值被忽略，nil 表示无宽度；这些单位均不产生实际缩进。
        if unit == "dxa":
            effective_indent = int(indent.get(qn("w:w"), "0"))
    alignment = resolved.get("jc")
    return effective_indent, alignment.get(qn("w:val")) if alignment is not None else "left"


def _verify_table(table: Any, width: int, slots: list[dict], styles: Any) -> None:
    props = table.find("./w:tblPr", _NS)
    indent, alignment = _effective_table_position(table, styles)
    # 历史 writer 未固定对齐；零缩进且总宽受有效区域约束时，三种对齐均不越界。
    _check(indent == 0 and alignment in {"left", "center", "right"}, "布局表有效缩进或对齐")
    _check(props.find("./w:tblLayout", _NS).get(qn("w:type")) == "fixed", "表格非固定布局")
    _check(props.find("./w:tblW", _NS).attrib == {qn("w:type"): "dxa", qn("w:w"): str(width)}, "表格总宽")
    _check(not props.findall("./w:tblpPr", _NS) and not table.findall(".//w:shd", _NS) and not table.findall(".//w:tblHeader", _NS), "布局表浮动或带内容样式")
    borders = props.find("./w:tblBorders", _NS)
    _check(borders is not None and {child.tag for child in borders} == {qn("w:" + side) for side in ("top", "left", "bottom", "right", "insideH", "insideV")}
           and all(child.get(qn("w:val")) == "nil" for child in borders), "布局表边框")
    _check(list(props).index(borders) < list(props).index(props.find("./w:tblLayout", _NS)), "布局表属性顺序")
    rows = table.findall("./w:tr", _NS)
    _check(len(rows) == 1 and rows[0].find("./w:trPr/w:cantSplit", _NS) is not None, "布局表行")
    _check(not any(node.get(qn("w:hRule")) == "exact" for node in rows[0].findall("./w:trPr/w:trHeight", _NS)), "布局表精确行高")
    cells = rows[0].findall("./w:tc", _NS)
    grid = table.findall("./w:tblGrid/w:gridCol", _NS)
    _check(len(cells) == len(slots) == len(grid), "布局表列数")
    for cell, col, slot in zip(cells, grid, slots, strict=True):
        _check(col.get(qn("w:w")) == str(slot["width"])
               and cell.find("./w:tcPr/w:tcW", _NS).attrib == {qn("w:type"): "dxa", qn("w:w"): str(slot["width"])}, "布局列宽")
        for side in ("left", "right", "top", "bottom"):
            margin = cell.find("./w:tcPr/w:tcMar/w:" + side, _NS)
            _check(margin is not None and margin.get(qn("w:w")) == str(slot.get(side, 0)) and margin.get(qn("w:type")) == "dxa", "布局 cell 边距")
        cell_props = cell.find("./w:tcPr", _NS)
        alignment = cell_props.find("./w:vAlign", _NS)
        _check(alignment is not None and alignment.get(qn("w:val")) == "top"
               and list(cell_props).index(cell_props.find("./w:tcMar", _NS)) < list(cell_props).index(alignment), "布局 cell 属性顺序")
