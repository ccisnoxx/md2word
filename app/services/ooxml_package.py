"""从 DOCX 实物读取分节装饰和 OPC 关系，不访问包外资源。"""

from __future__ import annotations

import hashlib
import io
import posixpath
import warnings
import zlib
from dataclasses import dataclass
from urllib.parse import unquote, urlsplit
from zipfile import BadZipFile, ZipFile

from docx.opc.constants import CONTENT_TYPE as CT
from docx.opc.constants import RELATIONSHIP_TYPE as RT
from docx.oxml.ns import qn
from lxml import etree
from PIL import Image
from pydantic import BaseModel, ConfigDict

RELATIONSHIP_NS = "{http://schemas.openxmlformats.org/package/2006/relationships}"
CONTENT_TYPE_NS = "{http://schemas.openxmlformats.org/package/2006/content-types}"
OFFICE_RELATIONSHIP_NS = qn("r:id").removesuffix("id")
LEGACY_RELATIONSHIP_ID = "{urn:schemas-microsoft-com:office:office}relid"
REFERENCE_TYPES = frozenset({"default", "first", "even"})
IMAGE_REFERENCE_ELEMENTS = frozenset({qn("a:blip"), "{urn:schemas-microsoft-com:vml}imagedata"})
IMAGE_REFERENCE_ATTRIBUTES = frozenset({qn("r:id"), qn("r:embed"), qn("r:link"), LEGACY_RELATIONSHIP_ID})
ZIP_READ_ERRORS = (BadZipFile, EOFError, OSError, RuntimeError, zlib.error)
RASTER_FORMATS = {CT.PNG: "PNG", CT.JPEG: "JPEG", CT.GIF: "GIF", CT.TIFF: "TIFF", CT.BMP: "BMP"}


class DocxPackageError(ValueError):
    """只携带固定代码和逻辑位置的 DOCX 结构错误。"""

    def __init__(self, code: str, path: str) -> None:
        super().__init__(code)
        self.code = code
        self.path = path


@dataclass(frozen=True, slots=True)
class DocxPackageIssue:
    code: str
    path: str


class DecorationFingerprint(BaseModel):
    """按 XML 使用位置认证关系和媒体，不绑定 ZIP 文件名或 rId。"""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    markup_sha256: str
    media_sha256: list[str]


@dataclass(frozen=True, slots=True)
class DocxSectionInspection:
    title_page: bool
    header: dict[str, DecorationFingerprint]
    footer: dict[str, DecorationFingerprint]


@dataclass(frozen=True, slots=True)
class DocxPackageInspection:
    sections: tuple[DocxSectionInspection, ...]
    even_and_odd_headers: bool
    issues: tuple[DocxPackageIssue, ...]


@dataclass(frozen=True, slots=True)
class _Relationship:
    type: str
    target: str | None
    external: bool


def inspect_docx_package(content: bytes, *, verify_all_parts: bool = False) -> DocxPackageInspection:
    """读取可达装饰。上传预检额外认证所有 ZIP 成员、XML 和内部目标。"""

    try:
        with ZipFile(io.BytesIO(content)) as archive:
            return _DocxReader(archive).inspect(verify_all_parts=verify_all_parts)
    except ZIP_READ_ERRORS:
        raise DocxPackageError("docx_package_invalid", "docx") from None


def _resolve_internal_target(source: str, target: str) -> str | None:
    """相对所属 part 解析，拒绝路径越过包根和 URI 混淆。"""

    try:
        uri = urlsplit(target)
    except ValueError:
        return None
    if uri.scheme or uri.netloc or uri.query or uri.fragment or not uri.path or uri.path != target:
        return None
    directory = posixpath.dirname(source)
    resolved = [] if uri.path.startswith("/") or not directory else directory.split("/")
    for segment in uri.path.removeprefix("/").split("/"):
        if segment == ".":
            continue
        if segment == "..":
            if not resolved:
                return None
            resolved.pop()
            continue
        decoded = unquote(segment)
        if not segment or decoded in {".", ".."} or any(char in decoded for char in ("/", "\\", "\x00")):
            return None
        resolved.append(segment)
    return "/".join(resolved) or None


def _relationship_part(source: str) -> str:
    directory, name = posixpath.split(source)
    return posixpath.join(directory, "_rels", f"{name}.rels")


def _verify_raster_media(content: bytes, content_type: str) -> bool:
    image_format = RASTER_FORMATS.get(content_type)
    if image_format is None:
        # Word 可以保留 WMF、EMF 等矢量部件，不交给栅格解码器。
        return True
    try:
        with warnings.catch_warnings():
            # verify 不解码像素，尺寸警告本身不表示文件结构损坏。
            warnings.simplefilter("ignore", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(content), formats=[image_format]) as image:
                image.verify()
    except (OSError, ValueError, SyntaxError, Image.DecompressionBombError):
        return False
    return True


def _is_on(element: etree._Element | None) -> bool:
    return element is not None and element.get(qn("w:val"), "true") in {"true", "1", "on"}


class _DocxReader:
    def __init__(self, archive: ZipFile) -> None:
        self.archive = archive
        files = [item.filename for item in archive.infolist() if not item.is_dir()]
        self.names = frozenset(files)
        if len(self.names) != len(files):
            raise DocxPackageError("docx_package_invalid", "docx")
        self.issues: list[DocxPackageIssue] = []
        self._relationships: dict[str, dict[str, _Relationship]] = {}
        self._fingerprints: dict[tuple[str, str], DecorationFingerprint | None] = {}
        self._sha256: dict[str, str] = {}
        self._media_sha256: dict[str, str | None] = {}
        self._read_parts: set[str] = set()
        self._parsed_parts: set[str] = set()
        self._defaults: dict[str, str] = {}
        self._overrides: dict[str, str] = {}

    def inspect(self, *, verify_all_parts: bool) -> DocxPackageInspection:
        self._load_content_types()
        main = self._single_internal_relationship(
            self.relationships("", "docx.relationships"), RT.OFFICE_DOCUMENT, "docx.document", required=True,
        )
        document = self.xml(main, "docx.document")
        body = document.find(qn("w:body"))
        if document.tag != qn("w:document") or body is None or self._content_type(main) != CT.WML_DOCUMENT_MAIN:
            raise DocxPackageError("docx_main_document_invalid", "docx.document")
        final_sections = body.findall(qn("w:sectPr"))
        last_element = next((child for child in reversed(body) if isinstance(child.tag, str)), None)
        if len(final_sections) != 1 or last_element is not final_sections[0]:
            raise DocxPackageError("docx_section_missing", "docx.sections")
        earlier_sections = body.findall(f"./{qn('w:p')}/{qn('w:pPr')}/{qn('w:sectPr')}")
        relationships = self.relationships(main, "docx.document.relationships")
        settings = self._single_internal_relationship(relationships, RT.SETTINGS, "docx.settings")
        even_and_odd_headers = False
        if settings:
            settings_xml = self.xml(settings, "docx.settings")
            if settings_xml.tag != qn("w:settings"):
                raise DocxPackageError("docx_part_invalid", "docx.settings")
            even_and_odd_headers = _is_on(settings_xml.find(qn("w:evenAndOddHeaders")))
        headers: dict[str, DecorationFingerprint] = {}
        footers: dict[str, DecorationFingerprint] = {}
        sections = []
        for section in (*earlier_sections, *final_sections):
            self._apply_section_references(section, relationships, "header", RT.HEADER, headers)
            self._apply_section_references(section, relationships, "footer", RT.FOOTER, footers)
            sections.append(DocxSectionInspection(
                _is_on(section.find(qn("w:titlePg"))), headers.copy(), footers.copy(),
            ))
        if verify_all_parts:
            self._verify_remaining_parts()
        return DocxPackageInspection(tuple(sections), even_and_odd_headers, tuple(self.issues))

    def xml(self, name: str, path: str) -> etree._Element:
        if name not in self.names:
            raise DocxPackageError("docx_part_invalid", path)
        parser = etree.XMLParser(resolve_entities=False, load_dtd=False, no_network=True, remove_blank_text=True)
        try:
            root = etree.fromstring(self._read(name), parser)
        except etree.XMLSyntaxError:
            raise DocxPackageError("docx_part_invalid", path) from None
        if root.getroottree().docinfo.doctype:
            raise DocxPackageError("docx_part_invalid", path)
        self._parsed_parts.add(name)
        return root

    def _read(self, name: str) -> bytes:
        data = self.archive.read(name)
        self._read_parts.add(name)
        return data

    def _load_content_types(self) -> None:
        try:
            types = self.xml("[Content_Types].xml", "docx.content_types")
        except DocxPackageError:
            raise DocxPackageError("docx_content_types_invalid", "docx.content_types") from None
        if types.tag != CONTENT_TYPE_NS + "Types":
            raise DocxPackageError("docx_content_types_invalid", "docx.content_types")
        for item in types:
            if item.tag == CONTENT_TYPE_NS + "Default":
                key, registry = item.get("Extension", "").lower(), self._defaults
            elif item.tag == CONTENT_TYPE_NS + "Override":
                key, registry = item.get("PartName", "").removeprefix("/"), self._overrides
            else:
                continue
            content_type = item.get("ContentType", "")
            if not key or not content_type or key in registry:
                raise DocxPackageError("docx_content_types_invalid", "docx.content_types")
            registry[key] = content_type

    def _content_type(self, name: str) -> str:
        extension = posixpath.basename(name).rpartition(".")[2]
        return self._overrides.get(name, self._defaults.get(extension.lower(), ""))

    def _media_digest(self, name: str) -> str | None:
        if name not in self._media_sha256:
            content_type = self._content_type(name)
            digest = None
            if content_type.startswith("image/") and self.archive.getinfo(name).file_size:
                data = self._read(name)
                if _verify_raster_media(data, content_type):
                    digest = hashlib.sha256(data).hexdigest()
            self._media_sha256[name] = digest
        return self._media_sha256[name]

    def relationships(self, source: str, path: str) -> dict[str, _Relationship]:
        if source in self._relationships:
            return self._relationships[source]
        relationships: dict[str, _Relationship] = {}
        self._relationships[source] = relationships
        part_name = _relationship_part(source)
        if part_name not in self.names:
            return relationships
        try:
            part = self.xml(part_name, path)
        except DocxPackageError:
            self.issues.append(DocxPackageIssue("docx_relationship_broken", path))
            return relationships
        if part.tag != RELATIONSHIP_NS + "Relationships":
            self.issues.append(DocxPackageIssue("docx_relationship_broken", path))
            return relationships
        seen = set()
        for element in part.findall(RELATIONSHIP_NS + "Relationship"):
            relation_id, relation_type = element.get("Id"), element.get("Type")
            target, mode = element.get("Target"), element.get("TargetMode", "Internal")
            if not relation_id or relation_id in seen or not relation_type or not target or mode not in {"External", "Internal"}:
                self.issues.append(DocxPackageIssue("docx_relationship_broken", path))
                continue
            seen.add(relation_id)
            external = mode == "External"
            if not external:
                target = _resolve_internal_target(source, target)
                if target is None or target not in self.names:
                    self.issues.append(DocxPackageIssue("docx_relationship_broken", path))
                    target = None
            relationships[relation_id] = _Relationship(relation_type, target, external)
        return relationships

    @staticmethod
    def _single_internal_relationship(
        relationships: dict[str, _Relationship], relation_type: str, path: str, *, required: bool = False,
    ) -> str:
        matches = [relation for relation in relationships.values() if relation.type == relation_type]
        if not matches and not required:
            return ""
        if len(matches) != 1 or matches[0].external or required and matches[0].target is None:
            code = "docx_main_document_invalid" if required else "docx_relationship_broken"
            raise DocxPackageError(code, path)
        return matches[0].target or ""

    def _apply_section_references(
        self, section: etree._Element, relationships: dict[str, _Relationship],
        kind: str, relation_type: str, inherited: dict[str, DecorationFingerprint],
    ) -> None:
        seen = set()
        path = f"docx.{kind}.references"
        for reference in section.findall(qn(f"w:{kind}Reference")):
            role, relation_id = reference.get(qn("w:type")), reference.get(qn("r:id"))
            relation = relationships.get(relation_id) if relation_id is not None else None
            if (
                role is None or role not in REFERENCE_TYPES or role in seen
                or relation is None or relation.target is None or relation.external or relation.type != relation_type
            ):
                self.issues.append(DocxPackageIssue("docx_section_reference_invalid", path))
                if role is not None:
                    inherited.pop(role, None)
                continue
            seen.add(role)
            fingerprint = self._decoration(relation.target, kind)
            if fingerprint is None:
                inherited.pop(role, None)
                self.issues.append(DocxPackageIssue("docx_section_reference_invalid", path))
            else:
                inherited[role] = fingerprint

    def _decoration(self, name: str, kind: str) -> DecorationFingerprint | None:
        key = (name, kind)
        if key in self._fingerprints:
            return self._fingerprints[key]
        path = f"docx.{kind}.part"
        try:
            root = self.xml(name, path)
            tag, content_type = (qn("w:hdr"), CT.WML_HEADER) if kind == "header" else (qn("w:ftr"), CT.WML_FOOTER)
            if root.tag != tag or self._content_type(name) != content_type:
                raise DocxPackageError("docx_part_invalid", path)
        except DocxPackageError as error:
            self.issues.append(DocxPackageIssue(error.code, error.path))
            self._fingerprints[key] = None
            return None

        relationships_path = f"docx.{kind}.relationships"
        relationships = self.relationships(name, relationships_path)
        media = []
        for node in root.iter():
            for attribute, relation_id in sorted(node.attrib.items()):
                if not attribute.startswith(OFFICE_RELATIONSHIP_NS) and attribute != LEGACY_RELATIONSHIP_ID:
                    continue
                relation = relationships.get(relation_id)
                image_reference = node.tag in IMAGE_REFERENCE_ELEMENTS and attribute in IMAGE_REFERENCE_ATTRIBUTES
                if relation is None or (image_reference and relation.type != RT.IMAGE) or (
                    attribute == qn("r:embed") and relation.external
                ):
                    self.issues.append(DocxPackageIssue("docx_relationship_broken", relationships_path))
                    node.set(attribute, "invalid")
                    continue
                if relation.target is None:
                    # 关系读取时已记录无效目标，不因 XML 再次引用而重复计数。
                    node.set(attribute, "invalid")
                    continue
                if relation.external:
                    digest = hashlib.sha256(relation.target.encode("utf-8")).hexdigest()
                    node.set(attribute, f"external:{relation.type}:{digest}")
                    continue
                if relation.type == RT.IMAGE:
                    digest = self._media_digest(relation.target)
                    if digest is None:
                        self.issues.append(DocxPackageIssue("docx_media_invalid", f"docx.{kind}.media"))
                        node.set(attribute, "invalid")
                    else:
                        media.append(digest)
                        node.set(attribute, "internal-image")
                    continue
                if relation.target not in self._sha256:
                    self._sha256[relation.target] = hashlib.sha256(self._read(relation.target)).hexdigest()
                node.set(attribute, f"internal:{relation.type}:{self._sha256[relation.target]}")
        try:
            markup = etree.tostring(root, method="c14n", exclusive=True, with_comments=False)
        except etree.C14NError:
            self.issues.append(DocxPackageIssue("docx_part_invalid", path))
            self._fingerprints[key] = None
            return None
        result = DecorationFingerprint(markup_sha256=hashlib.sha256(markup).hexdigest(), media_sha256=media)
        self._fingerprints[key] = result
        return result

    def _verify_remaining_parts(self) -> None:
        for member in self.archive.infolist():
            name = member.filename
            if member.is_dir() or name == "[Content_Types].xml":
                continue
            content_type = self._content_type(name)
            if not content_type:
                raise DocxPackageError("docx_content_types_invalid", "docx.content_types")
            if name in self._parsed_parts:
                continue
            directory, basename = posixpath.split(name)
            parent, folder = posixpath.split(directory)
            if folder == "_rels" and basename.endswith(".rels"):
                source = posixpath.join(parent, basename.removesuffix(".rels"))
                if source and source not in self.names:
                    self.issues.append(DocxPackageIssue("docx_relationship_broken", "docx.relationships"))
                self.relationships(source, "docx.relationships")
            elif content_type in RASTER_FORMATS:
                if name not in self._media_sha256 and self._media_digest(name) is None:
                    self.issues.append(DocxPackageIssue("docx_media_invalid", "docx.media"))
            elif name.endswith((".xml", ".vml", ".rels")) or content_type.endswith(("+xml", "/xml")):
                self.xml(name, "docx.parts")
            elif name not in self._read_parts:
                with self.archive.open(member) as part:
                    while part.read(1024 * 1024):
                        pass
