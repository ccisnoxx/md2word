"""Word 渲染的表格占位图来源与依赖核验。"""

from __future__ import annotations

from typing import Callable

from app.domains.document_jobs.models import DocumentJobRecord
from app.domains.document_jobs.repository import DocumentJobRepositoryProtocol
from app.domains.files import FileUploadService
from app.domains.files.models import DocumentFileRecord
from app.domains.files.repository import DocumentFileRepositoryProtocol
from app.domains.resources.models import utc_now
from app.services.document_ir.models import DocumentIR, DocumentIRAsset, TableReferenceProvenance
from app.services.document_ir.table_placeholder import (
    PdfCropSource,
    TablePlaceholderError,
    checksum as placeholder_checksum,
    decode_placeholders,
)
from app.services.document_ir.table_reference_assets import TABLE_REFERENCE_ROLE, decode_table_references


class RenderPlaceholderSource:
    """表格占位图的来源与依赖核验：绑定源 PDF、占位图资产的当前身份与字节，以及占位感知的图片加载器。

    所有读取前后都核对同代任务快照与文件描述；错误只给出稳定错误码，不带存储定位。
    """

    def __init__(
        self,
        *,
        job_repository: DocumentJobRepositoryProtocol,
        file_repository: DocumentFileRepositoryProtocol,
        file_service: FileUploadService,
    ) -> None:
        self.job_repository = job_repository
        self.file_repository = file_repository
        self.file_service = file_service

    def _ensure_attempt_current(self, job: DocumentJobRecord, error_code: str) -> None:
        """慢读两侧核对仍在执行的同代/最终 IR；质量摘要等无关并发更新不影响快照。"""
        current = self.job_repository.get_document_job(job.id)
        if (current is None or current.status != "running" or current.deleted_at is not None
                or current.archived_at is not None or current.retry_count != job.retry_count
                or current.document_ir_file_id != job.document_ir_file_id
                or (current.tenant_id, current.company_id, current.source_file_id, current.source_job_id) !=
                   (job.tenant_id, job.company_id, job.source_file_id, job.source_job_id)):
            raise TablePlaceholderError(error_code)

    def ensure_file_current(self, job: DocumentJobRecord, file: DocumentFileRecord, error_code: str) -> None:
        """与 IR-206 相同：按 ID 重取并比较完整描述，不把有 file_id 当作当前可读。"""
        if (self.file_repository.get_document_file(file.id) != file or file.status != "uploaded"
                or file.expires_at is not None and file.expires_at <= utc_now()):
            raise TablePlaceholderError(error_code)
        self._ensure_attempt_current(job, error_code)

    def _read_current_file(self, job: DocumentJobRecord, file: DocumentFileRecord,
                                       error_code: str = "table_placeholder_integrity_failed") -> bytes:
        """字节读取前后核验同一描述、生命周期、任务快照与实际 hash；错误不带存储定位。"""
        snapshot = file.model_copy(deep=True)
        self.ensure_file_current(job, snapshot, error_code)
        try:
            content = self.file_service.read_file_content(snapshot)
        except Exception:
            raise TablePlaceholderError(error_code) from None
        self.ensure_file_current(job, snapshot, error_code)
        if len(content) != snapshot.size_bytes or placeholder_checksum(content) != snapshot.checksum_sha256:
            raise TablePlaceholderError("table_placeholder_integrity_failed")
        return content

    def _get_source_file(self, job: DocumentJobRecord,
                                      error_code: str = "table_placeholder_source_unavailable") -> DocumentFileRecord:
        """裁图或未完成 receipt 只认绑定源；clone 沿既有同源父链核验归属。"""
        file = self.file_repository.get_document_file(job.source_file_id)
        if (file is None or file.file_type != "source_pdf" or file.status != "uploaded"
                or (file.tenant_id, file.company_id) != (job.tenant_id, job.company_id)
                or file.expires_at is not None and file.expires_at <= utc_now()
                or not file.checksum_sha256):
            raise TablePlaceholderError(error_code)
        owner = job
        seen = set()
        while file.job_id != owner.id:
            if owner.id in seen or owner.source_job_id is None:
                raise TablePlaceholderError(error_code)
            seen.add(owner.id)
            owner = self.job_repository.get_document_job(owner.source_job_id)
            if (owner is None or owner.source_file_id != file.id
                    or (owner.tenant_id, owner.company_id) != (job.tenant_id, job.company_id)):
                raise TablePlaceholderError(error_code)
        return file

    def load_source(self, job: DocumentJobRecord) -> PdfCropSource:
        file = self._get_source_file(job)
        content = self._read_current_file(job, file, "table_placeholder_source_unavailable")
        return PdfCropSource(file.id, file.checksum_sha256, content)

    def _read_asset(self, job: DocumentJobRecord, document: DocumentIR, asset: DocumentIRAsset, binding):
        """仅显式消费的占位图按当前 ID 读取；来源 attempt 可早于翻译 retry，不能硬套最新代。"""
        file = self.file_repository.get_document_file(asset.file_id)
        try:
            provenance = TableReferenceProvenance.model_validate(document.metadata.mineru_validation_input)
        except ValueError:
            raise TablePlaceholderError("table_placeholder_integrity_failed") from None
        expected = {"asset_id": asset.id, "source_file_id": job.source_file_id,
                    "fragment_id": binding.fragment_id, "retry_count": provenance.retry_count}
        if binding.source_kind == "mineru_reference":
            reference = next(item for item in decode_table_references(document, require_bound=True)
                             if item.fragment.fragment_id == binding.fragment_id)
            expected.update(asset_role=TABLE_REFERENCE_ROLE, block_id=reference.block_id,
                logical_group_id=reference.logical_group_id, source_path=asset.source_path,
                mineru_raw_result_file_id=provenance.mineru_raw_result_file_id)
        else:
            expected.update(asset_role="table_placeholder", source_pdf_sha256=binding.source_pdf_sha256)
        if (file is None or file.file_type != "image_asset" or file.mime_type != asset.mime_type
                or (file.tenant_id, file.company_id, file.job_id) != (job.tenant_id, job.company_id, job.id)
                or file.checksum_sha256 != asset.checksum_sha256 or file.object_key != asset.object_key
                or not provenance.retry_count <= job.retry_count
                or type(file.metadata.get("retry_count")) is not int
                or any(file.metadata.get(key) != value for key, value in expected.items())):
            raise TablePlaceholderError("table_placeholder_integrity_failed")
        return file, self._read_current_file(job, file)

    def verify_dependencies(self, job: DocumentJobRecord, document: DocumentIR) -> None:
        """未完成 receipt 复核原绑定依赖；只读取原件，不重渲染、重裁图或替换身份。"""
        bindings = decode_placeholders(document, require_bound=True)
        if not bindings:
            return
        source = self._get_source_file(job, "table_placeholder_integrity_failed")
        snapshots = [source]
        crop_hashes = {item.source_pdf_sha256 for item in bindings if item.source_kind == "source_pdf_crop"}
        if crop_hashes:
            self._read_current_file(job, source)
            if crop_hashes != {source.checksum_sha256}:
                raise TablePlaceholderError("table_placeholder_integrity_failed")
        assets = {asset.id: asset for asset in document.assets}
        for binding in bindings:
            file, _ = self._read_asset(job, document, assets[binding.asset_ref], binding)
            snapshots.append(file)
        # 后续图片慢读也可能使前面的源/图片失效；所有 I/O 完成后再次对账。
        for file in snapshots:
            self.ensure_file_current(job, file, "table_placeholder_integrity_failed")

    def build_image_loader(self, job: DocumentJobRecord, document_ir: DocumentIR) -> Callable[[DocumentIRAsset], bytes | None]:
        bindings = {item.asset_ref: item for item in decode_placeholders(document_ir, require_bound=True)}
        image_files = {
            file.id: file
            for file in self.file_repository.list_document_files()
            if file.job_id == job.id and file.file_type == "image_asset" and file.status == "uploaded"
        }

        def load_image(asset: DocumentIRAsset) -> bytes | None:
            if asset.id in bindings:
                return self._read_asset(job, document_ir, asset, bindings[asset.id])[1]
            if asset.id.startswith(("table-reference:", "table-placeholder:")):
                # 普通 QA 参考图不能借普通 image loader 绕过显式占位消费及其来源核验。
                raise TablePlaceholderError("table_placeholder_integrity_failed")
            if asset.file_id is None:
                return None
            record = image_files.get(asset.file_id)
            return self.file_service.read_file_content(record) if record is not None else None

        return load_image
