"""翻译计划生成：读取并校验不可变 source，按资源快照计算本代权威根计划。"""

from __future__ import annotations

import hashlib

from app.domains.document_jobs.execution_support import require_uploaded_file
from app.domains.document_jobs.models import DocumentJobRecord
from app.domains.document_jobs.translation_execution.deps import TranslationExecutionDeps
from app.domains.document_jobs.workflow import TranslationRootPlan
from app.domains.files.models import DocumentFileRecord
from app.domains.jobs.models import JobResourceSnapshot
from app.domains.jobs.resource_snapshots import JobResourceSnapshotError
from app.domains.translation.document_ir_translator import (
    DocumentIRTranslationError,
    DocumentIRTranslationTarget,
)
from app.domains.translation.models import TranslationProfileSnapshot
from app.domains.translation.modes import spec_for_document_job_mode
from app.services.document_ir.models import DocumentIR


class TranslationPlanner:
    """由 source IR 与任务资源快照（Profile、术语版本）计算权威根计划；不写任何状态。"""

    def __init__(
        self,
        deps: TranslationExecutionDeps,
    ) -> None:
        self.deps = deps

    def read_artifact(
        self, job: DocumentJobRecord, file_id: str, *, file_type: str,
    ) -> tuple[DocumentFileRecord, bytes]:
        """按已登记的对象读取并验证字节；路径模板和 payload 不能自证归属。"""
        record = require_uploaded_file(self.deps.file_repository, file_id)
        if (
            record.job_id != job.id or record.tenant_id != job.tenant_id
            or record.company_id != job.company_id or record.file_type != file_type
            or (file_type == "translation_batch_result" and (
                type(record.metadata.get("retry_count")) is not int
                or record.metadata["retry_count"] != job.retry_count
            ))
        ):
            raise DocumentIRTranslationError("翻译 Artifact 来源或代次不一致。", code="translation_integrity_evidence_mismatch")
        content = self.deps.file_service.read_file_content(record)
        checksum = "sha256:" + hashlib.sha256(content).hexdigest()
        if record.checksum_sha256 != checksum or record.size_bytes != len(content):
            raise DocumentIRTranslationError("翻译 Artifact 字节校验失败。", code="translation_integrity_evidence_mismatch")
        return record, content

    def read_source(
        self, job: DocumentJobRecord, file_id: str | None,
    ) -> tuple[DocumentFileRecord, DocumentIR]:
        if not file_id or file_id != job.source_document_ir_file_id:
            raise DocumentIRTranslationError("翻译 source IR 引用不一致。", code="translation_integrity_evidence_mismatch")
        # retry 沿用任务权威指针指向的不可变源件；创建代次不等于本次消费代次。
        record, content = self.read_artifact(job, file_id, file_type="document_ir")
        translation = record.metadata.get("translation")
        if not isinstance(translation, dict) or translation.get("role") != "source" or translation.get("applied") is not False:
            raise DocumentIRTranslationError("翻译 source IR 角色不一致。", code="translation_integrity_evidence_mismatch")
        document_ir = DocumentIR.model_validate_json(content)
        if document_ir.metadata.job_id != job.id or document_ir.metadata.source_file_id != job.source_file_id:
            raise DocumentIRTranslationError("翻译 source IR 文档来源不一致。", code="translation_integrity_evidence_mismatch")
        return record, document_ir

    def build_expected_plans(
        self,
        job: DocumentJobRecord,
        source_document_ir: DocumentIR,
    ) -> list[TranslationRootPlan]:
        """由不可变 source、资源快照计算本代根计划，供 reducer 与安装端口共用。"""

        spec = spec_for_document_job_mode(job.mode)
        if spec.language_pair is None:
            return []
        if self.deps.document_ir_translation_service is None:
            raise DocumentIRTranslationError("DocumentIR 翻译服务未配置。")
        profile = self.profile_for_job(job, language_pair=spec.language_pair)
        max_pages, max_chars = self.profile_batch_limits(profile)
        term_version = self.resolve_term_version(job)
        _targets, _items, plans = self.deps.document_ir_translation_service.build_translation_plan(
            source_document_ir,
            max_pages_per_batch=max_pages,
            max_chars_per_batch=max_chars,
            batch_id_prefix=f"{job.id}_retry{job.retry_count}_translation_batch",
        )
        provider_call_budget = min(200, len(plans) * 12)
        max_attempts = max(1, self.deps.settings.translation_provider_batch_max_attempts)
        return [
            TranslationRootPlan(
                batch_id=plan.batch_id,
                job_id=job.id,
                generation=job.retry_count,
                job_retry_count=job.retry_count,
                source_document_ir_file_id=job.source_document_ir_file_id or "",
                language_pair=spec.language_pair,
                item_ids=tuple(plan.item_ids),
                item_count=plan.item_count,
                char_count=plan.char_count,
                page_start=plan.page_start,
                page_end=plan.page_end,
                term_version_id=(
                    term_version.term_version_id
                    if term_version is not None else job.term_version_id
                ),
                term_snapshot_hash=(
                    term_version.snapshot_hash if term_version is not None else None
                ),
                split_level=plan.split_level,
                deterministic_batch_count=len(plans),
                provider_call_budget=provider_call_budget,
                max_attempts=max_attempts,
            )
            for plan in plans
        ]

    def profile_for_job(
        self,
        job: DocumentJobRecord,
        *,
        language_pair: str,
    ) -> TranslationProfileSnapshot | None:
        """读取任务绑定的不可变 Profile；无资源快照仅表示 legacy mode。"""

        resources = job.request_snapshot.get("resources")
        if resources is None:
            return None
        if not isinstance(resources, dict):
            raise DocumentIRTranslationError("任务资源快照格式非法。")
        try:
            snapshot = JobResourceSnapshot.model_validate(resources)
        except ValueError as exc:
            raise DocumentIRTranslationError(f"任务资源快照格式非法: {exc}") from exc
        if snapshot.translation_profile is None:
            raise DocumentIRTranslationError("翻译任务缺少绑定的 Translation Profile。")
        if self.deps.job_resource_snapshot_service is None:
            raise DocumentIRTranslationError(
                "当前 Worker 缺少 resource snapshot service。"
            )
        try:
            profile = self.deps.job_resource_snapshot_service.materialize_translation_profile(
                snapshot.translation_profile
            )
        except (JobResourceSnapshotError, FileNotFoundError, ValueError) as exc:
            raise DocumentIRTranslationError(str(exc)) from exc
        if profile.language_pair != language_pair:
            raise DocumentIRTranslationError(
                "任务绑定的 Translation Profile 语言方向不匹配: "
                f"expected={language_pair} actual={profile.language_pair}"
            )

        prompt_metadata = (
            snapshot.translation_prompt_id,
            snapshot.translation_prompt_content_hash,
        )
        if any(value is not None for value in prompt_metadata):
            if (
                snapshot.translation_prompt_id != profile.prompt.id
                or snapshot.translation_prompt_content_hash
                != profile.prompt.content_hash
            ):
                raise DocumentIRTranslationError(
                    "任务绑定的 Translation Profile Prompt 元数据不匹配。"
                )
        return profile

    def profile_batch_limits(
        self,
        profile: TranslationProfileSnapshot | None,
    ) -> tuple[int, int]:
        if profile is None:
            return (
                max(1, int(self.deps.settings.translation_max_pages)),
                max(1, int(self.deps.settings.translation_max_chars)),
            )
        return (
            max(1, int(profile.max_pages_per_batch)),
            max(1, int(profile.max_chars_per_batch)),
        )

    def resolve_term_version(self, job: DocumentJobRecord):
        if self.deps.term_version_service is None:
            return None
        spec = spec_for_document_job_mode(job.mode)
        if spec.language_pair is None:
            return None
        if job.term_version_id:
            return self.deps.term_version_service.load_version(job.term_version_id, language_pair=spec.language_pair)
        return self.deps.term_version_service.resolve_for_job(None, language_pair=spec.language_pair)

    @staticmethod
    def page_range_for_item_ids(
        item_ids: list[str],
        targets_by_id: dict[str, DocumentIRTranslationTarget],
    ) -> tuple[int | None, int | None]:
        pages = [
            target.page_number
            for item_id in item_ids
            if (target := targets_by_id.get(item_id)) is not None and target.page_number is not None
        ]
        if not pages:
            return None, None
        return min(pages), max(pages)
