"""获胜结果的基础质量贡献；只派生原 owner 已认证的内容证据，不执行 I/O。"""
from __future__ import annotations

import re
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.services.document_ir.artifact_validator import MinerUValidationReport
from app.services.document_ir.mineru_package import DEFAULT_POLICY
from app.services.renderer.docx_quality import validate_formula_report
from app.services.renderer.evidence import ensure_renderer_integrity
from app.services.tables.evidence import ISSUE_CODES, read_table_evidence
from app.services.tables.models import canonical_sha256


VERSION = "document-base-quality/v1"
SCOPE_VERSION = "scope/v1"
Reason = Literal["not_ready", "base_evidence_incomplete", "base_risk_unclassified", "base_checks_complete"]
Count = Annotated[int, Field(ge=0)]
Hash = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]


class BaseQualityCounts(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)
    count: Count = 0
    formula_count: Count = 0
    fallback_count: Count = 0
    image_count: Count = 0
    table_count: Count = 0
    blocker_count: Count = 0
    warning_count: Count = 0
    unknown_flag_count: Count = 0


class BaseQualityContribution(BaseModel):
    """有界安全摘要；任意正文、路径、配置及私有报告只能留在原 receipt。"""
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)
    schema_version: Literal["document-base-quality/v1"] = VERSION
    scope_version: Literal["scope/v1"] = SCOPE_VERSION
    generation: Count
    evaluation_state: Literal["complete", "incomplete"] = "incomplete"
    quality_status: Literal["pending", "passed", "warning", "blocked"] = "pending"
    reason_code: Reason = "not_ready"
    report_sha256: Hash | None = None
    receipt_sha256: Annotated[str, Field(pattern=r"^sha256:[0-9a-f]{64}$")] | None = None
    counts: BaseQualityCounts = Field(default_factory=BaseQualityCounts)
    warning_codes: list[str] = Field(default_factory=list)


def fresh_quality_summary(generation: int) -> dict:
    """仅 create/clone/合法 failed retry 调用；legacy 默认和普通换件不获得 fresh 身份。"""
    return {"checks_v1": {"document_base": BaseQualityContribution(generation=generation).model_dump(mode="json")}}


def _read_base_quality(value: Any, *, generation: int | None = None) -> BaseQualityContribution | None:
    """持久槽必须显式声明身份，再由唯一模型校验完整结构；不借默认值追认 fresh。"""
    if not isinstance(value, dict) or not {"schema_version", "scope_version", "generation"} <= value.keys():
        return None
    try:
        contribution = BaseQualityContribution.model_validate(value)
    except ValidationError:
        return None
    return contribution if generation is None or contribution.generation == generation else None


def current_base(job: Any) -> BaseQualityContribution | None:
    """非法贡献结构沿原 owner 受控拒绝，不抢抛属性错误或误认 legacy。"""
    from app.domains.document_jobs.quality_state import _checks
    return _read_base_quality(_checks(job.quality_summary).get("document_base"), generation=job.retry_count)


def unknown_base_status(value: Any, *, generation: int | None = None) -> str | None:
    """未知身份或完整结构非法均保持未完成；保留 blocker，不授予 passed 资格。"""
    if _read_base_quality(value, generation=generation) is not None:
        return None
    return "blocked" if isinstance(value, dict) and value.get("quality_status") == "blocked" else "pending"


def project_base_quality(value: Any, *, generation: int | None = None) -> dict:
    """详情与有效状态共用同一完整校验，不公开私有键、路径或自由风险字符串。"""
    contribution = _read_base_quality(value, generation=generation)
    if contribution is None:
        return {"quality_status": "blocked" if isinstance(value, dict) and value.get("quality_status") == "blocked" else "pending",
                "evaluation_state": "incomplete"}
    public = contribution.model_dump(mode="json")
    public["warning_codes"] = [code for code in contribution.warning_codes
        if code in ISSUE_CODES or code == "formula_text_fallback"]
    return public


def derive_base_quality(job: Any) -> dict | None:
    """完成 CAS 只消费自己的本代 marker 和已选 receipt；实物认证由原执行器先完成。"""
    if current_base(job) is None:
        return None
    from app.domains.document_jobs.review import receipt_identity
    receipt = job.prepared_result
    if receipt is None or receipt.generation != job.retry_count or receipt.document_ir_file_id != job.document_ir_file_id:
        raise ValueError("基础质量完成必须绑定本代已选结果凭据。")
    metadata = receipt.file.metadata
    # 不截获 mandatory 损坏；沿原严格认证器失败，不能将 fatal 改写为 pending。
    ensure_renderer_integrity(metadata)
    complete = True
    blockers = warnings = 0
    codes: set[str] = set()
    source = metadata.get("source_integrity", {})
    source_count = source.get("expected_source_block_count")
    if (type(source_count) is not int or source_count < 0 or source_count != source.get("ir_main_block_count")
            or source.get("source_block_count_delta") != 0
            or not isinstance(source.get("expected_source_type_counts"), dict)
            or source.get("expected_source_type_counts") != source.get("ir_source_type_counts")):
        complete = False
    report_value = metadata.get("mineru_validation")
    try:
        source_report = MinerUValidationReport.model_validate(report_value)
    except ValidationError:
        source_report = None
    if (source_report is None or source_report.validator_version != "mineru-artifact-validator/v3"
            or source_report.policy_version != DEFAULT_POLICY.version):
        complete = False
    else:
        if not source_report.can_convert or source_report.fatal_count:
            from app.services.document_ir.artifact_validator import MinerUArtifactValidationError
            raise MinerUArtifactValidationError(source_report)
        blockers += source_report.blocker_count
        warnings += source_report.warning_count
        if (not source_report.complete or source_report.details_truncated or source_report.omitted_issue_count
                or not re.fullmatch(r"[0-9a-f]{64}", source_report.package_sha256)
                or not re.fullmatch(r"[0-9a-f]{64}", source_report.content_list_sha256 or "")
                or source_report.effective_inventory != {"block_count": source_count,
                    "type_counts": source.get("expected_source_type_counts")}):
            complete = False
    mandatory = metadata.get("renderer_content_contract_version") == "renderer-content/v2"
    complete = complete and mandatory and metadata.get("render_trace_status") == "complete"
    from app.services.renderer.render_plan import read_render_plan
    from app.services.renderer.block_evidence import read_block_render_evidence
    try:
        plan = read_render_plan(metadata.get("render_plan"))
        trace = read_block_render_evidence(metadata.get("block_render_evidence"))
        complete = complete and (plan.schema_version == "render-plan/v2" and trace.schema_version == "block-render-evidence/v2"
            and trace.complete and trace.plan_sha256 == plan.plan_sha256
            and trace.input_ir_sha256 == plan.input_ir_sha256
            and "sha256:" + trace.docx_sha256 == receipt.file.checksum_sha256)
    except ValueError:
        complete = False
    docx = metadata.get("docx_quality", {})
    if (not docx or docx.get("analysis_error") or type(docx.get("paragraph_count")) is not int
            or type(docx.get("editable_content_available")) is not bool):
        complete = False
    formula = validate_formula_report(metadata["formula_report"]) if "formula_report" in metadata else None
    if formula is None or formula != metadata.get("formula_summary"):
        complete = False
    elif formula["fallback_count"]:
        codes.add("formula_text_fallback")
        warnings += formula["fallback_count"]
    image = metadata.get("image_layout_report")
    image_summary = metadata.get("image_layout_summary", {})
    if (not isinstance(image, dict) or image.get("schema_version") != "image-layout/v1"
            or image_summary.get("schema_version") != "image-layout/v1"):
        complete = False
    table = read_table_evidence(metadata["table_evidence"]) if "table_evidence" in metadata else None
    if table is None:
        complete = False
    else:
        complete = complete and table.coverage == "complete"
        blockers += table.counts.blocker_count
        warnings += table.counts.warning_count
        codes.update(flag.code for item in table.tables for flag in item.flags)
    # 自由 flags 没有原 typed 分级；即使看起来像 info，也不能据名称忽略。
    risk_flags = [flag for key in ("quality_flags", "layout_quality_flags") for flag in metadata.get(key, [])]
    unknown_count = sum(flag != "formula_text_fallback" for flag in risk_flags)
    complete = complete and not unknown_count
    status = "blocked" if blockers else "pending" if not complete else "warning" if warnings else "passed"
    counts = BaseQualityCounts(count=source_count if type(source_count) is int and source_count >= 0 else 0,
        formula_count=formula["formula_count"] if formula else 0, fallback_count=formula["fallback_count"] if formula else 0,
        image_count=metadata.get("expected_inline_shape_count", 0), table_count=table.counts.table_count if table else 0,
        blocker_count=blockers, warning_count=warnings, unknown_flag_count=unknown_count)
    return BaseQualityContribution(generation=job.retry_count, quality_status=status,
        evaluation_state="complete" if complete else "incomplete",
        reason_code="base_checks_complete" if complete else "base_risk_unclassified" if unknown_count else "base_evidence_incomplete",
        report_sha256=canonical_sha256(metadata), receipt_sha256=receipt_identity(job), counts=counts,
        warning_codes=sorted(codes)).model_dump(mode="json")
