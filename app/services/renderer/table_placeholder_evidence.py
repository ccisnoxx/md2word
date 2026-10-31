"""非编辑占位的实际 OOXML 来源/图像证明；不修改原生表格的行区间。"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from io import BytesIO
import posixpath
import json
from xml.etree import ElementTree as ET
import zipfile

from app.services.document_ir.table_placeholder import (
    BLOCKER, LABEL, TablePlaceholderBinding, TablePlaceholderError, canonical_hash,
    checksum, decode_placeholders, source_label, binding_identity, re_hash,
)

VERSION = "table-placeholder-rendering/v1"
NS = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
      "wp": "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing",
      "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
      "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships"}
W = "{" + NS["w"] + "}"


@dataclass(frozen=True, slots=True)
class _PlaceholderImageOwnership:
    """原占位 owner 认证同一最终包后冻结的实际 inline 路径，不进入 metadata。"""
    docx_sha256: str
    inline_paths: tuple[tuple[int, ...], ...]


def marker(binding):
    return "_md2tp_" + binding.placeholder_id.split(":")[1][:30]


def build_placeholder_evidence(document, content, *, _with_ownership=False):
    bindings = decode_placeholders(document)
    try:
        with zipfile.ZipFile(BytesIO(content)) as package:
            root = ET.fromstring(package.read("word/document.xml"))
            shapes = root.findall(".//wp:docPr", NS)
            bookmarks = [n.get(W + "name") for n in root.findall(".//w:bookmarkStart", NS)
                         if n.get(W + "name", "").startswith("_md2tp_")]
            if Counter(bookmarks) != Counter(marker(b) for b in bindings):
                raise ValueError()
            actual = [shape.get("descr") for shape in shapes if shape.get("descr", "").startswith("table-placeholder:")]
            if Counter(actual) != Counter(item.placeholder_id for item in bindings):
                raise ValueError()
            if not bindings:
                return (None, _PlaceholderImageOwnership(checksum(content), ())) if _with_ownership else None
            content_types = ET.fromstring(package.read("[Content_Types].xml"))
            assets = {asset.id: asset for asset in document.assets}
            relations = {node.get("Id"): node for node in ET.fromstring(package.read("word/_rels/document.xml.rels"))}
            maps = []
            inlines = []
            for index, binding in enumerate(bindings):
                paragraphs = [p for p in root.findall(".//w:p", NS) if any(
                    node.get(W + "name") == marker(binding) for node in p.findall("w:bookmarkStart", NS))]
                if len(paragraphs) != 1:
                    raise ValueError()
                p = paragraphs[0]
                starts, ends = p.findall("w:bookmarkStart", NS), p.findall("w:bookmarkEnd", NS)
                expected_id = str(2_000_000 + index)
                if ([n.get(W + "id") for n in starts] != [expected_id]
                        or [n.get(W + "id") for n in ends] != [expected_id]
                        or "".join(p.itertext()) != LABEL + source_label(binding)):
                    raise ValueError()
                pictures = p.findall(".//wp:inline", NS)
                if len(pictures) != 1 or pictures[0].find("wp:docPr", NS).get("descr") != binding.placeholder_id:
                    raise ValueError()
                inlines.append(pictures[0])
                rid = pictures[0].find(".//a:blip", NS).get("{" + NS["r"] + "}embed")
                relation = relations[rid]
                extent = pictures[0].find("wp:extent", NS)
                if extent is None or int(extent.get("cx", "0")) <= 0 or int(extent.get("cy", "0")) <= 0:
                    raise ValueError()
                if relation.get("TargetMode") == "External" or relation.get("Type") != NS["r"] + "/image":
                    raise ValueError()
                target = posixpath.normpath("word/" + relation.get("Target", ""))
                if not target.startswith("word/media/") or checksum(package.read(target)) != binding.asset_sha256:
                    raise ValueError()
                extension = target.rsplit(".", 1)[-1]
                types = [n.get("ContentType") for n in content_types if n.get("PartName") == "/" + target
                         or n.get("Extension") == extension]
                if types != [assets[binding.asset_ref].mime_type]:
                    raise ValueError()
                maps.append({**binding.model_dump(mode="json"), "marker": marker(binding),
                             "image_relationship": rid, "media_sha256": binding.asset_sha256,
                             "source_label_sha256": checksum(source_label(binding).encode())})
        result = {"version": VERSION, "ir_sha256": canonical_hash(document.model_dump(mode="json")),
                  "docx_sha256": checksum(content), "count": len(maps), "issue_codes": [BLOCKER], "maps": maps}
        result["evidence_sha256"] = canonical_hash(result)
        if _with_ownership:
            paths, pending = {}, [(root, ())]
            while pending:
                node, path = pending.pop()
                paths[node] = path
                pending.extend((child, (*path, index)) for index, child in reversed(list(enumerate(node))))
            return result, _PlaceholderImageOwnership(checksum(content), tuple(paths[node] for node in inlines))
        return result
    except Exception:
        raise TablePlaceholderError("table_placeholder_integrity_failed") from None


def valid_placeholder_evidence(value):
    try:
        if (not isinstance(value, dict) or set(value) != {"version", "ir_sha256", "docx_sha256", "count", "issue_codes", "maps", "evidence_sha256"}
                or value.get("version") != VERSION or not re_hash(value.get("ir_sha256")) or not re_hash(value.get("docx_sha256")) or type(value.get("count")) is not int
                or not 0 < value["count"] <= 64 or value.get("issue_codes") != [BLOCKER]
                or not isinstance(value.get("maps"), list) or len(value["maps"]) != value["count"] or value["evidence_sha256"] != canonical_hash(
                    {key: item for key, item in value.items() if key != "evidence_sha256"})):
            return False
        ids, fragments = [], []
        extra = {"marker", "image_relationship", "media_sha256", "source_label_sha256"}
        for item in value["maps"]:
            if not isinstance(item, dict):
                return False
            binding = TablePlaceholderBinding.model_validate_json(json.dumps({key: v for key, v in item.items() if key not in extra}))
            if (binding.placeholder_id != binding_identity(binding) or item["marker"] != marker(binding) or item["media_sha256"] != binding.asset_sha256
                    or item["source_label_sha256"] != checksum(source_label(binding).encode())
                    or not isinstance(item["image_relationship"], str)):
                return False
            ids.append(binding.placeholder_id)
            fragments.append(binding.fragment_id)
        return len(set(ids)) == len(ids) and len(set(fragments)) == len(fragments)
    except (ValueError, TypeError, KeyError):
        return False
