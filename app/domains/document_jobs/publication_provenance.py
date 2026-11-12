"""在执行时固化真实配置，发布时只认证已有快照，不解析当前默认值。"""
from __future__ import annotations

import base64
from dataclasses import asdict
import hashlib
import json

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter

from app.domains.document_jobs.publication import PublicationConflict
from app.domains.document_jobs.review import digest
from app.domains.jobs.models import JobResourceSnapshot
from app.services.renderer.resource_identity import renderer_implementation_identity


class _CallParameters(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    timeout_seconds: float = Field(gt=0)
    max_output_tokens: int = Field(gt=0)
    stream: bool
    thinking: dict[str, str]


class _ActualCall(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    schema_version: str
    backend: str
    model: str = Field(min_length=1)
    parameters: _CallParameters


def actual_call_fact(value):
    if value is None:
        return None
    call = _ActualCall.model_validate(value)
    if (call.schema_version != "publication_provenance/v1" or call.backend != "openai_compatible"
            or call.parameters.stream is not False or call.parameters.thinking != {"type": "disabled"}):
        raise ValueError("实际 Provider 配置来源协议无效。")
    return call.model_dump(mode="json")


def batch_publication_provenance(*, result, integrity, batch, profile, term_version):
    """只消费本次实际返回事实；缺事实的历史/fake继续转换但不能据此发布。"""
    call = actual_call_fact(result.publication_provenance)
    return {"schema_version": "publication-batch/v1", "call": call,
        "integrity_sha256": digest(integrity.to_dict()), "attempt": batch.attempt_count,
        "lease_sha256": digest(batch.lease_owner),
        "profile": asdict(profile) if profile is not None else None,
        "term": TypeAdapter(type(term_version)).dump_python(term_version, mode="json") if term_version is not None else None}


def save_translation_publication_provenance(job, calls, *, file_service):
    payload = {"schema_version": "publication-translation/v1", "job_id": job.id, "generation": job.retry_count,
        "source_document_ir_file_id": job.source_document_ir_file_id,
        "status": "complete" if all(call is not None and call["provenance"]["call"] is not None for call in calls) else "unavailable",
        "batches": calls}
    return _save_private_report(job, payload, file_service, "publication-translation.json")


def _save_private_report(job, payload, file_service, filename):
    return file_service.register_generated_content(tenant_id=job.tenant_id, company_id=job.company_id, job_id=job.id,
        created_by=job.created_by, file_type="quality_report", filename=filename, mime_type="application/json",
        content=json.dumps(payload, ensure_ascii=False, sort_keys=True, allow_nan=False).encode(),
        metadata={"asset_role": "publication_provenance", "generation": job.retry_count})


def capture_render_publication_provenance(job, ir_file, render_result, *, resources_publishable, file_service):
    """冻结本次渲染实际消费的实物；草稿和无绑定历史任务不产生可发布证明。"""

    payload = {"schema_version": "publication-render/v1", "job_id": job.id, "generation": job.retry_count,
        "document_ir_file_id": ir_file.id, "document_ir_sha256": ir_file.checksum_sha256,
        "result_sha256": "sha256:" + hashlib.sha256(render_result.content).hexdigest(),
        "renderer": renderer_implementation_identity(), "status": "unavailable"}
    inputs = render_result.resource_inputs
    if resources_publishable and inputs is not None and inputs.template_config is not None:
        try:
            snapshot = JobResourceSnapshot.model_validate(job.request_snapshot["resources"])
        except ValueError:
            # direct 历史惰性翻译字段不影响渲染，完整快照无法认证时保留不可发布状态。
            pass
        else:
            identity = render_result.plan.resource_identity.model_dump(mode="json")
            payload.update(status="complete", resource_identity=identity, declared_resource_identity=identity,
                declared_resources=snapshot.model_dump(mode="json"), resources={
                    "template_docx": base64.b64encode(inputs.template_docx).decode(),
                    "template_config": base64.b64encode(inputs.template_config).decode(),
                    "symbol_rules": base64.b64encode(inputs.symbol_rules).decode(),
                    "logo": base64.b64encode(inputs.logo).decode() if inputs.logo is not None else None})
    translation = ir_file.metadata.get("translation", {})
    payload["translation_provenance_file_id"] = translation.get("publication_provenance_file_id")
    return _save_private_report(job, payload, file_service, "publication-render.json")


def read_private_provenance(file_id, job, *, file_repository, file_service):
    from app.domains.document_jobs.publication import publication_file_available
    from app.domains.resources.models import utc_now
    file = file_repository.get_document_file(file_id)
    if (file is None or file.file_type != "quality_report" or file.metadata.get("asset_role") != "publication_provenance"
            or (file.tenant_id, file.company_id, file.job_id) != (job.tenant_id, job.company_id, job.id)
            or not publication_file_available(file, now=utc_now())):
        raise PublicationConflict("publication_snapshot_unavailable")
    content = file_service.read_file_content(file)
    if len(content) != file.size_bytes or "sha256:" + hashlib.sha256(content).hexdigest() != file.checksum_sha256:
        raise PublicationConflict("publication_hash_mismatch")
    try:
        payload = json.loads(content)
    except (UnicodeError, ValueError):
        raise PublicationConflict("publication_snapshot_mismatch") from None
    if not isinstance(payload, dict) or payload.get("job_id") != job.id or type(payload.get("generation")) is not int or payload["generation"] != job.retry_count:
        raise PublicationConflict("publication_snapshot_mismatch")
    return file, payload
