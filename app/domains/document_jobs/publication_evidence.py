"""发布的锁外认证闭包；复用复核、表格和预览 owner，不重跑生产者。"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib

from app.domains.document_jobs.preview import read_current_preview_evidence
from app.domains.document_jobs.publication import (
    PublicationConflict, ensure_publication_object_identities, publication_file_available,
)
from app.domains.document_jobs.publication_provenance import actual_call_fact, read_private_provenance
from app.domains.document_jobs.review import digest, quality_snapshot
from app.domains.document_jobs.table_evidence import verify_report
from app.domains.files.models import DocumentFileRecord
from app.domains.jobs.models import JobResourceSnapshot
from app.domains.resources.models import utc_now
from app.domains.translation.modes import spec_for_document_job_mode


@dataclass(frozen=True)
class PublicationEvidence:
    files: tuple[DocumentFileRecord, ...]
    quality: dict
    preview: dict
    configuration: dict


def prepare_publication_evidence(job, *, file_repository, file_service, job_repository) -> PublicationEvidence:
    now = utc_now()
    files = {}

    def require(file_id, kind, *, same_job=True):
        file = file_repository.get_document_file(file_id)
        if (file is None or file.file_type != kind or not publication_file_available(file, now=now)
                or (file.tenant_id, file.company_id) != (job.tenant_id, job.company_id)
                or same_job and file.job_id != job.id):
            raise PublicationConflict("publication_result_unavailable")
        try:
            content = file_service.read_file_content(file)
        except FileNotFoundError:
            raise PublicationConflict("publication_result_unavailable") from None
        if len(content) != file.size_bytes or "sha256:" + hashlib.sha256(content).hexdigest() != file.checksum_sha256:
            raise PublicationConflict("publication_hash_mismatch")
        files[file.id] = file
        return file

    source = require(job.source_file_id, "source_pdf", same_job=False)
    source_snapshot = job.request_snapshot.get("source_file")
    if not isinstance(source_snapshot, dict) or any(source_snapshot.get(key) != getattr(source, key)
            for key in ("id", "object_key", "mime_type", "size_bytes", "checksum_sha256")):
        raise PublicationConflict("publication_source_changed")
    result = require(job.result_file_id, "generated_word")
    if (result.metadata.get("source_file_id") != source.id or job.prepared_result is None
            or job.prepared_result.file.id != result.id):
        raise PublicationConflict("publication_source_changed")
    state = job.word_preview_state
    if (state is None or state.current_run.status != "succeeded" or state.current_run.artifact_stage != "confirmed"
            or state.current_run.confirmed_attempt != state.current_run.attempt_count):
        raise PublicationConflict("publication_preview_unavailable")
    try:
        preview = read_current_preview_evidence(job, file_repository, file_service,
            include_page_quality=True, include_render=True)
    except ValueError:
        raise PublicationConflict("publication_preview_unavailable") from None
    if not preview.observation.available or preview.render_plan is None:
        raise PublicationConflict("publication_preview_unavailable")
    for file in (*preview.observation.files, *preview.authentication_files):
        files[file.id] = file
    if job.document_ir_file_id not in {file.id for file in preview.authentication_files}:
        raise PublicationConflict("publication_snapshot_unavailable")
    verified = verify_report(job, result, file_repository=file_repository, file_service=file_service,
                             job_repository=job_repository)
    if verified is not None:
        for file in verified.files:
            files[file.id] = file
    provenance_id = result.metadata.get("publication_provenance_file_id")
    if not isinstance(provenance_id, str):
        raise PublicationConflict("publication_snapshot_unavailable")
    provenance_file, provenance = read_private_provenance(provenance_id, job,
        file_repository=file_repository, file_service=file_service)
    files[provenance_file.id] = provenance_file
    if provenance.get("status") == "mismatch":
        raise PublicationConflict("publication_snapshot_mismatch")
    if provenance.get("status") != "complete" or provenance.get("schema_version") != "publication-render/v1":
        raise PublicationConflict("publication_snapshot_unavailable")
    plan_identity = preview.render_plan.resource_identity.model_dump(mode="json")
    if (provenance.get("document_ir_file_id") != job.document_ir_file_id
            or provenance.get("document_ir_sha256") != files[job.document_ir_file_id].checksum_sha256
            or provenance.get("result_sha256") != result.checksum_sha256
            or provenance.get("resource_identity") != plan_identity
            or provenance.get("declared_resource_identity") != plan_identity
            or not isinstance(provenance.get("renderer"), dict)
            or provenance["renderer"].get("schema_version") != "renderer-python-code/v1"
            or not provenance["renderer"].get("implementation_sha256")):
        raise PublicationConflict("publication_snapshot_mismatch")
    try:
        declared = JobResourceSnapshot.model_validate(provenance["declared_resources"])
        current = JobResourceSnapshot.model_validate(job.request_snapshot["resources"])
    except (KeyError, ValueError, TypeError):
        raise PublicationConflict("publication_snapshot_unavailable") from None
    if (declared != current or declared.template is None or declared.term_rule_set is None
            or job.template_version_id != f"{declared.template.resource_id}@{declared.template.version}"
            or result.metadata.get("template_version_id") != job.template_version_id
            or job.request_snapshot.get("mode") != job.mode):
        raise PublicationConflict("publication_snapshot_mismatch")
    spec = spec_for_document_job_mode(job.mode)
    translation = {"status": "not_applicable"}
    if spec.is_translation:
        translation_id = provenance.get("translation_provenance_file_id")
        if not isinstance(translation_id, str):
            raise PublicationConflict("publication_snapshot_unavailable")
        translation_file, translation = read_private_provenance(translation_id, job,
            file_repository=file_repository, file_service=file_service)
        files[translation_file.id] = translation_file
        if (translation.get("schema_version") != "publication-translation/v1" or translation.get("status") != "complete"
                or translation.get("source_document_ir_file_id") != job.source_document_ir_file_id
                or not isinstance(translation.get("batches"), list)):
            raise PublicationConflict("publication_snapshot_unavailable")
        for batch in translation["batches"]:
            fact = batch["provenance"]
            try:
                actual_call_fact(fact["call"])
                profile, term = fact["profile"], fact["term"]
                if (declared.translation_profile is None or declared.translation_term_set is None
                        or profile["snapshot_hash"] != declared.translation_profile.snapshot_hash
                        or profile["prompt"]["id"] != declared.translation_prompt_id
                        or profile["prompt"]["content_hash"] != declared.translation_prompt_content_hash
                        or term["snapshot_hash"] != declared.translation_term_set.snapshot_hash):
                    raise PublicationConflict("publication_snapshot_mismatch")
            except (KeyError, TypeError, ValueError):
                raise PublicationConflict("publication_snapshot_mismatch") from None
        # 有效成功批次的调用事实已在 fan-in 汇总到独立不可变报告，不永久保留批次正文。
    file_service.ensure_publication_physical_exclusive(tuple(files.values()))
    ensure_publication_object_identities(list(files.values()), file_repository.list_document_files())
    quality = quality_snapshot(job).model_dump(mode="json")
    quality["table_report"] = ({"file_id": verified.files[0].id, "sha256": verified.files[0].checksum_sha256,
        "report_sha256": verified.envelope.report.report_sha256} if verified is not None else None)
    quality["page_quality_run_sha256"] = preview.page_quality_run.get("run_sha256") if preview.page_quality_run else None
    return PublicationEvidence(tuple(sorted(files.values(), key=lambda file: file.id)), quality,
        {"run_id": state.current_run.run_id, "revision": state.revision, "attempt": state.current_run.attempt_count,
         "profile_id": state.profile_id, "profile_sha256": state.profile_sha256,
         "manifest_file_id": state.current_run.manifest_file_id,
         "manifest_sha256": files[state.current_run.manifest_file_id].checksum_sha256,
         "pdf_file_id": preview.manifest["pdf_file_id"], "page_file_ids": preview.manifest["page_file_ids"]},
        {"mode": job.mode, "document_language": plan_identity["document_language"],
         "declared_resources": declared.model_dump(mode="json"), "render": provenance,
         "translation": translation})


def public_publication_record(record):
    """公开字段显式白名单；Prompt、术语、对象定位和私有执行快照均留在仓储。"""
    resources = record.configuration["declared_resources"]
    translation = record.configuration["translation"]
    models = sorted({batch["provenance"]["call"]["model"] for batch in translation.get("batches", [])})
    return {"publication_id": record.id, "job_id": record.job_id, "generation": record.generation,
        "source_file_id": record.source_file_id, "source_sha256": record.source_sha256,
        "result_file_id": record.result_file_id, "result_sha256": record.result_sha256,
        "review_record_id": record.review_record_id, "review_sequence": record.review_sequence,
        "preview_run_id": record.preview["run_id"], "published_by": record.published_by,
        "published_at": record.published_at, "note": record.note,
        "versions": {"template": {key: resources["template"][key] for key in ("resource_id", "version", "snapshot_hash")},
            "symbol_rules": {key: resources["term_rule_set"][key] for key in ("resource_id", "version", "snapshot_hash")},
            "renderer_implementation_sha256": record.configuration["render"]["renderer"]["implementation_sha256"],
            "translation_status": translation["status"], "models": models}}
