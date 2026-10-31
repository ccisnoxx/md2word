"""复用 TAB 的物理表/报告 owner；v2 只改变明确版本的序号与 marker 认证。"""
from __future__ import annotations
from collections import Counter
from io import BytesIO
from xml.etree import ElementTree as ET
import hashlib
import zipfile
from typing import Any
from app.services.document_ir.integrity import is_visible_body_block
from app.services.document_ir.models import DocumentIR
from app.services.renderer.logical_table_plan import (
    TABLE_RENDERING_VERSION, TABLE_RENDERING_POLICY, LogicalTableRenderPlan,
    QUALITY_BLOCKERS, QUALITY_WARNINGS,
)
from app.services.renderer.table_renderer import iter_grid_rows
from app.services.tables.evidence import (
    EvidenceFlag, FragmentOutput, NativeOutput, PlaceholderEvidence, ReferenceEvidence, TableEvidence,
    TableEvidenceError, WordTableObservation, aggregate_table_evidence, flags_status, source_grid_summary,
)
from app.services.tables.models import canonical_sha256
from app.services.tables.validator import validate_document_tables
from app.services.document_ir.table_reference_assets import decode_table_references
from app.services.document_ir.table_placeholder import decode_placeholders
_NS = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
_W = "{" + _NS["w"] + "}"

def _row_flag_enabled(row: Any, name: str) -> bool:
    marker = row.find("w:trPr/w:" + name, _NS)
    return marker is not None and marker.get(_W + "val", "true").lower() not in {"0", "false", "off"}


def _table_rendering_evidence(
    document: DocumentIR, content: bytes, plan: LogicalTableRenderPlan, observations: list[dict], *, v2: bool = False, expected_table_order: list[str] | None = None,
) -> tuple[dict[str, Any], list[str]]:
    """逐个定位实物 table/row/header/span/bookmark，不能拿 expected=actual 消除丢失。"""
    flags = []
    root = None
    try:
        with zipfile.ZipFile(BytesIO(content)) as package:
            root = ET.fromstring(package.read("word/document.xml"))
    except (zipfile.BadZipFile, KeyError, ET.ParseError):
        flags.append("ir_docx_integrity:table_anchor_mismatch")
    physical_tables = root.findall(".//w:tbl", _NS) if root is not None else []
    anchored: dict[str, list[tuple[int, Any]]] = {}
    for index, table in enumerate(physical_tables):
        caption = table.find("w:tblPr/w:tblCaption", _NS)
        if caption is not None:
            key = caption.get(_W + "val", "")
            if key.startswith("md2word-table-"):
                anchored.setdefault(key, []).append((index, table))
    if set(anchored) != {unit.key for unit in plan.units}:
        flags.append("ir_docx_integrity:table_anchor_mismatch")
    bookmark_names = Counter(node.get(_W + "name") for node in root.findall(".//w:bookmarkStart", _NS)) if root is not None else Counter()
    if v2:
        actual_order = []
        starts = root.findall(".//w:bookmarkStart", _NS) if root is not None else []
        ends = root.findall(".//w:bookmarkEnd", _NS) if root is not None else []
        for node in starts:
            identity = node.get(_W + "id")
            if (sum(other.get(_W + "id") == identity for other in starts) != 1 or
                    sum(other.get(_W + "id") == identity for other in ends) != 1):
                flags.append("ir_docx_integrity:table_fragment_anchor_mismatch")
        for table in physical_tables:
            caption = table.find("w:tblPr/w:tblCaption", _NS)
            actual_order.append(caption.get(_W + "val") if caption is not None else None)
        if actual_order != expected_table_order:
            flags.append("ir_docx_integrity:table_anchor_mismatch")
    tables = []
    quality_blockers = []
    warnings = []
    source_fragments = []
    for expected_index, unit in enumerate(plan.units):
        quality_blockers.extend(unit.blocking_quality_flags)
        warnings.extend(unit.warning_flags)
        found = anchored.get(unit.key, [])
        table_index, actual = found[0] if len(found) == 1 else (None, None)
        if actual is None or (not v2 and table_index != expected_index):
            flags.append("ir_docx_integrity:table_anchor_mismatch")
        rows = actual.findall("w:tr", _NS) if actual is not None else []
        observed = observations[table_index] if table_index is not None else None
        headers = [index for index, row in enumerate(observed["rows"]) if row["header"]] if observed else []
        if len(rows) != unit.rows:
            flags.append("ir_docx_integrity:table_row_count_mismatch")
        if headers != list(range(unit.header_rows)):
            flags.append("ir_docx_integrity:table_header_mismatch")
        if observed and any(not row["cant_split"] for row in observed["rows"]):
            flags.append("ir_docx_integrity:table_geometry_mismatch")
        if observed is None or observed["grid_columns"] != unit.columns:
            flags.append("ir_docx_integrity:table_geometry_mismatch")
        fragments = []
        for fragment in unit.fragments:
            source = fragment.source
            source_fragments.append(source.fragment_id)
            actual_range = [0, 0] if fragment.render is None else None
            if fragment.render is not None:
                first_row = 0 if fragment.status == "header_only" else fragment.output_start
                matches = [(index, node) for index, row in enumerate(rows)
                           for node in row.findall(".//w:bookmarkStart", _NS)
                           if node.get(_W + "name") == fragment.bookmark]
                if (len(matches) != 1 or matches[0][0] != first_row or bookmark_names[fragment.bookmark] != 1 or
                        (not v2 and matches[0][1].get(_W + "id") != str(fragment.bookmark_id)) or
                        not any(node.get(_W + "id") == matches[0][1].get(_W + "id")
                                for node in rows[first_row].findall(".//w:bookmarkEnd", _NS))):
                    flags.append("ir_docx_integrity:table_fragment_anchor_mismatch")
                else:
                    actual_range = [fragment.output_start, fragment.output_end]
                for source_row, owners in iter_grid_rows(fragment.render.grid, block_index=fragment.block_index):
                    if source_row < fragment.removed_header_rows:
                        continue
                    output_row = fragment.output_start + source_row - fragment.removed_header_rows
                    if output_row >= len(rows):
                        continue
                    expected_shape = []
                    cursor = 0
                    for owner in owners:
                        expected_shape.extend([(1, None)] * (owner.column - cursor))
                        expected_shape.append((owner.colspan, "continue" if owner.row < source_row else
                                               "restart" if owner.rowspan > 1 else None))
                        cursor = owner.column + owner.colspan
                    expected_shape.extend([(1, None)] * (unit.columns - cursor))
                    observed_shape = [(cell["grid_span"], cell["vertical_merge"])
                                      for cell in observed["rows"][output_row]["cells"]]
                    if observed_shape != expected_shape:
                        flags.append("ir_docx_integrity:table_geometry_mismatch")
            current_rows = fragment.render.grid.rows if fragment.render is not None else 0
            fragments.append({
                "fragment_id": source.fragment_id, "block_id": source.block_id,
                "render_owner_block_id": source.render_owner_block_id,
                "source_span": source.source_span.model_dump(mode="json"),
                "html_state": source.html_state, "raw_html_sha256": source.raw_html_sha256,
                "render_input_sha256": fragment.render.input_sha256 if fragment.render else None,
                "render_fragment_id": fragment.render.grid.source_fragments[0].fragment_id if fragment.render else None,
                "source_rows": [0, current_rows], "retained_source_rows": [fragment.removed_header_rows, current_rows],
                "output_rows": [fragment.output_start, fragment.output_end], "actual_output_rows": actual_range,
                "removed_header_rows": [0, fragment.removed_header_rows] if fragment.removed_header_rows else None,
                "shared_header_rows": [0, fragment.removed_header_rows] if fragment.removed_header_rows else None,
                "bookmark": fragment.bookmark, "status": fragment.status,
                "reason": "table_fragment_missing" if fragment.render is None else None,
            })
        tables.append({
            "output_table_key": unit.key, "output_table_index": table_index,
            "logical_group_id": unit.logical_group_id,
            "anchor_block_id": document.blocks[unit.anchor_block_index].id,
            "member_block_ids": [fragment.source.block_id for fragment in unit.fragments if fragment.source.block_id],
            "columns": unit.columns, "expected_rows": unit.rows, "actual_rows": len(rows),
            "expected_header_rows": list(range(unit.header_rows)), "actual_header_rows": headers,
            "group_status": "blocked" if unit.blocking_quality_flags else "warning" if unit.warning_flags else "passed",
            "blocking_quality_flags": list(unit.blocking_quality_flags), "warning_flags": list(unit.warning_flags),
            "continuation_diagnostics": list(unit.continuation_diagnostics), "fragments": fragments,
        })
    output_groups = {unit.logical_group_id for unit in plan.units}
    expected_fragments = [fragment.fragment_id for group in document.metadata.logical_table_groups
                          if group.logical_group_id in output_groups for fragment in group.fragments]
    if v2:
        expected_fragments = [fragment.source.fragment_id for unit in plan.units for fragment in unit.fragments]
    if Counter(source_fragments) != Counter(expected_fragments):
        flags.append("ir_docx_integrity:table_fragment_map_mismatch")
    blockers = list(dict.fromkeys(quality_blockers))
    warning_flags = list(dict.fromkeys(warnings))
    result = {
        "version": TABLE_RENDERING_VERSION, "policy_version": TABLE_RENDERING_POLICY,
        "render_input_sha256": plan.input_sha256,
        "quality_status": "blocked" if blockers else "warning" if warning_flags else "passed",
        "blocking_quality_flags": blockers, "warning_flags": warning_flags,
        "source_table_block_count": sum(1 for block in document.blocks if block.type == "table" and is_visible_body_block(block)),
        "output_table_count": len(plan.units), "consumed_block_count": len(plan.consumed_block_ids),
        "placeholder_table_block_count": sum(1 for block in document.blocks if block.type == "table"
            and not (block.html or "").strip() and any(p.owner_block_id == block.id for p in decode_placeholders(document))),
        "fragment_count": len(expected_fragments),
        "empty_fragment_count": sum(fragment.source.html_state == "empty" for unit in plan.units for fragment in unit.fragments),
        "missing_fragment_count": sum(fragment.source.html_state == "missing" for unit in plan.units for fragment in unit.fragments),
        "tables": tables,
    }
    return result, list(dict.fromkeys(flags))


def _build_table_evidence(document: DocumentIR, content: bytes, evidence: dict):
    """唯一编排点连接来源、当前渲染视图和实际 OOXML；纯层不感知 IR 或 renderer。"""
    source = validate_document_tables(document)
    references = {item.fragment.fragment_id: item for item in decode_table_references(document)}
    native = evidence.get("table_rendering", {})
    proof = evidence.get("table_placeholder_rendering")
    blocks = {block.id: block for block in document.blocks}
    observations = evidence["docx_quality"]["table_observations"]
    tables = []
    for group, validation in zip(document.metadata.logical_table_groups, source.reports, strict=True):
        refs, flags, outputs, placeholders = [], [], [], []
        for finding in validation.findings:
            flags.append(EvidenceFlag(producer="table_validator", code=finding.flag.code, severity=finding.flag.severity,
                                      identity=finding.finding_id, fragment_id=finding.flag.fragment_id))
        for fragment in group.fragments:
            reference = references.get(fragment.fragment_id)
            asset = reference.asset if reference else None
            state = reference.detail.source_status if reference else "unavailable"
            refs.append(ReferenceEvidence(fragment_id=fragment.fragment_id, source_status=state,
                asset_id=asset.id if asset else None, file_id=asset.file_id if asset else None,
                mime_type=asset.mime_type if asset else None, checksum_sha256=asset.checksum_sha256 if asset else None,
                registered=bool(asset and asset.file_id)))
            if state in {"missing", "invalid"}:
                code = state + "_table_reference"
                flags.append(EvidenceFlag(producer="table_reference", code=code, severity="warning",
                    identity="table-observation:" + canonical_sha256(["table_reference", code, fragment.fragment_id]),
                    fragment_id=fragment.fragment_id))
        for output in native.get("tables", []):
            if output["logical_group_id"] != group.logical_group_id:
                continue
            index = output["output_table_index"]
            if type(index) is not int or index >= len(observations):
                raise TableEvidenceError("table_evidence_integrity")
            outputs.append(NativeOutput(output_table_key=output["output_table_key"], anchor_block_id=output["anchor_block_id"],
                actual=WordTableObservation.model_validate(observations[index]),
                fragments=[FragmentOutput.model_validate({key: item[key] for key in FragmentOutput.model_fields})
                           for item in output["fragments"]]))
            for code in [*output["blocking_quality_flags"], *output["warning_flags"]]:
                flag = EvidenceFlag(producer="table_rendering", code=code,
                    severity="blocker" if code in QUALITY_BLOCKERS else "warning",
                    identity="table-observation:" + canonical_sha256(["table_rendering", code, group.logical_group_id]), fragment_id=None)
                if flag not in flags:
                    flags.append(flag)
        for item in proof["maps"] if proof else []:
            if item["logical_group_id"] != group.logical_group_id:
                continue
            placeholders.append(PlaceholderEvidence.model_validate({
                **{key: item[key] for key in PlaceholderEvidence.model_fields if key != "proof_sha256"},
                "proof_sha256": proof["evidence_sha256"]}))
            flags.append(EvidenceFlag(producer="table_placeholder", code="table_noneditable_placeholder", severity="blocker",
                                      identity=item["placeholder_id"], fragment_id=item["fragment_id"]))
        members = list(dict.fromkeys(f.render_owner_block_id for f in group.fragments))
        state = "mixed" if outputs and placeholders else "native" if outputs else "placeholder" if placeholders else "excluded_margin_artifact"
        if state == "excluded_margin_artifact" and any(is_visible_body_block(blocks[identity]) for identity in members):
            raise TableEvidenceError("table_evidence_integrity")
        tables.append(TableEvidence(table_id=group.logical_group_id, logical_group_id=group.logical_group_id,
            member_block_ids=members, anchor_block_id=members[0], source_grid=source_grid_summary(validation), validation=validation,
            references=refs, outputs=outputs, placeholders=placeholders, render_state=state, flags=flags, status=flags_status(flags)))
    return aggregate_table_evidence(source, ir_model_sha256=canonical_sha256(document.model_dump(mode="json")),
        docx_sha256=hashlib.sha256(content).hexdigest(), tables=tables,
        reference_available=document.metadata.table_references_version is not None,
        rendering_available="table_rendering" in evidence, placeholder_version=proof["version"] if proof else None)
