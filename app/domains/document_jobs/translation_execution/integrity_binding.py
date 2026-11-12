"""翻译完整性绑定：批次与任务快照的绑定校验，以及成功叶子译文的重核回放。"""

from __future__ import annotations

import json

from app.domains.document_jobs.execution_support import require_uploaded_file
from app.domains.document_jobs.models import DocumentJobRecord, DocumentJobTranslationBatchRecord
from app.domains.document_jobs.publication_provenance import actual_call_fact
from app.domains.document_jobs.review import digest
from app.domains.document_jobs.translation_execution.deps import TranslationExecutionDeps
from app.domains.document_jobs.translation_execution.planning import TranslationPlanner
from app.domains.files.models import DocumentFileRecord
from app.domains.translation.document_ir_translator import DocumentIRTranslationError
from app.domains.translation.integrity import TranslationIntegrityBinding
from app.domains.translation.models import (
    TranslationProfileSnapshot,
    TranslationTextItem,
    TermVersionSnapshot,
)
from app.domains.translation.modes import spec_for_document_job_mode
from app.domains.translation.provider import OpenAICompatibleTranslationProvider


class TranslationIntegrityBinder:
    """构造批次完整性绑定，并在汇合前对全部成功叶子的来源、恢复文本与证据重核。"""

    def __init__(
        self,
        deps: TranslationExecutionDeps,
        *,
        planner: TranslationPlanner,
    ) -> None:
        self.deps = deps
        self.planner = planner

    def binding(
        self, job: DocumentJobRecord, batch: DocumentJobTranslationBatchRecord,
        source_file: DocumentFileRecord, profile: TranslationProfileSnapshot | None,
        term_version: TermVersionSnapshot | None,
    ) -> TranslationIntegrityBinding:
        spec = spec_for_document_job_mode(job.mode)
        term_hash = term_version.snapshot_hash if term_version is not None else None
        term_id = term_version.term_version_id if term_version is not None else job.term_version_id
        if (
            batch.job_id != job.id or batch.job_retry_count != job.retry_count
            or batch.generation != job.retry_count or batch.source_document_ir_file_id != source_file.id
            or batch.language_pair != spec.language_pair or batch.term_snapshot_hash != term_hash
            or batch.term_version_id != term_id
        ):
            raise DocumentIRTranslationError("翻译批次绑定与当前任务快照不一致。", code="translation_integrity_evidence_mismatch")
        return TranslationIntegrityBinding(
            job_id=job.id, batch_id=batch.id, root_batch_id=batch.root_batch_id,
            parent_batch_id=batch.parent_batch_id, attempt=batch.attempt_count, generation=batch.generation,
            source_document_ir_file_id=source_file.id, source_document_ir_sha256=source_file.checksum_sha256,
            profile_snapshot_hash=profile.snapshot_hash if profile is not None else None,
            prompt_content_hash=profile.prompt.content_hash if profile is not None else None,
            term_snapshot_hash=term_hash,
        )

    def load_batch_replacements(
        self, job: DocumentJobRecord, source_file: DocumentFileRecord,
        source_items: list[TranslationTextItem], batches: list[DocumentJobTranslationBatchRecord],
        *, publication_calls: list | None = None,
    ) -> dict[str, str]:
        """对全部叶子的本地来源、恢复文本和证据重核，全部通过后才交给 apply。"""
        replacements: dict[str, str] = {}
        spec = spec_for_document_job_mode(job.mode)
        profile = self.planner.profile_for_job(job, language_pair=spec.language_pair)
        term_version = self.planner.resolve_term_version(job)
        for selected in sorted(batches, key=lambda item: (item.page_start or 0, item.created_at, item.id)):
            batch = self.deps.translation_batch_repository.get_translation_batch(selected.id)
            if batch is None or batch.status != "succeeded" or not batch.result_file_id or (
                batch.attempt_count != selected.attempt_count
            ):
                raise DocumentIRTranslationError("翻译成功批次已变化或缺少结果。", code="translation_integrity_evidence_mismatch")
            binding = self.binding(job, batch, source_file, profile, term_version)
            local_items = tuple(item for item in source_items if item.id in batch.item_ids)
            if (
                tuple(item.id for item in local_items) != tuple(batch.item_ids)
                or batch.item_count != len(local_items)
                or batch.char_count != sum(len(item.text) for item in local_items)
            ):
                raise DocumentIRTranslationError("翻译批次有序源项边界不一致。", code="translation_integrity_evidence_mismatch")
            candidate = require_uploaded_file(self.deps.file_repository, batch.result_file_id)
            candidate_payload = json.loads(self.deps.file_service.read_file_content(candidate))
            candidate_items = candidate_payload.get("items") if isinstance(candidate_payload, dict) else None
            if isinstance(candidate_items, list):
                candidate_ids = [item.get("id") for item in candidate_items if isinstance(item, dict)]
                if set(candidate_ids) != set(batch.item_ids) and len(candidate_ids) == len(set(candidate_ids)):
                    raise DocumentIRTranslationError(
                        "翻译批次合并结果不完整。", code="translation_fan_in_mismatch",
                    )
            result_file, content = self.planner.read_artifact(job, batch.result_file_id, file_type="translation_batch_result")
            payload = json.loads(content)
            raw_items = payload.get("items") if isinstance(payload, dict) else None
            if isinstance(raw_items, list):
                raw_item_ids = [item.get("id") for item in raw_items if isinstance(item, dict)]
                if set(raw_item_ids) != set(batch.item_ids) and len(raw_item_ids) == len(set(raw_item_ids)):
                    raise DocumentIRTranslationError(
                        "翻译批次合并结果不完整。", code="translation_fan_in_mismatch",
                    )
            envelope = {
                "job_id": job.id, "batch_id": batch.id, "root_batch_id": batch.root_batch_id,
                "parent_batch_id": batch.parent_batch_id, "generation": batch.generation,
                "attempt": batch.attempt_count, "source_document_ir_file_id": source_file.id,
                "language_pair": batch.language_pair,
            }
            if (
                not isinstance(payload, dict) or payload.get("schema_version") != "translation-batch-result/v1"
                or any(key not in payload or type(payload[key]) is not type(value) or payload[key] != value for key, value in envelope.items())
                or any(key not in result_file.metadata or type(result_file.metadata[key]) is not type(value) or result_file.metadata[key] != value for key, value in envelope.items() if key not in {"job_id", "attempt"})
                or type(result_file.metadata.get("attempt_count")) is not int
                or result_file.metadata["attempt_count"] != batch.attempt_count
            ):
                raise DocumentIRTranslationError("翻译结果 Artifact 关联不一致。", code="translation_integrity_evidence_mismatch")
            restored = OpenAICompatibleTranslationProvider._parse_items({"items": payload.get("items")})
            validated = self.deps.document_ir_translation_service.validator.validate_persisted(
                local_items, restored, payload.get("integrity"), binding=binding,
            )
            if publication_calls is not None:
                provenance = payload.get("publication_provenance")
                if provenance is not None:
                    if (not isinstance(provenance, dict) or provenance.get("schema_version") != "publication-batch/v1"
                            or provenance.get("integrity_sha256") != digest(payload["integrity"])
                            or type(provenance.get("attempt")) is not int or provenance["attempt"] != batch.attempt_count):
                        raise DocumentIRTranslationError("翻译发布来源与成功尝试不一致。", code="translation_integrity_evidence_mismatch")
                    actual_call_fact(provenance.get("call"))
                publication_calls.append({"batch_id": batch.id, "attempt": batch.attempt_count,
                    "result_file_id": result_file.id, "result_sha256": result_file.checksum_sha256,
                    "provenance": provenance} if provenance is not None else None)
            if replacements.keys() & validated.replacements.keys():
                raise DocumentIRTranslationError("翻译叶子批次包含重复合并项。", code="translation_integrity_item_duplicate")
            replacements.update(validated.replacements)
        return replacements
