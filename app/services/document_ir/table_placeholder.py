"""空 HTML 的唯一占位合同：来源选择、严格绑定和图像预算，不执行存储或渲染。"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import io
import json
import math
from typing import Callable, Literal, Protocol
import warnings

from PIL import Image
from pydantic import BaseModel, ConfigDict, Field

VERSION = "table-placeholder/v1"
BLOCKER = "table_noneditable_placeholder"
LABEL = "表格非编辑占位；质量阻塞，不可交付"
MAX_IMAGE_BYTES = 16 * 1024 * 1024
MAX_PIXELS = 16_000_000
MAX_PLACEHOLDERS = 64
MAX_TOTAL_BYTES = 64 * 1024 * 1024
HASH_PATTERN = r"^sha256:[0-9a-f]{64}$"


class TablePlaceholderError(ValueError):
    """只携带稳定安全码，不公开源文字、对象路径或子进程异常。"""
    def __init__(self, code: str):
        self.code = code
        super().__init__(f"表格占位处理失败：{code}。")


def checksum(content: bytes) -> str:
    return "sha256:" + hashlib.sha256(content).hexdigest()


def canonical_hash(value) -> str:
    return checksum(json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"),
                               allow_nan=False).encode())


class TablePlaceholderBinding(BaseModel):
    """每条缺失片段的来源与资产绑定；完整 IR 身份由渲染证据另行绑定以避免循环 hash。"""
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)
    placeholder_id: str
    job_id: str
    issue_code: Literal["table_noneditable_placeholder"] = BLOCKER
    fragment_id: str
    logical_group_id: str
    owner_block_id: str
    content_list_sha256: str
    fragment_sha256: str = Field(pattern=HASH_PATTERN)
    html_state: Literal["missing", "empty"]
    asset_ref: str
    asset_sha256: str = Field(pattern=HASH_PATTERN)
    source_kind: Literal["mineru_reference", "source_pdf_crop"]
    source_file_id: str
    source_pdf_sha256: str | None = None
    page_index: int | None = Field(default=None, ge=0)
    bbox: tuple[float, float, float, float] | None = Field(default=None, strict=False)
    frame: tuple[float, float] | None = Field(default=None, strict=False)
    provider: str


@dataclass(frozen=True, slots=True)
class PdfCropSource:
    file_id: str
    checksum_sha256: str
    content: bytes


@dataclass(frozen=True, slots=True)
class PdfCropRequest:
    source: PdfCropSource
    page_index: int
    bbox: tuple[float, float, float, float]
    frame: tuple[float, float]


@dataclass(frozen=True, slots=True)
class PdfCropResult:
    content: bytes
    frame: tuple[float, float]
    provider: str = "poppler-pdftoppm/v1"


class PdfTableCropProvider(Protocol):
    def crop(self, request: PdfCropRequest) -> PdfCropResult: ...


@dataclass(frozen=True, slots=True)
class PlaceholderAsset:
    asset_id: str
    content: bytes
    mime_type: str


def validate_image(content: bytes) -> None:
    try:
        if not content or len(content) > MAX_IMAGE_BYTES:
            raise ValueError()
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(content)) as image:
                if image.format not in {"PNG", "JPEG", "GIF", "BMP", "TIFF", "WEBP"}:
                    raise ValueError()
                if min(image.size) <= 0 or image.width * image.height > MAX_PIXELS:
                    raise ValueError()
                image.verify()
            with Image.open(io.BytesIO(content)) as image:
                image.load()
    except Exception:
        raise TablePlaceholderError("table_placeholder_integrity_failed") from None


def validate_geometry(page_index, bbox, frame) -> None:
    if (type(page_index) is not int or page_index < 0 or bbox is None or frame is None
            or len(bbox) != 4 or len(frame) != 2
            or any(type(n) not in (int, float) or not math.isfinite(n) for n in (*bbox, *frame))):
        raise TablePlaceholderError("table_placeholder_geometry_invalid")
    x0, y0, x1, y1 = bbox
    width, height = frame
    if (width <= 0 or height <= 0 or not 0 <= x0 < x1 <= width or not 0 <= y0 < y1 <= height
            or (x0 == y0 == 0 and x1 == width and y1 == height)):
        raise TablePlaceholderError("table_placeholder_geometry_invalid")


def binding_identity(binding: TablePlaceholderBinding) -> str:
    return "table-placeholder:" + canonical_hash(binding.model_dump(mode="json", exclude={"placeholder_id"}))[7:]


def prepare_placeholders(document, references, *, source_loader: Callable[[], PdfCropSource] | None,
                         crop_provider: PdfTableCropProvider | None) -> list[PlaceholderAsset]:
    """仅对可信账本的 missing/empty 片段准备绑定；安全输入错误已由 IR-201 先验拒绝。"""
    from app.services.document_ir.models import DocumentIRAsset
    from app.services.document_ir.table_reference_assets import decode_table_references

    decoded = {item.fragment.fragment_id: item for item in decode_table_references(document)}
    needed = [item for item in decoded.values() if item.fragment.html_state in {"missing", "empty"}]
    if not needed:
        return []
    if len(needed) > MAX_PLACEHOLDERS:
        raise TablePlaceholderError("table_placeholder_source_unavailable")
    pages = {page.index: page for page in document.pages}
    source = None
    pending = []
    bindings = []
    total = 0
    for item in needed:
        fragment = item.fragment
        span = fragment.source_span
        frame = None
        pdf_hash = None
        if item.asset is not None:
            reference = references[span.json_pointer]
            content = reference.image.content
            validate_image(content)
            asset_ref = item.asset.id
            source_kind = "mineru_reference"
            provider = "mineru-reference/v1"
        else:
            if source_loader is None or crop_provider is None:
                raise TablePlaceholderError("table_placeholder_source_unavailable")
            if source is None:
                source = source_loader()
                if (source.file_id != document.metadata.source_file_id or
                        checksum(source.content) != source.checksum_sha256):
                    raise TablePlaceholderError("table_placeholder_integrity_failed")
            page = pages.get(span.page_index)
            raw_size = page.metadata.get("pdf_page_size") if page is not None else None
            if page is not None and page.metadata.get("page_size_source") and isinstance(raw_size, list) and len(raw_size) == 2:
                frame = tuple(raw_size)
            validate_geometry(span.page_index, span.bbox, frame)
            result = crop_provider.crop(PdfCropRequest(source, span.page_index, span.bbox, frame))
            if result.frame != frame or result.provider != "poppler-pdftoppm/v1":
                raise TablePlaceholderError("table_placeholder_geometry_invalid")
            content = result.content
            validate_image(content)
            pdf_hash = source.checksum_sha256
            source_kind, provider = "source_pdf_crop", result.provider
            asset_ref = "table-placeholder:" + canonical_hash([VERSION, fragment.fragment_id, pdf_hash, span.bbox, frame, checksum(content)])[7:]
            document.assets = [asset for asset in document.assets if asset.id != asset_ref]
            document.assets.append(DocumentIRAsset(id=asset_ref, kind="image", source_path="derived/table-placeholder.png",
                                                   mime_type="image/png", checksum_sha256=checksum(content)))
            pending.append(PlaceholderAsset(asset_ref, content, "image/png"))
        total += len(content)
        if total > MAX_TOTAL_BYTES:
            raise TablePlaceholderError("table_placeholder_source_unavailable")
        binding = TablePlaceholderBinding(
            placeholder_id="pending", job_id=document.metadata.job_id, fragment_id=fragment.fragment_id, logical_group_id=item.logical_group_id,
            owner_block_id=item.block_id, content_list_sha256=document.metadata.mineru_validation.content_list_sha256,
            fragment_sha256=canonical_hash(fragment.raw_fragment), html_state=fragment.html_state,
            asset_ref=asset_ref, asset_sha256=checksum(content), source_kind=source_kind,
            source_file_id=document.metadata.source_file_id, source_pdf_sha256=pdf_hash,
            page_index=span.page_index, bbox=span.bbox, frame=frame, provider=provider,
        )
        binding.placeholder_id = binding_identity(binding)
        bindings.append(binding)
    document.metadata.table_placeholders_version = VERSION
    document.metadata.table_placeholders = bindings
    decode_placeholders(document)
    return pending


def decode_placeholders(document, *, require_bound: bool = False) -> list[TablePlaceholderBinding]:
    """模型、完整性、renderer、完成 CAS 共用严格 decoder，不从旧缺字段猜造证明。"""
    from app.services.document_ir.table_reference_assets import decode_table_references
    metadata = document.metadata
    bindings = metadata.table_placeholders
    derived = {asset.id for asset in document.assets if asset.id.startswith("table-placeholder:")}
    if metadata.table_placeholders_version is None:
        if bindings or derived:
            raise TablePlaceholderError("table_placeholder_integrity_failed")
        return []
    def fail():
        raise TablePlaceholderError("table_placeholder_integrity_failed")
    if metadata.table_placeholders_version != VERSION:
        fail()
    refs = {item.fragment.fragment_id: item for item in decode_table_references(document)}
    needed = {key for key, value in refs.items() if value.fragment.html_state in {"missing", "empty"}}
    if not needed or len(bindings) > MAX_PLACEHOLDERS or [b.fragment_id for b in bindings] != [key for key in refs if key in needed]:
        fail()
    assets = {asset.id: asset for asset in document.assets}
    used = set()
    for binding in bindings:
        # 重新解码可变 typed 实例，不能依赖首次构建后的赋值仍满足模型。
        binding = TablePlaceholderBinding.model_validate(binding.model_dump(mode="python"))
        item = refs[binding.fragment_id]
        fragment = item.fragment
        asset = assets.get(binding.asset_ref)
        if (binding.placeholder_id != binding_identity(binding) or binding.job_id != metadata.job_id or binding.owner_block_id != item.block_id
                or binding.logical_group_id != item.logical_group_id or binding.html_state != fragment.html_state
                or binding.content_list_sha256 != metadata.mineru_validation.content_list_sha256
                or binding.fragment_sha256 != canonical_hash(fragment.raw_fragment)
                or binding.source_file_id != metadata.source_file_id or binding.page_index != fragment.source_span.page_index
                or binding.bbox != fragment.source_span.bbox or asset is None or asset.kind != "image"
                or asset.checksum_sha256 != binding.asset_sha256 or (require_bound and not asset.file_id)):
            fail()
        if binding.source_kind == "mineru_reference":
            if item.asset is None or item.asset.id != binding.asset_ref or binding.source_pdf_sha256 is not None or binding.frame is not None or binding.provider != "mineru-reference/v1":
                fail()
        else:
            page = next((page for page in document.pages if page.index == binding.page_index), None)
            if (page is None or not page.metadata.get("page_size_source")
                    or page.metadata.get("pdf_page_size") != list(binding.frame or ())):
                fail()
            validate_geometry(binding.page_index, binding.bbox, binding.frame)
            expected_asset = "table-placeholder:" + canonical_hash([VERSION, fragment.fragment_id, binding.source_pdf_sha256,
                binding.bbox, binding.frame, binding.asset_sha256])[7:]
            if (item.asset is not None or binding.asset_ref != expected_asset or binding.source_pdf_sha256 is None
                    or not re_hash(binding.source_pdf_sha256) or binding.provider != "poppler-pdftoppm/v1"
                    or asset.mime_type != "image/png"):
                fail()
            used.add(binding.asset_ref)
    if derived != used:
        fail()
    return bindings


def re_hash(value):
    import re
    return isinstance(value, str) and re.fullmatch(HASH_PATTERN, value) is not None


def source_label(binding: TablePlaceholderBinding) -> str:
    page = str(binding.page_index + 1) if binding.page_index is not None else "未知"
    bbox = ",".join(format(value, ".8g") for value in binding.bbox) if binding.bbox is not None else "未知"
    kind = "MinerU参考图" if binding.source_kind == "mineru_reference" else "源PDF裁图"
    return f"来源：{kind}；源页：{page}；bbox：{bbox}；片段：{binding.fragment_id}"
