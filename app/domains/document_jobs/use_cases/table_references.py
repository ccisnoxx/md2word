from __future__ import annotations

# app/domains/document_jobs/use_cases/table_references.py: 用例：表格参考图列表与内容读取。

import hashlib
from typing import Any

from app.core.errors import ApiError
from app.domains.document_jobs.models import DocumentJobRecord
from app.domains.document_jobs.views.translation import (
    DocumentJobTableReferenceListResponse,
    DocumentJobTableReferenceResponse,
)
from app.domains.document_jobs.use_cases.access import DocumentJobAccess
from app.domains.document_jobs.use_cases.common import TableReferenceContent, TableReferenceSnapshot
from app.domains.files.models import DocumentFileRecord
from app.domains.files.repository import DocumentFileRepositoryProtocol
from app.domains.resources.models import utc_now
from app.services.auth.models import AuthenticatedUser
from app.services.document_ir.models import DocumentIR, TableReferenceProvenance
from app.services.document_ir.table_reference_assets import (
    CHECKSUM_RE,
    DecodedTableReference,
    INLINE_MIME_TYPES,
    RASTER_EXTENSIONS,
    TABLE_REFERENCE_ROLE,
    decode_table_references,
)


class DocumentJobTableReferences:
    """用例：表格参考图列表与内容读取。"""

    def __init__(
        self,
        *,
        file_repository: DocumentFileRepositoryProtocol,
        file_upload_service: Any | None,
        access: DocumentJobAccess,
    ) -> None:
        self.file_repository = file_repository
        self.file_upload_service = file_upload_service
        self.access = access

    def list_table_references(
        self, job_id: str, *, user: AuthenticatedUser, block_id: str | None = None,
    ) -> DocumentJobTableReferenceListResponse:
        """从当前选中 IR 读取审核导航；列表不探测每张远端图片的实际字节。"""
        job = self.access.get_job(job_id, user=user)
        self.access.ensure_job_not_deleted(job)
        ir_file_id = job.document_ir_file_id or job.source_document_ir_file_id
        if ir_file_id is None:
            return DocumentJobTableReferenceListResponse(job_id=job.id, generation=job.retry_count,
                                                        ir_file_id=None, evidence_status="not_ready")
        snapshot = self._load_table_reference_snapshot(job)
        return self.list_table_references_snapshot(snapshot, user=user, block_id=block_id)

    def list_table_references_snapshot(
        self, snapshot: TableReferenceSnapshot, *, user: AuthenticatedUser, block_id: str | None = None,
    ) -> DocumentJobTableReferenceListResponse:
        """只投影已认证观察；新内容 reader 可复用原 IR，免于重复读取字节。"""
        job, ir_file_id = snapshot.job, snapshot.file.id
        items: list[DocumentJobTableReferenceResponse] = []
        for reference in snapshot.references:
            if block_id is not None and reference.block_id != block_id:
                continue
            asset = reference.asset
            file = self._get_table_reference_file(snapshot, reference) if asset is not None else None
            availability = self._table_reference_availability(file) if asset is not None else "source_" + reference.detail.source_status
            items.append(DocumentJobTableReferenceResponse(
                block_id=reference.block_id, fragment_id=reference.fragment.fragment_id,
                logical_group_id=reference.logical_group_id, page_index=reference.fragment.source_span.page_index,
                bbox=reference.fragment.source_span.bbox, asset_id=asset.id if asset else None,
                file_id=asset.file_id if asset else None, source_status=reference.detail.source_status,
                availability=availability, mime_type=asset.mime_type if asset else None,
                checksum_sha256=asset.checksum_sha256 if asset else None, size_bytes=file.size_bytes if file else None,
                warning_codes=(["missing_table_reference"] if reference.detail.source_status == "missing" else
                               ["invalid_table_reference"] if reference.detail.source_status == "invalid" else []),
                display_supported=asset is not None and asset.mime_type in INLINE_MIME_TYPES,
                # 内容入口是 HTTP 路由地址，由路由层 with_table_reference_content_paths 补齐。
                content_path=None,
            ))
        self._recheck_table_reference_snapshot(snapshot, user=user)
        return DocumentJobTableReferenceListResponse(
            job_id=job.id, generation=job.retry_count, ir_file_id=ir_file_id,
            evidence_status="registered" if snapshot.document.metadata.table_references_version else "legacy_unavailable",
            items=items,
        )

    def read_table_reference_content(
        self, job_id: str, asset_id: str, *, user: AuthenticatedUser,
        generation: int, ir_file_id: str, disposition: str,
    ) -> TableReferenceContent:
        """每次重新鉴权并核验 IR/图像实际字节，慢读后再次确认当前快照。"""
        job = self.access.get_job(job_id, user=user)
        self.access.ensure_job_not_deleted(job)
        if generation != job.retry_count or ir_file_id != (job.document_ir_file_id or job.source_document_ir_file_id):
            raise ApiError(409, "conflict", "表格参考图所属任务快照已变化，请刷新列表。")
        snapshot = self._load_table_reference_snapshot(job)
        reference = next((item for item in snapshot.references if item.asset is not None and item.asset.id == asset_id), None)
        if reference is None:
            raise ApiError(404, "not_found", "当前文档未引用该表格参考图。")
        file = self._get_table_reference_file(snapshot, reference)
        availability = self._table_reference_availability(file)
        if availability == "missing":
            raise ApiError(404, "not_found", "表格参考图文件不存在。")
        if availability != "available":
            raise ApiError(409, "conflict", "表格参考图当前不可用。")
        if disposition == "inline" and file.mime_type not in INLINE_MIME_TYPES:
            raise ApiError(409, "conflict", "该栅格格式请使用附件下载。")
        content = self._read_table_reference_bytes(file)
        self._check_table_reference_bytes(file, content)
        self._recheck_table_reference_snapshot(snapshot, user=user)
        if self.file_repository.get_document_file(file.id) != file:
            raise ApiError(409, "conflict", "表格参考图文件状态已变化，请刷新列表。")
        self.access.ensure_file_not_expired(file)
        return TableReferenceContent(content, file.mime_type,
                                     f"table_reference_{asset_id.split(':')[-1]}.{RASTER_EXTENSIONS[file.mime_type]}",
                                     file.id, snapshot.file.id, generation)

    def _load_table_reference_snapshot(self, job: DocumentJobRecord) -> TableReferenceSnapshot:
        ir_id = job.document_ir_file_id or job.source_document_ir_file_id
        file = self.file_repository.get_document_file(ir_id) if ir_id else None
        if file is None:
            raise ApiError(404, "not_found", "当前文档 IR 文件不存在。")
        if file.tenant_id != job.tenant_id or file.company_id != job.company_id or file.job_id != job.id:
            raise ApiError(403, "forbidden", "当前文档 IR 与任务归属不匹配。")
        if file.file_type != "document_ir" or file.status != "uploaded" or file.mime_type != "application/json":
            raise ApiError(409, "conflict", "当前文档 IR 文件不可用。")
        self.access.ensure_file_not_expired(file)
        content = self._read_table_reference_bytes(file)
        self._check_table_reference_bytes(file, content)
        try:
            document = DocumentIR.model_validate_json(content)
        except (ValueError, TypeError, KeyError) as error:
            raise ApiError(409, "conflict", "当前文档的表格参考资产合同无效。") from error
        return self.table_reference_snapshot(job, file, document)

    def table_reference_snapshot(
        self, job: DocumentJobRecord, file: DocumentFileRecord, document: DocumentIR,
    ) -> TableReferenceSnapshot:
        """沿原引用 owner 校验已认证 IR 的绑定及转换来源，不执行额外对象读取。"""
        try:
            references = decode_table_references(document, require_bound=True)
            provenance = (TableReferenceProvenance.model_validate(document.metadata.mineru_validation_input)
                          if document.metadata.table_references_version else None)
        except (ValueError, TypeError, KeyError) as error:
            raise ApiError(409, "conflict", "当前文档的表格参考资产合同无效。") from error
        if document.metadata.job_id != job.id or document.metadata.source_file_id != job.source_file_id:
            raise ApiError(409, "conflict", "当前文档来源与任务不匹配。")
        if provenance is not None:
            file_retry = file.metadata.get("retry_count")
            if (type(file_retry) is not int or not provenance.retry_count <= file_retry <= job.retry_count or
                    file.metadata.get("source_file_id") != job.source_file_id or
                    file.metadata.get("mineru_validation_input") != provenance.model_dump() or
                    document.metadata.mineru_validation is None or
                    document.metadata.mineru_validation.package_sha256 != provenance.mineru_raw_result_sha256.removeprefix("sha256:")):
                raise ApiError(409, "conflict", "当前文档的转换来源校验不一致。")
        return TableReferenceSnapshot(job, file, document, references, provenance)

    def _get_table_reference_file(
        self, snapshot: TableReferenceSnapshot, reference: DecodedTableReference,
    ) -> DocumentFileRecord | None:
        asset, provenance, job = reference.asset, snapshot.provenance, snapshot.job
        file = self.file_repository.get_document_file(asset.file_id)
        if file is None:
            return None
        if file.tenant_id != job.tenant_id or file.company_id != job.company_id or file.job_id != job.id:
            raise ApiError(403, "forbidden", "表格参考图与任务归属不匹配。")
        expected = {"asset_role": TABLE_REFERENCE_ROLE, "asset_id": asset.id, "block_id": reference.block_id,
                    "fragment_id": reference.fragment.fragment_id, "logical_group_id": reference.logical_group_id,
                    "source_file_id": job.source_file_id, "source_path": asset.source_path,
                    "mineru_raw_result_file_id": provenance.mineru_raw_result_file_id, "retry_count": provenance.retry_count}
        if (file.file_type != "image_asset" or file.mime_type != asset.mime_type or
                file.checksum_sha256 != asset.checksum_sha256 or file.size_bytes <= 0 or
                type(file.metadata.get("retry_count")) is not int or
                any(file.metadata.get(key) != value for key, value in expected.items())):
            raise ApiError(409, "conflict", "表格参考图的角色、来源或完整性校验不一致。")
        return file

    @staticmethod
    def _table_reference_availability(file: DocumentFileRecord | None) -> str:
        if file is None:
            return "missing"
        if file.status == "deleted":
            return "deleted"
        if file.status == "expired" or file.expires_at is not None and file.expires_at <= utc_now():
            return "expired"
        return "available" if file.status == "uploaded" else "not_uploaded"

    def _read_table_reference_bytes(self, file: DocumentFileRecord) -> bytes:
        if self.file_upload_service is None:
            raise ApiError(503, "service_unavailable", "表格参考资产存储当前不可用。")
        try:
            return self.file_upload_service.read_file_content(file)
        except FileNotFoundError as error:
            raise ApiError(404, "not_found", "表格参考资产内容不存在。") from error
        except Exception as error:
            # S3 错误只读取受控 code，不能把 bucket、key 或原始异常返回客户端。
            response = getattr(error, "response", None)
            details = response.get("Error") if isinstance(response, dict) else None
            if isinstance(details, dict) and details.get("Code") in {"NoSuchKey", "404", "NotFound"}:
                raise ApiError(404, "not_found", "表格参考资产内容不存在。") from error
            raise ApiError(503, "service_unavailable", "表格参考资产存储当前不可用。") from error

    @staticmethod
    def _check_table_reference_bytes(file: DocumentFileRecord, content: bytes) -> None:
        if (not isinstance(file.checksum_sha256, str) or CHECKSUM_RE.fullmatch(file.checksum_sha256) is None or
                len(content) != file.size_bytes or "sha256:" + hashlib.sha256(content).hexdigest() != file.checksum_sha256):
            raise ApiError(409, "conflict", "表格参考资产内容校验不一致。")

    def _recheck_table_reference_snapshot(self, snapshot: TableReferenceSnapshot, *, user: AuthenticatedUser) -> None:
        current = self.access.get_job(snapshot.job.id, user=user)
        self.access.ensure_job_not_deleted(current)
        if (current.retry_count != snapshot.job.retry_count or
                (current.document_ir_file_id or current.source_document_ir_file_id) != snapshot.file.id or
                self.file_repository.get_document_file(snapshot.file.id) != snapshot.file):
            raise ApiError(409, "conflict", "表格参考图所属任务快照已变化，请刷新列表。")
        self.access.ensure_file_not_expired(snapshot.file)
