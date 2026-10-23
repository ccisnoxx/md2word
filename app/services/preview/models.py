"""只读 Word 预览端口的数据、资源预算和输入输出边界。"""

from __future__ import annotations

import hashlib
import io
import struct
import zipfile
import zlib
from typing import Literal
from xml.etree import ElementTree

from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictInt, ValidationError

PreviewErrorCode = Literal[
    "preview_disabled", "preview_provider_unavailable", "preview_profile_unavailable",
    "preview_sandbox_unavailable", "preview_input_invalid", "preview_timeout",
    "preview_resource_exceeded", "preview_output_invalid", "preview_engine_failed",
    "preview_storage_failed", "preview_unexpected_error",
]
SHA256_PATTERN = r"^sha256:[0-9a-f]{64}$"


def sha256(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


class PreviewPolicy(BaseModel):
    """新任务固化的非敏感策略；不含部署路径或进程环境。"""

    model_config = ConfigDict(frozen=True, extra="forbid")
    schema_version: Literal["word-preview-policy/v1"] = "word-preview-policy/v1"
    backend: Literal["disabled", "sandboxed"] = "disabled"
    profile_id: str = Field(default="unconfigured", min_length=1, max_length=100, pattern=r"^[a-zA-Z0-9_.-]+$")
    profile_sha256: str = Field(default="sha256:" + "0" * 64, pattern=SHA256_PATTERN)
    required: StrictBool = False
    render_pages: StrictBool = False
    timeout_seconds: float = Field(default=60, gt=0, le=300)
    deadline_seconds: float = Field(default=125, gt=0, le=900)
    max_attempts: StrictInt = Field(default=2, ge=1, le=5)
    max_runs_per_result: StrictInt = Field(default=16, ge=1, le=100)
    max_input_bytes: StrictInt = Field(default=52_428_800, gt=0)
    max_output_bytes: StrictInt = Field(default=104_857_600, gt=0)
    max_pages: StrictInt = Field(default=200, ge=1, le=10000)
    max_page_pixels: StrictInt = Field(default=20_000_000, gt=0)
    max_temp_bytes: StrictInt = Field(default=536_870_912, gt=0)
    max_cpu_seconds: StrictInt = Field(default=60, gt=0)
    max_memory_bytes: StrictInt = Field(default=536_870_912, gt=0)
    max_processes: StrictInt = Field(default=16, ge=1, le=128)


class PreviewFailure(Exception):
    """局部白名单错误；不携带 stderr、文档内容或部署路径。"""

    def __init__(self, code: PreviewErrorCode, *, retryable: bool = False):
        super().__init__(f"Word 预览失败（{code}）。")
        self.code = code
        self.retryable = retryable and code in {"preview_timeout", "preview_engine_failed"}


class PreviewPage(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    page_index: StrictInt = Field(ge=0)
    content: bytes
    width: StrictInt = Field(gt=0)
    height: StrictInt = Field(gt=0)


class PreviewResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    pdf: bytes
    page_count: StrictInt = Field(gt=0)
    pages: tuple[PreviewPage, ...] = ()
    provider_id: str = Field(min_length=1, max_length=100, pattern=r"^[a-zA-Z0-9_.-]+$")
    provider_version: str = Field(min_length=1, max_length=100, pattern=r"^[a-zA-Z0-9_.+-]+$")
    profile_sha256: str = Field(pattern=SHA256_PATTERN)


class _PackageXmlTreeBuilder(ElementTree.TreeBuilder):
    """在 XML 编码解码后拒绝 DTD，避免 UTF-16 绕过字节级预检。"""

    def doctype(self, name, pubid, system):
        raise PreviewFailure("preview_input_invalid")


def _validate_package_xml(content: bytes, *, name: str) -> None:
    root = ElementTree.fromstring(content, parser=ElementTree.XMLParser(target=_PackageXmlTreeBuilder()))
    if name == "[content_types].xml":
        for part in root:
            content_type = part.attrib.get("ContentType", "").lower()
            if any(active in content_type for active in ("macroenabled", "vba", "oleobject", "activex")):
                raise PreviewFailure("preview_input_invalid")
    if name.endswith(".rels"):
        for relationship in root:
            relation_type = relationship.attrib.get("Type", "").rstrip("/").rsplit("/", 1)[-1].lower()
            if relation_type in {"vbaproject", "vbaprojectsignature", "oleobject", "activex", "control", "package"}:
                raise PreviewFailure("preview_input_invalid")


def validate_docx(data: bytes, policy: PreviewPolicy) -> None:
    """只做有界包预检，不解释或执行宏、嵌入对象或外部资源。"""
    if not data:
        raise PreviewFailure("preview_input_invalid")
    if len(data) > policy.max_input_bytes:
        raise PreviewFailure("preview_resource_exceeded")
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as package:
            entries = package.infolist()
            if len(entries) > 4096 or sum(i.file_size for i in entries) > policy.max_temp_bytes:
                raise PreviewFailure("preview_resource_exceeded")
            names = [i.filename for i in entries]
            if len(names) != len(set(names)):
                raise PreviewFailure("preview_input_invalid")
            for item in entries:
                name = item.filename.lower()
                if (name.startswith("/") or ".." in name.split("/") or "\\" in name
                        or "vbaproject" in name or "/embeddings/" in name or "/activex/" in name
                        or item.flag_bits & 1):
                    raise PreviewFailure("preview_input_invalid")
                if item.file_size > max(1, item.compress_size) * 200:
                    raise PreviewFailure("preview_resource_exceeded")
                # 逐条读取会检验 CRC；大小在解压前已受总预算约束。
                content = package.read(item)
                if name.endswith(".xml") or name.endswith(".rels"):
                    if b"<!DOCTYPE" in content.upper() or b"<!ENTITY" in content.upper():
                        raise PreviewFailure("preview_input_invalid")
                    _validate_package_xml(content, name=name)
            if not {"[Content_Types].xml", "word/document.xml", "_rels/.rels"}.issubset(names):
                raise PreviewFailure("preview_input_invalid")
    except PreviewFailure:
        raise
    except (zipfile.BadZipFile, KeyError, ValueError, ElementTree.ParseError, RuntimeError, NotImplementedError):
        raise PreviewFailure("preview_input_invalid") from None


def png_dimensions(data: bytes, *, max_pixels: int) -> tuple[int, int]:
    """验证 PNG 的 CRC、像素数据及解压上限；不引入额外图像运行时。"""
    try:
        if data[:8] != b"\x89PNG\r\n\x1a\n":
            raise ValueError()
        offset, width, height, idat, ended = 8, 0, 0, bytearray(), False
        header = None
        while offset < len(data):
            size = struct.unpack(">I", data[offset:offset + 4])[0]
            kind = data[offset + 4:offset + 8]
            chunk = data[offset + 8:offset + 8 + size]
            crc = data[offset + 8 + size:offset + 12 + size]
            if len(chunk) != size or len(crc) != 4 or zlib.crc32(kind + chunk) & 0xffffffff != struct.unpack(">I", crc)[0]:
                raise ValueError()
            if header is None:
                if kind != b"IHDR" or size != 13:
                    raise ValueError()
                header = struct.unpack(">IIBBBBB", chunk)
                width, height, depth, color, compression, filtering, interlace = header
                if width <= 0 or height <= 0 or width * height > max_pixels:
                    raise PreviewFailure("preview_resource_exceeded")
                if (depth, color) not in {(8, 0), (8, 2), (8, 4), (8, 6)} or (compression, filtering, interlace) != (0, 0, 0):
                    raise ValueError()
            elif kind == b"IHDR":
                raise ValueError()
            if kind == b"IDAT":
                idat.extend(chunk)
            if kind == b"IEND":
                ended = size == 0 and offset + 12 == len(data)
                break
            offset += size + 12
        if not ended or not idat or header is None:
            raise ValueError()
        channels = {0: 1, 2: 3, 4: 2, 6: 4}[header[3]]
        stride = width * channels + 1
        expected = stride * height
        decoder = zlib.decompressobj()
        decoded = decoder.decompress(bytes(idat), expected + 1)
        if len(decoded) != expected or not decoder.eof or decoder.unused_data or decoder.unconsumed_tail:
            raise ValueError()
        if any(decoded[i * stride] > 4 for i in range(height)):
            raise ValueError()
        return width, height
    except PreviewFailure:
        raise
    except (ValueError, struct.error, zlib.error, IndexError, KeyError):
        raise PreviewFailure("preview_output_invalid") from None


def validate_result(result: PreviewResult, policy: PreviewPolicy) -> None:
    """端口共享格式/预算校验；完整 PDF 解码由批准的隔离 validator 承担。"""
    try:
        PreviewResult.model_validate(result.model_dump(mode="python"))
    except (ValidationError, AttributeError):
        raise PreviewFailure("preview_output_invalid") from None
    if result.profile_sha256 != policy.profile_sha256:
        raise PreviewFailure("preview_output_invalid")
    if result.page_count > policy.max_pages:
        raise PreviewFailure("preview_resource_exceeded")
    if sum(len(page.content) for page in result.pages) + len(result.pdf) > policy.max_output_bytes:
        raise PreviewFailure("preview_resource_exceeded")
    if not result.pdf.startswith(b"%PDF-") or not result.pdf.rstrip().endswith(b"%%EOF"):
        raise PreviewFailure("preview_output_invalid")
    if (len(result.pages) != result.page_count if policy.render_pages else bool(result.pages)):
        raise PreviewFailure("preview_output_invalid")
    for index, page in enumerate(result.pages):
        if page.page_index != index or png_dimensions(page.content, max_pixels=policy.max_page_pixels) != (page.width, page.height):
            raise PreviewFailure("preview_output_invalid")
