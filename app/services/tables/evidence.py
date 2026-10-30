"""表格证据的严格安全值合同与纯聚合；不执行渲染、文件或仓储 I/O。"""
from __future__ import annotations

from typing import Annotated, Literal, Self

from pydantic import Field, ValidationError, model_validator

from app.services.tables.models import FragmentId, NonNegativeInt, PositiveInt, Sha256, canonical_json_bytes, canonical_sha256
from app.services.tables.quality import (
    CODES, GROUPS_VERSION, TableId, TableQualityContribution, TableValidationPolicy,
    TableValidationReport, _QualityModel, _invalid, aggregate_table_quality,
)

VERSION = "table-evidence/v1"
MAX_REPORT_BYTES = 64 * 1024 * 1024
SafeId = Annotated[str, Field(pattern=r"^[A-Za-z0-9_:.\-]{1,160}$")]
Checksum = Annotated[str, Field(pattern=r"^sha256:[0-9a-f]{64}$")]
Status = Literal["pending", "passed", "warning", "blocked"]
NATIVE_BLOCKERS = frozenset({"table_fragment_missing", "table_render_layout_incompatible"})
NATIVE_WARNINGS = frozenset({"table_render_header_not_removed", "table_render_continuation_uncertain"})
REFERENCE_WARNINGS = frozenset({"missing_table_reference", "invalid_table_reference"})
ISSUE_CODES = CODES | NATIVE_BLOCKERS | NATIVE_WARNINGS | REFERENCE_WARNINGS | {"table_noneditable_placeholder"}


class TableEvidenceError(ValueError):
    """异常只携带固定安全码，不转发上游值或模型错误。"""
    def __init__(self, code: Literal["table_evidence_input", "table_evidence_integrity", "table_evidence_limit"]):
        self.code = code
        super().__init__(f"表格证据处理失败：{code}。")


class EvidenceModel(_QualityModel):
    failure_code = "table_evidence_input"


class WordCellObservation(EvidenceModel):
    grid_span: PositiveInt
    vertical_merge: Literal["restart", "continue"] | None


class WordRowObservation(EvidenceModel):
    cells: list[WordCellObservation]
    header: bool
    cant_split: bool
    bookmarks: list[SafeId]


class WordTableObservation(EvidenceModel):
    table_index: NonNegativeInt
    anchor: Annotated[str, Field(pattern=r"^md2word-table-[0-9a-f]{32}$")] | None
    grid_columns: NonNegativeInt
    rows: list[WordRowObservation]

    @model_validator(mode="after")
    def _width(self) -> Self:
        if any(sum(cell.grid_span for cell in row.cells) != self.grid_columns for row in self.rows):
            _invalid("table_evidence_input")
        return self


class FragmentOutput(EvidenceModel):
    fragment_id: FragmentId
    block_id: SafeId | None
    render_owner_block_id: SafeId
    render_input_sha256: Sha256 | None
    render_fragment_id: FragmentId | None
    source_rows: list[NonNegativeInt]
    retained_source_rows: list[NonNegativeInt]
    output_rows: list[NonNegativeInt]
    removed_header_rows: list[NonNegativeInt] | None
    shared_header_rows: list[NonNegativeInt] | None
    bookmark: SafeId | None
    status: Literal["rendered", "header_only", "empty", "missing"]

    @model_validator(mode="after")
    def _ranges(self) -> Self:
        for interval in (self.source_rows, self.retained_source_rows, self.output_rows,
                         self.removed_header_rows, self.shared_header_rows):
            if interval is not None and (len(interval) != 2 or interval[1] < interval[0]):
                _invalid("table_evidence_input")
        if self.status in {"empty", "missing"}:
            if (self.source_rows != [0, 0] or self.output_rows != [0, 0] or self.block_id is not None
                    or self.render_input_sha256 is not None or self.render_fragment_id is not None or self.bookmark is not None):
                _invalid("table_evidence_input")
        else:
            if (self.render_input_sha256 is None or self.render_fragment_id is None or self.bookmark is None
                    or self.source_rows[0] != 0 or self.retained_source_rows[1] != self.source_rows[1]
                    or self.retained_source_rows[0] > self.retained_source_rows[1]
                    or self.output_rows[1] - self.output_rows[0] != self.retained_source_rows[1] - self.retained_source_rows[0]
                    or self.removed_header_rows != ([0, self.retained_source_rows[0]] if self.retained_source_rows[0] else None)
                    or self.shared_header_rows != self.removed_header_rows):
                _invalid("table_evidence_input")
        return self


class NativeOutput(EvidenceModel):
    output_table_key: Annotated[str, Field(pattern=r"^md2word-table-[0-9a-f]{32}$")]
    anchor_block_id: SafeId
    actual: WordTableObservation
    fragments: list[FragmentOutput]

    @model_validator(mode="after")
    def _coverage(self) -> Self:
        if self.actual.anchor != self.output_table_key:
            _invalid("table_evidence_input")
        cursor = 0
        for fragment in self.fragments:
            if fragment.status in {"empty", "missing"}:
                continue
            start, end = fragment.output_rows
            if start != cursor or end > len(self.actual.rows):
                _invalid("table_evidence_input")
            row = 0 if fragment.status == "header_only" else start
            if row >= len(self.actual.rows) or fragment.bookmark not in self.actual.rows[row].bookmarks:
                _invalid("table_evidence_input")
            cursor = end
        if cursor != len(self.actual.rows):
            _invalid("table_evidence_input")
        return self


class ReferenceEvidence(EvidenceModel):
    fragment_id: FragmentId
    source_status: Literal["valid", "missing", "invalid", "unavailable"]
    asset_id: SafeId | None
    file_id: SafeId | None
    mime_type: Literal["image/png", "image/jpeg", "image/gif", "image/bmp", "image/tiff", "image/webp"] | None
    checksum_sha256: Checksum | None
    registered: bool
    physical_verified: Literal[False] = False

    @model_validator(mode="after")
    def _reference(self) -> Self:
        if self.source_status == "valid":
            if self.asset_id is None or self.mime_type is None or self.checksum_sha256 is None:
                _invalid("table_evidence_input")
        elif any(value is not None for value in (self.asset_id, self.file_id, self.mime_type, self.checksum_sha256)):
            _invalid("table_evidence_input")
        if self.registered != (self.file_id is not None):
            _invalid("table_evidence_input")
        return self


class PlaceholderEvidence(EvidenceModel):
    placeholder_id: Annotated[str, Field(pattern=r"^table-placeholder:[0-9a-f]{64}$")]
    fragment_id: FragmentId
    logical_group_id: TableId
    owner_block_id: SafeId
    asset_ref: SafeId
    asset_sha256: Checksum
    fragment_sha256: Checksum
    source_kind: Literal["mineru_reference", "source_pdf_crop"]
    source_file_id: SafeId
    source_pdf_sha256: Checksum | None
    marker: Annotated[str, Field(pattern=r"^_md2tp_[0-9a-f]{30}$")]
    media_sha256: Checksum
    source_label_sha256: Checksum
    proof_sha256: Checksum
    issue_code: Literal["table_noneditable_placeholder"]

    @model_validator(mode="after")
    def _media(self) -> Self:
        if self.asset_sha256 != self.media_sha256:
            _invalid("table_evidence_input")
        return self


class EvidenceFlag(EvidenceModel):
    producer: Literal["table_validator", "table_rendering", "table_reference", "table_placeholder"]
    code: str
    severity: Literal["blocker", "warning"]
    identity: SafeId
    fragment_id: FragmentId | None

    @model_validator(mode="after")
    def _fixed_code(self) -> Self:
        allowed = {"table_validator": CODES, "table_rendering": NATIVE_BLOCKERS | NATIVE_WARNINGS,
                   "table_reference": REFERENCE_WARNINGS, "table_placeholder": {"table_noneditable_placeholder"}}
        if (self.code not in allowed[self.producer]
                or self.producer == "table_rendering" and self.severity != ("blocker" if self.code in NATIVE_BLOCKERS else "warning")
                or self.producer == "table_reference" and self.severity != "warning"
                or self.producer == "table_placeholder" and self.severity != "blocker"):
            _invalid("table_evidence_input")
        return self


class SourceGridSummary(EvidenceModel):
    rows: NonNegativeInt
    columns: NonNegativeInt
    header_rows: list[NonNegativeInt]
    raw_html_sha256: Sha256
    source_binding_sha256: Sha256


class TableEvidence(EvidenceModel):
    table_id: TableId
    logical_group_id: TableId
    member_block_ids: list[SafeId]
    anchor_block_id: SafeId
    source_grid: SourceGridSummary
    validation: TableValidationReport
    references: list[ReferenceEvidence]
    outputs: list[NativeOutput]
    placeholders: list[PlaceholderEvidence]
    render_state: Literal["native", "placeholder", "mixed", "excluded_margin_artifact"]
    flags: list[EvidenceFlag]
    status: Status

    @model_validator(mode="after")
    def _table(self) -> Self:
        report = self.validation
        if any(fragment.bbox is not None and (fragment.bbox[2] <= fragment.bbox[0] or fragment.bbox[3] <= fragment.bbox[1])
               for fragment in (*report.fragments, *report.related_fragments)):
            _invalid("table_evidence_input")
        fragments = {item.fragment_id: item for item in report.fragments}
        if (self.table_id != self.logical_group_id or self.table_id != report.table_id
                or len(set(self.member_block_ids)) != len(self.member_block_ids)
                or self.anchor_block_id not in self.member_block_ids
                or self.source_grid != source_grid_summary(report)
                or [item.fragment_id for item in self.references] != list(fragments)):
            _invalid("table_evidence_input")
        native = [item for output in self.outputs for item in output.fragments]
        placeholder_ids = [item.fragment_id for item in self.placeholders]
        native_ids = [item.fragment_id for item in native]
        if (len(set(native_ids)) != len(native_ids) or len(set(placeholder_ids)) != len(placeholder_ids)
                or not set(native_ids + placeholder_ids) <= fragments.keys()
                or any(item.logical_group_id != self.table_id or item.owner_block_id not in self.member_block_ids for item in self.placeholders)
                or any(item.render_owner_block_id not in self.member_block_ids for item in native)):
            _invalid("table_evidence_input")
        expected_state = "mixed" if self.outputs and self.placeholders else "native" if self.outputs else "placeholder" if self.placeholders else "excluded_margin_artifact"
        if self.render_state != expected_state:
            _invalid("table_evidence_input")
        if self.render_state != "excluded_margin_artifact" and set(native_ids + placeholder_ids) != fragments.keys():
            _invalid("table_evidence_input")
        for item in native:
            source = fragments[item.fragment_id]
            if source.html_state != "present" and (item.status != source.html_state or item.fragment_id not in placeholder_ids):
                _invalid("table_evidence_input")
        for identity in placeholder_ids:
            if fragments[identity].html_state == "present":
                _invalid("table_evidence_input")
        source_flags = [EvidenceFlag(producer="table_validator", code=f.flag.code, severity=f.flag.severity,
                                    identity=f.finding_id, fragment_id=f.flag.fragment_id) for f in report.findings]
        if [f for f in self.flags if f.producer == "table_validator"] != source_flags:
            _invalid("table_evidence_input")
        expected_reference = []
        for reference in self.references:
            if reference.source_status in {"missing", "invalid"}:
                code = reference.source_status + "_table_reference"
                expected_reference.append(EvidenceFlag(producer="table_reference", code=code, severity="warning",
                    identity="table-observation:" + canonical_sha256(["table_reference", code, reference.fragment_id]),
                    fragment_id=reference.fragment_id))
        expected_placeholder = [EvidenceFlag(producer="table_placeholder", code="table_noneditable_placeholder",
            severity="blocker", identity=item.placeholder_id, fragment_id=item.fragment_id) for item in self.placeholders]
        if ([f for f in self.flags if f.producer == "table_reference"] != expected_reference
                or [f for f in self.flags if f.producer == "table_placeholder"] != expected_placeholder):
            _invalid("table_evidence_input")
        if any(f.fragment_id is not None and f.fragment_id not in fragments for f in self.flags):
            _invalid("table_evidence_input")
        identities = [(f.producer, f.identity) for f in self.flags]
        if len(set(identities)) != len(identities) or self.status != flags_status(self.flags):
            _invalid("table_evidence_input")
        return self


def source_grid_summary(report: TableValidationReport) -> SourceGridSummary:
    return SourceGridSummary(rows=sum(f.row_count for f in report.fragments),
        columns=max((f.columns for f in report.fragments), default=0),
        header_rows=sorted({c.row for c in report.cells if c.is_header}),
        raw_html_sha256=report.raw_html_sha256, source_binding_sha256=report.source_binding_sha256)


def flags_status(flags, *, unavailable=False) -> str:
    return "blocked" if any(f.severity == "blocker" for f in flags) else "pending" if unavailable else "warning" if flags else "passed"


class EvidenceCounts(EvidenceModel):
    table_count: NonNegativeInt
    fragment_count: NonNegativeInt
    native_count: NonNegativeInt
    placeholder_count: NonNegativeInt
    blocker_count: NonNegativeInt
    warning_count: NonNegativeInt


class TableEvidenceReport(EvidenceModel):
    schema_version: Literal["table-evidence/v1"]
    producer: Literal["table_evidence"]
    source_content_sha256: Sha256 | None
    ir_model_sha256: Sha256
    docx_sha256: Sha256
    source_groups_version: Literal["logical-table-groups/v1"] | None
    validator_version: Literal["table-validator/v1"]
    normalizer_version: Literal["table-html/v1"]
    policy: TableValidationPolicy
    policy_sha256: Sha256
    rendering_version: Literal["table-rendering/v1"] | None
    rendering_policy_version: Literal["logical-table-renderer/v1"] | None
    placeholder_version: Literal["table-placeholder-rendering/v1"] | None
    coverage: Literal["complete", "unavailable"]
    reason: Literal["source_groups_unavailable", "rendering_evidence_unavailable", "reference_evidence_unavailable"] | None
    components: dict[Literal["source", "reference", "native", "placeholder"], Literal["available", "not_applicable", "unavailable"]]
    expected_table_ids: list[TableId]
    evaluated_table_ids: list[TableId]
    tables: list[TableEvidence]
    status: Status
    counts: EvidenceCounts
    report_sha256: Sha256

    @model_validator(mode="after")
    def _report(self) -> Self:
        if (set(self.components) != {"source", "reference", "native", "placeholder"}
                or len(set(self.expected_table_ids)) != len(self.expected_table_ids)
                or self.expected_table_ids != self.evaluated_table_ids
                or [t.table_id for t in self.tables] != self.expected_table_ids
                or self.policy_sha256 != self.policy.policy_sha256):
            _invalid("table_evidence_input")
        if self.source_groups_version is None:
            if self.tables or self.reason != "source_groups_unavailable" or self.components["source"] != "unavailable":
                _invalid("table_evidence_input")
        else:
            if self.source_content_sha256 is None or self.components["source"] != "available":
                _invalid("table_evidence_input")
        all_fragments = [f.fragment_id for table in self.tables for f in table.validation.fragments]
        all_outputs = [o.output_table_key for table in self.tables for o in table.outputs]
        ordinals = [o.actual.table_index for table in self.tables for o in table.outputs]
        if (len(set(all_fragments)) != len(all_fragments) or len(set(all_outputs)) != len(all_outputs)
                or len(set(ordinals)) != len(ordinals)):
            _invalid("table_evidence_input")
        for table in self.tables:
            if table.validation.source_content_sha256 != self.source_content_sha256 or table.validation.policy_sha256 != self.policy_sha256:
                _invalid("table_evidence_input")
        aggregate_table_quality([table.validation for table in self.tables], expected_table_ids=self.expected_table_ids,
            source_content_sha256=self.source_content_sha256, source_groups_version=self.source_groups_version,
            expected_fragment_count=len(all_fragments) if self.source_groups_version else None, policy=self.policy)
        if (bool(self.placeholder_version) != any(table.placeholders for table in self.tables)
                or (self.rendering_version is None) != (self.rendering_policy_version is None)
                or self.tables and self.components["native"] == "available" and self.rendering_version is None):
            _invalid("table_evidence_input")
        unavailable = "unavailable" in self.components.values()
        if ((self.coverage == "unavailable") != unavailable or (self.reason is not None) != unavailable
                or self.status != flags_status([f for t in self.tables for f in t.flags], unavailable=unavailable)
                or self.counts != evidence_counts(self.tables)):
            _invalid("table_evidence_input")
        if self.report_sha256 != canonical_sha256(self.model_dump(mode="json", exclude={"report_sha256"}, warnings=False)):
            _invalid("table_evidence_input")
        return self


def evidence_counts(tables) -> EvidenceCounts:
    flags = [f for t in tables for f in t.flags]
    return EvidenceCounts(table_count=len(tables), fragment_count=sum(len(t.validation.fragments) for t in tables),
        native_count=sum(len(t.outputs) for t in tables), placeholder_count=sum(len(t.placeholders) for t in tables),
        blocker_count=sum(f.severity == "blocker" for f in flags), warning_count=sum(f.severity == "warning" for f in flags))


def aggregate_table_evidence(contribution: TableQualityContribution, *, ir_model_sha256: str, docx_sha256: str,
                             tables: list[TableEvidence], reference_available: bool, rendering_available: bool,
                             placeholder_version: str | None) -> TableEvidenceReport:
    """消费已校验 producer 的安全投影，重复同报幂等，冲突或漏覆盖失败关闭。"""
    try:
        source = TableQualityContribution.model_validate(contribution.model_dump(warnings=False))
        unique = {}
        for table in tables:
            checked = TableEvidence.model_validate(table.model_dump(warnings=False))
            if checked.table_id in unique and unique[checked.table_id] != checked:
                raise TableEvidenceError("table_evidence_integrity")
            unique[checked.table_id] = checked
        if set(unique) != set(source.expected_table_ids):
            raise TableEvidenceError("table_evidence_integrity")
        ordered = [unique[identity] for identity in source.expected_table_ids]
        if [t.validation for t in ordered] != list(source.reports):
            raise TableEvidenceError("table_evidence_integrity")
        has_tables = bool(ordered)
        components = {"source": "available" if source.source_groups_version else "unavailable",
            "reference": "available" if has_tables and reference_available else "unavailable" if has_tables else "not_applicable",
            "native": "available" if has_tables and rendering_available else "unavailable" if has_tables else "not_applicable",
            "placeholder": "available" if placeholder_version else "not_applicable"}
        reason = ("source_groups_unavailable" if source.source_groups_version is None else
                  "rendering_evidence_unavailable" if has_tables and not rendering_available else
                  "reference_evidence_unavailable" if has_tables and not reference_available else None)
        payload = dict(schema_version=VERSION, producer="table_evidence", source_content_sha256=source.source_content_sha256,
            ir_model_sha256=ir_model_sha256, docx_sha256=docx_sha256, source_groups_version=source.source_groups_version,
            validator_version=source.validator_version, normalizer_version=source.normalizer_version,
            policy=source.policy.model_dump(mode="json"), policy_sha256=source.policy_sha256,
            rendering_version="table-rendering/v1" if rendering_available else None,
            rendering_policy_version="logical-table-renderer/v1" if rendering_available else None,
            placeholder_version=placeholder_version, coverage="unavailable" if reason else "complete", reason=reason,
            components=components, expected_table_ids=list(source.expected_table_ids), evaluated_table_ids=list(source.evaluated_table_ids),
            tables=[t.model_dump(mode="json", warnings=False) for t in ordered],
            status=flags_status([f for t in ordered for f in t.flags], unavailable=reason is not None),
            counts=evidence_counts(ordered).model_dump(mode="json"))
        payload["report_sha256"] = canonical_sha256(payload)
        encoded = canonical_json_bytes(payload)
        if len(encoded) > MAX_REPORT_BYTES:
            raise TableEvidenceError("table_evidence_limit")
        return TableEvidenceReport.model_validate_json(encoded)
    except (ValidationError, TypeError, AttributeError):
        raise TableEvidenceError("table_evidence_input") from None


def read_table_evidence(value) -> TableEvidenceReport:
    """所有声明新版的边界严格重读，不能以缺键降级成历史报告。"""
    try:
        encoded = value if isinstance(value, bytes) else canonical_json_bytes(value)
        if len(encoded) > MAX_REPORT_BYTES:
            raise TableEvidenceError("table_evidence_limit")
        return TableEvidenceReport.model_validate_json(encoded)
    except (ValidationError, ValueError, TypeError) as exc:
        if isinstance(exc, TableEvidenceError):
            raise
        raise TableEvidenceError("table_evidence_integrity") from None


def table_evidence_summary(report: TableEvidenceReport) -> dict:
    checked = read_table_evidence(report.model_dump(mode="json", warnings=False))
    return {"schema_version": VERSION, "report_sha256": checked.report_sha256,
        "ir_model_sha256": checked.ir_model_sha256, "docx_sha256": checked.docx_sha256,
        "coverage": checked.coverage, "reason": checked.reason, "status": checked.status,
        **checked.counts.model_dump(), "issue_codes": sorted({f.code for t in checked.tables for f in t.flags})}
